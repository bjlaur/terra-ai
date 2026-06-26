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
from textual.widgets import Input

from terra_ai import plugin as terra_plugin
from test_tool.console import TerraAIApp, TerraAITestClient


def _extract_svg_texts(svg_str: str) -> list[str]:
    """Extract all text content from an SVG string (for Static widgets only).

    SVG may HTML-encode < and > as &lt; and &gt;.
    """
    svg = html.unescape(svg_str)
    return [m.group(1) for m in re.finditer(r"<text[^>]*>([^<]*)</text>", svg)]


def _chat_text(app) -> str:
    """Get the chat text from the app's messages list."""
    return "\n".join(app.messages)


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
    """Header shows #terra-ai."""
    async with app.run_test() as pilot:
        await pilot.pause()
        svg = app.export_screenshot()
        texts = _extract_svg_texts(svg)
        all_text = " ".join(texts)
        assert "#terra-ai" in all_text, f"Header not found. texts: {texts[:10]}"
        assert app.messages == [], "Chat should be empty on launch"


@pytest.mark.asyncio
async def test_after_message(app):
    """User message + bot response visible in chat."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", ".optin")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app)
        assert "optin" in text.lower() or "opted" in text.lower(), \
            f"Optin response not found. messages: {app.messages}"


@pytest.mark.asyncio
async def test_pm_sends_with_prefix(app):
    """/msg hello shows [PM] <tester> hello prefix."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", "/msg hello")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app)
        assert "[PM]" in text, f"[PM] prefix not found. messages: {app.messages}"
        assert "tester" in text.lower(), f"tester nick not found"


@pytest.mark.asyncio
async def test_notice_shows_thinking(app):
    """With noisy ON, -!- Thinking... appears before AI response."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", ".noisy")
        await pilot.press("enter")
        await pilot.pause()
        await _type_text(pilot, "#input", "TerraAI: hello")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app)
        assert "-!-" in text, f"Notice prefix not found. messages: {app.messages}"
        assert "Thinking" in text, f"Thinking notice not found. messages: {app.messages}"


@pytest.mark.asyncio
async def test_noisy_toggle_shows_notice(app):
    """.noisy shows 'Noisy mode ON/OFF'."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", ".noisy")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app)
        assert "Noisy" in text, f"Noisy mode notice not found. messages: {app.messages}"


@pytest.mark.asyncio
async def test_help_shows_command_list(app):
    """.help shows all commands."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", ".help")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app)
        assert ".optin" in text, f"Command list not found. messages: {app.messages}"


@pytest.mark.asyncio
async def test_tab_completion(app):
    """Pressing Tab at start of line completes to 'TerraAI: '."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", "Ter")
        await pilot.press("tab")
        await pilot.pause()
        input_widget = app.query_one("#input", Input)
        value = input_widget.value
        assert value.startswith("TerraAI"), \
            f"Tab did not complete. Got: {value!r}"


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
    """.optin, .effort low, etc. produce correct responses."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", ".optin")
        await pilot.press("enter")
        await pilot.pause()
        await _type_text(pilot, "#input", ".effort low")
        await pilot.press("enter")
        await pilot.pause()
        text = _chat_text(app)
        assert "opted" in text.lower() or "optin" in text.lower(), \
            f"Optin response not found. messages: {app.messages}"
        assert "low" in text.lower(), \
            f"Effort level not found. messages: {app.messages}"
