#!/usr/bin/env python3
"""Screenshot tests for the TerraAI test tool.

Exports SVGs of the test tool UI for visual inspection.
Inspired by /mnt/jbrowse/tools/svg_screenshot_poc.py

Usage:
    python test_tool/screenshot_test.py
"""

import os
import sys
import tempfile

# Named themes require colors — remove NO_COLOR if set
os.environ.pop("NO_COLOR", None)

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textual.app import App
from textual.widgets import Static, Input

from test_tool.irc_client import TerraAITestClient


class TerraAIScreenshotApp(App):
    """Minimal Textual app for screenshot testing."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #header {
        height: 1;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 0 1;
    }
    #chat {
        height: 1fr;
        overflow-y: auto;
    }
    #input {
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    .user-msg {
        color: $text;
    }
    .bot-msg {
        color: $accent;
    }
    """

    def __init__(self, client: TerraAITestClient):
        super().__init__()
        self.client = client

    def compose(self):
        yield Static("#terra-ai (test mode)", id="header")
        yield Static("", id="chat")
        yield Input(placeholder="Type a message...", id="input")

    def on_input_submitted(self, event: Input.Submitted):
        text = event.value
        if text.lower() in ("quit", "/quit"):
            self.exit()
            return

        # Send message
        responses = self.client.send_message(text)

        # Update chat
        chat = self.query_one("#chat", Static)
        current = str(chat.renderable).strip() if hasattr(chat, 'renderable') and chat.renderable else ""
        lines = []
        if current:
            lines = current.split("\n")
        lines.append(f"<tester> {text}")
        for r in responses:
            lines.append(f"<TerraAI> {r}")
        chat.update("\n".join(lines[-20:]))  # Keep last 20 lines


def check_svg(svg_path: str, expected_texts: list[str]) -> None:
    """Check that an SVG contains expected text.

    This is a programmatic check — visual inspection by a human is still required.
    SVG may HTML-encode < and > as &lt; and &gt;.
    """
    import html

    with open(svg_path) as f:
        svg = html.unescape(f.read())

    missing = [t for t in expected_texts if t not in svg]
    if missing:
        print(f"  FAIL {svg_path}: missing {missing}")
    else:
        print(f"  PASS {svg_path}")


def run_screenshots():
    """Run the app and export screenshots."""
    os.makedirs("test_tool/screenshots", exist_ok=True)
    client = TerraAITestClient()

    # Pre-populate some messages
    client.send_message(".optin")
    client.send_message("hello")

    app = TerraAIScreenshotApp(client)

    async def take_screenshots():
        async with app.run_test(size=(80, 24)) as pilot:
            # Screenshot 1: Initial state
            svg = app.export_screenshot()
            with open("test_tool/screenshots/initial.svg", "w") as f:
                f.write(svg)
            await pilot.pause(0.5)

            # Screenshot 2: After typing a message
            await pilot.press(*"hello world")
            await pilot.press("enter")
            await pilot.pause(1)
            svg = app.export_screenshot()
            with open("test_tool/screenshots/after-message.svg", "w") as f:
                f.write(svg)
            await pilot.pause(0.5)

            # Screenshot 3: Add a prompt, then list
            await pilot.press(*".addprompt wea sunny")
            await pilot.press("enter")
            await pilot.pause(0.5)
            await pilot.press(*".listprompts")
            await pilot.press("enter")
            await pilot.pause(1)
            svg = app.export_screenshot()
            with open("test_tool/screenshots/listprompts.svg", "w") as f:
                f.write(svg)

    import asyncio
    asyncio.run(take_screenshots())

    # Programmatic checks on SVGs
    print("Checking SVGs...")
    check_svg("test_tool/screenshots/initial.svg", ["#terra-ai"])
    check_svg("test_tool/screenshots/after-message.svg", ["<tester>", "<TerraAI>"])
    check_svg("test_tool/screenshots/listprompts.svg", [".wea", "sunny"])

    print("\nScreenshots exported to test_tool/screenshots/")
    print("VISUAL INSPECTION REQUIRED: Open each SVG in a browser/image viewer and verify:")
    print("  1. Initial state: header shows '#terra-ai (test mode)', empty chat, input line at bottom")
    print("  2. After message: user message and bot response visible in chat area")
    print("  3. Listprompts: prompt list displayed correctly")


if __name__ == "__main__":
    os.makedirs("test_tool/screenshots", exist_ok=True)
    run_screenshots()
