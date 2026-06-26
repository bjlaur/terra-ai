"""SVG screenshot tests for the TerraAI console.

These tests drive the real TerraAIApp headlessly via Textual's test
pilot, then export SVG screenshots of the rendered UI and verify the
content programmatically.
"""

import html
import os
import re

import pytest
from textual.widgets import Input

from terra_ai import plugin as terra_plugin
from test_tool.console import TerraAIApp, TerraAITestClient


def _extract_svg_texts(svg_str: str) -> list[str]:
    """Extract all text content from an SVG string.

    SVG may HTML-encode < and > as &lt; and &gt;.
    """
    svg = html.unescape(svg_str)
    # Get content between <text ...> and </text>
    return [m.group(1) for m in re.finditer(r"<text[^>]*>([^<]*)</text>", svg)]


def _svg_contains(svg_str: str, expected: str) -> bool:
    """Check if an SVG contains the expected text (HTML-decoded)."""
    return expected in html.unescape(svg_str)


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
    """Header shows #terra-ai, empty chat, input line at bottom."""
    async with app.run_test() as pilot:
        await pilot.pause()
        svg = app.export_screenshot()
        texts = _extract_svg_texts(svg)
        all_text = " ".join(texts)
        assert "#terra-ai" in all_text, f"Header not found. texts: {texts[:10]}"


@pytest.mark.asyncio
async def test_after_message(app):
    """User message + bot response visible in chat."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", ".optin")
        await pilot.press("enter")
        await pilot.pause()
        svg = app.export_screenshot()
        texts = _extract_svg_texts(svg)
        all_text = " ".join(texts)
        # The optin response should appear
        assert "opted" in all_text.lower() or "optin" in all_text.lower(), \
            f"Optin response not found. texts: {texts[:20]}"


@pytest.mark.asyncio
async def test_pm_sends_with_prefix(app):
    """/msg hello shows [PM] <tester> hello prefix."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", "/msg hello")
        await pilot.press("enter")
        await pilot.pause()
        svg = app.export_screenshot()
        texts = _extract_svg_texts(svg)
        all_text = " ".join(texts)
        assert "[PM]" in all_text, f"[PM] prefix not found. texts: {texts[:20]}"
        assert "tester" in all_text.lower(), f"tester nick not found"


@pytest.mark.asyncio
async def test_notic_shows_thinking(app):
    """With noisy ON, -!- Thinking... appears before AI response."""
    async with app.run_test() as pilot:
        # Enable noisy first
        await _type_text(pilot, "#input", ".noisy")
        await pilot.press("enter")
        await pilot.pause()
        # Now send a message that triggers AI
        await _type_text(pilot, "#input", "TerraAI: hello")
        await pilot.press("enter")
        await pilot.pause()
        svg = app.export_screenshot()
        texts = _extract_svg_texts(svg)
        all_text = " ".join(texts)
        assert "-!-" in all_text, f"Notice prefix not found. texts: {texts[:20]}"
        assert "Thinking" in all_text, f"Thinking notice not found. texts: {texts[:20]}"


@pytest.mark.asyncio
async def test_noisy_toggle_shows_notice(app):
    """.noisy shows 'Noisy mode ON/OFF'."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", ".noisy")
        await pilot.press("enter")
        await pilot.pause()
        svg = app.export_screenshot()
        texts = _extract_svg_texts(svg)
        all_text = " ".join(texts)
        assert "Noisy" in all_text, f"Noisy mode notice not found. texts: {texts[:20]}"


@pytest.mark.asyncio
async def test_help_shows_command_list(app):
    """.help shows all commands."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", ".help")
        await pilot.press("enter")
        await pilot.pause()
        svg = app.export_screenshot()
        texts = _extract_svg_texts(svg)
        all_text = " ".join(texts)
        assert ".optin" in all_text, f"Command list not found. texts: {texts[:20]}"


@pytest.mark.asyncio
async def test_tab_completion(app):
    """Pressing Tab at start of line completes to 'TerraAI: '."""
    async with app.run_test() as pilot:
        await _type_text(pilot, "#input", "Ter")
        await pilot.press("tab")
        await pilot.pause()
        # Check the input widget value
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
        # Clear input and press Up
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
        svg = app.export_screenshot()
        texts = _extract_svg_texts(svg)
        all_text = " ".join(texts)
        assert "opted" in all_text.lower() or "optin" in all_text.lower(), \
            f"Optin response not found. texts: {texts[:20]}"
        assert "low" in all_text.lower(), \
            f"Effort level not found. texts: {texts[:20]}"
