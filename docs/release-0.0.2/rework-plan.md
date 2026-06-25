# Rework Plan — SOPEL-Native Plugin Architecture

**Date:** 2026-06-25
**Agent:** agent2
**Status:** Draft

---

## Context

Our plugin was implemented using deprecated SOPEL APIs (`@sopel.module.rule`) and has routing logic split across `plugin.py`, `bot.py`, and `test_tool/chat.py`. OWL (agent1) has shown the correct approach: use `@plugin.command()` for management commands and `@plugin.rule(r'$nick (.+)')` for freeform addressed messages.

**Core principle: The plugin should be structured the way SOPEL expects.** No `MANAGEMENT_COMMANDS` set, no duplicated routing, no custom `dispatch()` method that replicates what SOPEL already provides.

---

## What SOPEL Gives Us

### `@plugin.command('name')`
Creates a `.name` command. SOPEL handles prefix matching, routing, and `trigger.group(2)` parsing automatically. Anyone can run it.

### `@plugin.command('name') + @plugin.require_admin`
Same, but only admins/owners can run it. SOPEL checks `trigger.admin` before calling.

### `@plugin.rule(r'$nick (.+)')`
Matches `TerraAI: hello` style messages. SOPEL replaces `$nick` with the bot's nick. `trigger.group(1)` is the rest of the message.

### `@plugin.require_privmsg` / `@plugin.require_chanmsg`
Restrict where a command works.

### `@plugin.priority('high'/'medium'/'low')`
Control execution order when multiple rules match.

### Key insight: SOPEL handles all routing
When a message comes in, SOPEL:
1. Checks all registered rules/commands
2. Finds matching ones
3. Sorts by priority
4. Calls each one

So we don't need to check `is_management_command()` or `should_respond()` inside our handlers — SOPEL routes to the right handler based on the decorators.

---

## Problems With Current Code

### 1. `plugin.py` uses deprecated `@sopel.module.rule`
```python
# WRONG (deprecated since SOPEL 7.1, removed in 9.0)
from sopel.module import rule
@sopel.module.rule("^TerraAI[:,] (.*)")

# CORRECT
from sopel import plugin
@plugin.rule(r'$nick (.+)')
@plugin.allow_bots
```

### 2. Manual command parsing in `plugin.py`
Our `handle_shorthand()` manually parses `.command args` with regex. SOPEL's `@plugin.command()` does this automatically.

### 3. `should_respond()` checked manually
We check `is_opted_in()` in `handle_trigger()` and `handle_shorthand()`. SOPEL doesn't have a built-in opt-in system — we need to keep this check, but it should be at the top of each handler (or use a decorator/uniform pattern).

### 4. Custom prompt matching in routing
`handle_shorthand()` line 114 calls `match_prompt()` and injects context. This is fragile and not how SOPEL plugins work.

### 5. `test_tool/chat.py` duplicates routing
The test tool reimplements the if/elif chain from `plugin.py`. It should use the real handlers.

### 6. `MANAGEMENT_COMMANDS` set is unnecessary
If we use `@plugin.command()` for each management command, we don't need a set to check against. SOPEL routes `.optin` to the `cmd_optin` handler automatically.

### 7. Opt-in/opt-out not in SOPEL style
`.optin` and `.optout` should be `@plugin.command('optin')` etc., not entries in a routing if/elif chain.

---

## New Architecture

### `plugin.py` — Thin SOPEL wrapper (~50 lines)

```python
from sopel import plugin as sopel_plugin
from terraai.bot import TerraAI
from terraai.config import load_config

_terrai = None

def setup(bot):
    global _terrai
    config_path = getattr(bot.config, 'terraai', None)
    _terrai = TerraAI(load_config(config_path or "config/terraai.yaml"))

def _guard(bot, trigger):
    """Shared guard: opt-in check + should_respond."""
    if not _terrai.should_respond(_server(bot), trigger.nick, trigger):
        return False
    return True

def _server(bot):
    return bot.isupport.get('NETWORK', 'unknown')

def _channel(trigger):
    return trigger.sender or "#unknown"

# ── Management commands (anyone can run) ──────────────────────────────

@sopel_plugin.command('optin')
@sopel_plugin.example('.optin')
def cmd_optin(bot, trigger):
    if not _guard(bot, trigger): return
    bot.say(_terrai.user.handle_optin(_server(bot), trigger.nick))

@sopel_plugin.command('optout')
@sopel_plugin.example('.optout')
def cmd_optout(bot, trigger):
    # Don't guard — users should always be able to opt out
    bot.say(_terrai.user.handle_optout(_server(bot), trigger.nick))

# ... same pattern for: noisy, ai, setlocation, effort, help, compact, clear, stats

# ── Admin-only commands ────────────────────────────────────────────────

@sopel_plugin.command('compact')
@sopel_plugin.require_admin("Admin only.")
def cmd_compact(bot, trigger):
    bot.say(_terrai.admin.handle_compact(_server(bot), _channel(trigger), trigger.nick))

# ── Freeform addressed queries: TerraAI: <message> ────────────────────

@sopel_plugin.rule(r'$nick (.+)')
@sopel_plugin.allow_bots
@sopel_plugin.priority('high')
def addressed_freeform(bot, trigger):
    if not _guard(bot, trigger): return
    text = (trigger.group(1) or '').strip()
    response = _terrai.handle_ai_message(
        _server(bot), _channel(trigger), trigger.nick, text)
    if response:
        bot.say(response)

# ── Unaddressed messages in channel (optional: respond to all) ────────

# If we want the bot to respond to all messages in channel (not just
# $nick: style), add a low-priority rule that catches everything else.
# Uncomment if desired:
#
# @sopel_plugin.rule(r'(.*)')
# @sopel_plugin.priority('low')
# def catch_all(bot, trigger):
#     if not _guard(bot, trigger): return
#     # Don't respond to other bot commands
#     if trigger.startswith(bot.config.core.prefix):
#         return
#     text = trigger.group(1) or trigger or ''
#     response = _terrai.handle_ai_message(
#         _server(bot), _channel(trigger), trigger.nick, text)
#     if response:
#         bot.say(response)
```

### `bot.py` — Pure business logic (no routing)

Remove `handle_setlocation()` from `bot.py`. Move `.setlocation` handling into `admin.py`:

```python
# terraai/bot.py — TerraAI class
class TerraAI:
    def __init__(self, config):
        # ... unchanged ...

    def should_respond(self, server, nick, text):
        """Check opt-in + not-self. Plugin calls this in _guard()."""
        if not self.is_opted_in(server, nick):
            return False
        if nick == self.config.bot.get("bot_nick", "TerraAI"):
            return False
        return True

    def handle_ai_message(self, server, channel, nick, text, include_history=True):
        # ... unchanged — assembles context, calls provider ...

    def handle_management(self, server, channel, nick, text):
        # ... dispatches to admin/user handlers ...
        # KEEP the .setlocation hybrid (returns None → caller forwards to AI)
```

### `admin.py` — Management command handlers

```python
# terraai/commands/admin.py

class AdminCommands:
    def handle_optin(self, server, nick):
        users = UserStore(self.db)
        users.opt_in(server, nick)
        return "You are now opted in. TerraAI will respond to you."

    def handle_optout(self, server, nick):
        users = UserStore(self.db)
        users.opt_out(server, nick)
        return "You are opted out. Your history has been forgotten."

    def handle_compact(self, server, channel, nick):
        if not self.is_admin(nick):
            return "Permission denied. .compact is admin-only."
        # ... compaction logic ...

    # ... handle_help, handle_clear, handle_stats ...
    # NOTE: .setlocation stays in bot.py handle_management() as hybrid (returns None)
    # Custom prompts (.addprompt/.rmprompt/.listprompts) — TBD, needs discussion
```

**Note:** `.setlocation` hybrid is kept — `handle_management()` returns `None` as a signal for the plugin to forward to AI. The plugin's `addressed_freeform` handler checks for this and forwards.

### `prompts/manager.py` — Remove `match_prompt()`

```python
# TBD — custom prompts need a separate discussion
# Keep existing code as-is for now
```

### `prompts/defaults.py` — Remove `MANAGEMENT_COMMANDS`

SOPEL already tracks commands via `@plugin.command()` decorators (`bot.commands`).
We don't need to maintain a separate set.

```python
# REMOVE this entire set — no longer needed
# MANAGEMENT_COMMANDS = { ... }

# Keep:
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_EFFORT = "high"
```

If `.help` needs to list commands, use `bot.commands` or hardcode the list in the help text.

### `commands/user.py` — Simplify

```python
# terraai/commands/user.py
class UserCommands:
    def handle_optin(self, server, nick): ...
    def handle_optout(self, server, nick): ...
    def handle_noisy(self, server, nick): ...
    def is_noisy(self, server, nick): ...
    # REMOVE: handle_setlocation (moved to admin.py)
    def handle_effort(self, args): ...
```

---

## What Happens to Custom Prompts

### Decision: Keep as context injection, remove trigger matching

**Still works:**
- `.addprompt wea sunny` — stores `wea -> sunny` in DB
- `.rmprompt 1` — removes it
- `.listprompts` — lists them
- On every AI call, stored prompts are injected as system context: `"Registered prompts:\n.wea -> sunny"`

**No longer works:**
- `.wea` returning "sunny" directly (trigger matching removed)

This is the right tradeoff — custom prompts are now "always-on context" rather than "triggered shortcuts." Simpler, more predictable, matches how `.setlocation` already works.

---

## What Happens to the Test Tool

### `test_tool/chat.py` — Call real handlers via SOPEL

The test tool should create a real SOPEL bot instance in-process and call the actual `plugin.py` handlers. This is what the ergo integration tests do, but without needing a running IRC server.

**Approach:** Use SOPES's internal bot dispatch:

```python
class TerraAITestClient:
    def __init__(self, config_path="config/terraai.yaml"):
        # Load config
        self.config = load_config(config_path)
        self.terra = TerraAI(self.config)

    def send_message(self, text):
        """Send a message through the real SOPEL plugin handlers."""
        # Create fake bot and trigger
        bot = FakeBot()
        trigger = FakeTrigger("tester", "#terra-ai", text)

        # Let SOPEL route to the right handler
        # Option A: call handlers directly (knowing the routing)
        # Option B: use SOPEL's internal dispatch (more realistic)
        ...
```

**The challenge:** SOPEL's `bot.dispatch()` is designed for use with a running bot. Calling it from tests requires setting up a minimal SOPEL environment.

**Simpler approach for now:** Call the handler functions directly (since they're just functions), passing fake `bot` and `trigger`:

```python
from terraai import plugin as terra_plugin

def send_message(self, text):
    bot = FakeBot()
    trigger = FakeTrigger("tester", "#terra-ai", text)

    # SOPEL would route based on decorators — we replicate that
    # by checking the text pattern and calling the right handler
    for handler in terra_plugin._handlers:
        if handler.matches(bot, trigger):
            handler(bot, trigger)

    return bot.messages
```

This still has some routing duplication, but it calls the REAL handler functions (not reimplementations). The only duplication is "which handler to call" — which is minimal.

**Better approach (future):** Use SOPEL's actual dispatch. This requires more setup but is the "right" way.

---

## Execution Order

| Step | Description | Files Changed |
|------|-------------|---------------|
| 1 | Rewrite `plugin.py` with `@plugin.command` and `@plugin.rule` | `terraai/plugin.py` |
| 2 | Remove `MANAGEMENT_COMMANDS` set | `terraai/prompts/defaults.py` |
| 3 | Update `help` command text (hardcode list) | `terraai/commands/admin.py` |
| 4 | Update README.md commands table | `README.md` |
| 5 | Update test tool to call real handlers | `test_tool/chat.py` |
| 6 | Update tests | `tests/test_tool.py`, `tests/test_integration.py` |
| 7 | Run full suite, fix failures | all |

**Out of scope (needs discussion):**
- Custom prompts (`.addprompt`, `.rmprompt`, `.listprompts`, `match_prompt()`)
- `.setlocation` hybrid behavior (keep as-is for now)

## Risks

- **Breaking existing tests** — Steps 1-3 change behavior. Steps 9-10 fix tests.
- **`.setlocation` behavior change** — Returns confirmation string instead of forwarding to AI. The AI still sees location in context. But the user gets an immediate confirmation.
- **Custom prompts behavior change** — `.wea` no longer returns "sunny" directly. Users who relied on this will be confused. But the feature was already broken in the test tool.
- **SOPEL version compatibility** — `@plugin.command` requires SOPEL 7.1+. Our config uses SOPEL 8.0+, so this is fine.
- **Test tool SOPEL setup** — Step 8 may be complex if we want to use real SOPEL dispatch. Start with direct handler calls.

## Verification

```bash
# Unit tests
python -m pytest tests/test_commands.py tests/test_database.py tests/test_integration.py -v

# Test tool tests
python -m pytest tests/test_tool.py -v

# --real tests
source ~/.terra-ai/.env && python -m pytest tests/test_tool.py::TestRealAPI -v

# Interactive test tool
python test_tool/chat.py

# Screenshots
python test_tool/screenshot_test.py

# Full suite
source ~/.terra-ai/.env && python -m pytest tests/ -v --ignore=tests/test_ergo.py
```

Expected: all pass.
