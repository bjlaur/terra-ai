"""Screenshot tests for the TerraAI console.

These tests drive the real TerraAIApp headlessly via Textual's test
pilot, then verify the rendered content.

Note: We do NOT parse SVG text for chat content — Textual 8.2's
App.export_screenshot() does not reliably capture Static widget content
when updated dynamically. Instead, we assert against app.messages (the
source of truth) directly. SVG screenshots are saved as debug artifacts
only.

See: ~/textual-richlog-svg-export-report.md
"""

import html
import re

import pytest
from textual.widgets import Input, TabbedContent

from terra_ai import plugin as terra_plugin
from test_tool.console import TerraAIApp, TerraAITestClient

# The command prefix configured in FakeBot's settings.core.prefix.
PREFIX = "-"


def _extract_svg_texts(svg_str: str) -> list[str]:
    """Extract all text content from an SVG string.

    SVG may HTML-encode < and > as &lt; and &gt;.
    """
    svg = html.unescape(svg_str)
    return [m.group(1) for m in re.finditer(r"<text[^>]*>([^<]*)</text>", svg)]


def _chat_text(app, tab="channel") -> str:
    """Get the chat text from the specified tab's messages list."""
    return "\n".join(app.messages.get(tab, []))


async def _type_text(pilot, selector, text):
    """Type text character-by-character (Textual 8.2 Pilot has no .type())."""
    pilot.app.query_one(selector, Input).focus()
    for ch in text:
        await pilot.press(ch)


@pytest.fixture
def app(terra):
    """Create a TerraAIApp with the mocked terra fixture."""
    client = TerraAITestClient()
    client.terra = terra
    terra_plugin._terrai = terra
    return TerraAIApp(client=client)


@pytest.mark.asyncio
async def test_initial_state(app):
    """Header shows #terra-ai, Channel tab is active, both tabs empty."""
    async with app.run_test() as pilot:
        await pilot.pause()
        svg = app.export_screenshot()
        texts = _extract_svg_texts(svg)
        all_text = " ".join(texts)
        assert "#terra-ai" in all_text, f"Header not found. texts: {texts[:10]}"
        assert app.messages == {"channel": [], "pm": []}, \
            f"Both tabs should be empty on launch. messages: {app.messages}"
        assert app.query_one(TabbedContent).active == "channel"


@pytest.mark.asyncio
async def test_after_message(app):
    """User message + bot response visible in channel tab."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", f"{PREFIX}optin")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app, "channel")
        assert "optin" in text.lower() or "opted" in text.lower(), \
            f"Optin response not found. channel messages: {app.messages['channel']}"


@pytest.mark.asyncio
async def test_pm_routes_to_pm_tab(app):
    """/msg hello shows <tester> hello in the PM tab (no [PM] prefix)."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", "/msg hello")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app, "pm")
        assert "[PM]" not in text, \
            f"[PM] prefix should be gone in tabbed layout. pm messages: {app.messages['pm']}"
        assert "tester" in text.lower(), \
            f"tester nick not found in PM tab. pm messages: {app.messages['pm']}"
        assert "hello" in text.lower(), \
            f"hello not found in PM tab. pm messages: {app.messages['pm']}"


@pytest.mark.asyncio
async def test_notice_shows_thinking(app):
    """With noisy ON, -!- Thinking... appears in channel tab."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", f"{PREFIX}noisy")
        await pilot.press("enter")
        await pilot.pause()
        await _type_text(pilot, "#input", "TerraAI: hello")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app, "channel")
        assert "-!-" in text, f"Notice prefix not found. channel: {app.messages['channel']}"
        assert "Thinking" in text, f"Thinking notice not found. channel: {app.messages['channel']}"


@pytest.mark.asyncio
async def test_noisy_toggle_shows_notice(app):
    """-noisy shows 'Noisy mode ON/OFF' in channel tab."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", f"{PREFIX}noisy")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app, "channel")
        assert "Noisy" in text, f"Noisy mode notice not found. channel: {app.messages['channel']}"


@pytest.mark.asyncio
async def test_help_shows_command_list(app):
    """-help shows all commands in channel tab."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", f"{PREFIX}help")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app, "channel")
        assert "optin" in text.lower(), \
            f"Command list not found. channel: {app.messages['channel']}"


@pytest.mark.asyncio
async def test_tab_start_of_line_nick_completion(app):
    """Ter<Tab> at start of line completes to 'TerraAI: ' (IRC addressing)."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", "Ter")
        await pilot.press("tab")
        await pilot.pause()
        input_widget = app.query_one("#input", Input)
        assert input_widget.value == "TerraAI: ", \
            f"Start-of-line nick completion wrong. Got: {input_widget.value!r}"


@pytest.mark.asyncio
async def test_tab_mid_line_nick_completion(app):
    """Hello Ter<Tab> completes to 'Hello TerraAI ' (no colon, trailing space)."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", "Hello Ter")
        await pilot.press("tab")
        await pilot.pause()
        input_widget = app.query_one("#input", Input)
        assert input_widget.value == "Hello TerraAI ", \
            f"Mid-line nick completion wrong. Got: {input_widget.value!r}"


@pytest.mark.asyncio
async def test_tab_command_completion(app):
    """-op<Tab> completes to '-optin ' (prefix + command + trailing space)."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", f"{PREFIX}op")
        await pilot.press("tab")
        await pilot.pause()
        input_widget = app.query_one("#input", Input)
        assert input_widget.value == f"{PREFIX}optin ", \
            f"Command completion wrong. Got: {input_widget.value!r}"


@pytest.mark.asyncio
async def test_tab_no_match_bells(app):
    """Tab with no matching completion leaves input unchanged."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", "zzzzznope")
        await pilot.press("tab")
        await pilot.pause()
        input_widget = app.query_one("#input", Input)
        assert input_widget.value == "zzzzznope", \
            f"Input changed on no-match tab. Got: {input_widget.value!r}"


@pytest.mark.asyncio
async def test_input_history(app):
    """Pressing Up recalls previous input."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", "hello")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        input_widget = app.query_one("#input", Input)
        value = input_widget.value
        assert value == "hello", f"History recall failed. Got: {value!r}"


@pytest.mark.asyncio
async def test_management_commands_work(app):
    """-optin, -effort low produce correct responses in channel tab."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", f"{PREFIX}optin")
        await pilot.press("enter")
        await pilot.pause()
        await _type_text(pilot, "#input", f"{PREFIX}effort low")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app, "channel")
        assert "opted" in text.lower() or "optin" in text.lower(), \
            f"Optin response not found. channel: {app.messages['channel']}"
        assert "low" in text.lower(), \
            f"Effort level not found. channel: {app.messages['channel']}"


@pytest.mark.asyncio
async def test_f1_switches_to_channel(app):
    """F1 switches to Channel tab."""
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f2")
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "pm"
        await pilot.press("f1")
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "channel"


@pytest.mark.asyncio
async def test_f2_switches_to_pm(app):
    """F2 switches to PM tab."""
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "channel"
        await pilot.press("f2")
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "pm"


@pytest.mark.asyncio
async def test_pm_tab_implies_pm_routing(app):
    """Typing in the PM tab routes as a PM without needing /msg prefix."""
    async with app.run_test() as pilot:
        await pilot.pause()
        # Switch to PM tab
        await pilot.press("f2")
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "pm"
        # Type a plain message — should route to PM
        await _type_text(pilot, "#input", "hello")
        await pilot.press("enter")
        await pilot.pause()
        # Message should appear in PM tab
        text = _chat_text(app, "pm")
        assert "hello" in text.lower(), \
            f"hello not found in PM tab. pm: {app.messages['pm']}"
        # Channel tab should be empty
        assert len(app.messages["channel"]) == 0, \
            f"Channel should be empty. channel: {app.messages['channel']}"
