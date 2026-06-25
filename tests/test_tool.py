"""Tests for the TerraAI test tool.

These tests verify the test tool works correctly by simulating user input
and checking bot responses. Screenshots are exported for visual inspection.
"""

import os
import tempfile

import pytest

from terraai.bot import TerraAI
from terraai.config import TerraConfig
from terraai.database import DBConfig, Database

# Skip if textual not available
try:
    from textual.app import TextualApp
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


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
    config.provider.api_key = os.environ.get("OPENROUTER_API_KEY", "test-key")
    t = TerraAI(config)
    return t


class TestTestTool:
    """Test the test tool's core functionality."""

    def test_send_message(self, terra):
        """Test sending a management command."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_message(".optin")
        assert len(responses) > 0
        assert "opted in" in responses[0]

    def test_send_ai_message(self, terra):
        """Test sending an AI message."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_message("hello")
        assert len(responses) > 0

    def test_send_as_different_nick(self, terra):
        """Test sending as different users."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_as("other-user", "hello")
        assert len(responses) > 0

    def test_custom_prompt_flow(self, terra):
        """Test creating and matching a custom prompt."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra

        # Add prompt
        add_response = client.send_message(".addprompt wea sunny")
        assert "Added" in add_response[0]

        # Trigger prompt
        trigger_response = client.send_message(".wea")
        assert "sunny" in trigger_response[0]

    def test_help_command(self, terra):
        """Test help command."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_message(".help")
        assert len(responses) > 0
        assert ".optin" in responses[0]
