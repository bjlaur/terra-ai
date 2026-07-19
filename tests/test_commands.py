"""Tests for TerraAI prompt and context managers."""

import pytest

from terra_ai.context.manager import ContextManager
from terra_ai.database import DBConfig, Database
from terra_ai.prompts.manager import PromptManager
from terra_ai.prompts.defaults import SYSTEM_PROMPTS
from terra_ai.providers.base import ProviderCapabilities


@pytest.fixture
def db(tmp_path):
    config = DBConfig(path=str(tmp_path / "terraai.db"), wal=False)
    database = Database(config)
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def prompts(db):
    return PromptManager(db)


@pytest.fixture
def context(db, prompts):
    return ContextManager(db, prompts)


class TestPromptManager:
    def test_context_seed(self, prompts):
        seed = prompts.get_context_seed(
            "irc.example.com",
            "#chan",
            capabilities=ProviderCapabilities(
                local_tools=True,
                native_search=True,
            ),
        )
        assert len(seed) > 0
        # The prompt is a list of `system` messages, one per rule.
        assert seed[0]["role"] == "system"
        assert all(m["role"] == "system" for m in seed)
        # It must teach persona AND tool usage.
        joined = " ".join(m["content"] for m in seed)
        assert "weather_forecast" in joined
        assert "web search" in joined
        # The bot nick placeholder is interpolated per server/config.
        assert "{botnick}" not in joined
        assert "{prefix_char}" not in joined
        assert [message["content"] for message in seed] == [
            template.format(botnick="", prefix_char="")
            for template, _ in SYSTEM_PROMPTS
        ]

    def test_context_seed_uses_configured_command_prefix(self, db):
        prompts = PromptManager(db, prefix_char="!")
        seed = prompts.get_context_seed(
            "irc.example.com",
            "#chan",
            capabilities=ProviderCapabilities(local_tools=True),
        )

        joined = " ".join(message["content"] for message in seed)
        assert "!wea" in joined
        assert "-wea" not in joined

    def test_context_seed_does_not_advertise_unsupported_features(self, prompts):
        seed = prompts.get_context_seed("irc.example.com", "#chan")
        joined = " ".join(message["content"] for message in seed)
        assert "weather_forecast" not in joined
        assert "provider-side web search" not in joined

    def test_add_and_remove_prompt(self, prompts):
        prompts.add_prompt("irc.example.com", "wea", "sunny", "admin")
        assert prompts.remove_prompt("irc.example.com", "wea") is True

    def test_list_prompts(self, prompts):
        prompts.add_prompt("irc.example.com", "wea", "sunny")
        prompts.add_prompt("irc.example.com", "bye", "goodbye")
        all_prompts = prompts.list_prompts("irc.example.com")
        assert len(all_prompts) == 2

    def test_effort(self, prompts):
        assert prompts.effort == "high"
        assert prompts.set_effort("low") is True
        assert prompts.effort == "low"
        assert prompts.set_effort("invalid") is False
        assert prompts.effort == "low"  # Unchanged


class TestContextManager:
    def test_compose_context(self, context):
        # The manager is a faithful pass-through: what's passed in comes out.
        # (The <nick> prefix is added upstream by TerraAI.handle_ai_message —
        # not the manager's concern; verified at the integration layer.)
        ctx = context.compose_context("irc.example.com", "#chan", "hello", "nick")
        assert len(ctx) > 0
        # The prompt is a list of `system` messages (one per rule), so the
        # first turn is a system message, and the last is the current user
        # message, echoed verbatim.
        assert ctx[0]["role"] == "system"
        assert ctx[-1]["role"] == "user"  # Current message
        assert ctx[-1]["content"] == "hello"

    def test_save_exchange(self, context):
        # What's saved is stored verbatim and replayed back unchanged.
        context.save_exchange("irc.example.com", "#chan", "nick", "hello", "hi there")
        history = context.history.recent("irc.example.com", "#chan")
        assert len(history) == 2
        assert history[0]["content"] == "hello"
        assert history[1]["content"] == "hi there"

    def test_save_exchange_rolls_back_both_rows_on_failure(self, context, db):
        with db.transaction() as conn:
            conn.execute(
                """CREATE TRIGGER fail_assistant_history
                   BEFORE INSERT ON conversation_history
                   WHEN NEW.role = 'assistant'
                   BEGIN
                       SELECT RAISE(ABORT, 'assistant write failed');
                   END"""
            )

        with pytest.raises(Exception, match="assistant write failed"):
            context.save_exchange(
                "irc.example.com", "#chan", "nick", "hello", "hi there"
            )

        rows = db.fetchall(
            "SELECT role, content FROM conversation_history WHERE server = ? AND channel = ?",
            ("irc.example.com", "#chan"),
        )
        assert rows == []

    def test_compact(self, context):
        context.save_exchange("irc.example.com", "#chan", "nick", "hello", "hi")
        new_session = context.compact("irc.example.com", "#chan")
        assert new_session is not None
        # After compact, history should be empty (new session)
        history = context.history.recent("irc.example.com", "#chan")
        assert len(history) == 0
