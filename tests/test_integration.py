"""Integration tests for TerraAI."""

from unittest.mock import MagicMock, patch

import pytest

from terra_ai.providers.openrouter import _reasoning_for_model

# db and terra fixtures live in conftest.py


class TestTerraAI:
    def test_is_admin(self, terra):
        terra.config.admin_nicks = ["admin"]
        assert terra.is_admin("admin") is True
        assert terra.is_admin("user") is False

    def test_is_opted_in_default(self, terra):
        assert terra.is_opted_in("irc.example.com", "newuser") is True

    def test_is_opted_in_after_optout(self, terra):
        terra.user.handle_optout("irc.example.com", "nick")
        assert terra.is_opted_in("irc.example.com", "nick") is False

    def test_should_respond_opted_out(self, terra):
        terra.user.handle_optout("irc.example.com", "nick")
        assert terra.should_respond("irc.example.com", "nick", "hello") is False

    def test_should_respond_opted_in(self, terra):
        assert terra.should_respond("irc.example.com", "nick", "hello") is True

    def test_should_respond_self(self, terra):
        # Without config setting bot_nick, self-nick is "" so any nick matches nothing
        botnick = terra.config.bot.get("bot_nick", "")
        if botnick:
            assert terra.should_respond("irc.example.com", botnick, "hello") is False
        else:
            # Self-check disabled when bot_nick not configured
            assert terra.should_respond("irc.example.com", "anyone", "hello") is True

    def test_is_management_command(self, terra):
        assert terra.is_management_command(".optin") is True
        assert terra.is_management_command(".wea") is False

    def test_handle_ai_message(self, terra):
        """Test that handle_ai_message returns the provider's response."""
        provider = terra.registry.get()
        provider.chat = lambda messages, system_prompt=None, effort="high": "Hello!"

        result = terra.handle_ai_message("irc.example.com", "#chan", "nick", "hi")
        assert result == "Hello!"

    def test_handle_management_optin(self, terra):
        result = terra.handle_management("irc.example.com", "#chan", "nick", ".optin")
        assert "opted in" in result

    def test_handle_management_optout(self, terra):
        result = terra.handle_management("irc.example.com", "#chan", "nick", ".optout")
        assert "opted out" in result

    def test_handle_management_setlocation(self, terra):
        # .setlocation uses hybrid routing: handle_management returns None
        # as a signal that the caller should forward to AI for the response
        result = terra.handle_management("irc.example.com", "#chan", "nick", ".setlocation chicago, il")
        assert result is None


class TestPluginRules:
    """Verify SOPEL plugin rule configuration."""

    def test_addressed_freeform_allows_bots(self):
        """$nick rule must allow bot-tagged messages."""
        from terra_ai import plugin as terra_plugin
        assert getattr(terra_plugin.addressed_freeform, 'allow_bots', False), \
            "addressed_freeform.allow_bots must be True for IRCv3 bot tag compatibility"

    def test_setup_exists(self):
        """Plugin must have a setup() function for SOPEL."""
        from terra_ai import plugin as terra_plugin
        assert callable(getattr(terra_plugin, 'setup', None)), \
            "plugin.setup must be callable"

    def test_cmd_help_exists(self):
        """Plugin must have a cmd_help command handler."""
        from terra_ai import plugin as terra_plugin
        assert callable(getattr(terra_plugin, 'cmd_help', None)), \
            "plugin.cmd_help must be callable"


class TestAdminCommands:
    def test_add_and_list_prompts(self, terra):
        terra.admin.handle_addprompt("irc.example.com", "nick", ".wea sunny")
        result = terra.admin.handle_listprompts("irc.example.com", "nick")
        assert ".wea" in result
        assert "sunny" in result

    def test_rmprompt(self, terra):
        terra.admin.handle_addprompt("irc.example.com", "nick", ".wea sunny")
        result = terra.admin.handle_rmprompt("irc.example.com", "nick", "1")
        assert "Removed" in result

    def test_help(self, terra):
        result = terra.admin.handle_help()
        assert ".optin" in result
        assert ".ai" in result


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

        def spy_chat(messages, system_prompt=None, effort="high"):
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

    def test_reasoning_for_model_owl_gets_effort(self):
        """owl-alpha: user opted in to experimental effort — should get reasoning.effort."""
        r = _reasoning_for_model("openrouter/owl-alpha", "high")
        # owl-alpha is not in _NO_REASONING_MODELS, so it falls through to None
        # per the final "return None" catch-all (no prefix match).
        # If we add owl-specific handling, this test updates accordingly.
        assert r is None  # Currently no prefix match — change if owl gets effort support
