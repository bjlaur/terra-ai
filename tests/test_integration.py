"""Integration tests for TerraAI."""

from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest
from sopel.config import Config

from terra_ai.providers.openrouter import _reasoning_for_model

# db and terra fixtures live in conftest.py


class TestTerraAI:
    def test_is_opted_in_default(self, terra):
        assert terra.is_opted_in("irc.example.com", "newuser") is True

    def test_is_opted_in_after_optout(self, terra):
        terra.user.handle_optout("irc.example.com", "nick")
        assert terra.is_opted_in("irc.example.com", "nick") is False

    def test_should_respond_opted_out(self, terra):
        terra.user.handle_optout("irc.example.com", "nick")
        assert terra.should_respond("irc.example.com", "nick") is False

    def test_should_respond_opted_in(self, terra):
        assert terra.should_respond("irc.example.com", "nick") is True

    def test_should_respond_self(self, terra):
        # Without config setting bot_nick, self-nick is "" so any nick matches nothing
        botnick = terra.config.bot_nick
        if botnick:
            assert terra.should_respond("irc.example.com", botnick) is False
        else:
            # Self-check disabled when bot_nick not configured
            assert terra.should_respond("irc.example.com", "anyone") is True

    @pytest.mark.mock
    def test_handle_ai_message_mock(self, terra):
        """Mock version: handle_ai_message returns mocked response."""
        provider = terra.registry.get()
        provider.chat = lambda messages, system_prompt=None, effort="high", tools=None, max_tool_rounds=3, noisy_callback=None: "Hello!"

        result = terra.handle_ai_message("irc.example.com", "#chan", "nick", "hi")
        assert result == "Hello!"

    def test_handle_optin(self, terra):
        result = terra.user.handle_optin("irc.example.com", "nick")
        assert "opted in" in result

    def test_handle_optout(self, terra):
        result = terra.user.handle_optout("irc.example.com", "nick")
        assert "opted out" in result


class TestPluginRules:
    """Verify SOPEL plugin rule configuration."""

    @pytest.mark.mock
    def test_addressed_freeform_allows_bots_mock(self):
        """$nick rule must allow bot-tagged messages."""
        from terra_ai import plugin as terra_plugin
        assert getattr(terra_plugin.addressed_freeform, 'allow_bots', False), \
            "addressed_freeform.allow_bots must be True for IRCv3 bot tag compatibility"

    def test_setup_exists(self):
        """Plugin must have a setup() function for SOPEL."""
        from terra_ai import plugin as terra_plugin
        assert callable(getattr(terra_plugin, 'setup', None)), \
            "plugin.setup must be callable"

    def test_typed_config_is_registered_and_shutdown_closes_database(self, tmp_path):
        from terra_ai import plugin as terra_plugin
        from terra_ai.config import TerraAISection

        config_path = tmp_path / "sopel.cfg"
        config_path.write_text(
            "\n".join(
                [
                    "[core]",
                    "nick = TerraAI",
                    "host = irc.example.test",
                    "owner = tester",
                    "",
                    "[terraai]",
                    "model = test/model",
                    "api_key = test-key",
                    "base_url = https://openrouter.example/v1",
                    "provider_timeout = 15",
                    f"sqlite_path = {tmp_path / 'terraai.db'}",
                ]
            )
        )
        config = Config(str(config_path), validate=False)
        terra_plugin.configure(config)
        assert isinstance(config.terraai, TerraAISection)

        bot = SimpleNamespace(config=config, settings=config)
        terra_plugin.setup(bot)
        instance = terra_plugin._terrai
        try:
            assert isinstance(instance.config, TerraAISection)
            assert instance.config.provider_timeout == 15
            assert instance.config.bot_nick == "TerraAI"
        finally:
            terra_plugin.shutdown(bot)

        assert terra_plugin._terrai is None
        with pytest.raises(RuntimeError, match="closed"):
            instance.db.fetchone("SELECT 1")

    def test_cmd_help_exists(self):
        """Plugin must have a cmd_help command handler."""
        from terra_ai import plugin as terra_plugin
        assert callable(getattr(terra_plugin, 'cmd_help', None)), \
            "plugin.cmd_help must be callable"


class TestManagementCommands:
    def test_add_and_list_prompts(self, terra):
        terra.management.handle_addprompt("irc.example.com", "nick", ".wea sunny")
        result = terra.management.handle_listprompts("irc.example.com", "nick")
        assert ".wea" in result
        assert "sunny" in result

    def test_rmprompt(self, terra):
        terra.management.handle_addprompt("irc.example.com", "nick", ".wea sunny")
        result = terra.management.handle_rmprompt("irc.example.com", "nick", "1")
        assert "Removed" in result

    def test_help(self, terra):
        result = terra.management.handle_help()
        assert "-optin" in result
        assert "-ai" in result


class TestUserCommands:
    def test_effort(self, terra):
        result = terra.user.handle_effort("low")
        assert "low" in result
        result = terra.user.handle_effort("")
        assert "low" in result  # Unchanged

    def test_effort_invalid(self, terra):
        result = terra.user.handle_effort("ultra")
        assert "Invalid" in result


class TestEffortWire:
    """Verify .effort command actually reaches the AI provider payload."""

    def test_effort_low_reaches_provider(self, terra):
        """Setting .effort low should pass effort='low' to provider.chat()."""
        captured = {}

        provider = terra.registry.get()
        original_chat = provider.chat

        def spy_chat(messages, system_prompt=None, effort="high",
                     tools=None, max_tool_rounds=3, noisy_callback=None):
            captured["effort"] = effort
            return "ok"

        provider.chat = spy_chat
        terra.prompts.set_effort("low")
        terra.handle_ai_message("irc.example.com", "#chan", "nick", "hello")
        assert captured["effort"] == "low"

    def test_effort_default_is_high(self, terra):
        """Default effort should be 'high'."""
        assert terra.prompts.effort == "high"

    def test_reasoning_for_model_gemini_25(self):
        """Gemini 2.5 models should get reasoning.max_tokens."""
        r = _reasoning_for_model("google/gemini-2.5-flash", "high")
        assert r is not None
        assert r["max_tokens"] == 8192
        assert r["exclude"] is True

    def test_reasoning_for_model_claude(self):
        """Claude models should get reasoning.effort."""
        r = _reasoning_for_model("anthropic/claude-sonnet-4-6", "medium")
        assert r is not None
        assert r["effort"] == "medium"
        assert r["exclude"] is True

    def test_reasoning_for_model_openai_o3(self):
        """OpenAI reasoning models should get reasoning.effort."""
        r = _reasoning_for_model("openai/o3", "max")
        assert r is not None
        assert r["effort"] == "max"

    def test_reasoning_for_model_gpt4o_none(self):
        """GPT-4o should not get reasoning (unsupported)."""
        assert _reasoning_for_model("openai/gpt-4o", "high") is None

    def test_reasoning_for_model_unknown_falls_through_none(self):
        """An unrecognized model must NOT get reasoning controls (avoids 422)."""
        r = _reasoning_for_model("openrouter/some-future-model", "high")
        # Not in _NO_REASONING_MODELS and matches no known prefix, so the
        # catch-all returns None — no reasoning field is sent to unknown models.
        assert r is None
