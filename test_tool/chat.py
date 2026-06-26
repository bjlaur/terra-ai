#!/usr/bin/env python3
"""Irssi-like terminal client for testing TerraAI locally.

Usage:
    python test_tool/chat.py
"""

import asyncio
import curses
import sys
import os
import time

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terra_ai.bot import TerraAI
from terra_ai.config import TerraConfig
from terra_ai.database import Database, DBConfig


class FakeTrigger:
    """Mimics a SOPEL trigger object."""

    def __init__(self, nick, channel, text, is_pm=False):
        self.nick = nick
        # For PMs, sender is the nick; for channel messages, sender is the channel
        self.sender = nick if is_pm else channel
        self.group = lambda x: None
        self.match = None
        self.text = text
        self.is_pm = is_pm


class FakeBot:
    """Mimics a SOPEL bot object.

    Tracks say() (channel messages) and notice() (PMs) separately.
    In SOPEL, bot.say() sends to the channel, bot.notice() sends a
    private notice back to the user.
    """

    def __init__(self):
        self.messages = []  # say() calls — channel messages
        self.notices = []   # notice() calls — PM responses

    def say(self, msg):
        self.messages.append(msg)
        return msg

    def reply(self, msg):
        self.messages.append(msg)
        return msg

    def notice(self, nick, msg):
        # Matches SOPEL bot.notice(nick, msg) signature
        self.notices.append((nick, msg))
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
            from terra_ai.config import load_config
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

        NOTE: opt-in/opt-out gating (should_respond) is core bot
        functionality in plugin.py — NOT tested here. This method
        just routes messages the same way regardless of opt-in status.
        """
        self.bot.messages.clear()
        trigger = FakeTrigger(self.nick, self.channel, text)
        trigger_phrase = self.terra.config.bot.get("trigger_phrase", "")
        trigger_char = self.terra.prompts.trigger_char if self.terra.prompts else ""

        # Send "Thinking..." notice to noisy users before AI calls
        # (matches plugin.py behavior: bot.notice(nick, "Thinking..."))
        def notify_thinking():
            if self.terra.user.is_noisy(self.server, self.nick):
                self.bot.notice(self.nick, "Thinking...")

        # .ai command — context-free (checked first because .ai is in the
        # management command list but handle_management returns None for it)
        if text.startswith(f"{trigger_char}ai "):
            ai_text = text[len(trigger_char) + 3:]
            notify_thinking()
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
            elif text.lower().startswith(f"{trigger_char}setlocation"):
                # Hybrid command: stored locally, now forward to AI for response
                ai_text = f"{self.nick} {text}"
                ai_response = self.terra.handle_ai_message(
                    self.server, self.channel, self.nick, ai_text, include_history=True
                )
                if ai_response:
                    self.bot.say(ai_response)
            return list(self.bot.messages)

        # Trigger phrase — route to AI with history
        if text.lower().startswith(trigger_phrase.lower()):
            ai_text = text[len(trigger_phrase):].strip()
            notify_thinking()
            response = self.terra.handle_ai_message(
                self.server, self.channel, self.nick, ai_text, include_history=True
            )
            if response:
                self.bot.say(response)
            return list(self.bot.messages)

        # Unknown .command — forward to AI (matches plugin.py behavior:
        # anything starting with . that isn't a management command goes to AI)
        if text.startswith(trigger_char):
            full_text = text[len(trigger_char):].strip()
            notify_thinking()
            response = self.terra.handle_ai_message(
                self.server, self.channel, self.nick, full_text, include_history=True
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

    def send_pm(self, nick: str, text: str) -> dict:
        """Send a PM (direct message) to the bot.

        Unlike channel messages, PMs don't need a trigger phrase — everything
        in a PM is already addressed to the bot. Routing:
        - Management commands (.) handled locally
        - Unknown .commands forwarded to AI
        - Everything else → AI with history (it's a direct message)

        Returns {"say": [...], "notice": [...]} with responses and notices.
        """
        self.bot.messages.clear()
        self.bot.notices.clear()
        trigger = FakeTrigger(nick, self.channel, text, is_pm=True)

        # Send "Thinking..." notice to noisy users before AI calls
        def notify_thinking():
            if self.terra.user.is_noisy(self.server, nick):
                self.bot.notice(nick, "Thinking...")

        # .ai command — context-free (checked first)
        if text.startswith(".ai "):
            ai_text = text[4:]
            notify_thinking()
            response = self.terra.handle_ai_message(
                self.server, nick, nick, ai_text, include_history=False
            )
            if response:
                self.bot.say(response)
            return {"say": list(self.bot.messages), "notice": list(self.bot.notices)}

        # Check management commands
        if self.terra.is_management_command(text):
            response = self.terra.handle_management(self.server, nick, nick, text)
            if response:
                self.bot.say(response)
            elif text.lower().startswith(".setlocation"):
                ai_text = f"{nick} {text}"
                notify_thinking()
                ai_response = self.terra.handle_ai_message(
                    self.server, nick, nick, ai_text, include_history=True
                )
                if ai_response:
                    self.bot.say(ai_response)
            return {"say": list(self.bot.messages), "notice": list(self.bot.notices)}

        # Unknown .command — forward to AI
        if text.startswith("."):
            full_text = text[1:].strip()
            notify_thinking()
            response = self.terra.handle_ai_message(
                self.server, nick, nick, full_text, include_history=True
            )
            if response:
                self.bot.say(response)
            return {"say": list(self.bot.messages), "notice": list(self.bot.notices)}

        # Direct message (no trigger phrase needed in PMs) — AI with history
        notify_thinking()
        response = self.terra.handle_ai_message(
            self.server, nick, nick, text, include_history=True
        )
        if response:
            self.bot.say(response)
        return {"say": list(self.bot.messages), "notice": list(self.bot.notices)}


def run_interactive():
    """Run the test client in interactive mode using curses."""
    client = TerraAITestClient()

    def main(stdscr):
        botnick = client.terra.config.bot.get("bot_nick", "")
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

        # Create windows — recreated on resize
        def make_windows():
            nonlocal header, chat, input_win, height, width
            height, width = stdscr.getmaxyx()
            header = curses.newwin(1, width, 0, 0)
            chat = curses.newwin(height - 2, width, 1, 0)
            input_win = curses.newwin(1, width, height - 1, 0)
            input_win.keypad(True)
            chat.scrollok(True)

        header = None
        chat = None
        input_win = None
        make_windows()
        input_win.timeout(100)  # 100ms timeout so we can poll for async AI results

        def redraw_header():
            try:
                header.addstr(0, 0, " #terra-ai (test mode) — type 'quit' to exit ", curses.A_BOLD)
                header.refresh()
            except curses.error:
                pass

        def redraw_chat():
            try:
                max_lines = max(height - 3, 1)
                visible = messages[-max_lines:]
                chat.clear()
                for i, msg in enumerate(visible):
                    if msg.startswith("<TerraAI>"):
                        chat.addstr(i, 0, msg, curses.color_pair(1))
                    else:
                        chat.addstr(i, 0, msg)
                chat.refresh()
            except curses.error:
                pass

        messages: list[str] = []
        input_history: list[str] = []
        history_idx = -1  # -1 = new input
        cursor_pos = 0
        completions_shown = False  # True when completion hints are on the hint line

        redraw_header()
        redraw_chat()

        # Completions for Tab. In a real IRC client this completes nicks
        # from the channel member list; here the only other entity is the
        # bot. We include the trigger-phrase suffix so the user can
        # immediately type their message after completing.
        trigger_phrase = client.terra.config.bot.get("trigger_phrase", "")
        tab_completions = [trigger_phrase] if trigger_phrase else []

        def clear_hint_line():
            """Clear the completion hint line (row above input)."""
            nonlocal completions_shown
            completions_shown = False
            try:
                chat.move(height - 3, 0)
                chat.clrtoeol()
                chat.refresh()
            except curses.error:
                pass

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
                        clear_hint_line()
                        redraw_input("".join(buf))
                elif key == curses.KEY_DC:  # Delete
                    if cursor_pos < len(buf):
                        buf.pop(cursor_pos)
                        clear_hint_line()
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
                    line_start = current.lstrip()
                    at_line_start = len(current) == len(line_start)

                    # Get the word being typed (from last space to cursor)
                    word_start = current.rfind(" ") + 1
                    word = current[word_start:]

                    if at_line_start:
                        # At start of line: complete to trigger phrase
                        # e.g. "Ter<Tab>" -> "TerraAI: "
                        completions = ["TerraAI: "]
                    else:
                        # Mid-line: complete to just the bot nick
                        # e.g. "...Ter<Tab>" -> "...TerraAI "
                        completions = ["TerraAI "]

                    # Case-insensitive prefix match
                    matches = [c for c in completions
                               if c.lower().startswith(word.lower())]
                    if matches:
                        common = matches[0]
                        for m in matches[1:]:
                            while not m.lower().startswith(common.lower()):
                                common = common[:-1]
                        completed = current[:word_start] + common
                        buf = list(completed)
                        cursor_pos = len(buf)
                        redraw_input("".join(buf))
                    else:
                        curses.beep()
                elif key == curses.KEY_RESIZE:
                    # Terminal resized — recreate windows and redraw
                    make_windows()
                    redraw_header()
                    redraw_chat()
                    redraw_input("".join(buf))
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
                        clear_hint_line()
                        redraw_input("".join(buf))

        def ts():
            """Irssi-style timestamp [HH:MM]."""
            return time.strftime("[%H:%M]")

        # Async AI call state
        import threading
        pending_call = {"thread": None, "result": None, "done": False}
        notices_snapshot = [len(client.bot.notices)]

        def do_ai_call(text, is_pm):
            """Run the AI call in a thread. Stores result when done."""
            try:
                if is_pm:
                    result = client.send_pm(client.nick, text)
                else:
                    result = client.send_message(text)
                pending_call["result"] = result
            except Exception as e:
                pending_call["result"] = [f"Error: {e}"]
            finally:
                pending_call["done"] = True

        def maybe_finish_call():
            """If a background AI call finished, render its result."""
            if not pending_call["done"]:
                return
            pending_call["done"] = False
            result = pending_call["result"]
            is_pm = pending_call.get("is_pm", False)

            # send_pm returns a dict, send_message returns a list
            if isinstance(result, dict):
                responses = result["say"]
            else:
                responses = result

            # Collect any new notices appended during the call
            total_notices = len(client.bot.notices)
            new_notices = client.bot.notices[notices_snapshot[0]:total_notices]
            notices_snapshot[0] = total_notices

            # Replace "thinking" with actual response
            for r in responses:
                if is_pm:
                    messages.append(f"{ts()} [PM <TerraAI> {r}")
                else:
                    messages.append(f"{ts()} <TerraAI> {r}")

            # Show notices in channel with -!- prefix (irssi-style)
            for _, msg in new_notices:
                messages.append(f"{ts()} -!- {msg}")

            redraw_chat()

        while True:
            # Check if a background call finished
            maybe_finish_call()

            redraw_input("")
            cmd = read_line()

            if cmd is None:
                break
            cmd = cmd.rstrip("\n")

            if cmd.lower() in ("quit", "/quit", "exit"):
                break

            if not cmd.strip():
                continue

            # Parse "/msg <text>" as a PM
            is_pm = cmd.lower().startswith("/msg ")
            pm_text = cmd[5:] if is_pm else cmd

            # Add to history
            if cmd not in input_history:
                input_history.append(cmd)
            history_idx = -1

            # Display user message immediately (before blocking on AI)
            if is_pm:
                messages.append(f"{ts()} [PM] <{client.nick}> {pm_text}")
            else:
                messages.append(f"{ts()} <{client.nick}> {cmd}")
            redraw_chat()

            # Show "thinking" indicator — also send notice to noisy users
            # (matches plugin.py behavior: bot.notice(nick, "Thinking..."))
            try:
                max_lines = max(height - 3, 1)
                visible = messages[-max_lines:]
                chat.addstr(len(visible), 0, f"<{botnick}> ...", curses.color_pair(1))
                chat.refresh()
            except curses.error:
                pass
            if client.terra.user.is_noisy(client.server, client.nick):
                client.bot.notice(client.nick, "Thinking...")

            # Kick off AI call in background thread (non-blocking)
            pending_call["done"] = False
            pending_call["is_pm"] = is_pm
            t = threading.Thread(target=do_ai_call, args=(pm_text if is_pm else cmd, is_pm))
            t.daemon = True
            t.start()
            pending_call["thread"] = t

    curses.wrapper(main)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Non-interactive mode for testing
        client = TerraAITestClient()
        botnick = client.terra.config.bot.get("bot_nick", "")
        print(f"{botnick or 'TerraAI'} Test Client")
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
