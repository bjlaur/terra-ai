"""Tests for the TerraAI console (Textual TUI + TerraAITestClient).

These tests verify:
1. The test client routes messages correctly via SOPEL's dispatcher.
2. The Textual TUI can be driven headlessly via the test pilot.

Routing:
- Management commands: ``-optin``, ``-help``, etc. (SOPEL's core.prefix = ``-``)
- Addressed freeform: ``TerraAI: hello`` (SOPEL's ``$nick`` rule)
- Unknown prefixed: ``-whatever ...`` (lazy prefix fallback rule → AI)

Mock vs Real:
- Tests marked @pytest.mark.mock always use the mocked provider.
- Tests marked @pytest.mark.real require --real + OPENROUTER_API_KEY.
- Tests with no marker default to mock.

Run mock tests (default): pytest
Run real API tests:       pytest --real -m real
Run everything:            pytest --real
"""

import os

import pytest
from textual.widgets import Input

from terra_ai import plugin as terra_plugin

# db and terra fixtures live in conftest.py

# The command prefix configured in FakeBot's settings.core.prefix.
# The regex r"\-" matches the literal character "-".
PREFIX = "-"


async def _type_text(pilot, selector, text):
    """Type text into a widget character-by-character via pilot.press().

    Textual 8.2's Pilot doesn't have a .type() method, so we focus the
    widget and press each key.
    """
    pilot.app.query_one(selector, Input).focus()
    for ch in text:
        await pilot.press(ch)


class TestTestTool:
    """Test the test tool's core routing functionality.

    send_message() and send_pm() route through SOPEL's real rule dispatcher
    via ``dispatch_line``. These tests verify end-to-end routing.
    """

    @pytest.mark.mock
    def test_send_message(self, terra):
        """Test sending a management command."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_message(f"{PREFIX}optin")
        assert len(result["say"]) > 0
        assert "opted in" in result["say"][0]

    @pytest.mark.mock
    def test_regular_message_ignored(self, terra):
        """Test that regular messages (no prefix) are ignored by the bot."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_message("hello")
        assert len(result["say"]) == 0, "Regular message should not produce a response"

    @pytest.mark.mock
    def test_addressed_freeform_routes_to_ai_mock(self, terra):
        """Mock version: addressing the bot by nick routes to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_message("TerraAI: hello")
        assert len(result["say"]) > 0
        assert "mocked AI response" in result["say"][0]

    @pytest.mark.real
    def test_addressed_freeform_routes_to_ai_real(self, terra):
        """Real version: addressing the bot by nick routes to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_message("TerraAI: hello")
        assert len(result["say"]) > 0
        assert result["say"][0].strip() != ""

    @pytest.mark.mock
    def test_unknown_command_routes_to_ai_mock(self, terra):
        """Mock version: unknown -command forwarded to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_message(f"{PREFIX}whats 2+2")
        assert len(result["say"]) > 0
        assert "mocked" in result["say"][0].lower()

    @pytest.mark.real
    def test_unknown_command_routes_to_ai_real(self, terra):
        """Real version: unknown -command forwarded to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_message(f"{PREFIX}whats 2+2")
        assert len(result["say"]) > 0
        assert result["say"][0].strip() != ""

    @pytest.mark.mock
    def test_help_command(self, terra):
        """Test help command."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_message(f"{PREFIX}help")
        assert len(result["say"]) > 0
        assert "optin" in result["say"][0].lower()


class TestPM:
    """Test PM (private message) routing."""

    @pytest.mark.mock
    def test_pm_addressed_routes_to_ai_mock(self, terra):
        """Mock version: PM addressed to the bot routes to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", "TerraAI: hello from PM")
        assert len(result["say"]) > 0
        assert "mocked" in result["say"][0].lower()

    @pytest.mark.real
    def test_pm_addressed_routes_to_ai_real(self, terra):
        """Real version: PM addressed to the bot routes to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", "TerraAI: hello from PM")
        assert len(result["say"]) > 0

    @pytest.mark.mock
    def test_pm_management_command(self, terra):
        """PM with management command should work (e.g. -optin)."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", f"{PREFIX}optin")
        assert len(result["say"]) > 0
        assert "opted in" in result["say"][0]

    @pytest.mark.mock
    def test_pm_help_command(self, terra):
        """PM with -help should return command list."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", f"{PREFIX}help")
        assert len(result["say"]) > 0
        assert "optin" in result["say"][0].lower()

    @pytest.mark.mock
    def test_pm_unknown_command_routes_to_ai_mock(self, terra):
        """Mock version: PM with unknown -command routes to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", f"{PREFIX}whats 2+2")
        assert len(result["say"]) > 0
        assert "mocked" in result["say"][0].lower()

    @pytest.mark.real
    def test_pm_unknown_command_routes_to_ai_real(self, terra):
        """Real version: PM with unknown -command routes to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", f"{PREFIX}whats 2+2")
        assert len(result["say"]) > 0

    @pytest.mark.mock
    def test_ai_command_context_free_mock(self, terra):
        """Mock version: -ai command in PM — context-free prompt."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", f"{PREFIX}ai hello")
        assert len(result["say"]) > 0
        assert "mocked" in result["say"][0].lower()

    @pytest.mark.real
    def test_ai_command_context_free_real(self, terra):
        """Real version: -ai command in PM — context-free prompt."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", f"{PREFIX}ai hello")
        assert len(result["say"]) > 0

    @pytest.mark.mock
    def test_pm_unknown_prefixed_message_mock(self, terra):
        """Mock version: PM with unknown prefixed message routes to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", f"{PREFIX}hello there")
        assert len(result["say"]) > 0
        assert "mocked" in result["say"][0].lower()

    @pytest.mark.real
    def test_pm_unknown_prefixed_message_real(self, terra):
        """Real version: PM with unknown prefixed message routes to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", f"{PREFIX}hello there")
        assert len(result["say"]) > 0

    @pytest.mark.mock
    def test_pm_setlocation_forwards_to_ai_mock(self, terra):
        """Mock version: PM -setlocation forwards to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", f"{PREFIX}setlocation Portland, OR")
        assert len(result["say"]) > 0
        assert "mocked" in result["say"][0].lower()

    @pytest.mark.real
    def test_pm_setlocation_forwards_to_ai_real(self, terra):
        """Real version: PM -setlocation forwards to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", f"{PREFIX}setlocation Portland, OR")
        assert len(result["say"]) > 0

    @pytest.mark.mock
    def test_pm_bare_message_routes_to_ai_mock(self, terra):
        """Mock version: bare PM (no prefix, no nick) routes to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", "hello there, how are you?")
        assert len(result["say"]) > 0
        assert "mocked" in result["say"][0].lower()

    @pytest.mark.real
    def test_pm_bare_message_routes_to_ai_real(self, terra):
        """Real version: bare PM (no prefix, no nick) routes to AI."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", "hello there, how are you?")
        assert len(result["say"]) > 0

    @pytest.mark.mock
    def test_clear_command(self, terra):
        """Test -clear command — wipes session, starts fresh."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        client.send_pm("tester", f"{PREFIX}optin")
        client.send_pm("tester", "TerraAI: hello")
        result = client.send_pm("tester", f"{PREFIX}clear")
        assert len(result["say"]) > 0
        assert "cleared" in result["say"][0].lower()

    @pytest.mark.mock
    def test_compact_admin_only_for_non_admin(self, terra):
        """Test -compact is gated to admin via @plugin.require_admin."""
        from test_tool.console import TerraAITestClient
        terra_plugin._terrai = terra
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", f"{PREFIX}compact")
        assert len(result["say"]) > 0
        assert "denied" in result["say"][0].lower()


class TestNoisy:
    """Test noisy mode — status notices for verbose users."""

    @pytest.mark.mock
    def test_noisy_toggle(self, terra):
        """Test -noisy toggles ON then OFF."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        on = client.send_message(f"{PREFIX}noisy")
        assert "ON" in on["say"][0].upper()
        off = client.send_message(f"{PREFIX}noisy")
        assert "OFF" in off["say"][0].upper()

    @pytest.mark.mock
    def test_noisy_off_no_notice(self, terra):
        """When noisy is OFF, no 'Thinking...' notice is sent."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        client.send_message(f"{PREFIX}optin")
        client.send_message(f"{PREFIX}noisy")  # toggle ON
        client.send_message(f"{PREFIX}noisy")  # toggle back OFF
        client.bot.notices.clear()
        client.send_message(f"{PREFIX}optin")
        assert len(client.bot.notices) == 0

    @pytest.mark.mock
    def test_noisy_on_sends_notice_mock(self, terra):
        """Mock version: noisy ON sends 'Thinking...' notice."""
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        client.send_message(f"{PREFIX}optin")
        client.send_message(f"{PREFIX}noisy")  # toggle ON
        client.send_message("TerraAI: hello")
        assert len(client.bot.notices) > 0
        assert any("Thinking" in msg for _, msg in client.bot.notices)

    @pytest.mark.real
    def test_noisy_shows_tool_progress_real(self, terra):
        """Real version: noisy ON shows per-tool notices during weather query.

        Sends a weather question with noisy enabled. The tool-call loop
        should generate multiple notices: "Thinking...", then tool-specific
        notices like "Fetching weather...", then "Thinking..." again.
        """
        from test_tool.console import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        client.send_message(f"{PREFIX}noisy")  # toggle ON
        client.bot.notices.clear()
        client.send_message("TerraAI: weather Detroit")
        # Should have multiple notices (Thinking + tool calls).
        assert len(client.bot.notices) >= 2, \
            f"Expected multiple notices, got {len(client.bot.notices)}: {client.bot.notices}"
        all_notices = " ".join(msg for _, msg in client.bot.notices)
        assert "Thinking" in all_notices
        # Should contain a tool-specific notice (weather fetch).
        tool_words = ["weather", "Fetching", "forecast"]
        assert any(w.lower() in all_notices.lower() for w in tool_words), \
            f"Expected tool-specific notice, got: {client.bot.notices}"


class TestInteractiveMode:
    """Test the Textual TUI via the test pilot.

    These tests use app.run_test() to drive the UI headlessly — no pty
    subprocess needed.
    """

    @pytest.mark.asyncio
    @pytest.mark.mock
    async def test_interactive_launches_and_exits(self, terra):
        """Test that the app launches and can be quit."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.exit()
        assert True

    @pytest.mark.asyncio
    @pytest.mark.mock
    async def test_interactive_accepts_input(self, terra):
        """Test that the app accepts input and dispatches commands."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await _type_text(pilot, "#input", f"{PREFIX}optin")
            await pilot.press("enter")
            await pilot.pause()
            content = "\n".join(app.messages["channel"])
            assert "optin" in content.lower() or "opted" in content.lower()

    @pytest.mark.asyncio
    @pytest.mark.mock
    async def test_interactive_accepts_pm(self, terra):
        """Test that /msg <text> sends as a PM (routes to PM tab, no [PM] prefix)."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await _type_text(pilot, "#input", "/msg hello")
            await pilot.press("enter")
            await pilot.pause()
            # PM messages go to the PM tab, no [PM] prefix needed
            content = "\n".join(app.messages["pm"])
            assert "[PM]" not in content, \
                f"[PM] prefix should not appear in PM tab. pm: {app.messages['pm']}"
            assert "hello" in content.lower(), \
                f"hello not found in PM tab. pm: {app.messages['pm']}"

    @pytest.mark.asyncio
    @pytest.mark.mock
    async def test_interactive_empty_input(self, terra):
        """Test that empty input (just enter) doesn't crash."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.pause()

    @pytest.mark.asyncio
    @pytest.mark.mock
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


class TestToolEnableDisable:
    """Test -disable-tool / -enable-tool / -list-tools."""

    @pytest.mark.asyncio
    @pytest.mark.mock
    async def test_tui_disable_tool(self, terra):
        """-disable-tool weather_forecast reports it disabled."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await _type_text(pilot, "#input", f"{PREFIX}disable-tool weather_forecast")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()  # extra wait for async queue
            text = "\n".join(app.messages["channel"]).lower()
            assert "disabled" in text
            assert "weather_forecast" in text

    @pytest.mark.asyncio
    @pytest.mark.mock
    async def test_tui_enable_tool(self, terra):
        """-enable-tool weather_forecast re-enables it."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await _type_text(pilot, "#input", f"{PREFIX}disable-tool weather_forecast")
            await pilot.press("enter")
            await pilot.pause()
            await _type_text(pilot, "#input", f"{PREFIX}enable-tool weather_forecast")
            await pilot.press("enter")
            await pilot.pause()
            text = "\n".join(app.messages["channel"]).lower()
            assert "enabled" in text
            assert "weather_forecast" in text

    @pytest.mark.asyncio
    @pytest.mark.mock
    async def test_tui_disable_unknown_tool(self, terra):
        """-disable-tool with an invalid name reports the valid tools."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await _type_text(pilot, "#input", f"{PREFIX}disable-tool not_a_tool")
            await pilot.press("enter")
            await pilot.pause()
            text = "\n".join(app.messages["channel"]).lower()
            assert "unknown tool" in text
            assert "weather_forecast" in text

    @pytest.mark.asyncio
    @pytest.mark.mock
    async def test_tui_list_tools(self, terra):
        """-list-tools shows tool status."""
        from test_tool.console import TerraAIApp, TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        app = TerraAIApp(client=client)
        async with app.run_test() as pilot:
            await _type_text(pilot, "#input", f"{PREFIX}list-tools")
            await pilot.press("enter")
            await pilot.pause()
            text = "\n".join(app.messages["channel"]).lower()
            assert "weather_forecast" in text or "enabled" in text
