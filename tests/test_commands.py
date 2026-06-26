"""Tests for TerraAI prompt and context managers."""

import os
import tempfile

import pytest

from terra_ai.context.manager import ContextManager
from terra_ai.database import DBConfig, Database
from terra_ai.prompts.manager import PromptManager


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    config = DBConfig(path=path, wal=False)
    database = Database(config)
    yield database
    os.unlink(path)


@pytest.fixture
def prompts(db):
    return PromptManager(db, trigger_char=".")


@pytest.fixture
def context(db, prompts):
    return ContextManager(db, prompts)


class TestPromptManager:
    def test_get_system_prompt(self, prompts):
        sp = prompts.get_system_prompt()
        # With no config, botnick defaults to "" so no name appears
        assert "{triggerchar}" not in sp  # Should be interpolated

    def test_context_seed(self, prompts):
        seed = prompts.get_context_seed("irc.example.com", "#chan")
        assert len(seed) > 0
        assert seed[0]["role"] == "user"
        assert seed[0]["source"] == "system"

    def test_add_and_remove_prompt(self, prompts):
        prompts.add_prompt("irc.example.com", ".wea", "sunny", "admin")
        assert prompts.remove_prompt("irc.example.com", ".wea") is True

    def test_list_prompts(self, prompts):
        prompts.add_prompt("irc.example.com", ".wea", "sunny")
        prompts.add_prompt("irc.example.com", ".bye", "goodbye")
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
        ctx = context.compose_context("irc.example.com", "#chan", "hello", "nick")
        assert len(ctx) > 0
        assert ctx[0]["role"] == "system"  # System prompt
        assert ctx[-1]["role"] == "user"  # Current message
        assert ctx[-1]["content"] == "hello"

    def test_save_exchange(self, context):
        context.save_exchange("irc.example.com", "#chan", "nick", "hello", "hi there")
        history = context.history.recent("irc.example.com", "#chan")
        assert len(history) == 2
        assert history[0]["content"] == "hello"
        assert history[1]["content"] == "hi there"

    def test_save_system_message(self, context):
        context.save_system_message("irc.example.com", "#chan", "nick", "location: chicago")
        history = context.history.recent("irc.example.com", "#chan")
        assert len(history) == 1
        assert history[0]["source"] == "system"

    def test_compact(self, context):
        context.save_exchange("irc.example.com", "#chan", "nick", "hello", "hi")
        new_session = context.compact("irc.example.com", "#chan")
        assert new_session is not None
        # After compact, history should be empty (new session)
        history = context.history.recent("irc.example.com", "#chan")
        assert len(history) == 0
