# Console (test_tool/) — Feature Specification

**Date:** 2026-06-26
**Status:** Rewrite in progress
**Agent:** OWL
**Previous name:** `test_tool/chat.py` (renamed to `console.py`)

---

## 1. Purpose

Console is an irssi-like terminal client for interacting with TerraAI locally without a real IRC server. It is a **development and manual-testing tool** — not a production component.

Run via: `python test_tool/console.py`

Original design spec: `.agentic/plan.md` §7 ("Test Tool (Interactive").

---

## 2. Design Principles

From `.agentic/plan.md` §7.1:

- **KISS** — not a full IRC client, just enough to test
- irssi-style controls (keyboard-driven, terminal UI)
- Default channel: `#terra-ai`
- PM support (simulated — just message the bot nick directly)
- All messages go through the same code path as real IRC

---

## 3. Irssi-like Layout

From `.agentic/plan.md` §7.2:

```
┌─────────────────────────────────────────────────────────┐
│ #terra-ai                                    12:34     │
│─────────────────────────────────────────────────────────│
│ [12:34] <nick1> hey TerraAI                             │
│ [12:34] <TerraAI> hi there                              │
│ [12:35] [PM] <nick1> hello                              │
│ [12:35] [PM] <TerraAI> response                         │
│ [12:36] -!- Thinking...                                 │
│                                                         │
│─────────────────────────────────────────────────────────│
│ _                                                       │
└─────────────────────────────────────────────────────────┘
```

- **Top bar:** channel name + clock
- **Middle:** scrollable message history (nick + message, bot responses)
- **Bottom:** input line with `_` cursor
- Single channel view — no window list, no split panes, no nick list

---

## 4. Controls

From `.agentic/plan.md` §7.3:

| Key | Action |
|-----|--------|
| `↑` / `↓` | Input history navigation (in the input box) |
| `Ctrl+Q` or `/quit` or `/exit` | Quit |
| `Ctrl+D` | Quit |
| `Ctrl+C` | Quit |
| `Tab` | Complete trigger phrase (start-of-line → `TerraAI: `, mid-line → `TerraAI `) |
| Anything else | Send as message to current target |

Additional implementation features:
- `KEY_RESIZE` — recreate windows on terminal resize
- `KEY_HOME` / `KEY_END` — move cursor to start/end of input
- Full arrow-key editing (left/right/backspace/delete)

---

## 5. Message Routing

The console calls `plugin.py` handler functions **directly** — no routing logic in the console itself. The console constructs a `FakeTrigger` and calls the same `(bot, trigger)` handlers that SOPEL calls in production.

### 5.1 How it works

```python
# Console builds a fake trigger
trigger = FakeTrigger(nick, channel, text, is_pm=is_pm)
handler = getattr(terra_plugin, f"cmd_{cmd_word}", None)
if handler:
    handler(bot, trigger)  # calls plugin.py directly
```

The `plugin.py` handlers (`cmd_optin`, `cmd_effort`, `addressed_freeform`, etc.) contain ALL the routing logic — trigger phrase matching, opt-in checks, prompt lookup, AI dispatch. The console does NOT duplicate this logic.

### 5.2 PMs

PMs are done by sending `/msg TerraAI hello` in the console. The console parses `/msg <text>` and sets `is_pm=True` on the trigger. The plugin.py handler then routes it as a direct message (no trigger phrase needed).

```python
# In the console's input loop
is_pm = cmd.lower().startswith("/msg ")
pm_text = cmd[5:] if is_pm else cmd
trigger = FakeTrigger(nick, channel, pm_text, is_pm=is_pm)
```

### 5.3 No routing in the console

The console does NOT:
- Check if a message starts with a trigger phrase
- Check if a user is opted in
- Decide locally whether to send to AI or handle as a management command
- Parse trigger phrases or nick prefixes

All of that lives in `plugin.py`. The console just:
1. Parses `/msg` for PM mode
2. Builds a `FakeTrigger` with the raw text
3. Calls `getattr(terra_plugin, f"cmd_{word}")` for management commands
4. Calls `addressed_freeform(bot, trigger)` for everything else

---

## 6. Display Features

### 6.1 Timestamps

- Top bar shows current time (`12:34`), updated on each render
- Each message line prefixed with `[HH:MM]` timestamp
- Format: `[HH:MM] <nick> message` for user, `[HH:MM] <TerraAI> response` for bot

### 6.2 PMs (Private Messages)

- Messages addressed to the bot go to AI without trigger phrase
- irssi-style format: `[HH:MM] [PM] <nick> message` for user input
- PM bot response: `[HH:MM] [PM] <TerraAI> response`
- `[PM]` has its own color pair (distinct from channel messages)

### 6.3 Notices (irssi format)

- irssi uses `-!-` prefix for notices
- Format: `[HH:MM] -!- <notice text>`
- `.noisy` "Thinking..." notice rendered immediately when AI call starts
- Other notices (optin/optout responses, etc.) also use this format
- Notices have their own color pair

### 6.4 Tab Completion

- `Tab` completes the trigger phrase in the input line
- At start of line: `<Tab>` → `TerraAI: ` (completes to trigger phrase + space)
- Mid-line (after a space): `<Tab>` → completes to `TerraAI ` (just the nick, no colon)
- Mid-line (mid-word): `<Tab>` → completes the word at cursor to the trigger phrase
- Case-insensitive prefix matching: `ter<Tab>` → `TerraAI: `
- If no match found: `curses.beep()` (visual/audio feedback)
- Completions are hardcoded: `["TerraAI: "]` for start-of-line, `["TerraAI "]` for mid-line
- From `testing-agent2.md` Round 1 #3a: `Ter<Tab>` → `TerraAI: `
- From `testing-agent2.md` Round 6 #57: mid-line `Ter<Tab>` completes correctly (word-at-cursor matching, not just start-of-line)

### 6.5 Input History

- `↑`/`↓` navigate through previously sent messages
- History is per-session (in-memory list)
- Navigation works in the input line (not the chat window)
- Same behavior as original `chat.py`

---

## 7. Architecture

### 7.1 Single file: `test_tool/console.py`

Uses Python's built-in `curses` module for the TUI.

### 7.2 FakeTrigger

Mimics a SOPEL trigger object. `plugin.py` accesses these attributes:

- `trigger.sender` — for PMs: the nick. For channel messages: the channel name. Used by `_server_name(bot)`.
- `trigger.nick` — the nick of the sender. Used by `_guard()`, `_nick()`, opt-in/out, etc.
- `trigger.admin` — boolean, whether the sender is an admin.
- `trigger.group(0)` — full text.
- `trigger.group(1)` — command word (first word after stripping `.` or `-`). Used by all `cmd_*` handlers to get args.
- `trigger.group(2)` — args (everything after command word). Used by `.effort`, `.addprompt`, `.rmprompt`, `.ai`, etc.
- `trigger.match` — set to None (only used by SOPEL's rule matching, not by our handlers).

Code:

```python
class FakeTrigger:
    """Mimics a SOPEL trigger object for direct handler dispatch."""

    def __init__(self, nick, channel, text, is_pm=False, admin=False):
        self.nick = nick
        # For PMs, sender is the nick; for channel messages, sender is the channel
        self.sender = nick if is_pm else channel
        self.match = None
        self.text = text
        self.is_pm = is_pm
        self.admin = admin
        self._text = text

    def group(self, num):
        """Return trigger group. group(1) = command word, group(2) = args."""
        if num == 0:
            return self._text
        text = self._text
        if text.startswith("."):
            text = text[1:]
        elif text.startswith("-"):
            text = text[1:]
        parts = text.split(None, 1)
        if num == 1:
            return parts[0] if parts else ""
        if num == 2:
            return parts[1] if len(parts) > 1 else ""
        return None
```

### 7.3 FakeBot

Mimics a SOPEL bot object. `plugin.py` calls these methods:

- `bot.say(msg)` — sends a message to the channel.
- `bot.reply(msg)` — same as say (for our purposes).
- `bot.notice(nick, msg)` — sends a private notice to the user.
- `bot.isupport.get("NETWORK", "unknown")` — returns the network name. Used by `_server_name(bot)`.
- `bot.settings.terraai` — the config section. Used in `setup()` but NOT in handler functions (they receive config via closure).

Code:

```python
class FakeBot:
    """Mimics a SOPEL bot object for direct handler dispatch.

    Tracks say() (channel messages) and notice() (PMs) separately.
    In SOPEL, bot.say() sends to the channel, bot.notice() sends a
    private notice back to the user.
    """

    def __init__(self):
        self.messages = []  # say() calls — channel messages
        self.notices = []   # notice() calls — PM responses
        # Minimal isupport for _server_name(bot)
        self.isupport = {"NETWORK": "test-network"}

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
```

### 7.4 _default_test_config()

Creates a `SimpleNamespace` with the same attributes as `TerraAISection`. Used when there's no SOPEL config file (test tool, fixtures).

```python
def _default_test_config():
    from types import SimpleNamespace
    c = SimpleNamespace()
    c.model = os.environ.get("TERRAI_MODEL", "openrouter/owl-alpha")
    c.api_key = os.environ.get("OPENROUTER_API_KEY", "")
    c.base_url = "https://openrouter.ai/api/v1"
    c.provider_timeout = 30
    c.trigger_phrase = "TerraAI:"
    c.bot_nick = ""
    c.trigger_char = "."
    c.effort = "high"
    c.sqlite_path = "data/test-terraai.db"
    return c
```

### 7.5 TerraAITestClient

The headless core. Loads config, creates a `TerraAI` instance, and routes messages via handler dispatch. Used by both the interactive console and the automated tests.

```python
class TerraAITestClient:
    """Test client that connects to TerraAI without a real IRC server."""

    def __init__(self, config_path: str = "config/terraai.yaml"):
        self._load_env()
        self.config = self._load_config(config_path)
        self.terra = TerraAI(self.config)
        self.server = "test-network"  # Matches FakeBot.isupport["NETWORK"]
        self.channel = "#terra-ai"
        self.nick = "tester"
        self.bot = FakeBot()

    def _load_env(self):
        """Load .env file if present."""
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
        import configparser
        from sopel.config import Config as SopelConfig

        try:
            sopel_config = SopelConfig(path)
            sopel_config.define_section('terraai', TerraAISection)
            return sopel_config.terraai
        except Exception:
            return _default_test_config()

    def send_message(self, text: str) -> list[str]:
        """Send a message as the test user and return bot responses.

        Calls plugin.py handler functions directly via getattr dispatch.
        """
        self.bot.messages.clear()
        trigger = FakeTrigger(self.nick, self.channel, text)
        trigger_char = self.terra.prompts.trigger_char if self.terra.prompts else ""
        trigger_phrase = self.terra.config.trigger_phrase

        def notify_thinking():
            if self.terra.user.is_noisy(self.server, self.nick):
                self.bot.notice(self.nick, "Thinking...")

        cmd_word = ""
        if text.startswith(trigger_char):
            cmd_word = text[len(trigger_char):].split()[0].lower() if text[len(trigger_char):].strip() else ""

        if cmd_word:
            handler = getattr(terra_plugin, f"cmd_{cmd_word}", None)
            if handler:
                notify_thinking()
                handler(self.bot, trigger)
                return list(self.bot.messages)
            else:
                full_text = text[len(trigger_char):].strip()
                trigger.group = lambda n: full_text if n == 1 else None
                notify_thinking()
                terra_plugin.addressed_freeform(self.bot, trigger)
                return list(self.bot.messages)

        if text.lower().startswith(trigger_phrase.lower()):
            notify_thinking()
            trigger.group = lambda n: text[len(trigger_phrase):].strip() if n == 1 else None
            terra_plugin.addressed_freeform(self.bot, trigger)
            return list(self.bot.messages)

        return list(self.bot.messages)

    def send_pm(self, nick: str, text: str) -> dict:
        """Send a PM (direct message) to the bot.

        Returns {"say": [...], "notice": [...]} with responses and notices.
        """
        self.bot.messages.clear()
        self.bot.notices.clear()
        trigger = FakeTrigger(nick, self.channel, text, is_pm=True)

        def notify_thinking():
            if self.terra.user.is_noisy(self.server, nick):
                self.bot.notice(nick, "Thinking...")

        cmd_word = text.split()[0].lstrip(".-") if text.split() else ""
        if cmd_word:
            handler = getattr(terra_plugin, f"cmd_{cmd_word}", None)
            if handler:
                notify_thinking()
                handler(self.bot, trigger)
                return {"say": list(self.bot.messages), "notice": list(self.bot.notices)}

        notify_thinking()
        response = self.terra.handle_ai_message(
            self.server, nick, nick, text, include_history=True
        )
        if response:
            self.bot.say(response)
        return {"say": list(self.bot.messages), "notice": list(self.bot.notices)}
```

### 7.6 Two modes of operation

1. **Non-interactive (`--test` flag):** runs a fixed sequence of management commands and prints results. Used by pytest harness tests.

```python
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        client = TerraAITestClient()
        print(f"{client.terra.config.bot_nick or 'TerraAI'} Test Client")
        print("=" * 40)

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
```

2. **Interactive (`run_interactive()`):** launches a curses TUI with a main loop that:
   - Dispatches local management commands (`.optin`, `.optout`, etc.) directly in-process via `getattr(terra_plugin, f"cmd_{word}")`
   - Sends AI-bound messages synchronously in the main thread
   - Renders a scrolling chat window, input line with history and tab completion, and `[HH:MM]` timestamps

### 7.4 AI call strategy

**Phase 1 — Synchronous in the main thread.**

The simplest approach: call `provider.chat()` directly in the main loop. The UI freezes briefly during the AI call (2-10 seconds depending on provider). Acceptable for a testing tool where you're sending one message at a time.

```python
def do_ai_call(text, is_pm):
    if is_pm:
        result = client.send_pm(client.nick, text)
    else:
        result = client.send_message(text)
    pending_call["result"] = result
    pending_call["done"] = True

# In the main loop — blocks until AI responds:
do_ai_call(text, is_pm)
maybe_finish_call()
```

**Phase 2 — Asynchronous with spawned worker process.**

When the UI must stay responsive (e.g. user wants to type while waiting), move AI calls into a separate spawned process. This avoids the httpx+curses+pty deadlock because the worker doesn't inherit curses/pty state.

The full root cause analysis and worker implementation details are in `docs/release-0.0.2/httpx-curses-pty-hang-analysis.md`. Key points:

- `multiprocessing.get_context("spawn")` gives a fresh interpreter without curses/pty state
- Jobs flow through `input_q`, results flow back through `output_q`
- The curses main loop polls the output queue each tick (100ms via `input_win.timeout(100)`)
- The worker process uses the real `OpenRouterProvider` (httpx) which works fine outside the pty

```python
# Worker process (separate interpreter)
def _ai_worker(input_q, output_q, config_dict):
    from terra_ai.bot import TerraAI
    from types import SimpleNamespace
    ai = TerraAI(SimpleNamespace(**config_dict))
    while True:
        job = input_q.get()
        if job is None:
            return
        job_id, text, is_pm, server, nick = job
        response = ai.handle_ai_message(server, nick, nick, text, include_history=True)
        output_q.put((job_id, "ok", response))

# Main loop polls for results
def maybe_finish_call():
    try:
        done_job_id, kind, payload = output_q.get_nowait()
    except Empty:
        return
    if done_job_id == pending_job:
        pending_job = None
        # render result
```

**Hybrid approach for testing:** Phase 1 for the console itself (simple, works in terminal), Phase 2 documented for when async is needed.

**Test architecture — three layers:**

1. **Unit tests (§8.1)** use `TerraAITestClient` directly in the test process. No pty, no curses, no AI mock. They test routing and plugin logic by calling `client.send_message("hello")` and asserting on the returned strings.

2. **SVG tests (§8.2)** run the console in a pty subprocess, send keystrokes, export the UI as SVG, and parse the SVG DOM in the test to verify content. This tests the curses rendering without relying on pty output capture.

3. **Interactive tests (§8.3)** are the same as SVG tests but focused on user-facing behaviors (launch, exit, tab complete, history navigation, etc.). They also use SVG export for verification.

Neither unit tests nor interactive tests depend on the console's main loop AI strategy (Phase 1 vs Phase 2). Unit tests bypass the console entirely. Interactive/SVG tests verify the UI via exported SVG, not by reading pty output.

---

## 8. Test Coverage

All tests use the **real AI provider** (no mocking). Tests that need an API key are skipped unless `--real` is passed.

### 8.1 Unit tests (`tests/test_console.py`)

Non-interactive tests that use `TerraAITestClient` directly (no pty subprocess). These test the routing and plugin logic, not the curses UI.

**TestTestTool:**
- `test_send_message` — trigger phrase routes to AI
- `test_regular_message_ignored` — no trigger = no AI call
- `test_async_ai_call` — AI response rendered
- `test_unknown_command_routes_to_ai` — `.unknown` goes to AI
- `test_help_command` — `.help` shows commands

**TestPM:**
- `test_pm_trigger_routes_to_ai` — PM without trigger goes to AI
- `test_pm_management_command` — PM with `.optin` handled locally
- `test_pm_help_command` — PM with `.help` handled locally
- `test_pm_unknown_command_routes_to_ai` — PM with `.unknown` goes to AI
- `test_ai_command_context_free` — `.ai` uses no history
- `test_pm_direct_message` — direct PM routing
- `test_pm_setlocation_forwards_to_ai` — PM `.setlocation` forwarded
- `test_clear_command` — `.clear` handled locally
- `test_compact_admin_only_for_non_admin` — `.compact` admin gate

**TestNoisy:**
- `test_noisy_toggle` — `.noisy` toggles
- `test_noisy_off_no_notice` — no notice when off
- `test_noisy_on_sends_notice` — notice when on

### 8.2 Console SVG tests (`tests/test_console_screenshots.py`)

These tests exercise the **curses UI** by running the console in a pty subprocess, sending keystrokes, and exporting SVG screenshots of the result. The tests then **inspect the SVG content programmatically** to verify the UI shows the correct output.

**How SVG export works:**

The console uses `curses` (not Textual). To export SVG with colors:
- After the console runs, call `stdscr.export_svg(path)` — this dumps the curses screen buffer as SVG with ANSI colors rendered.
- The SVG contains `<text>` elements with `(x, y)` positions and content.
- Tests parse the SVG, extract text elements, and assert expected strings are present.

**Test format:**

```python
def test_pm_mode():
    """PM mode shows [PM] prefix and bot responds."""
    with ConsoleRunner() as runner:
        runner.send_keys("/msg hello\n")
        runner.expect_response(timeout=30)
        svg = runner.export_svg()
        
        # Parse SVG and verify content
        texts = extract_svg_texts(svg)
        assert "[PM] <tester> hello" in texts
        assert any("TerraAI" in t and "hello" not in t for t in texts), \
            "Bot response not found"
```

**SVG tests:**

- `test_initial_state` — header shows `#terra-ai`, empty chat, input line at bottom
- `test_after_message` — user message + bot response visible in chat
- `test_pm_sends_with_prefix` — `/msg hello` shows `[PM] <tester> hello` prefix
- `test_notic_shows_thinking` — `-!- Thinking...` appears before AI response
- `test_noisy_toggle_shows_notice` — `.noisy` shows "Noisy mode ON/OFF"
- `test_help_shows_command_list` — `.help` shows all commands
- `test_tab_completion` — pressing Tab completes `TerraAI: `
- `test_input_history` — pressing Up recalls previous input
- `test_management_commands_work` — `.optin`, `.effort low`, etc. produce correct responses

**Why SVG tests?**

- Can't inspect curses output programmatically in a pty
- SVG export preserves colors, layout, and text positions
- Tests can parse the SVG DOM and assert on content
- Visual inspection still possible (open SVG in browser)

### 8.3 Interactive tests

Pty-subprocess tests that launch `run_interactive()` and verify behavior through the pty. These use the SVG export approach from §8.2 to verify UI state.

From `testing-agent2.md` Round 8:
- `test_interactive_launches_and_exits`
- `test_interactive_accepts_input`
- `test_interactive_tab_completes_trigger`
- `test_interactive_tab_completes_midline`
- `test_interactive_accepts_pm`
- `test_interactive_noisy_notice`
- `test_interactive_empty_input`
- `test_interactive_ctrl_d_exits`
- `test_interactive_history_navigation`

### 8.4 Real API tests (only with `--real` flag)

These hit the real OpenRouter API. Skipped unless `--real` is passed.

**TestRealAPI:**
- `test_real_effort_level`
- `test_real_unknown_command_goes_to_ai`
- `test_real_noisy_toggle`
- `test_real_setlocation_goes_to_ai`
- `test_real_pm_trigger_responds`
- `test_real_pm_effort_level`
- `test_real_noisy_sends_notice_on_ai_message`

### 8.4 Deleted: screenshot_test.py

The old `test_tool/screenshot_test.py` was a standalone script using Textual (which was never the actual implementation — the console uses curses). Deleted. Replaced by `tests/test_console_screenshots.py` which uses the real console + curses SVG export.

---

## 9. File Map

| File | Purpose |
|------|---------|
| `test_tool/console.py` | Interactive console (curses TUI) |
| `test_tool/__init__.py` | Package marker |
| `tests/test_console.py` | Automated tests for the console |
| `data/` | Runtime files (DB, logs, result files) |

---

## 10. Verification

```bash
# Manual test — run the console in a real terminal
cd ~/agentic-repos/terra-ai-agent2
source ~/.terra-ai/.env && export OPENROUTER_API_KEY
python test_tool/console.py

# Type: hello
# Expect: [HH:MM] <TerraAI> <response>
# Type: .noisy
# Expect: [HH:MM] -!- Noisy mode ON.
# Type: hello
# Expect: [HH:MM] -!- Thinking...
# Then:  [HH:MM] <TerraAI> <response>
# Type: /quit

# Automated tests
pytest tests/test_console.py -v

# With real API
pytest tests/test_console.py -v --real
```

---

## 11. KISS Compliance

From `.agentic/plan.md` §7.5:

> No separate "test harness" for automation — just **pytest**. All automated tests live in `tests/` and use mocked providers. The test tool is strictly for interactive/manual testing.

Current design follows this: automated tests use `TerraAITestClient` directly with mocked providers. The console is for interactive/manual testing.
