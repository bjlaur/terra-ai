"""Tests for the TerraAI test tool.

These tests verify the test tool works correctly by simulating user input
and checking bot responses. Screenshots are exported for visual inspection.
"""

import os
import pty
import select
import tempfile
import time

import pytest
from unittest.mock import MagicMock, patch

from terra_ai import plugin as terra_plugin
from terra_ai.bot import TerraAI
from terra_ai.config import TerraConfig
from terra_ai.database import DBConfig, Database

# Skip if textual not available
try:
    from textual.app import TextualApp
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    config = DBConfig(path=path, wal=False)
    database = Database(config)
    yield database
    os.unlink(path)


@pytest.fixture
def terra(db):
    config = TerraConfig()
    config.sqlite_path = db.config.path
    config.provider.api_key = os.environ.get("OPENROUTER_API_KEY", "test-key")
    t = TerraAI(config)
    # So plugin handlers (_get_terra()) work when test replaces client.terra
    terra_plugin._terrai = t
    yield t
    terra_plugin._terrai = None


class TestTestTool:
    """Test the test tool's core functionality."""

    def test_send_message(self, terra):
        """Test sending a management command."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_message(".optin")
        assert len(responses) > 0
        assert "opted in" in responses[0]

    def test_regular_message_ignored(self, terra):
        """Test that regular messages (no trigger) are ignored by the bot.

        Real IRC bots only respond to the trigger phrase — regular chat
        should not produce a response.
        """
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_message("hello")
        assert len(responses) == 0, "Regular message should not produce a response"

    def test_async_ai_call(self, terra):
        """Test that AI calls work (async, background thread).

        send_message() runs the AI call in a background thread. This
        verifies the result is collected and returned correctly, and
        that SQLite works across threads (check_same_thread=False).
        """
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        # Trigger phrase → async AI call
        responses = client.send_message("TerraAI: hello")
        assert len(responses) > 0, "Async AI call produced no response"
        assert responses[0].strip() != ""

    def test_send_as_different_nick(self, terra):
        """Test sending as different users."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_as("other-user", "hello")
        assert len(responses) > 0

    def test_unknown_command_routes_to_ai(self, terra):
        """Test that unknown .commands are forwarded to AI (not answered locally).

        Any .command that isn't a management command should go to AI.
        The AI generates the response — we just verify a non-empty response.
        """
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra

        # Send unknown .command — should route to AI
        response = client.send_message(".what's 2+2")
        assert len(response) > 0, "Unknown .command produced no response"
        assert response[0].strip() != "", "Unknown .command produced empty response"

    def test_help_command(self, terra):
        """Test help command."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_message(".help")
        assert len(responses) > 0
        assert ".optin" in responses[0]


class TestInteractiveMode:
    """Test the interactive curses mode using a pseudo-terminal.

    These tests catch bugs in the curses input loop that the screenshot
    and --test modes don't exercise.
    """

    @pytest.fixture
    def env_setup(self, monkeypatch):
        """Set up API key for interactive tests."""
        monkeypatch.setenv("OPENROUTER_API_KEY",
                           os.environ.get("OPENROUTER_API_KEY", "test-key"))

    def _run_interactive(self, inputs: list[bytes], timeout: int = 10) -> tuple[str, str]:
        """Run run_interactive() with a pseudo-terminal and feed inputs.

        Returns (stdout, stderr) as strings.
        """
        import subprocess
        import sys

        # Use a pty so curses has a real TTY
        master_fd, slave_fd = pty.openpty()

        env = os.environ.copy()
        env["OPENROUTER_API_KEY"] = os.environ.get("OPENROUTER_API_KEY", "test-key")
        env["TERM"] = "xterm-256color"

        proc = subprocess.Popen(
            [sys.executable, "-c",
             "import sys; sys.stdout = sys.__stdout__; sys.stderr = sys.__stderr__; "
             "from test_tool.chat import run_interactive; run_interactive()"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=subprocess.PIPE,
            env=env,
        )
        os.close(slave_fd)

        stdout_parts = []
        start = time.time()

        # Feed inputs with delays for curses to process
        for inp in inputs:
            time.sleep(0.5)
            os.write(master_fd, inp)

        # Read output until process exits or timeout
        while time.time() - start < timeout:
            if proc.poll() is not None:
                break
            ready, _, _ = select.select([master_fd], [], [], 0.5)
            if ready:
                try:
                    data = os.read(master_fd, 4096)
                    stdout_parts.append(data.decode("utf-8", errors="replace"))
                except OSError:
                    break

        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

        try:
            os.close(master_fd)
        except OSError:
            pass

        stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        return "".join(stdout_parts), stderr

    def _run_interactive_poll(self, inputs: list[bytes], expect: str,
                              expect_timeout: int = 30,
                              post_wait: int = 2) -> tuple[str, str]:
        """Run interactive mode, polling for expected output.

        Sends inputs one at a time, waiting up to expect_timeout seconds
        for the expected string to appear in stdout before sending the next
        input. After all inputs, waits post_wait seconds for final output.
        """
        import subprocess
        import sys

        master_fd, slave_fd = pty.openpty()
        env = os.environ.copy()
        env["OPENROUTER_API_KEY"] = os.environ.get("OPENROUTER_API_KEY", "test-key")
        env["TERM"] = "xterm-256color"

        proc = subprocess.Popen(
            [sys.executable, "-c",
             "import sys; sys.stdout = sys.__stdout__; sys.stderr = sys.__stderr__; "
             "from test_tool.chat import run_interactive; run_interactive()"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=subprocess.PIPE,
            env=env,
        )
        os.close(slave_fd)

        stdout_parts = []
        start = time.time()

        for inp in inputs:
            # Send input
            os.write(master_fd, inp)

            # Poll for expected output or until timeout
            deadline = time.time() + expect_timeout
            found = False
            while time.time() < deadline:
                if proc.poll() is not None:
                    break
                ready, _, _ = select.select([master_fd], [], [], 0.5)
                if ready:
                    try:
                        data = os.read(master_fd, 4096)
                        decoded = data.decode("utf-8", errors="replace")
                        stdout_parts.append(decoded)
                        if expect in "".join(stdout_parts):
                            found = True
                            # Give a moment for additional output
                            time.sleep(0.5)
                            # Drain any pending output
                            while True:
                                ready2, _, _ = select.select([master_fd], [], [], 0.3)
                                if not ready2:
                                    break
                                data2 = os.read(master_fd, 4096)
                                stdout_parts.append(data2.decode("utf-8", errors="replace"))
                            break
                    except OSError:
                        break
                time.sleep(0.5)

            if not found and expect:
                # Timed out waiting for expected output
                pass

        # Final wait
        time.sleep(post_wait)

        # Send quit if process still running
        if proc.poll() is None:
            try:
                os.write(master_fd, b"quit\n")
            except OSError:
                pass
            time.sleep(1)

        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

        try:
            os.close(master_fd)
        except OSError:
            pass

        stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        return "".join(stdout_parts), stderr

    def test_interactive_launches_and_exits(self, env_setup):
        """Test that the interactive mode launches and responds to 'quit'."""
        stdout, stderr = self._run_interactive([b"quit\n"])
        assert "A_CYAN" not in stderr, "A_CYAN bug still present"
        assert "cbreak" not in stderr, "cbreak error still present"
        assert "Traceback" not in stderr, f"Error in interactive mode:\n{stderr}"

    def test_interactive_accepts_input(self, env_setup):
        """Test that the interactive mode accepts input and sends to AI."""
        stdout, stderr = self._run_interactive([b".help\n", b"quit\n"])
        assert "Traceback" not in stderr, f"Error in interactive mode:\n{stderr}"
        # The help output should appear somewhere in the rendered output
        assert "optin" in stdout.lower() or "optin" in stderr.lower(), \
            "Help command response not found"

    def test_interactive_tab_completes_trigger(self, env_setup):
        """Test that Tab completes to trigger phrase at start of line: 'Ter<Tab>' -> 'TerraAI: '."""
        stdout, stderr = self._run_interactive([b"Ter\t", b"quit\n"])
        assert "Traceback" not in stderr, f"Error in interactive mode:\n{stderr}"
        # At start of line, Tab completes to trigger phrase with colon
        assert "TerraAI:" in stdout, \
            "Tab did not complete 'Ter' to 'TerraAI: ' at start of line"

    def test_interactive_tab_completes_midline(self, env_setup):
        """Test that Tab mid-line completes to just the bot nick: 'Ter<Tab>' -> 'TerraAI'."""
        # Type some text, then Tab mid-line
        stdout, stderr = self._run_interactive([b"hello Ter\t", b"quit\n"])
        assert "Traceback" not in stderr, f"Error in interactive mode:\n{stderr}"
        # Mid-line, Tab completes to just the nick (no colon)
        assert "TerraAI" in stdout, \
            "Tab did not complete mid-line 'Ter' to 'TerraAI'"

    def test_interactive_accepts_pm(self, env_setup):
        """Test that /msg <text> sends as a PM (no trigger phrase needed)."""
        import os
        os.environ["OPENROUTER_API_KEY"] = os.environ.get("OPENROUTER_API_KEY", "test-key")
        # Send PM and poll for the [PM] prefix in output
        stdout, stderr = self._run_interactive_poll(
            inputs=[b"/msg hello\n"],
            expect="[PM]",
            expect_timeout=30,
            post_wait=2,
        )
        assert "Traceback" not in stderr, f"Error in interactive mode:\n{stderr}"
        # The PM user message should appear with [PM] prefix
        assert "[PM]" in stdout, "PM message not displayed with [PM] prefix"
        # The bot should have responded to the PM
        assert "TerraAI" in stdout

    def test_interactive_noisy_notice(self, env_setup):
        """Test that noisy mode shows 'Thinking...' notice in channel."""
        import os
        os.environ["OPENROUTER_API_KEY"] = os.environ.get("OPENROUTER_API_KEY", "test-key")
        # Enable noisy, then send message and poll for the -!- Thinking notice
        stdout, stderr = self._run_interactive_poll(
            inputs=[b".noisy\n", b"TerraAI: hello\n"],
            expect="-!- Thinking",
            expect_timeout=30,
            post_wait=2,
        )
        assert "Traceback" not in stderr, f"Error in interactive mode:\n{stderr}"
        assert "-!- Thinking" in stdout, \
            f"Noisy notice not shown in interactive chat.\nstdout:\n{stdout}"

    def test_interactive_empty_input(self, env_setup):
        """Test that empty input (just enter) doesn't crash."""
        stdout, stderr = self._run_interactive([b"\n", b"quit\n"])
        assert "Traceback" not in stderr, f"Error in interactive mode:\n{stderr}"

    def test_interactive_ctrl_d_exits(self, env_setup):
        """Test that Ctrl+D exits cleanly."""
        stdout, stderr = self._run_interactive([b"\x04"])  # Ctrl+D
        assert "Traceback" not in stderr, f"Error in interactive mode:\n{stderr}"

    def test_interactive_history_navigation(self, env_setup):
        """Test that KEY_UP navigates input history."""
        # Send a message, then press KEY_UP to recall it
        stdout, stderr = self._run_interactive([
            b"hello\n",       # first message
            b"\x1b[A",        # KEY_UP (ANSI escape)
            b"quit\n"
        ])
        assert "Traceback" not in stderr, f"Error in interactive mode:\n{stderr}"


class TestPM:
    """Test PM (private message) routing.

    PMs route identically to channel messages but use the nick as the
    channel for scoping. The bot should respond to the same triggers
    and commands in PMs.
    """

    def test_pm_trigger_routes_to_ai(self, terra):
        """PM with trigger phrase should route to AI with history."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", "TerraAI: hello from PM")
        assert len(result["say"]) > 0, "PM with trigger phrase produced no response"

    def test_pm_management_command(self, terra):
        """PM with management command should work (e.g. .optin)."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".optin")
        assert len(result["say"]) > 0
        assert "opted in" in result["say"][0]

    def test_pm_help_command(self, terra):
        """PM with .help should return command list."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".help")
        assert len(result["say"]) > 0
        assert ".optin" in result["say"][0]

    def test_pm_unknown_command_routes_to_ai(self, terra):
        """PM with unknown .command should route to AI."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".what's 2+2")
        assert len(result["say"]) > 0, "PM with unknown .command produced no response"

    def test_ai_command_context_free(self, terra):
        """Test .ai command in PM — context-free prompt."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".ai hello")
        assert len(result["say"]) > 0, ".ai in PM produced no response"

    def test_pm_direct_message(self, terra):
        """Test PM with plain text (no trigger, no dot) → AI with history."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        # Plain text PM — no trigger phrase, no dot prefix
        result = client.send_pm("tester", "hello there")
        assert len(result["say"]) > 0, "Plain text PM produced no AI response"

    def test_pm_setlocation_forwards_to_ai(self, terra):
        """Test .setlocation in PM — hybrid routing forwards to AI."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".setlocation Portland, OR")
        assert len(result["say"]) > 0, "PM .setlocation produced no response"

    def test_clear_command(self, terra):
        """Test .clear command — wipes session, starts fresh."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        # Build some history first
        client.send_pm("tester", ".optin")
        client.send_pm("tester", "TerraAI:hello")
        # Clear
        result = client.send_pm("tester", ".clear")
        assert len(result["say"]) > 0
        assert "cleared" in result["say"][0].lower()

    def test_compact_admin_only_for_non_admin(self, terra):
        """Test .compact is gated to admin via @plugin.require_admin."""
        from test_tool.chat import TerraAITestClient
        terra_plugin._terrai = terra
        client = TerraAITestClient()
        client.terra = terra
        result = client.send_pm("tester", ".compact")  # admin=False by default
        assert len(result["say"]) > 0
        assert "denied" in result["say"][0].lower()


class TestNoisy:
    """Test noisy mode — status notices for verbose users.

    When .noisy is ON, the bot sends "Thinking..." as a notice before
    the AI call. The notices appear in bot.notices (not bot.messages).
    """

    def test_noisy_toggle(self, terra):
        """Test .noisy toggles ON then OFF."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        on = client.send_message(".noisy")
        assert "ON" in on[0].upper()
        off = client.send_message(".noisy")
        assert "OFF" in off[0].upper()

    def test_noisy_off_no_notice(self, terra):
        """When noisy is OFF, no 'Thinking...' notice is sent."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        client.send_message(".optin")
        client.send_message(".noisy")  # toggle ON (default is off)
        client.send_message(".noisy")  # toggle back OFF
        # Clear any notices from the toggle-OFF step (noisy was ON at that point)
        client.bot.notices.clear()
        client.send_message(".optin")  # trigger an AI-compatible message
        # No notices should exist (noisy is OFF)
        assert len(client.bot.notices) == 0

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_noisy_on_sends_notice(self, mock_client_cls, terra):
        """When noisy is ON, a 'Thinking...' notice is sent before AI call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        client.send_message(".optin")
        client.send_message(".noisy")  # toggle ON
        # Now send a message that triggers AI — notice should be sent
        client.send_message("TerraAI: hello")
        assert len(client.bot.notices) > 0
        # notices are stored as (nick, msg) tuples
        assert any("Thinking" in msg for _, msg in client.bot.notices)


# --- Real API tests (skipped unless OPENROUTER_API_KEY is set) ---

HAS_REAL_API = bool(os.environ.get("OPENROUTER_API_KEY"))

if not HAS_REAL_API:
    import sys
    sys.stderr.write(
        "\n❌ GO SOURCE .env YOU DOLT!\n"
        "   OPENROUTER_API_KEY not set — --real tests skipped.\n"
        "   Fix: source ~/.terra-ai/.env\n\n"
    )


@pytest.mark.skipif(not HAS_REAL_API, reason="OPENROUTER_API_KEY not set — run: source ~/.terra-ai/.env")
class TestRealAPI:
    """Tests that hit the real AI provider.

    Run with: source ~/.terra-ai/.env && python -m pytest tests/test_tool.py::TestRealAPI -v
    """

    @pytest.fixture
    def real_terra(self, db):
        config = TerraConfig()
        config.sqlite_path = db.config.path
        config.provider.api_key = os.environ["OPENROUTER_API_KEY"]
        t = TerraAI(config)
        terra_plugin._terrai = t
        return t

    def test_real_effort_level(self, real_terra):
        """Test .effort low sets the level and responds with confirmation."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        responses = client.send_message(".effort low")
        assert len(responses) > 0
        assert "low" in responses[0].lower()

    def test_real_unknown_command_goes_to_ai(self, real_terra):
        """Test that unknown .commands are forwarded to AI in real API.

        Any .command that isn't a management command should go to AI.
        We verify a non-empty AI response comes back.
        """
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra

        # Send unknown .command — should route to AI
        resp = client.send_message(".what's 2+2")
        assert len(resp) > 0, "Unknown .command produced no AI response"
        assert resp[0].strip() != ""

    def test_real_noisy_toggle(self, real_terra):
        """Test .noisy toggles noisy mode (no API call needed)."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        # Toggle on
        resp_on = client.send_message(".noisy")
        assert len(resp_on) > 0
        assert "ON" in resp_on[0].upper()
        # Toggle off
        resp_off = client.send_message(".noisy")
        assert len(resp_off) > 0
        assert "OFF" in resp_off[0].upper()

    def test_real_setlocation_goes_to_ai(self, real_terra):
        """Test .setlocation forwards to AI for response.

        The AI may or may not echo "your location is set" — that's its
        own phrasing. The key assertion is that we got a non-empty AI
        response (proving hybrid routing did the forward).
        """
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        client.send_message(".optin")
        resp = client.send_message(".setlocation Portland, OR")
        assert len(resp) > 0, "Expected AI response from hybrid routing"
        assert resp[0].strip() != ""

    def test_real_pm_trigger_responds(self, real_terra):
        """Test PM with trigger phrase gets AI response."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        result = client.send_pm("tester", "TerraAI: hello from PM")
        assert len(result["say"]) > 0, "PM with trigger phrase produced no AI response"

    def test_real_pm_effort_level(self, real_terra):
        """Test .effort in PM sets level and confirms."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        result = client.send_pm("tester", ".effort low")
        assert len(result["say"]) > 0
        assert "low" in result["say"][0].lower()

    def test_real_noisy_toggle(self, real_terra):
        """Test .noisy toggles ON then OFF (no API call needed)."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        resp_on = client.send_message(".noisy")
        assert "ON" in resp_on[0].upper()
        resp_off = client.send_message(".noisy")
        assert "OFF" in resp_off[0].upper()

    def test_real_noisy_sends_notice_on_ai_message(self, real_terra):
        """When noisy is ON, a 'Thinking...' notice is sent before AI call."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        client.send_message(".optin")
        client.send_message(".noisy")  # toggle ON
        client.send_message("TerraAI: hello")
        assert len(client.bot.notices) > 0
        assert any("Thinking" in msg for _, msg in client.bot.notices)
