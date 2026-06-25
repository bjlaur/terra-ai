#!/usr/bin/env python3
"""Irssi-like terminal client for testing TerraAI locally.

Usage:
    python test_tool/irc_client.py
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
        # Look for .env in project root (parent of test_tool/)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(project_root, ".env")
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
        """Send a message as the test user and return bot responses."""
        self.bot.messages.clear()
        trigger = FakeTrigger(self.nick, self.channel, text)

        # Check management commands first
        if self.terra.is_management_command(text):
            response = self.terra.handle_management(self.server, self.channel, self.nick, text)
            if response:
                self.bot.say(response)
            return list(self.bot.messages)

        # Check custom prompts
        prompt_response = self.terra.prompts.match_prompt(self.server, text)
        if prompt_response:
            self.bot.say(prompt_response)
            return list(self.bot.messages)

        # .ai command — context-free
        if text.startswith(".ai "):
            ai_text = text[4:]
            response = self.terra.handle_ai_message(
                self.server, self.channel, self.nick, ai_text, include_history=False
            )
            self.bot.say(response)
            return list(self.bot.messages)

        # Regular message — route to AI
        response = self.terra.handle_ai_message(self.server, self.channel, self.nick, text)
        if response:
            self.bot.say(response)
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
        curses.curs_set(1)
        stdscr.clear()
        stdscr.refresh()

        height, width = stdscr.getmaxyx()

        # Create windows
        header = curses.newwin(1, width, 0, 0)
        chat = curses.newwin(height - 2, width, 1, 0)
        input_win = curses.newwin(1, width, height - 1, 0)

        header.addstr(0, 0, " #terra-ai (test mode) — type 'quit' to exit ", curses.A_BOLD)
        header.refresh()

        chat.scrollok(True)
        chat.refresh()

        messages = []

        while True:
            input_win.clear()
            input_win.addstr(0, 0, "> ")
            input_win.refresh()

            curses.echo()
            try:
                cmd = input_win.getstr(0, 2, 200).decode("utf-8")
            except KeyboardInterrupt:
                break
            curses.noecho()

            if cmd.lower() in ("quit", "/quit", "exit"):
                break

            if not cmd.strip():
                continue

            # Send message
            responses = client.send_message(cmd)

            # Display user message
            messages.append(f"<{client.nick}> {cmd}")
            for r in responses:
                messages.append(f"<TerraAI> {r}")

            # Redraw chat
            chat.clear()
            max_lines = height - 3
            visible = messages[-max_lines:]
            for i, msg in enumerate(visible):
                try:
                    if msg.startswith("<TerraAI>"):
                        chat.addstr(i, 0, msg, curses.A_CYAN)
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
