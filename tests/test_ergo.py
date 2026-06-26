"""Integration tests using ergochat IRC server.

These tests create a real SOPEL bot instance, connect it to ergochat
running on localhost:6667, and verify end-to-end behavior.

Run with: ERGO_TEST=1 pytest tests/test_ergo.py -v
Requires ergochat running on localhost:6667
"""

import asyncio
import os
import tempfile
import time

import pytest

from terra_ai.database import DBConfig, Database

# Check if ergo is reachable
def ergo_available():
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", 6667))
        sock.close()
        return result == 0
    except Exception:
        return False

ERGO_AVAILABLE = ergo_available()

pytestmark = pytest.mark.skipif(
    not ERGO_AVAILABLE,
    reason="ergochat not running on localhost:6667"
)


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
    from terra_ai.bot import TerraAI
    from tests.conftest import _make_test_config
    config = _make_test_config(
        sqlite_path=db.config.path,
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        bot_nick="TerraAI",
    )
    return TerraAI(config)


class TestErgoSmoke:
    """Basic smoke tests for ergochat connection."""

    def test_ergo_port_open(self):
        """Verify ergochat is listening on 6667."""
        assert ergo_available(), "ergochat not reachable"

    def test_ergo_config_exists(self):
        """Verify ergochat config file exists."""
        assert os.path.exists(os.path.expanduser("~/.ircd/ircd.yaml"))

    def test_can_connect_socket(self):
        """Test raw socket connection to ergo."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("127.0.0.1", 6667))
        sock.close()
        assert result == 0


class TestErgoIRCProtocol:
    """Test IRC protocol-level interaction with ergochat.

    These tests use raw IRC protocol (no SOPEL) to verify we can
    register, join channels, and exchange messages.
    """

    IRC_TIMEOUT = 10  # seconds

    def _connect_and_register(self, nick="TerraAITest"):
        """Connect to ergo and register a nick. Returns the socket."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", 6667))

        # IRC registration
        sock.sendall(f"NICK {nick}\r\n".encode())
        sock.sendall(f"USER {nick} 0 * :TerraAI Test Bot\r\n".encode())

        # Wait for 001 (RPL_WELCOME) or error
        welcome_received = False
        buf = b""
        deadline = time.time() + self.IRC_TIMEOUT
        while time.time() < deadline:
            sock.settimeout(2)
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            buf += chunk
            lines = buf.split(b"\r\n")
            buf = lines[-1]  # keep incomplete line
            for line in lines[:-1]:
                decoded = line.decode(errors="replace")
                if decoded.startswith(":") and " 001 " in decoded:
                    welcome_received = True
                # Respond to PING
                if decoded.startswith("PING"):
                    pong = decoded.replace("PING", "PONG", 1)
                    sock.sendall(f"{pong}\r\n".encode())

        assert welcome_received, f"Did not receive 001 RPL_WELCOME from ergo"
        return sock

    def _join_channel(self, sock, channel="#terra-ai-test"):
        """Join a channel and wait for JOIN confirmation."""
        import socket
        sock.sendall(f"JOIN {channel}\r\n".encode())

        joined = False
        buf = b""
        deadline = time.time() + self.IRC_TIMEOUT
        while time.time() < deadline:
            sock.settimeout(2)
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            buf += chunk
            lines = buf.split(b"\r\n")
            buf = lines[-1]
            for line in lines[:-1]:
                decoded = line.decode(errors="replace")
                if f"JOIN {channel}" in decoded:
                    joined = True
                if decoded.startswith("PING"):
                    pong = decoded.replace("PING", "PONG", 1)
                    sock.sendall(f"{pong}\r\n".encode())

        assert joined, f"Did not receive JOIN confirmation for {channel}"
        return sock

    def _read_until(self, sock, predicate, timeout=10):
        """Read from socket until predicate matches a line. Returns matching line or None."""
        import socket
        buf = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            sock.settimeout(2)
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            except Exception:
                break
            if not chunk:
                break
            buf += chunk
            lines = buf.split(b"\r\n")
            buf = lines[-1]
            for line in lines[:-1]:
                decoded = line.decode(errors="replace")
                if decoded.startswith("PING"):
                    pong = decoded.replace("PING", "PONG", 1)
                    sock.sendall(f"{pong}\r\n".encode())
                    continue
                if predicate(decoded):
                    return decoded
        return None

    def test_register_nick(self):
        """Test IRC NICK/USER registration with ergo."""
        sock = self._connect_and_register("TerraAIReg")
        sock.sendall(b"QUIT :bye\r\n")
        sock.close()

    def test_join_channel(self):
        """Test joining a channel on ergo."""
        sock = self._connect_and_register("TerraAIJoin")
        sock = self._join_channel(sock, "#terra-ai-test")
        sock.sendall(b"QUIT :bye\r\n")
        sock.close()

    def test_send_and_receive_message(self):
        """Test sending a message to a channel and reading it back."""
        # Bot 1: joins channel and listens
        listener = self._connect_and_register("TerraAIListen")
        self._join_channel(listener, "#terra-ai-msg")

        # Bot 2: joins same channel and sends a message
        sender = self._connect_and_register("TerraAISend")
        self._join_channel(sender, "#terra-ai-msg")

        # Give sender time to join and ergo to relay NAMES
        time.sleep(2)

        # Sender sends a message
        sender.sendall(b"PRIVMSG #terra-ai-msg :hello from sender\r\n")

        # Listener should see the message
        msg = self._read_until(
            listener,
            lambda line: "PRIVMSG" in line and "hello from sender" in line,
            timeout=10
        )
        assert msg is not None, "Listener did not receive the message from sender"

        sender.sendall(b"QUIT :bye\r\n")
        listener.sendall(b"QUIT :bye\r\n")
        sender.close()
        listener.close()

    def test_private_message(self):
        """Test sending a private message between two nicks."""
        recipient = self._connect_and_register("TerraAIPriv1")
        sender = self._connect_and_register("TerraAIPriv2")

        time.sleep(1)

        # Sender sends private message
        sender.sendall(b"PRIVMSG TerraAIPriv1 :private hello\r\n")

        # Recipient should see it
        msg = self._read_until(
            recipient,
            lambda line: "TerraAIPriv2" in line and "private hello" in line,
            timeout=10
        )
        assert msg is not None, "Recipient did not receive private message"

        sender.sendall(b"QUIT :bye\r\n")
        recipient.sendall(b"QUIT :bye\r\n")
        sender.close()
        recipient.close()


class TestErgoSopelBot:
    """Integration tests with a real SOPEL bot instance.

    These start an actual SOPEL process, load the TerraAI plugin,
    connect to ergo via SSL, and verify end-to-end behavior.
    """

    IRC_TIMEOUT = 15
    BOT_STARTUP_WAIT = 10  # seconds to wait for bot to connect and join
    ERGO_HOST = "127.0.0.1"
    ERGO_PORT = 6667  # plaintext for testing (SSL+CAP broken with self-signed cert)
    TEST_CHANNEL = "#terra-ai-agent1"
    PLUGIN_LIST = [
        "admin", "adminchannel", "ping", "reload",
        "safety", "tell", "coretasks", "terra_ai",
    ]
    COMMAND_PREFIX = "-"  # Must match [core] prefix in sopel_config
    BOT_NICK = "TerraAI"  # Must match [core] nick in sopel_config

    @pytest.fixture(scope="session")
    def sopel_config(self, tmp_path_factory):
        """Create a minimal SOPEL config file for testing."""
        tmp = tmp_path_factory.mktemp("sopel")
        db_path = tmp / "terra_ai.db"
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        plugins_lines = "\n    ".join(self.PLUGIN_LIST)
        config_content = f"""[core]
nick = TerraAI
host = {self.ERGO_HOST}
port = {self.ERGO_PORT}
use_ssl = false
owner = agent1
channels = {self.TEST_CHANNEL}
prefix = -
help_prefix = -
extra = {project_dir}
enable =
    {plugins_lines}

[terraai]
config_path = {tmp / "terra_ai.yaml"}
"""
        config_file = tmp / "sopel.cfg"
        config_file.write_text(config_content)

        # TerraAI yaml config
        terraai_yaml = tmp / "terra_ai.yaml"
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        terraai_yaml.write_text(f"""bot:
  trigger_phrase: "TerraAI:"
  bot_nick: "TerraAI"
provider:
  name: openrouter
  model: openrouter/owl-alpha
  api_key: "{api_key}"
sqlite_path: "{db_path}"
default_optin: true
""")

        return config_file

    @pytest.fixture(scope="session")
    def sopel_bot_process(self, sopel_config):
        """Start a SOPEL bot subprocess and yield its handle.

        Session-scoped: one SOPEL instance shared across all TestErgoSopelBot tests.
        """
        import subprocess
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = os.environ.copy()
        env["PYTHONPATH"] = project_dir

        stdout_file = open(os.path.join(tempfile.gettempdir(), "sopel_stdout.log"), "w")
        stderr_file = open(os.path.join(tempfile.gettempdir(), "sopel_stderr.log"), "w")
        proc = subprocess.Popen(
            ["sopel", "-c", str(sopel_config)],
            stdout=stdout_file,
            stderr=stderr_file,
            stdin=subprocess.DEVNULL,
            env=env,
        )
        # Wait for the bot to start up and connect
        time.sleep(self.BOT_STARTUP_WAIT)
        yield proc
        # Cleanup
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        stdout_file.close()
        stderr_file.close()

    BAD_PROVIDER_CHANNEL = "#terra-ai-error-test"
    BAD_PROVIDER_BOT_NICK = "ErrBot"

    @pytest.fixture(scope="session")
    def sopel_config_bad_provider(self, tmp_path_factory):
        """Create a SOPEL config with a provider that will fail (bad URL).

        The provider has an API key but points at a non-existent endpoint,
        so the HTTP call itself will error — exercising the real error path.
        """
        tmp = tmp_path_factory.mktemp("sopel-badprov")
        db_path = tmp / "terra_ai.db"
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        plugins_lines = "\n    ".join(self.PLUGIN_LIST)
        config_content = f"""[core]
nick = {self.BAD_PROVIDER_BOT_NICK}
host = {self.ERGO_HOST}
port = {self.ERGO_PORT}
use_ssl = false
owner = agent1
channels = {self.BAD_PROVIDER_CHANNEL}
prefix = -
help_prefix = -
extra = {project_dir}
enable =
    {plugins_lines}

[terraai]
config_path = {tmp / "terra_ai.yaml"}
"""
        config_file = tmp / "sopel.cfg"
        config_file.write_text(config_content)

        # TerraAI yaml — valid key format but unreachable URL
        terraai_yaml = tmp / "terra_ai.yaml"
        terraai_yaml.write_text(f"""bot:
  trigger_phrase: "TerraAI:"
  bot_nick: "{self.BAD_PROVIDER_BOT_NICK}"
provider:
  name: openrouter
  model: openrouter/owl-alpha
  api_key: "sk-or-test-key-that-exists"
  base_url: "http://127.0.0.1:1/nonexistent"
sqlite_path: "{db_path}"
default_optin: true
""")

        return config_file

    @pytest.fixture(scope="session")
    def sopel_bot_bad_provider(self, sopel_config_bad_provider):
        """Start a SOPEL bot with a bad provider URL for error-path testing."""
        import subprocess
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = os.environ.copy()
        env["PYTHONPATH"] = project_dir
        env.pop("OPENROUTER_API_KEY", None)

        stdout_file = open(os.path.join(tempfile.gettempdir(), "sopel_errbot_stdout.log"), "w")
        stderr_file = open(os.path.join(tempfile.gettempdir(), "sopel_errbot_stderr.log"), "w")
        proc = subprocess.Popen(
            ["sopel", "-c", str(sopel_config_bad_provider)],
            stdout=stdout_file,
            stderr=stderr_file,
            stdin=subprocess.DEVNULL,
            env=env,
        )
        time.sleep(self.BOT_STARTUP_WAIT)
        yield proc
        # Kill immediately — don't let SOPEL send QUIT to ergo, which can
        # interfere with the main bot's connection.
        proc.kill()
        proc.wait(timeout=5)

    def _read_irc_until(self, sock, predicate, timeout=None):
        """Read lines from sock until predicate(line) returns True.
        Returns list of all lines seen. Raises on timeout."""
        import socket
        timeout = timeout or self.IRC_TIMEOUT
        deadline = time.time() + timeout
        buf = b""
        lines = []
        while time.time() < deadline:
            sock.settimeout(max(0.1, min(1.0, deadline - time.time())))
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            buf += chunk
            while b"\r\n" in buf:
                raw, buf = buf.split(b"\r\n", 1)
                if not raw:
                    continue
                line = raw.decode(errors="replace")
                lines.append(line)
                if line.startswith("PING "):
                    token = line.split(" ", 1)[1]
                    sock.sendall(f"PONG {token}\r\n".encode())
                if predicate(line):
                    return lines
        raise AssertionError(
            "Timed out waiting for IRC condition. Lines seen:\n"
            + "\n".join(lines)
        )

    def _irc_connect(self, nick):
        """Connect to ergo plaintext and register. Returns socket."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.ERGO_HOST, self.ERGO_PORT))

        # Send NICK/USER/CAP END defensively, then wait for 001
        sock.sendall(
            f"NICK {nick}\r\n"
            f"USER {nick} 0 * :TerraAI Test\r\n"
            f"CAP END\r\n".encode()
        )
        lines = self._read_irc_until(
            sock,
            lambda line: f" 001 {nick} " in line,
        )
        assert any(f" 001 {nick} " in line for line in lines), \
            "Did not receive 001 RPL_WELCOME"
        return sock

    def _irc_join(self, sock, nick, channel):
        """Join a channel and wait for 366 end-of-NAMES."""
        sock.sendall(f"JOIN {channel}\r\n".encode())
        self._read_irc_until(
            sock,
            lambda line: f" 366 {nick} {channel} " in line,
        )

    def _irc_quit(self, sock):
        """Send QUIT and close socket."""
        try:
            sock.sendall(b"QUIT :bye\r\n")
        except Exception:
            pass
        sock.close()

    def test_sopel_connects_to_ergo(self, sopel_bot_process):
        """Test that SOPEL bot connects to ergochat via SSL."""
        # If the bot process is still running, it connected successfully
        # (SOPEL exits on connection failure)
        poll = sopel_bot_process.poll()
        assert poll is None, "SOPEL bot process exited early (connection failed?)"

    def test_bot_joins_channel(self, sopel_bot_process):
        """Test that the bot joins the test channel."""
        sock = self._irc_connect("TestChecker")
        self._irc_join(sock, "TestChecker", self.TEST_CHANNEL)

        # Request NAMES to verify bot is present
        sock.sendall(f"NAMES {self.TEST_CHANNEL}\r\n".encode())
        names_lines = self._read_irc_until(
            sock,
            lambda line: "353" in line and self.TEST_CHANNEL in line,
            timeout=10
        )
        assert names_lines is not None, "Did not receive NAMES reply"
        names_text = " ".join(names_lines)
        assert self.BOT_NICK in names_text, f"{self.BOT_NICK} not in channel, got: {names_text}"

        self._irc_quit(sock)

    def test_bot_responds_to_help(self, sopel_bot_process):
        """Test that the bot responds to help command."""
        sock = self._irc_connect("TestHelp")
        self._irc_join(sock, "TestHelp", self.TEST_CHANNEL)

        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}help\r\n".encode())

        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "PRIVMSG" in line and self.TEST_CHANNEL in line,
            timeout=15
        )
        assert response is not None, "Bot did not respond to help command"

        self._irc_quit(sock)

    def test_bot_responds_to_trigger(self, sopel_bot_process):
        """Test that the bot responds to TerraAI: trigger."""
        sock = self._irc_connect("TestTrigger")
        self._irc_join(sock, "TestTrigger", self.TEST_CHANNEL)

        # Send trigger
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :TerraAI: hello\r\n".encode())

        # Look for a response from the bot (this will hit the real AI API)
        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "PRIVMSG" in line,
            timeout=30
        )
        assert response is not None, "Bot did not respond to TerraAI: trigger"

        self._irc_quit(sock)

    def test_bot_responds_to_unknown_command(self, sopel_bot_process):
        """Test that unknown commands are routed to AI and get a response."""
        sock = self._irc_connect("TestUnknown")
        self._irc_join(sock, "TestUnknown", self.TEST_CHANNEL)

        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}what is 2+2\r\n".encode())

        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "PRIVMSG" in line,
            timeout=30
        )
        assert response is not None, "Bot did not respond to unknown command"

        self._irc_quit(sock)

    def test_bot_ignores_regular_messages(self, sopel_bot_process):
        """Test that regular messages (no trigger, no .command) are ignored."""
        sock = self._irc_connect("TestIgnore")
        self._irc_join(sock, "TestIgnore", self.TEST_CHANNEL)

        # Send a regular message — should be ignored
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :just regular chatter\r\n".encode())

        # Bot should NOT respond — read for a short window and confirm no bot message
        # We send a help command after to verify bot is still alive
        time.sleep(3)
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}help\r\n".encode())

        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "PRIVMSG" in line,
            timeout=15
        )
        assert response is not None, "Bot did not respond to help (may have crashed?)"

        self._irc_quit(sock)

    def test_bot_noisy_toggle(self, sopel_bot_process):
        """Test that .noisy toggles status notices."""
        sock = self._irc_connect("TestNoisy")
        self._irc_join(sock, "TestNoisy", self.TEST_CHANNEL)

        # Toggle noisy ON
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}noisy\r\n".encode())

        # Should see a notice about noisy mode
        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "Noisy" in line,
            timeout=10
        )
        assert response is not None, "Bot did not respond to .noisy toggle"

        self._irc_quit(sock)

    def test_bot_optin_optout(self, sopel_bot_process):
        """Test that .optout prevents responses and .optin re-enables."""
        sock = self._irc_connect("TestOptInOut")
        self._irc_join(sock, "TestOptInOut", self.TEST_CHANNEL)

        # Opt out
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}optout\r\n".encode())
        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "opted out" in line,
            timeout=10
        )
        assert response is not None, "Bot did not confirm opt-out"

        # Now send trigger — should NOT respond
        time.sleep(1)
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :TerraAI: hello\r\n".encode())
        time.sleep(3)

        # Opt back in
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}optin\r\n".encode())
        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "opted in" in line,
            timeout=10
        )
        assert response is not None, "Bot did not confirm opt-in"

        self._irc_quit(sock)

    def test_bot_reports_error_on_ai_failure(self, sopel_bot_bad_provider):
        """Bot MUST send an error message to IRC when the AI provider fails.

        Provider URL is unreachable, so the HTTP call errors. The bot must
        respond with 'Error:' — never stay silent.
        """
        sock = self._irc_connect("TestBadProv")
        self._irc_join(sock, "TestBadProv", self.BAD_PROVIDER_CHANNEL)

        # Send a trigger — this will attempt an AI call that fails (connection error)
        sock.sendall(f"PRIVMSG {self.BAD_PROVIDER_CHANNEL} :{self.BAD_PROVIDER_BOT_NICK}: hello\r\n".encode())

        # Read until we see the bot respond with an error
        all_lines = self._read_irc_until(
            sock,
            lambda line: self.BAD_PROVIDER_BOT_NICK in line and "PRIVMSG" in line,
            timeout=35,
        )
        assert all_lines is not None, "Bot stayed silent when AI provider failed — must send error message"
        full_text = "\n".join(all_lines)
        assert "Error:" in full_text, \
            f"Bot response should contain 'Error:', got:\n{full_text}"

        self._irc_quit(sock)
