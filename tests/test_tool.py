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

    def test_send_ai_message(self, terra):
        """Test sending an AI message."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_message("hello")
        assert len(responses) > 0

    def test_send_as_different_nick(self, terra):
        """Test sending as different users."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra
        responses = client.send_as("other-user", "hello")
        assert len(responses) > 0

    def test_custom_prompt_flow(self, terra):
        """Test creating and matching a custom prompt."""
        from test_tool.chat import TerraAITestClient
        client = TerraAITestClient()
        client.terra = terra

        # Add prompt
        add_response = client.send_message(".addprompt wea sunny")
        assert "Added" in add_response[0]

        # Trigger prompt
        trigger_response = client.send_message(".wea")
        assert "sunny" in trigger_response[0].lower()

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
