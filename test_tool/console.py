#!/usr/bin/env python3
"""Irssi-like terminal client for testing TerraAI locally.

Uses Textual (not curses) for the TUI — gives us SVG export and a test
pilot for automated UI verification.

Usage:
    python test_tool/console.py           # interactive mode
    python test_tool/console.py --test    # non-interactive mode
"""

import asyncio
import logging
import os
import sys
import time
from types import SimpleNamespace

# Log to file so interactive stdout stays clean
os.makedirs("data", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("data/test_tool.log", mode="w")],
)
logger = logging.getLogger("terraai")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textual.app import App
from textual.binding import Binding
from textual.color import Color
from textual.widgets import Input, RichLog, Static

from terra_ai import plugin as terra_plugin
from terra_ai.bot import TerraAI
from terra_ai.config import TerraAISection


def _default_test_config():
    """Create a lightweight config object with TerraAISection defaults.

    Used when there's no SOPEL bot running (test tool, fixtures).
    Returns a SimpleNamespace with the same attributes as TerraAISection.
    """
    c = SimpleNamespace()
    c.model = os.environ.get("TERRAI_MODEL", "openrouter/owl-alpha")
    c.api_key = os.environ.get("OPENROUTER_API_KEY", "")
    c.base_url = "https://openrouter.ai/api/v1"
    c.provider_timeout = 30
    c.trigger_phrase = "TerraAI:"
    c.bot_nick = ""
    c.trigger_char = "."
    c.effort = "high"
    c.sqlite_path = "data/test-terraai.db"
    return c


class FakeTrigger:
    """Mimic a SOPEL trigger object for direct handler dispatch."""

    def __init__(self, nick, channel, text, is_pm=False, admin=False):
        self.nick = nick
        self.sender = nick if is_pm else channel
        self.match = None
        self.text = text
        self.is_pm = is_pm
        self.admin = admin
        self._text = text

    def group(self, num):
        """group(0) = full text, group(1) = command word, group(2) = args."""
        if num == 0:
            return self._text
        text = self._text
        if text.startswith("."):
            text = text[1:]
        elif text.startswith("-"):
            text = text[1:]
        parts = text.split(None, 1)
        if num == 1:
            return parts[0] if parts else ""
        if num == 2:
            return parts[1] if len(parts) > 1 else ""
        return None


class FakeBot:
    """Mimic a SOPEL bot object.

    Tracks say() (channel messages) and notice() (PM responses) separately.
    In SOPEL, bot.say() sends to the channel, bot.notice() sends a
    private notice back to the user.
    """

    def __init__(self):
        self.messages = []
        self.notices = []
        self.isupport = {"NETWORK": "test-network"}

    def say(self, msg):
        self.messages.append(msg)
        return msg

    def reply(self, msg):
        self.messages.append(msg)
        return msg

    def notice(self, nick, msg):
        self.notices.append((nick, msg))
        return msg


class TerraAITestClient:
    """Test client that connects to TerraAI without a real IRC server."""

    def __init__(self, config_path="config/terraai.yaml"):
        self._load_env()
        self.config = self._load_config(config_path)
        self.terra = TerraAI(self.config)
        self.server = "test-network"
        self.channel = "#terra-ai"
        self.nick = "tester"
        self.bot = FakeBot()

    def _load_env(self):
        """Load .env file if present."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_paths = [
            os.path.join(project_root, ".env"),
            os.path.expanduser("~/.terra-ai/.env"),
        ]
        for env_path in env_paths:
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            os.environ.setdefault(key.strip(), value.strip())

    def _load_config(self, path):
        """Load config, fall back to defaults if file missing."""
        import configparser
        from sopel.config import Config as SopelConfig

        try:
            sopel_config = SopelConfig(path)
            sopel_config.define_section("terraai", TerraAISection)
            return sopel_config.terraai
        except Exception:
            return _default_test_config()

    def send_message(self, text):
        """Send a message as the test user and return bot responses.

        Calls plugin.py handler functions directly via getattr dispatch.
        """
        logger.info("send_message text=%r", text)
        self.bot.messages.clear()
        self.bot.notices.clear()
        trigger = FakeTrigger(self.nick, self.channel, text)
        trigger_char = self.terra.prompts.trigger_char if self.terra.prompts else ""
        trigger_phrase = self.terra.config.trigger_phrase

        def notify_thinking():
            if self.terra.user.is_noisy(self.server, self.nick):
                self.bot.notice(self.nick, "Thinking...")

        cmd_word = ""
        if text.startswith(trigger_char):
            cmd_word = (
                text[len(trigger_char):].split()[0].lower()
                if text[len(trigger_char):].strip()
                else ""
            )

        if cmd_word:
            handler = getattr(terra_plugin, f"cmd_{cmd_word}", None)
            if handler:
                notify_thinking()
                handler(self.bot, trigger)
                return list(self.bot.messages)
            else:
                full_text = text[len(trigger_char):].strip()
                trigger.group = lambda n: full_text if n == 1 else None
                notify_thinking()
                terra_plugin.addressed_freeform(self.bot, trigger)
                return list(self.bot.messages)

        if text.lower().startswith(trigger_phrase.lower()):
            notify_thinking()
            trigger.group = (
                lambda n: text[len(trigger_phrase):].strip() if n == 1 else None
            )
            terra_plugin.addressed_freeform(self.bot, trigger)
            return list(self.bot.messages)

        return list(self.bot.messages)

    def send_as(self, nick, text):
        """Send a message as a specific nick."""
        self.bot.messages.clear()
        self.bot.notices.clear()
        trigger = FakeTrigger(nick, self.channel, text)
        response = self.terra.handle_ai_message(self.server, self.channel, nick, text)
        if response:
            self.bot.say(response)
        return list(self.bot.messages)

    def send_pm(self, nick, text):
        """Send a PM (direct message) to the bot.

        Unlike channel messages, PMs don't need a trigger phrase — everything
        in a PM is already addressed to the bot.

        Returns {"say": [...], "notice": [...]}.
        """
        logger.info("send_pm nick=%r text=%r", nick, text)
        self.bot.messages.clear()
        self.bot.notices.clear()
        trigger = FakeTrigger(nick, self.channel, text, is_pm=True)

        def notify_thinking():
            if self.terra.user.is_noisy(self.server, nick):
                self.bot.notice(nick, "Thinking...")

        cmd_word = text.split()[0].lstrip(".-") if text.split() else ""
        if cmd_word:
            handler = getattr(terra_plugin, f"cmd_{cmd_word}", None)
            if handler:
                notify_thinking()
                handler(self.bot, trigger)
                return {"say": list(self.bot.messages), "notice": list(self.bot.notices)}

        notify_thinking()
        response = self.terra.handle_ai_message(
            self.server, nick, nick, text, include_history=True
        )
        if response:
            self.bot.say(response)
        return {"say": list(self.bot.messages), "notice": list(self.bot.notices)}


def _format_messages(messages, botnick):
    """Format a list of message strings for display in the chat widget.

    Returns a Rich Loggable object (plain string — RichLog.write() handles
    newlines natively).
    """
    lines = []
    for msg in messages:
        lines.append(msg)
    return "\n".join(lines) if lines else ""


class TerraAIApp(App):
    """Textual TUI for interacting with TerraAI."""

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
        padding: 0 1;
    }
    #input {
        height: 1;
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+d", "quit", "Quit", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(self, client: TerraAITestClient):
        super().__init__()
        self.client = client
        self.messages: list[str] = []
        self.input_history: list[str] = []
        self.history_idx: int = -1
        self.botnick = client.terra.config.bot_nick or "TerraAI"

    def compose(self):
        yield Static("", id="header")
        self.chat_log = RichLog(id="chat", wrap=True, markup=False)
        yield self.chat_log
        yield Input(placeholder="Type a message...", id="input")

    def on_mount(self):
        self._redraw_header()
        self._redraw_chat()
        self.query_one("#input", Input).focus()

    def _ts(self):
        """Irssi-style timestamp [HH:MM]."""
        return time.strftime("[%H:%M]")

    def _redraw_header(self):
        header = self.query_one("#header", Static)
        clock = time.strftime("%H:%M")
        header.update(f" #terra-ai (test mode) — type 'quit' to exit {clock}")

    def _redraw_chat(self):
        self.chat_log.clear()
        self.chat_log.write(_format_messages(self.messages, self.botnick))

    def _append_message(self, msg):
        self.messages.append(msg)
        # Keep history bounded
        if len(self.messages) > 500:
            self.messages = self.messages[-500:]
        self._redraw_chat()

    async def on_input_submitted(self, event: Input.Submitted):
        text = event.value
        event.input.value = ""

        if not text:
            return

        cmd = text.lower()
        if cmd in ("quit", "/quit", "exit"):
            self.exit()
            return

        # Parse /msg <text> as a PM
        is_pm = text.lower().startswith("/msg ")
        if is_pm:
            pm_text = text[5:]
            if not pm_text:
                return
        else:
            pm_text = text

        # Add to history
        if text not in self.input_history:
            self.input_history.append(text)
        self.history_idx = -1

        # Display user message immediately
        if is_pm:
            self._append_message(f"{self._ts()} [PM] <{self.client.nick}> {pm_text}")
        else:
            self._append_message(f"{self._ts()} <{self.client.nick}> {text}")

        # Show "thinking" indicator for noisy users
        if self.client.terra.user.is_noisy(self.client.server, self.client.nick):
            self.client.bot.notice(self.client.nick, "Thinking...")
            self._append_message(f"{self._ts()} -!- Thinking...")

        # Dispatch the message (synchronous — blocks during AI call)
        try:
            if is_pm:
                result = self.client.send_pm(self.client.nick, pm_text)
                responses = result["say"]
                notices = result["notice"]
            else:
                responses = self.client.send_message(text)
                notices = list(self.client.bot.notices)
        except Exception as e:
            logger.exception("dispatch failed")
            self._append_message(f"{self._ts()} -!- Error: {e}")
            return

        # Render bot responses
        for r in responses:
            if is_pm:
                self._append_message(f"{self._ts()} [PM] <{self.botnick}> {r}")
            else:
                self._append_message(f"{self._ts()} <{self.botnick}> {r}")

        # Render any new notices (besides the "Thinking..." we already showed)
        for nick, msg in notices:
            if msg == "Thinking...":
                continue
            self._append_message(f"{self._ts()} -!- {msg}")

    def action_quit(self):
        self.exit()


def run_interactive():
    """Run the console interactively."""
    client = TerraAITestClient()
    terra_plugin._terrai = client.terra
    app = TerraAIApp(client=client)
    app.run()


if __name__ == "__main__":
    if "--test" in sys.argv:
        # Non-interactive mode for testing
        client = TerraAITestClient()
        terra_plugin._terrai = client.terra
        botnick = client.terra.config.bot_nick or "TerraAI"
        print(f"{botnick} Test Client")
        print("=" * 40)

        print("\n[.optin]")
        print(client.send_message(".optin"))

        print("\n[.optout]")
        print(client.send_message(".optout"))

        print("\n[.optin]")
        print(client.send_message(".optin"))

        print("\n[.addprompt wea sunny]")
        print(client.send_message(".addprompt wea sunny"))

        print("\n[.listprompts]")
        print(client.send_message(".listprompts"))

        print("\n[.wea]")
        print(client.send_message(".wea"))

        print("\n[.help]")
        print(client.send_message(".help"))

        print("\n[.effort low]")
        print(client.send_message(".effort low"))

        print("\n[.effort]")
        print(client.send_message(".effort"))

        print("\nDone!")
    else:
        run_interactive()
