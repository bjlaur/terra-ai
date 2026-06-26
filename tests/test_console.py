"""Tests for the TerraAI console (Textual TUI + TerraAITestClient).

These tests verify:
1. The test client routes messages correctly (unit tests, no UI).
2. The Textual TUI can be driven headlessly via the test pilot.
3. Real API tests (skipped unless --real is passed).
"""

import os

import pytest
from textual.widgets import Input

from terra_ai import plugin as terra_plugin

# db and terra fixtures live in conftest.py
# terra is mocked by default; pass --real for real API calls


class TestTestTool:
    """Test the test tool's core routing functionality."""

    def test_send_message(self, terra):
        """Test sending a management command."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_message(".optin")
        assert len(responses) > 0
        assert "opted in" in responses[0]

    def test_regular_message_ignored(self, terra):
        """Test that regular messages (no trigger) are ignored by the bot."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_message("hello")
        assert len(responses) == 0, "Regular message should not produce a response"

    @pytest.mark.real
    def test_async_ai_call(self, terra):
        """Test that AI calls work.

        Provider is mocked by default — only routing is tested.
        Pass --real + @pytest.mark.real for live API.
        """
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_message("TerraAI: hello")
        assert len(responses) > 0, "AI call produced no response"
        assert responses[0].strip() != ""

    @pytest.mark.real
    def test_unknown_command_routes_to_ai(self, terra):
        """Test that unknown .commands are forwarded to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        response = client.send_message(".what's 2+2")
        assert len(response) > 0, "Unknown .command produced no response"
        assert response[0].strip() != "", "Unknown .command produced empty response"

    def test_help_command(self, terra):
        """Test help command."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_message(".help")
        assert len(responses) > 0
        assert ".optin" in responses[0]


class TestPM:
    """Test PM (private message) routing."""

    @pytest.mark.real
    def test_pm_trigger_routes_to_ai(self, terra):
        """PM with trigger phrase should route to AI with history."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", "TerraAI: hello from PM")
        assert len(result["say"]) > 0

    def test_pm_management_command(self, terra):
        """PM with management command should work (e.g. .optin)."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".optin")
        assert len(result["say"]) > 0
        assert "opted in" in result["say"][0]

    def test_pm_help_command(self, terra):
        """PM with .help should return command list."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".help")
        assert len(result["say"]) > 0
        assert ".optin" in result["say"][0]

    @pytest.mark.real
    def test_pm_unknown_command_routes_to_ai(self, terra):
        """PM with unknown .command should route to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".what's 2+2")
        assert len(result["say"]) > 0

    @pytest.mark.real
    def test_ai_command_context_free(self, terra):
        """Test .ai command in PM — context-free prompt."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".ai hello")
        assert len(result["say"]) > 0

    @pytest.mark.real
    def test_pm_direct_message(self, terra):
        """Test PM with plain text (no trigger, no dot) -> AI with history."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", "hello there")
        assert len(result["say"]) > 0

    @pytest.mark.real
    def test_pm_setlocation_forwards_to_ai(self, terra):
        """Test .setlocation in PM — hybrid routing forwards to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".setlocation Portland, OR")
        assert len(result["say"]) > 0

    def test_clear_command(self, terra):
        """Test .clear command — wipes session, starts fresh."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        client.send_pm("tester", ".optin")
        client.send_pm("tester", "TerraAI:hello")
        result = client.send_pm("tester", ".clear")
        assert len(result["say"]) > 0
        assert "cleared" in result["say"][0].lower()

    def test_compact_admin_only_for_non_admin(self, terra):
        """Test .compact is gated to admin via @plugin.require_admin."""
        from test_tool.console import TerraAITestClient
        terra_plugin._terrai = terra
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".compact")
        assert len(result["say"]) > 0
        assert "denied" in result["say"][0].lower()


class TestNoisy:
    """Test noisy mode — status notices for verbose users."""

    def test_noisy_toggle(self, terra):
        """Test .noisy toggles ON then OFF."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        on = client.send_message(".noisy")
        assert "ON" in on[0].upper()
        off = client.send_message(".noisy")
        assert "OFF" in off[0].upper()

    def test_noisy_off_no_notice(self, terra):
        """When noisy is OFF, no 'Thinking...' notice is sent."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        client.send_message(".optin")
        client.send_message(".noisy")  # toggle ON
        client.send_message(".noisy")  # toggle back OFF
        client.bot.notices.clear()
        client.send_message(".optin")
        assert len(client.bot.notices) == 0

    @pytest.mark.real
    def test_noisy_on_sends_notice(self, terra):
        """When noisy is ON, a 'Thinking...' notice is sent before AI call."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        client.send_message(".optin")
        client.send_message(".noisy")  # toggle ON
        client.send_message("TerraAI: hello")
        assert len(client.bot.notices) > 0
        assert any("Thinking" in msg for _, msg in client.bot.notices)


async def _type_text(pilot, selector, text):
    """Type text into a widget character-by-character via pilot.press().

    Textual 8.2's Pilot doesn't have a .type() method, so we focus the
    widget and press each key.
    """
    pilot.app.query_one(selector, Input).focus()
    for ch in text:
        await pilot.press(ch)


class TestInteractiveMode:
    """Test the Textual TUI via the test pilot.

    These tests use app.run_test() to drive the UI headlessly — no pty
    subprocess needed.
    """

    @pytest.fixture
    def env_setup(self, monkeypatch):
        """Set up API key for interactive tests."""
        monkeypatch.setenv(
            "OPENROUTER_API_KEY",
            os.environ.get("OPENROUTER_API_KEY", "test-key"),
        )

    @pytest.mark.asyncio
    async def test_interactive_launches_and_exits(self, terra):
        """Test that the app launches and can be quit."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.exit()
        assert True  # If we got here, no crash

    @pytest.mark.asyncio
    async def test_interactive_accepts_input(self, terra):
        """Test that the app accepts input and dispatches commands."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await _type_text(pilot, "#input", ".optin")
            await pilot.press("enter")
            await pilot.pause()
            # The chat should now contain the optin response
            content = "\n".join(app.messages)
            assert "optin" in content.lower() or "opted" in content.lower()

    @pytest.mark.asyncio
    async def test_interactive_accepts_pm(self, terra):
        """Test that /msg <text> sends as a PM."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await _type_text(pilot, "#input", "/msg hello")
            await pilot.press("enter")
            await pilot.pause()
            content = "\n".join(app.messages)
            assert "[PM]" in content

    @pytest.mark.asyncio
    async def test_interactive_empty_input(self, terra):
        """Test that empty input (just enter) doesn't crash."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.pause()
            # No crash = pass

    @pytest.mark.asyncio
    async def test_interactive_ctrl_d_exits(self, terra):
        """Test that Ctrl+D exits cleanly."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await pilot.press("ctrl+d")
            await pilot.pause()
        assert True


# --- Real API tests (skipped unless OPENROUTER_API_KEY is set) ---

HAS_REAL_API = bool(os.environ.get("OPENROUTER_API_KEY"))

if not HAS_REAL_API:
    import sys
    sys.stderr.write(
        "\n GO SOURCE .env YOU DOLT!\n"
        "   OPENROUTER_API_KEY not set — --real tests skipped.\n"
        "   Fix: source ~/.terra-ai/.env\n\n"
    )


@pytest.mark.skipif(
    not HAS_REAL_API,
    reason="OPENROUTER_API_KEY not set — run: source ~/.terra-ai/.env",
)
class TestRealAPI:
    """Tests that hit the real AI provider."""

    @pytest.fixture
    def real_terra(self, db):
        from terra_ai.bot import TerraAI
        from tests.conftest import _make_test_config
        config = _make_test_config(
            sqlite_path=db.config.path,
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        t = TerraAI(config)
        terra_plugin._terrai = t
        return t

    def test_real_effort_level(self, real_terra):
        """Test .effort low sets the level and responds with confirmation."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        responses = client.send_message(".effort low")
        assert len(responses) > 0
        assert "low" in responses[0].lower()

    def test_real_unknown_command_goes_to_ai(self, real_terra):
        """Test that unknown .commands are forwarded to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        resp = client.send_message(".what's 2+2")
        assert len(resp) > 0
        assert resp[0].strip() != ""

    def test_real_noisy_toggle(self, real_terra):
        """Test .noisy toggles noisy mode (no API call needed)."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        resp_on = client.send_message(".noisy")
        assert "ON" in resp_on[0].upper()
        resp_off = client.send_message(".noisy")
        assert "OFF" in resp_off[0].upper()

    def test_real_setlocation_goes_to_ai(self, real_terra):
        """Test .setlocation forwards to AI for response."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        client.send_message(".optin")
        resp = client.send_message(".setlocation Portland, OR")
        assert len(resp) > 0
        assert resp[0].strip() != ""

    def test_real_pm_trigger_responds(self, real_terra):
        """Test PM with trigger phrase gets AI response."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        result = client.send_pm("tester", "TerraAI: hello from PM")
        assert len(result["say"]) > 0

    def test_real_pm_effort_level(self, real_terra):
        """Test .effort in PM sets level and confirms."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        result = client.send_pm("tester", ".effort low")
        assert len(result["say"]) > 0
        assert "low" in result["say"][0].lower()

    def test_real_noisy_sends_notice_on_ai_message(self, real_terra):
        """When noisy is ON, a 'Thinking...' notice is sent before AI call."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        client.send_message(".optin")
        client.send_message(".noisy")  # toggle ON
        client.send_message("TerraAI: hello")
        assert len(client.bot.notices) > 0
        assert any("Thinking" in msg for _, msg in client.bot.notices)
