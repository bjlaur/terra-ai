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
from textual.widgets import Input, Static, TabbedContent, TabPane

from sopel.plugins import rules as plugin_rules, exceptions as plugin_exceptions
from sopel.plugins.rules import Manager

from terra_ai import plugin as terra_plugin
from terra_ai.bot import TerraAI


def _default_test_config():
    """Create a lightweight config object matching FakeBot's SOPEL settings.

    The test console doesn't have a running SOPEL instance, so we build a
    SimpleNamespace with the same attributes as TerraAISection.  The bot nick
    comes from _Core.nick — no separate YAML or .cfg needed.
    """
    c = SimpleNamespace()
    c.model = os.environ.get("TERRAI_MODEL", "openrouter/owl-alpha")
    c.api_key = os.environ.get("OPENROUTER_API_KEY", "")
    c.base_url = "https://openrouter.ai/api/v1"
    c.provider_timeout = 30
    c.bot_nick = _Core.nick  # Same nick FakeBot uses via _Core
    c.effort = "high"
    c.sqlite_path = "data/test-terraai.db"
    return c


# ── Minimal SOPEL-compatible bot for dispatch ─────────────────────────────────
#
# The test console routes every user line through SOPEL's real rule dispatcher.
# FakeBot provides the bare minimum the dispatcher needs: ``settings`` (with
# ``core.nick`` / ``core.prefix``), ``rules`` (a populated Manager), and
# ``say``/``notice``/``isupport``.  No IRC connection is involved.


class _Core:
    """Minimal SOPEL ``settings.core`` stand-in."""
    nick = "TerraAI"
    prefix = r"\-"
    help_prefix = "-"
    alias_nicks = ()
    owner = ""
    admins = ()
    admin_accounts = ()
    owner_account = ""


class _Settings:
    """Minimal SOPEL ``settings`` stand-in."""
    core = _Core()


def _build_fake_bot():
    """Create a FakeBot with all terra_ai plugin rules registered."""
    bot = FakeBot(_Settings())

    # Scan the plugin module for SOPEL-decorated callables and register them.
    callables = [
        getattr(terra_plugin, name)
        for name in dir(terra_plugin)
        if getattr(getattr(terra_plugin, name), "_sopel_callable", False)
    ]
    bot.register_callables(callables)
    return bot


class FakeBot:
    """SOPEL-compatible bot for the test console.

    Routes through SOPEL's real rule dispatcher (``dispatch_line``) so the
    test console follows the exact same path as production IRC.
    """

    def __init__(self, settings):
        self.settings = settings
        self.nick = settings.core.nick
        self._rules_manager = Manager()
        self.messages: list[str] = []
        self.notices: list[tuple[str, str]] = []

    @property
    def rules(self):
        return self._rules_manager

    @property
    def isupport(self):
        return {"NETWORK": "test-network"}

    def register_callables(self, callables):
        """Register SOPEL-decorated callables onto the rules manager.

        Mirrors :meth:`sopel.bot.Sopel.register_callables` — scans each
        callable for ``commands``, ``nickname_commands``, ``rules`` / ``rule``,
        ``rule_lazy_loaders``, and ``action_commands`` attributes and registers
        them with the appropriate rule type.
        """
        for callbl in callables:
            commands = getattr(callbl, "commands", [])
            nick_commands = getattr(callbl, "nickname_commands", [])
            lazy_rules = getattr(callbl, "rule_lazy_loaders", [])
            # SOPEL 8.0.4 uses .rule (singular); newer versions use .rules
            rules_attr = getattr(callbl, "rules", []) or getattr(callbl, "rule", [])
            action_commands = getattr(callbl, "action_commands", [])

            if commands:
                self._rules_manager.register_command(
                    plugin_rules.Command.from_callable(self.settings, callbl)
                )
            if nick_commands:
                self._rules_manager.register_nick_command(
                    plugin_rules.NickCommand.from_callable(self.settings, callbl)
                )
            if action_commands:
                self._rules_manager.register_action_command(
                    plugin_rules.ActionCommand.from_callable(self.settings, callbl)
                )
            if rules_attr:
                self._rules_manager.register(
                    plugin_rules.Rule.from_callable(self.settings, callbl)
                )
            if lazy_rules:
                try:
                    self._rules_manager.register(
                        plugin_rules.Rule.from_callable_lazy(self.settings, callbl)
                    )
                except plugin_exceptions.PluginError:
                    pass  # lazy loader may fail outside a running bot

    def say(self, message, destination=None, max_messages=1, truncation="", trailing=""):
        self.messages.append(message)

    def notice(self, message, destination=None):
        self.notices.append((destination or "", message))


class TerraAITestClient:
    """Test client that connects to TerraAI without a real IRC server.

    Routes every user line through ``dispatch_line``, which uses SOPEL's real
    rule dispatcher.  No routing logic lives here (spec §5.3).
    """

    def __init__(self):
        self._load_env()
        self.config = _default_test_config()
        self.terra = TerraAI(self.config)
        self.server = "test-network"  # Matches FakeBot.isupport["NETWORK"]
        self.channel = "#terra-ai"
        self.nick = "tester"
        self.bot = _build_fake_bot()

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

    def send_message(self, text: str) -> dict:
        """Send a channel message — routes through SOPEL's dispatcher.

        Returns {"say": [...], "notice": [...]}.
        """
        logger.info("send_message text=%r", text)
        return terra_plugin.dispatch_line(self.bot, self.nick, text, is_pm=False)

    def send_as(self, nick, text):
        """Send a message as a specific nick — routes through SOPEL's dispatcher."""
        logger.info("send_as nick=%r text=%r", nick, text)
        return terra_plugin.dispatch_line(self.bot, nick, text, is_pm=False)

    def send_pm(self, nick, text) -> dict:
        """Send a PM — routes through SOPEL's dispatcher.

        Returns {"say": [...], "notice": [...]}.
        """
        logger.info("send_pm nick=%r text=%r", nick, text)
        return terra_plugin.dispatch_line(self.bot, nick, text, is_pm=True)


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
    TabbedContent {
        height: 1fr;
    }
    Input {
        height: auto;
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+d", "quit", "Quit", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("f1", "switch_tab('channel')", "Channel", show=True),
        Binding("f2", "switch_tab('pm')", "PM", show=True),
        Binding("alt+left", "switch_tab('channel')", "← Channel", show=False),
        Binding("alt+right", "switch_tab('pm')", "PM →", show=False),
    ]

    def __init__(self, client: TerraAITestClient):
        super().__init__()
        self.client = client
        self.messages = {"channel": [], "pm": []}
        self.input_history: list[str] = []
        self.history_idx: int = -1
        self.botnick = client.bot.nick  # From FakeBot.nick → settings.core.nick

    def compose(self):
        yield Static("", id="header")
        with TabbedContent(initial="channel") as tc:
            with TabPane("Channel", id="channel"):
                yield Static("", id="channel-log")
            with TabPane("PM", id="pm"):
                yield Static("", id="pm-log")
        yield Input(placeholder="Type a message...", id="input")

    def on_mount(self):
        self._redraw_header()
        self.query_one("#input", Input).focus()

    def _ts(self):
        """Irssi-style timestamp [HH:MM]."""
        return time.strftime("[%H:%M]")

    def _redraw_header(self):
        header = self.query_one("#header", Static)
        clock = time.strftime("%H:%M")
        header.update(f" #terra-ai (test mode) — type 'quit' to exit {clock}")

    def _append_to_tab(self, tab, msg):
        """Append a message to the specified tab's Static widget."""
        self.messages[tab].append(msg)
        if len(self.messages[tab]) > 500:
            self.messages[tab] = self.messages[tab][500:]
        log = self.query_one(f"#{tab}-log", Static)
        log.update("\n".join(self.messages[tab]))

    def action_switch_tab(self, tab: str):
        """Switch to the given tab."""
        self.query_one(TabbedContent).active = tab

    def on_key(self, event):
        """Handle Tab/Up/Down in the input widget."""
        inp = self.query_one("#input", Input)
        if not inp.has_focus:
            return

        key = event.key
        if key == "tab":
            self._handle_tab_completion(inp)
            event.prevent_default()
            return

        if key == "up":
            if self.input_history:
                if self.history_idx == -1:
                    self.history_idx = len(self.input_history) - 1
                elif self.history_idx > 0:
                    self.history_idx -= 1
                inp.value = self.input_history[self.history_idx]
                inp.cursor_position = len(inp.value)
            event.prevent_default()
            return

        if key == "down":
            if self.input_history and self.history_idx >= 0:
                if self.history_idx < len(self.input_history) - 1:
                    self.history_idx += 1
                else:
                    self.history_idx = -1
                inp.value = self.input_history[self.history_idx] if self.history_idx >= 0 else ""
                inp.cursor_position = len(inp.value)
            event.prevent_default()
            return

    def _handle_tab_completion(self, inp: Input):
        """Tab-complete the word at the cursor.

        Rules (spec §6.4):
        - Start-of-line: complete bot nick with colon (IRC addressing).
          e.g. ``Ter<Tab>`` → ``TerraAI: ``
        - Mid-line: complete bot nick without colon.
          e.g. ``Hello Ter<Tab>`` → ``Hello TerraAI ``
        - If the word starts with the command prefix (``-``), complete
          SOPEL command names. e.g. ``-op<Tab>`` → ``-optin ``
        - Case-insensitive prefix match; replace just the partial word.
        - No match: ring the terminal bell, leave input unchanged.
        """
        current = inp.value
        cursor = inp.cursor_position

        # Scan left from cursor to find start of current word
        word_start = cursor
        while word_start > 0 and current[word_start - 1] not in (" ", "\t"):
            word_start -= 1

        # Extract the partial word at cursor
        partial = current[word_start:cursor]
        if not partial:
            self.bell()
            return

        # Derive the plain command prefix character from settings.core.prefix
        prefix_re = self.client.bot.settings.core.prefix
        prefix_char = prefix_re.lstrip("\\")

        # Build candidate list from SOPEL command names + bot nick
        # get_all_commands() returns [(plugin_name, {name: Command, ...}), ...]
        command_names = []
        for _plugin, cmds in self.client.bot.rules.get_all_commands():
            command_names.extend(cmds.keys())
        candidates = command_names + [self.botnick]

        # If partial starts with the prefix char, strip it for matching
        # and remember to re-add it in the completion.
        had_prefix = False
        match_partial = partial
        if word_start == 0 and partial.startswith(prefix_char):
            had_prefix = True
            match_partial = partial[len(prefix_char):]

        # Case-insensitive match against candidates
        matches = [c for c in candidates if c.lower().startswith(match_partial.lower())]

        if not matches:
            self.bell()
            return

        # Use the first match
        completion = matches[0]

        # Determine suffix: addressing at start-of-line gets "nick: ",
        # mid-line gets trailing space, commands get trailing space.
        at_start = word_start == 0

        if had_prefix:
            # Command completion: re-add prefix + trailing space
            completion = prefix_char + completion + " "
        elif completion == self.botnick:
            # Nick completion
            if at_start:
                # Start-of-line: "TerraAI: " (IRC addressing convention)
                completion = self.botnick + ": "
            else:
                # Mid-line: "TerraAI " (just the nick + space)
                completion = self.botnick + " "
        else:
            # Other candidate (shouldn't normally happen)
            completion = completion + " "

        # Replace the partial word with the completion
        inp.value = current[:word_start] + completion + current[cursor:]
        inp.cursor_position = word_start + len(completion)

    async def on_input_submitted(self, event: Input.Submitted):
        text = event.value
        event.input.value = ""

        if not text:
            return

        cmd = text.lower()
        if cmd in ("quit", "/quit", "exit"):
            self.exit()
            return

        # Determine PM routing:
        # - /msg prefix always routes to PM tab
        # - Being in the PM tab implies /msg (no prefix needed)
        active_tab = self.query_one(TabbedContent).active
        is_explicit_pm = text.lower().startswith("/msg ")
        is_pm = is_explicit_pm or active_tab == "pm"

        if is_explicit_pm:
            pm_text = text[5:]
            if not pm_text:
                return
        else:
            pm_text = text

        # Add to history
        if text not in self.input_history:
            self.input_history.append(text)
        self.history_idx = -1

        # Determine target tab
        target = "pm" if is_pm else active_tab

        # Display user message
        self._append_to_tab(target, f"{self._ts()} <{self.client.nick}> {pm_text}")

        # Dispatch the message in a worker so the UI stays responsive
        self.run_worker(
            self._dispatch(pm_text if is_pm else text, is_pm, target),
            name="ai-dispatch",
            exclusive=False,
        )

    async def _dispatch(self, text, is_pm, target):
        """Run AI dispatch in a thread pool so the UI stays responsive.

        Uses asyncio.to_thread() to offload the synchronous AI call,
        then updates the UI directly (we're back on the main thread).
        """
        try:
            if is_pm:
                result = await asyncio.to_thread(
                    self.client.send_pm, self.client.nick, text
                )
                responses = result["say"]
                notices = result["notice"]
            else:
                result = await asyncio.to_thread(self.client.send_message, text)
                responses = result["say"]
                notices = result["notice"]
        except Exception as e:
            logger.exception("dispatch failed")
            self._append_to_tab(target, f"{self._ts()} -!- Error: {e}")
            return

        # Update UI directly (we're back on the main thread)
        ts = self._ts()
        for r in responses:
            self._append_to_tab(target, f"{ts} <{self.botnick}> {r}")

        for _dest, msg in notices:
            self._append_to_tab(target, f"{ts} -!- {msg}")

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
        botnick = client.bot.nick
        # The command prefix is stored as a regex (e.g. r"\-"); strip the
        # backslash to get the plain character for display / typing.
        prefix_re = client.bot.settings.core.prefix
        prefix = prefix_re.lstrip("\\")
        print(f"{botnick} Test Client")
        print("=" * 40)

        print(f"\n[{prefix}optin]")
        print(client.send_message(f"{prefix}optin"))

        print(f"\n[{prefix}optout]")
        print(client.send_message(f"{prefix}optout"))

        print(f"\n[{prefix}optin]")
        print(client.send_message(f"{prefix}optin"))

        print(f"\n[{prefix}addprompt wea sunny]")
        print(client.send_message(f"{prefix}addprompt wea sunny"))

        print(f"\n[{prefix}listprompts]")
        print(client.send_message(f"{prefix}listprompts"))

        print(f"\n[{prefix}wea]")
        print(client.send_message(f"{prefix}wea"))

        print(f"\n[{prefix}help]")
        print(client.send_message(f"{prefix}help"))

        print(f"\n[{prefix}effort low]")
        print(client.send_message(f"{prefix}effort low"))

        print(f"\n[{prefix}effort]")
        print(client.send_message(f"{prefix}effort"))

        print("\nDone!")
    else:
        run_interactive()
