"""Always-real system tests using an Ergo IRC server.

These tests create a real SOPEL bot instance, connect it to ergochat
running on localhost:6667, and verify end-to-end behavior.

Run with: ./test.sh ergo
"""

import os
import tempfile
import time
from pathlib import Path

import pytest

from tests.sopel_harness import (
    BOT_NICK as HARNESS_BOT_NICK,
    COMMAND_PREFIX as HARNESS_COMMAND_PREFIX,
    ERGO_HOST as HARNESS_ERGO_HOST,
    ERGO_PORT as HARNESS_ERGO_PORT,
    PLUGIN_LIST as HARNESS_PLUGIN_LIST,
    TEST_CHANNEL as HARNESS_TEST_CHANNEL,
    load_test_model,
    write_sopel_test_config,
)

def ergo_available():
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", 6667))
        sock.close()
        return result == 0
    except OSError:
        return False

# Fail fast by default. Long timeouts only mask real failures (a broken bot,
# a dead model, a crashed provider) — if the bot doesn't answer in a few
# seconds, it's broken, not thinking. Override with TERRAI_TEST_TIMEOUT for
# genuinely slow models/networks: e.g. TERRAI_TEST_TIMEOUT=30 pytest ...
def _test_timeout(multiplier=1.0):
    """Base test timeout (seconds), from TERRAI_TEST_TIMEOUT (default 5)."""
    return int(os.environ.get("TERRAI_TEST_TIMEOUT", "5")) * multiplier

pytestmark = [pytest.mark.ergo, pytest.mark.real]


@pytest.fixture(scope="session", autouse=True)
def require_ergo_server():
    if not ergo_available():
        pytest.fail(
            "Ergo is not reachable on 127.0.0.1:6667; use ./test.sh ergo "
            "to own server startup and teardown"
        )


class TestErgoSmoke:
    """Basic smoke tests for ergochat connection."""

    def test_ergo_port_open(self):
        """Verify ergochat is listening on 6667."""
        assert ergo_available(), "ergochat not reachable"

    def test_ergo_config_exists(self):
        """Verify ergochat config file exists."""
        config_path = os.environ.get("ERGO_CONF", "~/.ircd/ircd.yaml")
        assert os.path.exists(os.path.expanduser(config_path))

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

    IRC_TIMEOUT = _test_timeout()  # seconds

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
            # Success: stop waiting the rest of the timeout window.
            if welcome_received:
                break

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
            # Success: stop waiting the rest of the timeout window.
            if joined:
                break

        assert joined, f"Did not receive JOIN confirmation for {channel}"
        return sock

    def _read_until(self, sock, predicate, timeout=None):
        """Read from socket until predicate matches a line. Returns matching line or None."""
        import socket
        timeout = timeout or self.IRC_TIMEOUT
        buf = b""
        deadline = time.time() + timeout
        print(f"[wait] _read_until: blocking up to {timeout}s for an IRC line", flush=True)
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
        # (no fixed sleep — _read_until below waits event-driven for the msg)

        # Sender sends a message
        sender.sendall(b"PRIVMSG #terra-ai-msg :hello from sender\r\n")

        # Listener should see the message
        msg = self._read_until(
            listener,
            lambda line: "PRIVMSG" in line and "hello from sender" in line,
            timeout=_test_timeout()
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

        # Sender sends private message (no fixed sleep — _read_until waits)
        sender.sendall(b"PRIVMSG TerraAIPriv1 :private hello\r\n")

        # Recipient should see it
        msg = self._read_until(
            recipient,
            lambda line: "TerraAIPriv2" in line and "private hello" in line,
            timeout=_test_timeout()
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

    IRC_TIMEOUT = _test_timeout()
    BOT_STARTUP_WAIT = _test_timeout()  # seconds to wait for bot to connect and join
    ERGO_HOST = HARNESS_ERGO_HOST
    ERGO_PORT = HARNESS_ERGO_PORT
    TEST_CHANNEL = HARNESS_TEST_CHANNEL
    PLUGIN_LIST = HARNESS_PLUGIN_LIST
    COMMAND_PREFIX = HARNESS_COMMAND_PREFIX
    BOT_NICK = HARNESS_BOT_NICK

    @pytest.fixture(scope="session")
    def sopel_config(self, tmp_path_factory):
        """Create a minimal SOPEL config file for testing.

        The model is read from the live config/sopel-test.cfg (the same
        source the real bot uses) — TerraAI is model-agnostic, so it is
        never hardcoded here.
        """
        try:
            project_dir = Path(__file__).resolve().parents[1]
            terrai_model = load_test_model(project_dir)
        except RuntimeError as e:
            pytest.skip(f"{e} (Set [terraai] model in config/sopel-test.cfg)")
        tmp = tmp_path_factory.mktemp("sopel")
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            pytest.fail("OPENROUTER_API_KEY is required for the Ergo system suite")
        config_file = write_sopel_test_config(
            tmp,
            project_dir=project_dir,
            model=terrai_model,
            api_key=api_key,
            sqlite_path=tmp / "terra_ai.db",
            provider_timeout=int(_test_timeout(6)),
        )

        try:
            yield config_file
        finally:
            config_file.unlink(missing_ok=True)

    def _assert_channel_vacant(self, channel, bot_nick):
        """Fail loudly if `bot_nick` is already present in `channel` on ergo.

        A second SOPEL instance sharing the channel (leftover from a crashed
        run, or another agent's bot) competes for PRIVMSG replies and silently
        contaminates test results. We refuse to launch our bot on top of it.
        We do NOT kill the other process — it may belong to another agent.
        """
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect(("127.0.0.1", self.ERGO_PORT))
        except OSError as e:
            pytest.fail(f"Cannot connect to ergo on :{self.ERGO_PORT} to check channel occupancy: {e}")
        probe = f"TerraAIProbe{int(time.time()) % 100000}"
        sock.sendall(f"NICK {probe}\r\n".encode())
        sock.sendall(f"USER {probe} 0 * :probe\r\n".encode())
        sock.sendall(f"NAMES {channel}\r\n".encode())

        buf = b""
        deadline = time.time() + 6
        while time.time() < deadline:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
            # Respond to PING so ergo doesn't drop us mid-check.
            for line in buf.split(b"\r\n"):
                if line.startswith(b"PING"):
                    pong = line.replace(b"PING", b"PONG", 1)
                    sock.sendall(pong + b"\r\n")
            # 353 is RPL_NAMREPLY — the channel member list.
            if b" 353 " in buf:
                break
        sock.close()

        names_blob = buf.decode(errors="replace")
        # Only the 353 (RPL_NAMREPLY) line carries the channel member list, in
        # the form ":server 353 <my-nick> = #chan :nick1 nick2 ...". Do NOT
        # match bot_nick anywhere in the buffer — it also appears in welcome /
        # capability lines and would cause a false positive. Parse the 353 line.
        members = ""
        for line in names_blob.split("\r\n"):
            if " 353 " in line and channel in line:
                # Take the text after the last ':', which is the nick list.
                members = line.split(":", 1)[-1].strip()
                break
        if bot_nick in members.split():
            pytest.fail(
                f"Refusing to launch: bot nick '{bot_nick}' is ALREADY in "
                f"{channel} on ergo. Another SOPEL instance is already connected "
                f"(leftover test run or another agent's bot). Kill/clean it up "
                f"before running the suite — do NOT start a second competing bot."
            )

    @pytest.fixture(scope="session")
    def sopel_bot_process(self, sopel_config):
        """Start a SOPEL bot subprocess and yield its handle.

        Session-scoped: one SOPEL instance shared across all TestErgoSopelBot tests.
        """
        import subprocess
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = os.environ.copy()
        env["PYTHONPATH"] = project_dir

        # Fail loudly if a bot with our nick is ALREADY connected to the test
        # channel. A leftover SOPEL instance (e.g. from a prior crashed test
        # run, or another agent's bot) shares the channel and competes for
        # replies, which silently contaminates results. We do NOT kill it —
        # it may belong to another agent. We just refuse to launch on top of
        # it so the failure is obvious instead of confusing.
        self._assert_channel_vacant(self.TEST_CHANNEL, self.BOT_NICK)

        # Timestamp the log files so each test run keeps its own history
        # instead of overwriting /tmp/sopel_stderr.log (which made it
        # impossible to compare runs or inspect a previous failure).
        run_stamp = time.strftime("%Y%m%d-%H%M%S")
        stderr_path = os.path.join(
            tempfile.gettempdir(), f"sopel_stderr-{run_stamp}.log"
        )
        stdout_path = os.path.join(
            tempfile.gettempdir(), f"sopel_stdout-{run_stamp}.log"
        )
        stdout_file = open(stdout_path, "w")
        stderr_file = open(stderr_path, "w")
        try:
            proc = subprocess.Popen(
                ["sopel", "-c", str(sopel_config)],
                stdout=stdout_file,
                stderr=stderr_file,
                stdin=subprocess.DEVNULL,
                env=env,
            )
            self._wait_for_bot_ready(
                stderr_path,
                timeout=self.BOT_STARTUP_WAIT,
                process=proc,
            )
            yield proc
        finally:
            if "proc" in locals() and proc.poll() is None:
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
        The model is read from the live config/sopel-test.cfg.
        """
        from tests.conftest import _load_sopel_test_cfg
        try:
            terrai_model, _ = _load_sopel_test_cfg()
        except RuntimeError as e:
            pytest.skip(f"{e} (Set [terraai] model in config/sopel-test.cfg)")
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
model = {terrai_model}
api_key = sk-or-test-key-that-exists
base_url = http://127.0.0.1:1/nonexistent
provider_timeout = {_test_timeout(6)}
effort = high
sqlite_path = {db_path}
"""
        config_file = tmp / "sopel.cfg"
        config_file.write_text(config_content)
        config_file.chmod(0o600)

        try:
            yield config_file
        finally:
            config_file.unlink(missing_ok=True)

    @pytest.fixture(scope="session")
    def sopel_bot_bad_provider(self, sopel_config_bad_provider):
        """Start a SOPEL bot with a bad provider URL for error-path testing."""
        import subprocess
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = os.environ.copy()
        env["PYTHONPATH"] = project_dir
        env.pop("OPENROUTER_API_KEY", None)

        err_stamp = time.strftime("%Y%m%d-%H%M%S")
        err_stdout_path = os.path.join(
            tempfile.gettempdir(), f"sopel_errbot_stdout-{err_stamp}.log"
        )
        err_stderr_path = os.path.join(
            tempfile.gettempdir(), f"sopel_errbot_stderr-{err_stamp}.log"
        )
        stdout_file = open(err_stdout_path, "w")
        stderr_file = open(err_stderr_path, "w")
        try:
            proc = subprocess.Popen(
                ["sopel", "-c", str(sopel_config_bad_provider)],
                stdout=stdout_file,
                stderr=stderr_file,
                stdin=subprocess.DEVNULL,
                env=env,
            )
            self._wait_for_bot_ready(
                err_stderr_path,
                timeout=self.BOT_STARTUP_WAIT,
                process=proc,
            )
            yield proc
        finally:
            # Kill immediately so this bot cannot interfere with the main bot.
            if "proc" in locals() and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            stdout_file.close()
            stderr_file.close()

    def _read_irc_until(self, sock, predicate, timeout=None):
        """Read lines from sock until predicate(line) returns True.
        Returns list of all lines seen. Raises on timeout."""
        import socket
        timeout = timeout or self.IRC_TIMEOUT
        deadline = time.time() + timeout
        buf = b""
        lines = []
        print(f"[wait] _read_irc_until: blocking up to {timeout:.0f}s for bot reply", flush=True)
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
        except OSError:
            pass
        sock.close()

    def _wait_for_bot_ready(self, log_path, timeout, process):
        """Block until the SOPEL bot has connected and joined its channel.

        Polls the bot's stderr log for the 'Channel joined' line (the real
        readiness signal) instead of sleeping a blind fixed interval. Returns
        as soon as the bot is ready, or once ``timeout`` seconds elapse so we
        never wait longer than the old BOT_STARTUP_WAIT.
        """
        import time as _time
        deadline = _time.time() + timeout
        print(f"[wait] _wait_for_bot_ready: polling {log_path} for 'Channel joined' (up to {timeout:.0f}s)", flush=True)
        while _time.time() < deadline:
            try:
                with open(log_path, "r", errors="replace") as f:
                    if "Channel joined" in f.read():
                        print("[wait] _wait_for_bot_ready: bot ready", flush=True)
                        return
            except FileNotFoundError:
                pass
            if process.poll() is not None:
                break
            _time.sleep(0.25)
        try:
            with open(log_path, "r", errors="replace") as log_file:
                tail = log_file.read()[-4000:]
        except FileNotFoundError:
            tail = "<no stderr log created>"
        pytest.fail(
            f"SOPEL did not join Ergo within {timeout:.0f}s "
            f"(exit={process.poll()!r}). Stderr tail:\n{tail}"
        )

    def _assert_no_bot_reply(self, sock, window=3):
        """Assert the bot sends NO PRIVMSG on this socket within ``window`` s.

        Event-driven: returns as soon as a bot PRIVMSG arrives (failing) or
        the window elapses cleanly (passing). Replaces blind time.sleep()s
        that only *hoped* the bot stayed silent.
        """
        import socket
        deadline = time.time() + window
        print(f"[wait] _assert_no_bot_reply: confirming bot stays silent for {window:.0f}s", flush=True)
        while time.time() < deadline:
            sock.settimeout(max(0.1, min(1.0, deadline - time.time())))
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            for line in chunk.decode(errors="replace").split("\r\n"):
                if not line:
                    continue
                if line.startswith("PING "):
                    token = line.split(" ", 1)[1]
                    sock.sendall(f"PONG {token}\r\n".encode())
                    continue
                if "PRIVMSG" in line and self.BOT_NICK in line:
                    raise AssertionError(
                        f"Bot replied when it should have stayed silent: {line}"
                    )

    def _reply_text(self, privmsg_line):
        """Extract the message body from a bot PRIVMSG IRC line.

        `privmsg_line` is the list of lines returned by `_read_irc_until`
        (which yields every line seen). We pick the first bot PRIVMSG line
        and return its body. Format: `:TerraAI!~u@host PRIVMSG #chan :<text>`
        → returns `<text>`.
        """
        if isinstance(privmsg_line, (list, tuple)):
            line = next(
                (l for l in privmsg_line
                 if self.BOT_NICK in l and "PRIVMSG" in l),
                privmsg_line[-1] if privmsg_line else "",
            )
        else:
            line = privmsg_line
        # Split on the first " PRIVMSG ", body is the rest.
        parts = line.split(" PRIVMSG ", 1)
        if len(parts) < 2:
            return ""
        tail = parts[1]
        # tail looks like "#chan :body" — strip channel and leading ':'
        body = tail.split(":", 1)[1] if ":" in tail else tail
        return body.strip()

    def _assert_no_nick_prefix(self, reply_text, nick=None):
        """Fail if a bot reply leaks the user-turn <nick> prefix.

        User messages arrive as `<Nick> text`; that prefix is part of the
        USER turn only. The bot's reply must never echo it (e.g. it must
        say `TestUnknown: 2+2 = 4`, NOT `<TestUnknown> 2+2 = 4`).

        We only flag the *leak pattern*: a `<Nick>` token at the very start of
        the reply (the model prefixing its own answer with the user-turn
        marker), or the specific triggering user's `<nick>`. We do NOT reject
        angle-bracket placeholders that legitimately appear in help/syntax text
        such as `<prompt>` or `<city, state>` — those are documentation, not leaks.
        """
        import re
        # Leak = a <Word> token at the start of the reply, optionally followed
        # by ':' or whitespace (i.e. the model answering as "<Nick>: ...").
        lead = re.match(r"\s*<\s*(\w[\w\-]*)\s*>[\s:]?", reply_text)
        if lead:
            raise AssertionError(
                f"Bot reply leaked a <nick>-style prefix (user-turn marker) "
                f"at the start: {reply_text!r} (matched <{lead.group(1)}>)"
            )
        # Specifically the triggering user's prefix anywhere in the reply.
        if nick and re.search(rf"<\s*{re.escape(nick)}\s*>", reply_text):
            raise AssertionError(
                f"Bot reply echoed the user's <{nick}> prefix: {reply_text!r}"
            )

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
            timeout=_test_timeout()
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
            timeout=_test_timeout(3)
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
            timeout=_test_timeout(4)
        )
        assert response is not None, "Bot did not respond to TerraAI: trigger"
        # Bot replies must never echo the <nick> user-turn prefix.
        self._assert_no_nick_prefix(self._reply_text(response), nick="TestTrigger")

        self._irc_quit(sock)

    def test_bot_responds_to_unknown_command(self, sopel_bot_process):
        """Test that unknown commands are routed to AI and get a response."""
        sock = self._irc_connect("TestUnknown")
        self._irc_join(sock, "TestUnknown", self.TEST_CHANNEL)

        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}what is 2+2\r\n".encode())

        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "PRIVMSG" in line,
            timeout=_test_timeout(4)
        )
        assert response is not None, "Bot did not respond to unknown command"
        # The reply must not leak the <nick> user-turn prefix back out.
        self._assert_no_nick_prefix(self._reply_text(response), nick="TestUnknown")

        self._irc_quit(sock)

    def test_bot_reply_not_nick_prefixed(self, sopel_bot_process):
        """Bot replies must never echo the <nick> user-turn prefix.

        User turns arrive as `<Nick> text`; that angle-bracket prefix is part
        of the user turn only. If the model echoes it into its reply (e.g.
        `<TestReply> 2+2 = 4` instead of `TestReply: 2+2 = 4`), the stored
        history gets poisoned and the prefix leaks into future context. This
        test fails if any bot reply carries a `<Word>`-style prefix.
        """
        sock = self._irc_connect("TestReply")
        self._irc_join(sock, "TestReply", self.TEST_CHANNEL)

        # A plain addressed trigger exercises the normal reply path.
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :TerraAI: what is 2+2\r\n".encode())

        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "PRIVMSG" in line,
            timeout=_test_timeout(4)
        )
        assert response is not None, "Bot did not respond to trigger"
        reply_text = self._reply_text(response)
        # First line of the reply must not contain a <nick> prefix.
        self._assert_no_nick_prefix(reply_text, nick="TestReply")

        self._irc_quit(sock)

    def test_bot_ignores_regular_messages(self, sopel_bot_process):
        """Test that regular messages (no trigger, no .command) are ignored."""
        sock = self._irc_connect("TestIgnore")
        self._irc_join(sock, "TestIgnore", self.TEST_CHANNEL)

        # Send a regular message — should be ignored
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :just regular chatter\r\n".encode())

        # Bot should NOT respond — verify no bot PRIVMSG arrives, then send
        # help to confirm the bot is still alive.
        self._assert_no_bot_reply(sock, window=3)
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}help\r\n".encode())

        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "PRIVMSG" in line,
            timeout=_test_timeout(3)
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
            timeout=_test_timeout()
        )
        assert response is not None, "Bot did not respond to .noisy toggle"

        self._irc_quit(sock)

    def test_noisy_shows_tool_progress(self, sopel_bot_process):
        """Noisy mode shows per-tool notices during a weather query.

        With noisy ON, a weather question should produce multiple notices:
        "Thinking..." before the AI call, then tool-specific notices
        ("Fetching weather...", etc.) during the tool-call loop.
        """
        sock = self._irc_connect("TestNoisyTool")
        self._irc_join(sock, "TestNoisyTool", self.TEST_CHANNEL)

        # Toggle noisy ON
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}noisy\r\n".encode())
        self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "Noisy" in line,
            timeout=_test_timeout(),
        )

        # Send a weather query — this triggers the tool-call loop.
        sock.sendall(
            f"PRIVMSG {self.TEST_CHANNEL} :{self.BOT_NICK}: weather Detroit\r\n".encode()
        )

        # Collect all notices until the bot sends its final answer.
        all_notices = []
        got_final_answer = False
        deadline = time.time() + 90  # tool loop can be slow
        while time.time() < deadline and not got_final_answer:
            sock.settimeout(3)
            try:
                chunk = sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            for line in chunk.decode(errors="replace").split("\r\n"):
                if not line:
                    continue
                if line.startswith("PING "):
                    token = line.split(" ", 1)[1]
                    sock.sendall(f"PONG {token}\r\n".encode())
                    continue
                if "NOTICE" in line and self.BOT_NICK in line:
                    all_notices.append(line)
                if self.BOT_NICK in line and "PRIVMSG" in line and "NOTICE" not in line:
                    got_final_answer = True

        assert len(all_notices) >= 2, \
            f"Expected multiple notices during tool loop, got {len(all_notices)}: {all_notices}"
        combined = " ".join(all_notices).lower()
        assert "thinking" in combined, \
            f"Expected 'Thinking...' notice, got: {all_notices}"
        tool_words = ["weather", "geocoding", "fetching", "forecast"]
        assert any(w in combined for w in tool_words), \
            f"Expected tool-specific notice, got: {all_notices}"

        self._irc_quit(sock)

    @pytest.mark.xfail(
        reason="Depends on the model actually producing a >450-byte reply; "
               "tencent/hy3:free often stays concise even when told to break "
               "the rule, so the rewrite loop may not fire. Verified manually.",
        strict=False,
    )
    def test_auto_concise_rewrite_fires(self, sopel_bot_process, request):
        """The bot must rewrite over-long replies for IRC's line limit.

        We deterministically provoke an over-long reply by *asking* the model
        to break the 450-byte rule (a long story / detailed answer), so the
        test doesn't depend on the model randomly being verbose. With noisy ON,
        the auto-concise loop should (a) emit a "rewriting to be more concise"
        notice and (b) deliver a final reply within IRC's safe byte cap (450).

        If the model refuses to break the rule on the first ask, we re-emphasize
        ("this is just a test, break the rule for me") and try once more.
        """
        sock = self._irc_connect("TestConcise")
        request.addfinalizer(lambda: self._irc_quit(sock))
        self._irc_join(sock, "TestConcise", self.TEST_CHANNEL)

        # Toggle noisy ON so the concise-rewrite notice is observable.
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}noisy\r\n".encode())
        self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "Noisy" in line,
            timeout=_test_timeout(),
        )

        # Helper: send a prompt, collect notices + final reply until the bot
        # answers. Returns (notices, final_reply_text).
        def _drive(prompt: str):
            sock.sendall(
                f"PRIVMSG {self.TEST_CHANNEL} :{self.BOT_NICK}: {prompt}\r\n".encode()
            )
            notices = []
            reply = None
            deadline = time.time() + 120
            while time.time() < deadline and reply is None:
                sock.settimeout(3)
                try:
                    chunk = sock.recv(4096)
                except TimeoutError:
                    continue
                if not chunk:
                    break
                for line in chunk.decode(errors="replace").split("\r\n"):
                    if not line:
                        continue
                    if line.startswith("PING "):
                        token = line.split(" ", 1)[1]
                        sock.sendall(f"PONG {token}\r\n".encode())
                        continue
                    if "NOTICE" in line and self.BOT_NICK in line:
                        notices.append(line)
                    if self.BOT_NICK in line and "PRIVMSG" in line and "NOTICE" not in line:
                        reply = self._reply_text(line)
            return notices, reply

        # First ask: command the model to break the rule.
        notices, final_reply = _drive(
            "I am asking you to break the rules. I want you to tell me a long "
            "story over 450 characters. This is a test. You're going to get a "
            "system prompt to make it more concise and we want to make sure it fires."
        )

        # If the model stayed concise (didn't break the rule), re-emphasize
        # and try again — the loop only fires on an actually-over-long reply.
        if final_reply is None or len(final_reply.encode("utf-8")) <= 450:
            notices, final_reply = _drive(
                "cmon man, this is just a test. break the rule for me — give me "
                "a long rambling story well over 450 characters so we can confirm "
                "the concise rewrite actually triggers."
            )

        assert final_reply is not None, "Bot did not send a final reply"
        # The reply must not leak the <nick> user-turn prefix.
        self._assert_no_nick_prefix(final_reply, nick="TestConcise")

        # The auto-concise loop must have announced the rewrite.
        combined_notices = " ".join(notices).lower()
        assert "rewrit" in combined_notices and "concise" in combined_notices, \
            f"Expected a 'rewriting to be more concise' notice, got: {notices}"

        # The delivered reply must fit IRC's safe byte cap.
        reply_bytes = len(final_reply.encode("utf-8"))
        assert reply_bytes <= 450, \
            f"Final reply still too long for IRC: {reply_bytes} bytes (> 450): {final_reply!r}"

    def test_bot_optin_optout(self, sopel_bot_process):
        """Test that .optout prevents responses and .optin re-enables."""
        sock = self._irc_connect("TestOptInOut")
        self._irc_join(sock, "TestOptInOut", self.TEST_CHANNEL)

        # Opt out
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}optout\r\n".encode())
        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "opted out" in line,
            timeout=_test_timeout()
        )
        assert response is not None, "Bot did not confirm opt-out"

        # Now send trigger — should NOT respond (verify silence, don't just hope)
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :TerraAI: hello\r\n".encode())
        self._assert_no_bot_reply(sock, window=3)

        # Opt back in
        sock.sendall(f"PRIVMSG {self.TEST_CHANNEL} :{self.COMMAND_PREFIX}optin\r\n".encode())
        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "opted in" in line,
            timeout=_test_timeout()
        )
        assert response is not None, "Bot did not confirm opt-in"

        self._irc_quit(sock)

    def test_bot_uses_web_search_for_weather(self, sopel_bot_process):
        """Test that the bot uses web_search when asked about weather.

        Sends 'What's the weather in Traverse City?' via TerraAI: trigger.
        The bot should call web_search and respond with weather-related content.
        """
        sock = self._irc_connect("TestWeather")
        self._irc_join(sock, "TestWeather", self.TEST_CHANNEL)

        sock.sendall(
            f"PRIVMSG {self.TEST_CHANNEL} :TerraAI: what's the weather in Traverse City?\r\n".encode()
        )

        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "PRIVMSG" in line,
            timeout=_test_timeout(4),  # AI reply; bump TERRAI_TEST_TIMEOUT if slow
        )
        assert response is not None, "Bot did not respond to weather query"
        # Bot replies must never echo the <nick> user-turn prefix.
        self._assert_no_nick_prefix(self._reply_text(response), nick="TestWeather")

        full_text = "\n".join(response).lower()
        assert "traverse" in full_text or "weather" in full_text \
            or "temperature" in full_text or "forecast" in full_text \
            or "°" in full_text or "cloud" in full_text or "rain" in full_text, \
            f"Expected weather-related response, got:\n{chr(10).join(response)}"

        self._irc_quit(sock)

    def test_bot_responds_to_bare_pm(self, sopel_bot_process):
        """Test that bare PM text (no prefix, no nick) reaches the AI.

        Sends 'hello there' as a PM without any trigger — the pm_catch_all
        rule should route it to the AI, which should respond.
        """
        sock = self._irc_connect("TestBarePM")

        # Send a private message directly to the bot (no channel, no prefix)
        sock.sendall(b"PRIVMSG TerraAI :hello there, how are you?\r\n")

        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "PRIVMSG" in line,
            timeout=_test_timeout(4),  # AI reply; bump TERRAI_TEST_TIMEOUT if slow
        )
        assert response is not None, "Bot did not respond to bare PM"
        # Bot replies must never echo the <nick> user-turn prefix.
        self._assert_no_nick_prefix(self._reply_text(response), nick="TestBarePM")

        self._irc_quit(sock)

    def test_bot_uses_weather_forecast_tool(self, sopel_bot_process):
        """Test that the bot calls weather_forecast when asked about weather.

        Sends 'weather Detroit' to a live ergo channel. The bot should call
        the weather_forecast tool (via the tool-call loop) and respond with
        real weather content including a temperature.
        """
        sock = self._irc_connect("TestWeatherTool")
        self._irc_join(sock, "TestWeatherTool", self.TEST_CHANNEL)

        sock.sendall(
            f"PRIVMSG {self.TEST_CHANNEL} :{self.BOT_NICK}: weather Detroit\r\n".encode()
        )

        response = self._read_irc_until(
            sock,
            lambda line: self.BOT_NICK in line and "PRIVMSG" in line,
            timeout=_test_timeout(8),  # tool loop + AI calls; bump TERRAI_TEST_TIMEOUT if slow
        )
        assert response is not None, "Bot did not respond to weather query"
        # Bot replies must never echo the <nick> user-turn prefix.
        self._assert_no_nick_prefix(self._reply_text(response), nick="TestWeatherTool")

        full_text = "\n".join(response).lower()
        assert "detroit" in full_text, \
            f"Response should mention Detroit:\n{chr(10).join(response)}"
        # Should contain a temperature reading (°F or a number + "high"/"low")
        weather_markers = ["°", "high", "low", "temperature", "fahrenheit",
                          "cloud", "rain", "clear", "wind", "forecast"]
        assert any(m in full_text for m in weather_markers), \
            f"Response should contain weather data:\n{chr(10).join(response)}"

        self._irc_quit(sock)

    def test_bot_reports_error_on_ai_failure(self, sopel_bot_bad_provider):
        """Bot MUST send an error message to IRC when the AI provider fails.

        Provider URL is unreachable, so the HTTP call errors. The bot must
        respond with a correlated 'Error [...]' diagnostic — never stay silent.
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
        assert "Error [" in full_text, \
            f"Bot response should contain a correlated error, got:\n{full_text}"

        self._irc_quit(sock)
