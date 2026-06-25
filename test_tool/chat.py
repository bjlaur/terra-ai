#!/usr/bin/env python3
"""Irssi-like terminal client for testing TerraAI locally.

Usage:
    python test_tool/chat.py
"""

import asyncio
import curses
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terraai.bot import TerraAI
from terraai.config import TerraConfig
from terraai.database import Database, DBConfig


class FakeTrigger:
    """Mimics a SOPEL trigger object."""

    def __init__(self, nick, channel, text):
        self.nick = nick
        self.sender = channel
        self.group = lambda x: None
        self.match = None
        self.text = text


class FakeBot:
    """Mimics a SOPEL bot object."""

    def __init__(self):
        self.messages = []

    def say(self, msg):
        self.messages.append(msg)
        return msg

    def reply(self, msg):
        self.messages.append(msg)
        return msg

    def notice(self, msg):
        self.messages.append(msg)
        return msg


class TerraAITestClient:
    """Test client that connects to TerraAI without a real IRC server."""

    def __init__(self, config_path: str = "config/terraai.yaml"):
        self._load_env()
        self.config = self._load_config(config_path)
        self.terra = TerraAI(self.config)
        self.server = "test-server"
        self.channel = "#terra-ai"
        self.nick = "tester"
        self.bot = FakeBot()

    def _load_env(self):
        """Load .env file if present."""
        # Look for .env in project root and ~/.terra-ai/.env
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
        try:
            from terraai.config import load_config
            return load_config(path)
        except FileNotFoundError:
            config = TerraConfig()
            config.sqlite_path = "data/test-terraai.db"
            config.resolve_env()
            return config

    def send_message(self, text: str) -> list[str]:
        """Send a message as the test user and return bot responses.

        Mimics real IRC bot routing:
        - Management commands (.) are handled locally
        - .ai <prompt> sends to AI without history
        - Trigger phrase (TerraAI:) sends to AI with history
        - Everything else is ignored (bot doesn't respond to regular chat)
        """
        self.bot.messages.clear()
        trigger = FakeTrigger(self.nick, self.channel, text)

        # .ai command — context-free (checked first because .ai is in the
        # management command list but handle_management returns None for it)
        if text.startswith(".ai "):
            ai_text = text[4:]
            response = self.terra.handle_ai_message(
                self.server, self.channel, self.nick, ai_text, include_history=False
            )
            self.bot.say(response)
            return list(self.bot.messages)

        # Check management commands (.optin, .optout, .help, etc.)
        if self.terra.is_management_command(text):
            response = self.terra.handle_management(self.server, self.channel, self.nick, text)
            if response:
                self.bot.say(response)
            return list(self.bot.messages)

        # Trigger phrase — route to AI with history
        trigger_phrase = self.terra.config.bot.get("trigger_phrase", "TerraAI:")
        if text.lower().startswith(trigger_phrase.lower()):
            ai_text = text[len(trigger_phrase):].strip()
            response = self.terra.handle_ai_message(
                self.server, self.channel, self.nick, ai_text, include_history=True
            )
            if response:
                self.bot.say(response)
            return list(self.bot.messages)

        # Regular message — ignore (real bot only responds to trigger phrase)
        return list(self.bot.messages)

    def send_as(self, nick: str, text: str) -> list[str]:
        """Send a message as a specific nick."""
        self.bot.messages.clear()
        trigger = FakeTrigger(nick, self.channel, text)
        response = self.terra.handle_ai_message(self.server, self.channel, nick, text)
        if response:
            self.bot.say(response)
        return list(self.bot.messages)


def run_interactive():
    """Run the test client in interactive mode using curses."""
    client = TerraAITestClient()

    def main(stdscr):
        # Note: curses.wrapper() already called cbreak(), noecho(), etc.
        # Don't call them again or they'll error.
        curses.curs_set(1)
        stdscr.keypad(True)  # Enable KEY_UP etc. on stdscr
        stdscr.clear()
        stdscr.refresh()

        # Initialize color pairs
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)

        height, width = stdscr.getmaxyx()

        # Create windows
        header = curses.newwin(1, width, 0, 0)
        chat = curses.newwin(height - 2, width, 1, 0)
        input_win = curses.newwin(1, width, height - 1, 0)
        input_win.keypad(True)  # Enable KEY_UP etc. on input window

        header.addstr(0, 0, " #terra-ai (test mode) — type 'quit' to exit ", curses.A_BOLD)
        header.refresh()

        chat.scrollok(True)
        chat.refresh()

        messages: list[str] = []
        input_history: list[str] = []
        history_idx = -1  # -1 = new input
        cursor_pos = 0

        # Known commands for tab completion
        known_commands = [".optin", ".optout", ".noisy", ".setlocation", ".ai",
                          ".effort", ".listprompts", ".addprompt", ".rmprompt",
                          ".compact", ".stats", ".help"]

        def redraw_input(buffer: str):
            """Redraw the input line with buffer content."""
            input_win.clear()
            prefix = "> "
            display = prefix + buffer
            if len(display) > width - 1:
                # Scroll buffer if too long
                offset = len(display) - width + 1
                display = ">" + display[1 + offset:]
            try:
                input_win.addstr(0, 0, display)
                # Place cursor
                cursor_x = min(len(prefix) + cursor_pos, width - 1)
                input_win.move(0, cursor_x)
            except curses.error:
                pass
            input_win.refresh()

        def read_line() -> str | None:
            """Read a line of input with arrow history and tab completion.

                Returns None on Ctrl+C / Ctrl+D.
                """
            nonlocal history_idx, cursor_pos
            buf = list(input_history[history_idx]) if history_idx >= 0 else []
            cursor_pos = len(buf)
            redraw_input("".join(buf))

            while True:
                key = input_win.getch()

                if key == 10 or key == 13:  # Enter
                    return "".join(buf)
                elif key == 4:  # Ctrl+D
                    return None
                elif key == 3:  # Ctrl+C
                    return None
                elif key == curses.KEY_BACKSPACE or key == 127:
                    if cursor_pos > 0:
                        cursor_pos -= 1
                        buf.pop(cursor_pos)
                        redraw_input("".join(buf))
                elif key == curses.KEY_DC:  # Delete
                    if cursor_pos < len(buf):
                        buf.pop(cursor_pos)
                        redraw_input("".join(buf))
                elif key == curses.KEY_LEFT:
                    if cursor_pos > 0:
                        cursor_pos -= 1
                        redraw_input("".join(buf))
                elif key == curses.KEY_RIGHT:
                    if cursor_pos < len(buf):
                        cursor_pos += 1
                        redraw_input("".join(buf))
                elif key == curses.KEY_UP:
                    if input_history:
                        if history_idx == -1:
                            history_idx = len(input_history) - 1
                        elif history_idx > 0:
                            history_idx -= 1
                        buf = list(input_history[history_idx])
                        cursor_pos = len(buf)
                        redraw_input("".join(buf))
                elif key == curses.KEY_DOWN:
                    if input_history and history_idx >= 0:
                        if history_idx < len(input_history) - 1:
                            history_idx += 1
                            buf = list(input_history[history_idx])
                        else:
                            history_idx = -1
                            buf = []
                        cursor_pos = len(buf)
                        redraw_input("".join(buf))
                elif key == 9:  # Tab completion
                    current = "".join(buf[:cursor_pos])
                    if " " in current:
                        # Don't complete after first word
                        curses.beep()
                    else:
                        matches = [c for c in known_commands
                                   if c.startswith(current)]
                        if matches:
                            # Complete common prefix
                            common = matches[0]
                            for m in matches[1:]:
                                while not m.startswith(common):
                                    common = common[:-1]
                            buf = list(common)
                            cursor_pos = len(buf)
                            redraw_input("".join(buf))
                            if len(matches) > 1:
                                # Show completions below
                                chat.addstr(height - 3, 0, "  ".join(matches[:8]),
                                           curses.color_pair(1))
                                chat.refresh()
                        else:
                            curses.beep()
                elif key == curses.KEY_HOME:
                    cursor_pos = 0
                    redraw_input("".join(buf))
                elif key == curses.KEY_END:
                    cursor_pos = len(buf)
                    redraw_input("".join(buf))
                elif 0 <= key < 256 and (32 <= key < 127 or key >= 161):
                    # Printable character
                    if len(buf) < 200:
                        buf.insert(cursor_pos, chr(key))
                        cursor_pos += 1
                        redraw_input("".join(buf))

        while True:
            redraw_input("")
            cmd = read_line()

            if cmd is None:
                break
            cmd = cmd.rstrip("\n")

            if cmd.lower() in ("quit", "/quit", "exit"):
                break

            if not cmd.strip():
                continue

            # Add to history
            if cmd not in input_history:
                input_history.append(cmd)
            history_idx = -1

            # Display user message immediately (before blocking on AI)
            messages.append(f"<{client.nick}> {cmd}")
            chat.clear()
            max_lines = height - 3
            visible = messages[-max_lines:]
            for i, msg in enumerate(visible):
                try:
                    if msg.startswith("<TerraAI>"):
                        chat.addstr(i, 0, msg, curses.color_pair(1))
                    else:
                        chat.addstr(i, 0, msg)
                except curses.error:
                    pass
            chat.refresh()

            # Show "thinking" indicator
            try:
                chat.addstr(len(visible), 0, "<TerraAI> ...", curses.color_pair(1))
            except curses.error:
                pass
            chat.refresh()

            # Send message (blocks on API call)
            responses = client.send_message(cmd)

            # Replace "thinking" with actual response
            for r in responses:
                messages.append(f"<TerraAI> {r}")

            # Redraw chat with response
            chat.clear()
            visible = messages[-max_lines:]
            for i, msg in enumerate(visible):
                try:
                    if msg.startswith("<TerraAI>"):
                        chat.addstr(i, 0, msg, curses.color_pair(1))
                    else:
                        chat.addstr(i, 0, msg)
                except curses.error:
                    pass
            chat.refresh()

    curses.wrapper(main)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Non-interactive mode for testing
        client = TerraAITestClient()
        print("TerraAI Test Client")
        print("=" * 40)

        # Test management commands
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
