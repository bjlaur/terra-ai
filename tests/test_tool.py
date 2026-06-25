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


# --- Real API tests (skipped unless OPENROUTER_API_KEY is set) ---

HAS_REAL_API = bool(os.environ.get("OPENROUTER_API_KEY"))


@pytest.mark.skipif(not HAS_REAL_API, reason="OPENROUTER_API_KEY not set")
class TestRealAPI:
    """Tests that hit the real AI provider.

    Run with: OPENROUTER_API_KEY=... python -m pytest tests/test_tool.py::TestRealAPI -v
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
        """Test .setlocation forwards to AI for response."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = real_terra
        client.send_message(".optin")
        resp = client.send_message(".setlocation Portland, OR")
        assert len(resp) > 0
        # Response should be AI-generated, not "Your location is set to..."
        assert "your location is set" not in resp[0].lower()
