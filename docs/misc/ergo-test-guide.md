# Ergo Integration Test Guide

OWL — 2026-06-26

## What These Tests Do

The ergo integration tests (`tests/test_ergo.py`) verify the TerraAI SOPEL plugin against a real ergochat IRC server. They start a real SOPEL bot process, connect to ergo on `127.0.0.1:6667`, and verify end-to-end behavior through raw IRC protocol.

## Prerequisites

1. **ergochat installed:** `ergochat` binary (v2.18.0-4 or compatible)
2. **ergo config:** `~/.ircd/ircd.yaml` with:
   - `accounts.registration.enabled: false` (required — ergo rejects PRIVMSG without full registration otherwise)
   - `prefix = -` configured in SOPEL bot config (our tests use `-` as command prefix)
3. **SOPEL installed:** `sopel` 8.0.4+
4. **Python dependencies:** see `requirements.txt`

## Starting Ergo

```bash
# Kill any existing ergo
pkill ergochat
sleep 2

# Start ergo (from its config directory)
cd ~/.ircd && /usr/sbin/ergochat run --conf ircd.yaml --quiet &

# Verify it's running
sleep 3
ss -tlnp | grep 6667
```

**Critical:** `accounts.registration.enabled` MUST be `false` in `~/.ircd/ircd.yaml`. Without this, ergo sends `451 ERR_NOTREGISTERED` when the test client tries to send PRIVMSG after NICK/USER. The test client waits for `001 RPL_WELCOME` which never comes because ergo expects full account registration.

## Running the Tests

```bash
cd ~/agentic-repos/terra-ai-agent1

# Run all ergo tests (requires ergo running on localhost:6667)
pytest tests/test_ergo.py -v

# Run a specific test class
pytest tests/test_ergo.py::TestErgoSopelBot -v

# Run a single test
pytest tests/test_ergo.py::TestErgoSopelBot::test_bot_optin_optout -v

# Run with short tracebacks
pytest tests/test_ergo.py -v --tb=short
```

## Test Structure

Three test classes:

| Class | What it tests | Requires SOPEL bot |
|-------|--------------|-------------------|
| `TestErgoSmoke` | Port open, config exists, raw socket connect | No |
| `TestErgoIRCProtocol` | NICK/USER registration, JOIN, channel msg, PM (raw socket) | No |
| `TestErgoSopelBot` | Full SOPEL bot: connect, join, help, trigger, unknown cmd, optin/out, error handling | Yes |

## Key Fixtures

- `sopel_config` (session-scoped): Creates a minimal SOPEL config file in a temp directory
- `sopel_bot_process` (session-scoped): Starts one SOPEL bot subprocess shared across all `TestErgoSopelBot` tests
- `sopel_config_bad_provider` (session-scoped): Creates a SOPEL config with an unreachable provider URL (for error-path testing)
- `sopel_bot_bad_provider` (session-scoped): Starts a SOPEL bot without API key, used by `test_bot_reports_error_on_ai_failure`

## Debugging

### Check SOPEL bot logs
The bot's stdout/stderr are written to:
- `/tmp/sopel_stdout.log` and `/tmp/sopel_stderr.log` (main bot)
- `/tmp/sopel_errbot_stdout.log` and `/tmp/sopel_errbot_stderr.log` (error bot)

### Check if bot is still running
```bash
ps aux | grep sopel | grep -v grep
```

### Manual IRC test
```bash
python3 -c "
import socket, time
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 6667))
sock.sendall(b'NICK TestManual\r\nUSER TestManual 0 * :test\r\nCAP END\r\n')
# Wait for 001, join channel, send trigger...
"
```

### Common issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `451 ERR_NOTREGISTERED` | `accounts.registration.enabled: true` | Set to `false` in `~/.ircd/ircd.yaml` |
| Bot not responding to messages | Bot process crashed | Check `/tmp/sopel_stderr.log` |
| `001` not received | Ergo not fully started | Wait longer, check `ss -tlnp \| grep 6667` |
| Test client can't connect | Ergo not running | Start ergo |
| Bot dies mid-test | SOPEL process died | Check stderr for traceback |

## How the Test Client Works

The test uses a raw socket IRC client (no library). Connection flow:

1. Connect TCP to `127.0.0.1:6667`
2. Send `NICK <nick>\r\nUSER <nick> 0 * :TerraAI Test\r\nCAP END\r\n`
3. Read until `001 <nick>` received (with PING/PONG handling)
4. Send `JOIN #terra-ai-agent1\r\n`
5. Read until `366 <nick> #terra-ai-agent1` (end-of-NAMES)
6. Send test PRIVMSG
7. Read until predicate matches or timeout

The `_read_irc_until(sock, predicate, timeout)` helper reads all IRC lines from the socket until `predicate(line)` returns True. It handles PING/PONG automatically.
