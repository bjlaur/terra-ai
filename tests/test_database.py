"""Tests for TerraAI database layer."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from terra_ai.database import (
    CommandStats,
    DBConfig,
    Database,
    HistoryStore,
    PerformanceStats,
    PromptStore,
    ToolPolicyStore,
    UserStore,
)
from terra_ai.commands.user import UserCommands
from terra_ai.prompts.manager import PromptManager


@pytest.fixture
def db(tmp_path):
    """Create one temporary database and close it after each test."""
    config = DBConfig(path=str(tmp_path / "terraai.db"), wal=False)
    database = Database(config)
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def users(db):
    return UserStore(db)


@pytest.fixture
def history(db):
    return HistoryStore(db)


@pytest.fixture
def prompts(db):
    return PromptStore(db)


@pytest.fixture
def stats(db):
    return CommandStats(db)


@pytest.fixture
def perf(db):
    return PerformanceStats(db)


class TestUserStore:
    def test_get_user_not_found(self, users):
        assert users.get_user("irc.example.com", "nick") is None

    def test_opt_in(self, users):
        users.opt_in("irc.example.com", "nick")
        assert users.is_opted_in("irc.example.com", "nick")

    def test_opt_out(self, users):
        users.opt_in("irc.example.com", "nick")
        users.opt_out("irc.example.com", "nick")
        assert not users.is_opted_in("irc.example.com", "nick")

    def test_opt_out_clears_history(self, users, history):
        history.append("irc.example.com", "#chan", "nick", "user", "hello")
        users.opt_out("irc.example.com", "nick")
        recent = history.recent("irc.example.com", "#chan")
        assert len(recent) == 0

    def test_noisy(self, users):
        users.set_noisy("irc.example.com", "nick", True)
        assert users.is_noisy("irc.example.com", "nick")

    def test_default_opted_in(self, users):
        assert users.is_opted_in("irc.example.com", "unknown") is True

    def test_multi_server_isolation(self, users):
        users.opt_out("irc.example.com", "nick")
        assert users.is_opted_in("irc.other.com", "nick") is True

    def test_shared_connection_serializes_handler_threads(self, db):
        def update_user(index):
            store = UserStore(db)
            store.set_noisy("irc.example.com", f"nick-{index}", True)
            return store.is_noisy("irc.example.com", f"nick-{index}")

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(update_user, range(40)))

        assert results == [True] * 40
        assert db.fetchone("SELECT COUNT(*) FROM users")[0] == 40

    def test_noisy_mode_survives_command_object_recreation(self, db):
        first = UserCommands(db, PromptManager(db))
        assert first.handle_noisy("irc.example.com", "nick") == "Noisy mode ON."

        recreated = UserCommands(db, PromptManager(db))
        assert recreated.is_noisy("irc.example.com", "nick") is True
        assert recreated.handle_noisy("irc.example.com", "nick") == "Noisy mode OFF."


class TestToolPolicyStore:
    def test_policy_is_server_wide_and_isolated_between_servers(self, db):
        policy = ToolPolicyStore(db)
        policy.disable("irc.example.com", "weather_forecast")

        assert policy.is_disabled("irc.example.com", "weather_forecast") is True
        assert policy.is_disabled("irc.other.com", "weather_forecast") is False
        assert policy.disabled_names("irc.example.com") == {"weather_forecast"}

        policy.enable("irc.example.com", "weather_forecast")
        assert policy.disabled_names("irc.example.com") == set()

    def test_legacy_tool_table_is_replaced_without_losing_other_data(self, tmp_path):
        path = tmp_path / "legacy.db"
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE users (
                server TEXT NOT NULL,
                nick TEXT NOT NULL,
                opted_in BOOLEAN NOT NULL DEFAULT 1,
                noisy BOOLEAN NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (server, nick)
            );
            INSERT INTO users (server, nick) VALUES ('irc.example.com', 'keeper');
            CREATE TABLE tools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server TEXT NOT NULL,
                nick TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(server, nick, tool_name)
            );
            INSERT INTO tools (server, nick, tool_name, disabled)
                VALUES ('irc.example.com', 'old-user', 'weather_forecast', 1);
            """
        )
        conn.close()

        migrated = Database(DBConfig(path=str(path), wal=False))
        try:
            assert UserStore(migrated).get_user("irc.example.com", "keeper") is not None
            tables = {
                row["name"]
                for row in migrated.fetchall(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            assert "tools" not in tables
            assert "disabled_tools" in tables
            assert ToolPolicyStore(migrated).disabled_names("irc.example.com") == set()
        finally:
            migrated.close()


class TestHistoryStore:
    def test_append_and_recent(self, history):
        history.append("irc.example.com", "#chan", "nick", "user", "hello")
        recent = history.recent("irc.example.com", "#chan")
        assert len(recent) == 1
        assert recent[0]["content"] == "hello"

    def test_recent_order(self, history):
        history.append("irc.example.com", "#chan", "nick", "user", "first")
        history.append("irc.example.com", "#chan", "nick", "user", "second")
        recent = history.recent("irc.example.com", "#chan")
        assert recent[0]["content"] == "first"
        assert recent[1]["content"] == "second"

    def test_recent_limit(self, history):
        for i in range(10):
            history.append("irc.example.com", "#chan", "nick", "user", f"msg{i}")
        recent = history.recent("irc.example.com", "#chan", limit=5)
        assert len(recent) == 5
        assert [r["content"] for r in recent] == [
            "msg5", "msg6", "msg7", "msg8", "msg9"
        ]

    def test_recent_default_is_unbounded(self, history):
        for i in range(55):
            history.append("irc.example.com", "#chan", "nick", "user", f"msg{i}")
        recent = history.recent("irc.example.com", "#chan")
        assert len(recent) == 55
        assert recent[0]["content"] == "msg0"
        assert recent[-1]["content"] == "msg54"

    def test_clear_channel(self, history):
        history.append("irc.example.com", "#chan", "nick", "user", "hello")
        history.clear_channel("irc.example.com", "#chan")
        assert len(history.recent("irc.example.com", "#chan")) == 0

    def test_session_isolation(self, history):
        history.append("irc.example.com", "#chan", "nick", "user", "msg1", session_id="s1")
        history.append("irc.example.com", "#chan", "nick", "user", "msg2", session_id="s2")
        # Default session is auto-created, so recent returns only default-session messages
        recent = history.recent("irc.example.com", "#chan")
        assert len(recent) == 0

    def test_source_field(self, history):
        history.append("irc.example.com", "#chan", "nick", "user", "hello", source="system")
        recent = history.recent("irc.example.com", "#chan")
        assert recent[0]["source"] == "system"


class TestPromptStore:
    def test_add_and_get(self, prompts):
        prompts.add("irc.example.com", ".wea", "sunny", "admin")
        p = prompts.get("irc.example.com", ".wea")
        assert p is not None
        assert p["response"] == "sunny"

    def test_list_all(self, prompts):
        prompts.add("irc.example.com", ".wea", "sunny")
        prompts.add("irc.example.com", ".bye", "goodbye")
        all_prompts = prompts.list_all("irc.example.com")
        assert len(all_prompts) == 2
        assert all_prompts[0]["trigger"] == ".bye"  # Alphabetical

    def test_remove(self, prompts):
        prompts.add("irc.example.com", ".wea", "sunny")
        prompts.remove("irc.example.com", ".wea")
        assert prompts.get("irc.example.com", ".wea") is None

    def test_remove_by_index(self, prompts):
        prompts.add("irc.example.com", ".aaa", "first")
        prompts.add("irc.example.com", ".bbb", "second")
        assert prompts.remove_by_index("irc.example.com", 0) is True
        assert prompts.get("irc.example.com", ".aaa") is None
        assert prompts.get("irc.example.com", ".bbb") is not None

    def test_remove_by_index_out_of_range(self, prompts):
        prompts.add("irc.example.com", ".aaa", "first")
        assert prompts.remove_by_index("irc.example.com", 5) is False

    def test_duplicate_trigger(self, prompts):
        prompts.add("irc.example.com", ".wea", "sunny")
        with pytest.raises(Exception):
            prompts.add("irc.example.com", ".wea", "other")

    def test_multi_server_isolation(self, prompts):
        prompts.add("irc.example.com", ".wea", "sunny")
        assert prompts.get("irc.other.com", ".wea") is None


class TestCommandStats:
    def test_log(self, stats):
        stats.log("irc.example.com", ".wea", "nick", "#chan")
        # No error = pass


class TestPerformanceStats:
    def test_log(self, perf):
        perf.log("irc.example.com", "#chan", "nick", "s1", "openrouter",
                  "gemini-2.0", prompt_tokens=100, completion_tokens=50,
                  processing_time_ms=1500, response_chars=200)
        # No error = pass
