"""Tests for TerraAI database layer."""

import os
import tempfile

import pytest

from terraai.database import (
    CommandStats,
    DBConfig,
    Database,
    HistoryStore,
    PerformanceStats,
    PromptStore,
    UserStore,
)


@pytest.fixture
def db():
    """Create a temporary in-memory database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    config = DBConfig(path=path, wal=False)
    database = Database(config)
    yield database
    os.unlink(path)


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
