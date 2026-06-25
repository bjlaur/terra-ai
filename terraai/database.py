"""SQLite database layer for TerraAI."""

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
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
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        if self.config.wal:
            self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    @contextmanager
    def transaction(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

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
        """)


class UserStore:
    """CRUD for users table."""

    def __init__(self, db: Database):
        self.db = db

    def get_user(self, server: str, nick: str) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM users WHERE server = ? AND nick = ?",
            (server, nick)
        ).fetchone()
        return dict(row) if row else None

    def opt_in(self, server: str, nick: str):
        self._upsert(server, nick, opted_in=True)

    def opt_out(self, server: str, nick: str):
        self._upsert(server, nick, opted_in=False)
        # Clear history on opt-out
        self.db.conn.execute(
            "DELETE FROM conversation_history WHERE server = ? AND nick = ?",
            (server, nick)
        )

    def set_noisy(self, server: str, nick: str, noisy: bool):
        self._upsert(server, nick, noisy=noisy)

    def is_opted_in(self, server: str, nick: str) -> bool:
        user = self.get_user(server, nick)
        return user["opted_in"] if user else True  # Default to opted in

    def is_noisy(self, server: str, nick: str) -> bool:
        user = self.get_user(server, nick)
        return user["noisy"] if user else False

    def _upsert(self, server: str, nick: str, **kwargs):
        now = datetime.now(timezone.utc).isoformat()
        self.db.conn.execute(
            """INSERT INTO users (server, nick, opted_in, noisy, created_at, updated_at)
               VALUES (?, ?, COALESCE(?, 1), COALESCE(?, 0), ?, ?)
               ON CONFLICT(server, nick) DO UPDATE SET
                   opted_in = COALESCE(?, opted_in),
                   noisy = COALESCE(?, noisy),
                   updated_at = ?""",
            (server, nick,
             kwargs.get("opted_in"), kwargs.get("noisy"), now, now,
             kwargs.get("opted_in"), kwargs.get("noisy"), now)
        )
        self.db.conn.commit()


class HistoryStore:
    """CRUD for conversation_history table."""

    def __init__(self, db: Database):
        self.db = db

    def append(self, server: str, channel: str, nick: str,
               role: str, content: str, source: str = "user",
               session_id: str | None = None):
        if session_id is None:
            session_id = self._get_active_session(server, channel)
        self.db.conn.execute(
            """INSERT INTO conversation_history
               (server, channel, nick, role, content, source, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (server, channel, nick, role, content, source, session_id)
        )
        self.db.conn.commit()

    def recent(self, server: str, channel: str, limit: int = 50) -> list[dict]:
        """Get recent messages for a channel, ordered oldest first."""
        session_id = self._get_active_session(server, channel)
        rows = self.db.conn.execute(
            """SELECT * FROM conversation_history
               WHERE server = ? AND channel = ? AND session_id = ?
               ORDER BY id ASC LIMIT ?""",
            (server, channel, session_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def clear_channel(self, server: str, channel: str):
        self.db.conn.execute(
            "DELETE FROM conversation_history WHERE server = ? AND channel = ?",
            (server, channel)
        )
        self.db.conn.commit()

    def _get_active_session(self, server: str, channel: str) -> str:
        row = self.db.conn.execute(
            "SELECT active_session_id FROM sessions WHERE server = ? AND channel = ?",
            (server, channel)
        ).fetchone()
        if row:
            return row["active_session_id"]
        # Create new session
        session_id = str(uuid.uuid4())
        self.db.conn.execute(
            "INSERT INTO sessions (server, channel, active_session_id) VALUES (?, ?, ?)",
            (server, channel, session_id)
        )
        self.db.conn.commit()
        return session_id


class PromptStore:
    """CRUD for prompts table."""

    def __init__(self, db: Database):
        self.db = db

    def list_all(self, server: str) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT * FROM prompts WHERE server = ? ORDER BY trigger ASC",
            (server,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, server: str, trigger: str) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM prompts WHERE server = ? AND trigger = ?",
            (server, trigger)
        ).fetchone()
        return dict(row) if row else None

    def add(self, server: str, trigger: str, response: str, created_by: str | None = None):
        self.db.conn.execute(
            "INSERT INTO prompts (server, trigger, response, created_by) VALUES (?, ?, ?, ?)",
            (server, trigger, response, created_by)
        )
        self.db.conn.commit()

    def remove(self, server: str, trigger: str):
        self.db.conn.execute(
            "DELETE FROM prompts WHERE server = ? AND trigger = ?",
            (server, trigger)
        )
        self.db.conn.commit()

    def remove_by_index(self, server: str, index: int) -> bool:
        """Remove prompt by its position in the alphabetically-ordered list."""
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
        self.db.conn.execute(
            "INSERT INTO command_stats (server, command, nick, channel) VALUES (?, ?, ?, ?)",
            (server, command, nick, channel)
        )
        self.db.conn.commit()


class PerformanceStats:
    """Write-only performance logging."""

    def __init__(self, db: Database):
        self.db = db

    def log(self, server: str, channel: str, nick: str | None,
            session_id: str, provider: str, model: str,
            prompt_tokens: int | None = None, completion_tokens: int | None = None,
            processing_time_ms: int | None = None, response_chars: int | None = None):
        total = (prompt_tokens or 0) + (completion_tokens or 0)
        self.db.conn.execute(
            """INSERT INTO performance_stats
               (server, channel, nick, session_id, provider, model,
                prompt_tokens, completion_tokens, total_tokens,
                processing_time_ms, response_chars)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (server, channel, nick, session_id, provider, model,
             prompt_tokens, completion_tokens, total,
             processing_time_ms, response_chars)
        )
        self.db.conn.commit()
