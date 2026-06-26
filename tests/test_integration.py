"""Integration tests for TerraAI."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from terra_ai.bot import TerraAI
from terra_ai.config import TerraConfig
from terra_ai.database import DBConfig, Database
from terra_ai.providers.base import Message


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    config = DBConfig(path=path, wal=False)
    database = Database(config)
    yield database
    os.unlink(path)


@pytest.fixture
def terra(db):
    config = TerraConfig()
    config.sqlite_path = db.config.path
    config.provider.api_key = "test-key"
    t = TerraAI(config)
    return t


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

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_handle_ai_message(self, mock_client_cls, terra):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

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
