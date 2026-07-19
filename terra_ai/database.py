"""SQLite database layer for TerraAI."""

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DB_VERSION = 1


@dataclass
class DBConfig:
    path: str = "data/terraai.db"
    wal: bool = True


class Database:
    """Manages SQLite connection and schema for TerraAI."""

    def __init__(self, config: DBConfig | None = None):
        self.config = config or DBConfig()
        db_path = Path(self.config.path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._transaction_state = threading.local()
        self._closed = False
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            if self.config.wal:
                self.conn.execute("PRAGMA journal_mode=WAL")
            self._init_schema()

    @contextmanager
    def transaction(self):
        """Serialize and own one transaction, supporting same-thread nesting."""
        with self._lock:
            if self._closed:
                raise RuntimeError("Database is closed")
            depth = getattr(self._transaction_state, "depth", 0)
            outermost = depth == 0
            if outermost:
                self._transaction_state.rollback_only = False
            self._transaction_state.depth = depth + 1
            try:
                if outermost:
                    self.conn.execute("BEGIN")
                yield self.conn
                if outermost:
                    if self._transaction_state.rollback_only:
                        self.conn.rollback()
                        raise RuntimeError(
                            "Transaction rolled back because a nested operation failed"
                        )
                    self.conn.commit()
            except Exception:
                self._transaction_state.rollback_only = True
                if outermost:
                    self.conn.rollback()
                raise
            finally:
                self._transaction_state.depth = depth
                if outermost:
                    del self._transaction_state.rollback_only

    def fetchone(self, sql: str, parameters=()):
        """Execute a query and fetch one row while holding the connection lock."""
        with self._lock:
            if self._closed:
                raise RuntimeError("Database is closed")
            return self.conn.execute(sql, parameters).fetchone()

    def fetchall(self, sql: str, parameters=()):
        """Execute a query and fetch all rows while holding the connection lock."""
        with self._lock:
            if self._closed:
                raise RuntimeError("Database is closed")
            return self.conn.execute(sql, parameters).fetchall()

    def close(self) -> None:
        """Close the owned SQLite connection exactly once."""
        with self._lock:
            if not self._closed:
                self.conn.close()
                self._closed = True

    def _init_schema(self):
        """Create tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                server TEXT NOT NULL,
                nick TEXT NOT NULL,
                opted_in BOOLEAN NOT NULL DEFAULT 1,
                noisy BOOLEAN NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (server, nick)
            );

            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server TEXT NOT NULL,
                channel TEXT NOT NULL,
                nick TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'user' CHECK(source IN ('user', 'system')),
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                server TEXT NOT NULL,
                channel TEXT NOT NULL,
                active_session_id TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (server, channel)
            );

            CREATE TABLE IF NOT EXISTS compactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server TEXT NOT NULL,
                channel TEXT NOT NULL,
                old_session_id TEXT NOT NULL,
                new_session_id TEXT NOT NULL,
                rows_before INTEGER NOT NULL,
                rows_after INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server TEXT NOT NULL,
                trigger TEXT NOT NULL,
                response TEXT NOT NULL,
                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (server, trigger)
            );

            CREATE TABLE IF NOT EXISTS command_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server TEXT NOT NULL,
                command TEXT NOT NULL,
                nick TEXT,
                channel TEXT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS performance_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server TEXT NOT NULL,
                channel TEXT NOT NULL,
                nick TEXT,
                session_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                processing_time_ms INTEGER,
                response_chars INTEGER,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_history_server_channel_nick
                ON conversation_history (server, channel, nick, id DESC);
            CREATE INDEX IF NOT EXISTS idx_prompts_server_trigger
                ON prompts (server, trigger);
            CREATE INDEX IF NOT EXISTS idx_stats_server_command
                ON command_stats (server, command, timestamp);

            -- Approved cleanup: legacy per-user tool overrides had the wrong
            -- ownership and semantics. Discard only that table and replace it
            -- with server-wide disabled-tool policy.
            DROP INDEX IF EXISTS idx_tools_server_nick;
            DROP TABLE IF EXISTS tools;

            CREATE TABLE IF NOT EXISTS disabled_tools (
                server TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (server, tool_name)
            );
        """)


class UserStore:
    """CRUD for users table."""

    def __init__(self, db: Database):
        self.db = db

    def get_user(self, server: str, nick: str) -> dict | None:
        row = self.db.fetchone(
            "SELECT * FROM users WHERE server = ? AND nick = ?",
            (server, nick)
        )
        return dict(row) if row else None

    def opt_in(self, server: str, nick: str):
        self._upsert(server, nick, opted_in=True)

    def opt_out(self, server: str, nick: str):
        with self.db.transaction() as conn:
            self._upsert(server, nick, opted_in=False)
            # Opt-out state and history removal are one privacy transaction.
            conn.execute(
                "DELETE FROM conversation_history WHERE server = ? AND nick = ?",
                (server, nick),
            )

    def set_noisy(self, server: str, nick: str, noisy: bool):
        self._upsert(server, nick, noisy=noisy)

    def toggle_noisy(self, server: str, nick: str) -> bool:
        """Atomically toggle noisy mode and return the new state."""
        with self.db.transaction():
            enabled = not self.is_noisy(server, nick)
            self._upsert(server, nick, noisy=enabled)
            return enabled

    def is_opted_in(self, server: str, nick: str) -> bool:
        user = self.get_user(server, nick)
        return bool(user["opted_in"]) if user else True  # Default to opted in

    def is_noisy(self, server: str, nick: str) -> bool:
        user = self.get_user(server, nick)
        return bool(user["noisy"]) if user else False

    def _upsert(self, server: str, nick: str, **kwargs):
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO users (server, nick, opted_in, noisy, created_at, updated_at)
                   VALUES (?, ?, COALESCE(?, 1), COALESCE(?, 0), ?, ?)
                   ON CONFLICT(server, nick) DO UPDATE SET
                       opted_in = COALESCE(?, opted_in),
                       noisy = COALESCE(?, noisy),
                       updated_at = ?""",
                (server, nick,
                 kwargs.get("opted_in"), kwargs.get("noisy"), now, now,
                 kwargs.get("opted_in"), kwargs.get("noisy"), now),
            )


class ToolPolicyStore:
    """Persistence for server-wide disabled local tools."""

    def __init__(self, db: Database):
        self.db = db

    def disable(self, server: str, tool_name: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO disabled_tools (server, tool_name, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(server, tool_name) DO UPDATE SET
                       updated_at = excluded.updated_at""",
                (server, tool_name, now),
            )

    def enable(self, server: str, tool_name: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM disabled_tools WHERE server = ? AND tool_name = ?",
                (server, tool_name),
            )

    def disabled_names(self, server: str) -> set[str]:
        rows = self.db.fetchall(
            "SELECT tool_name FROM disabled_tools WHERE server = ?",
            (server,),
        )
        return {str(row["tool_name"]) for row in rows}

    def is_disabled(self, server: str, tool_name: str) -> bool:
        row = self.db.fetchone(
            "SELECT 1 FROM disabled_tools WHERE server = ? AND tool_name = ?",
            (server, tool_name),
        )
        return row is not None


class HistoryStore:
    """CRUD for conversation_history table."""

    def __init__(self, db: Database):
        self.db = db

    def append(self, server: str, channel: str, nick: str,
               role: str, content: str, source: str = "user",
               session_id: str | None = None):
        with self.db.transaction() as conn:
            if session_id is None:
                session_id = self._get_active_session(server, channel)
            conn.execute(
                """INSERT INTO conversation_history
                   (server, channel, nick, role, content, source, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (server, channel, nick, role, content, source, session_id),
            )

    def recent(self, server: str, channel: str, limit: int | None = None) -> list[dict]:
        """Get active-session messages for a channel, ordered oldest first."""
        with self.db.transaction() as conn:
            session_id = self._get_active_session(server, channel)
            if limit is None:
                rows = conn.execute(
                    """SELECT * FROM conversation_history
                       WHERE server = ? AND channel = ? AND session_id = ?
                       ORDER BY id ASC""",
                    (server, channel, session_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM (
                           SELECT * FROM conversation_history
                           WHERE server = ? AND channel = ? AND session_id = ?
                           ORDER BY id DESC LIMIT ?
                       )
                       ORDER BY id ASC""",
                    (server, channel, session_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def clear_channel(self, server: str, channel: str):
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM conversation_history WHERE server = ? AND channel = ?",
                (server, channel),
            )

    def _get_active_session(self, server: str, channel: str) -> str:
        row = self.db.fetchone(
            "SELECT active_session_id FROM sessions WHERE server = ? AND channel = ?",
            (server, channel)
        )
        if row:
            return row["active_session_id"]
        # Create new session
        session_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            # A concurrent caller may have created the session while this
            # caller was waiting for the connection lock.
            row = conn.execute(
                "SELECT active_session_id FROM sessions WHERE server = ? AND channel = ?",
                (server, channel),
            ).fetchone()
            if row:
                return row["active_session_id"]
            conn.execute(
                "INSERT INTO sessions (server, channel, active_session_id) VALUES (?, ?, ?)",
                (server, channel, session_id),
            )
        return session_id


class PromptStore:
    """CRUD for prompts table."""

    def __init__(self, db: Database):
        self.db = db

    def list_all(self, server: str) -> list[dict]:
        rows = self.db.fetchall(
            "SELECT * FROM prompts WHERE server = ? ORDER BY trigger ASC",
            (server,)
        )
        return [dict(r) for r in rows]

    def get(self, server: str, trigger: str) -> dict | None:
        row = self.db.fetchone(
            "SELECT * FROM prompts WHERE server = ? AND trigger = ?",
            (server, trigger)
        )
        return dict(row) if row else None

    def add(self, server: str, trigger: str, response: str, created_by: str | None = None):
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO prompts (server, trigger, response, created_by) VALUES (?, ?, ?, ?)",
                (server, trigger, response, created_by),
            )

    def remove(self, server: str, trigger: str):
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM prompts WHERE server = ? AND trigger = ?",
                (server, trigger),
            )

    def remove_by_index(self, server: str, index: int) -> bool:
        """Remove prompt by its position in the alphabetically-ordered list."""
        with self.db.transaction():
            prompts = self.list_all(server)
            if 0 <= index < len(prompts):
                self.remove(server, prompts[index]["trigger"])
                return True
            return False


class CommandStats:
    """Write-only command usage logging."""

    def __init__(self, db: Database):
        self.db = db

    def log(self, server: str, command: str, nick: str | None = None, channel: str | None = None):
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO command_stats (server, command, nick, channel) VALUES (?, ?, ?, ?)",
                (server, command, nick, channel),
            )


class PerformanceStats:
    """Write-only performance logging."""

    def __init__(self, db: Database):
        self.db = db

    def log(self, server: str, channel: str, nick: str | None,
            session_id: str, provider: str, model: str,
            prompt_tokens: int | None = None, completion_tokens: int | None = None,
            processing_time_ms: int | None = None, response_chars: int | None = None):
        total = (prompt_tokens or 0) + (completion_tokens or 0)
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO performance_stats
                   (server, channel, nick, session_id, provider, model,
                    prompt_tokens, completion_tokens, total_tokens,
                    processing_time_ms, response_chars)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (server, channel, nick, session_id, provider, model,
                 prompt_tokens, completion_tokens, total,
                 processing_time_ms, response_chars),
            )
