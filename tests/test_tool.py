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

from terraai.bot import TerraAI
from terraai.config import TerraConfig
from terraai.database import DBConfig, Database

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
    return t


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

    def test_optout_blocks_response(self, terra):
        """Test that opted-out users get no AI response.

        This matches plugin.py behavior: should_respond() returns False
        for opted-out users, so the bot ignores their messages.
        Management commands still work so they can .optin again.
        """
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        # Opt in first (creates user in DB as opted-in)
        client.send_message(".optin")
        # Opt out
        client.send_message(".optout")
        # Regular message should be ignored
        responses = client.send_message("hello")
        assert len(responses) == 0, "Opted-out user should get no response"
        # Trigger phrase also ignored
        responses = client.send_message("TerraAI: hello")
        assert len(responses) == 0, "Opted-out user should get no response to trigger"
        # Management command still works
        responses = client.send_message(".optin")
        assert len(responses) > 0, "Management commands should still work when opted out"

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
        """Test that Tab completes to trigger phrase: 'Ter<Tab>' -> 'TerraAI: '."""
        stdout, stderr = self._run_interactive([b"Ter\t", b"quit\n"])
        assert "Traceback" not in stderr, f"Error in interactive mode:\n{stderr}"
        # After Tab, the input line should contain the full trigger phrase
        assert "TerraAI:" in stdout, \
            "Tab did not complete 'Ter' to 'TerraAI: ' in the input line"


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
        """Test .compact is gated to admin — non-admin gets denied."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        # tester is not in admin_nicks
        result = client.send_pm("tester", ".compact")
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
        client.send_message(".noisy")  # toggle OFF (default is off, so this toggles ON)
        client.send_message(".noisy")  # toggle back OFF
        client.send_message(".optin")  # trigger an AI-compatible message
        # No notices should exist
        assert len(client.bot.notices) == 0

    def test_noisy_on_sends_notice(self, terra):
        """When noisy is ON, a 'Thinking...' notice is sent before AI call."""
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
        return TerraAI(config)

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
