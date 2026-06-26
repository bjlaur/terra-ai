# Rework Plan — SOPEL-Native Plugin Architecture

**Date:** 2026-06-25 (updated 2026-06-26)
**Agent:** agent2 (original), OWL (cleanup pass)
**Status:** In progress — big rewrite done, cleanup pass remaining

---

## Context

Our plugin was originally implemented using deprecated SOPEL APIs (`@sopel.module.rule`) with routing logic split across `plugin.py`, `bot.py`, and `test_tool/chat.py`. OWL (agent1) rewrote it to use `@plugin.command()` and `@plugin.rule()` — that rewrite is **already merged** into `release-0.0.2` (commit `d96c55c`).

**What's done (carry-over merge):**
- `plugin.py` rewritten to SOPEL-native (`@sopel_plugin.command()`, `@sopel_plugin.rule(r'$nick (.+)')`, `@sopel_plugin.allow_bots`)
- `_KNOWN_NICK_COMMANDS` set added to avoid double-processing addressed management commands
- Package renamed `terraai/` → `terra_ai/`
- Config-driven `trigger_char` and `bot_nick`
- `{botnick}` interpolation in prompts

**What remains (cleanup pass):**
1. **Delete `handle_management()`** — the 40-line if/elif chain in `bot.py` is pure routing. SOPEL already routes via `@plugin.command()` decorators. Each plugin command handler should call the specific `user.*` / `management.*` handler directly.
2. **Remove `MANAGEMENT_COMMANDS` set** — only read by `is_management_command()`, which only existed to support `handle_management()`. Goes away with it.
3. **Remove `match_prompt()`** — dead code, called nowhere. Custom prompts rework (context injection) is out of scope for this pass.
4. **Update `test_tool/chat.py`** — call the same real handlers the plugin commands call; read config instead of hardcoding `"."` and `"<TerraAI>"`.
5. **Rename `AdminCommands` → `ManagementCommands`** — "admin" implies permission-gating; these commands manage bot state. File: `commands/admin.py` → `commands/management.py`.
6. **Delete dead `handle_ai()` from `user.py`** — never called. `.ai` is handled in `plugin.py:cmd_ai()`.
7. **Remove unused params** — `should_respond(server, nick, text)` → `should_respond(server, nick)`; `handle_setlocation(server, channel, nick, args)` loses the unused `channel` param.

**Core principle: The plugin should be structured the way SOPEL expects.** No routing if/elif chain in `bot.py`, no `MANAGEMENT_COMMANDS` set, no dead code, no misleading names.

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

### 1. `plugin.py` used deprecated `@sopel.module.rule` — ✅ FIXED
~~Our `handle_shorthand()` manually parsed `.command args` with regex.~~ OWL rewrote plugin.py to SOPEL-native decorators. `@plugin.command()` handles prefix matching and routing automatically.

### 2. `should_respond()` checked manually — ✅ FIXED
Now at the top of each handler via `_guard()` pattern. SOPEL doesn't have a built-in opt-in system — we keep the check in each handler.

### 3. Custom prompt matching in routing — ⚠️ DEAD CODE
`match_prompt()` in `prompts/manager.py` is called by nothing. The custom prompts rework (context injection instead of trigger matching) is out of scope for this pass, but the dead method should be removed.

### 4. `handle_management()` is pure routing — ⚠️ DELETE
The 40-line if/elif chain in `bot.py` (lines 72-116) maps command strings to handler methods. SOPEL already routes via `@plugin.command()` decorators. Each plugin command handler should call the specific `user.*` / `admin.*` handler directly. No middleman needed.

### 5. `MANAGEMENT_COMMANDS` set is unnecessary — ⚠️ DELETE
Only read by `is_management_command()`, which only existed to support `handle_management()`. Both go away together.

### 6. Opt-in/opt-out not in SOPEL style — ✅ FIXED
`.optin` and `.optout` are now `@plugin.command('optin')` / `@plugin.command('optout')`.

---

## New Architecture

### `plugin.py` — Thin SOPEL wrapper — ⚠️ EXPAND (more handlers, no middleman)

Currently each `@plugin.command()` handler calls `_handle_management()` → `handle_management()` → if/elif chain. After cleanup, each handler calls the specific `user.*` / `admin.*` method directly. Plugin gets fatter (one function per command, ~5 lines each) but the routing layer below it disappears.

```python
# AFTER cleanup — example for @sopel_plugin.command("optin"):
@sopel_plugin.command("optin")
def cmd_optin(bot, trigger):
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    if not terra.should_respond(server, nick, None):
        return
    bot.say(terra.user.handle_optin(server, nick))

# .setlocation — hybrid: store locally, then forward to AI
@sopel_plugin.command("setlocation")
def cmd_setlocation(bot, trigger):
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)
    if not terra.should_respond(server, nick, None):
        return
    args = (trigger.group(2) or "").strip()
    terra.user.handle_setlocation(server, channel, nick, args)
    text = f"{nick} .setlocation {args}"  # forward to AI
    response = terra.handle_ai_message(server, channel, nick, text)
    if response:
        bot.say(response)
```

**Delete:** `_handle_management()` function (lines 63-75), `is_management_command()` call in `addressed_freeform` (line 185).

### `bot.py` — Pure business logic (no routing) — ⚠️ SHRINK

Delete `handle_management()` (72-116), `is_management_command()` (68-70), `handle_setlocation()` (165-170). The `TerraAI` class shrinks to:
- `should_respond(server, nick, text)` — opt-in + self-nick check
- `is_opted_in(server, nick)` — DB lookup
- `is_admin(nick)` — admin list check
- `handle_ai_message(server, channel, nick, text, include_history=True)` — the AI call

No routing. No dispatching. Just state + the AI call.

### `admin.py` — Management command handlers — ✅ IMPLEMENTED, no changes needed

Already has `handle_listprompts`, `handle_rmprompt`, `handle_addprompt`, `handle_compact`, `handle_clear`, `handle_stats`, `handle_help`. These stay exactly as-is — plugin command handlers will call them directly.

### `prompts/manager.py` — Remove `match_prompt()` — ⚠️ TODO

`match_prompt()` (lines 71-84) is called by nothing. Remove it. Custom prompt *storage* (add/remove/list) stays; only the trigger-matching is removed.

```python
# REMOVE: match_prompt() method (lines 71-84)
# KEEP: add_prompt(), remove_prompt(), remove_prompt_by_index(), list_prompts()
# KEEP: is_management_command() — wait, no, remove that too (see below)
```

Actually `is_management_command()` also goes — it reads `MANAGEMENT_COMMANDS` which we're removing. Both methods are dead weight.

### `prompts/defaults.py` — Remove `MANAGEMENT_COMMANDS` — ⚠️ TODO

SOPEL already tracks commands via `@plugin.command()` decorators (`bot.commands`).
We don't need to maintain a separate set.

```python
# REMOVE this entire set — no longer needed
# MANAGEMENT_COMMANDS = { ... }

# Keep:
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_EFFORT = "high"
```

### `commands/user.py` — ⚠️ Changes

- **Delete `handle_setlocation()`** (lines 57-71) — with `handle_management()` gone, the plugin's `cmd_setlocation` handler does the storage inline (`prompts.add_prompt(...)`) then forwards to AI.
- **Delete `handle_ai()`** (lines 73-75) — dead code, never called. `.ai` command is handled in `plugin.py:cmd_ai()`.

Remaining: `handle_optin`, `handle_optout`, `handle_noisy`, `is_noisy`, `handle_effort`.

---

## What Happens to Custom Prompts

### Status: DEFERRED — rework after cleanup pass

Custom prompts need a separate design discussion. The cleanup pass only removes `match_prompt()` (dead code, called by nothing). The storage layer (`.addprompt`/`.rmprompt`/`.listprompts`) stays.

**Still works after cleanup:**
- `.addprompt wea sunny` — stores `wea -> sunny` in DB
- `.rmprompt 1` — removes it
- `.listprompts` — lists them

**No longer works after cleanup:**
- `.wea` returning "sunny" directly via `match_prompt()` — removed as dead code

**Out of scope (next task after this):**
- Whether stored prompts should be injected as always-on context
- Whether trigger-matching should be restored in a SOPEL-consistent way
- How this interacts with `@plugin.command()` registration

---

## What Happens to the Test Tool

### `test_tool/chat.py` — Call real handlers + read config — ⚠️ TODO

The current test tool reimplements the if/elif routing chain from `bot.py`. It should instead:

1. **Call `handle_management()` directly** for `.command` text — this is the real dispatch point, already wired up in `bot.py`.
2. **Read `trigger_char` from config** instead of hardcoding `"."` — currently `send_message()` and `send_pm()` hardcode `f"{trigger_char}ai "` and `text.startswith(".")`.
3. **Read `botnick` from config** in `redraw_chat()` — currently the rendering function hardcodes `<TerraAI>` instead of using the configured bot nick.

**Why NOT use SOPEL's internal dispatch:** SOPEL's `bot.dispatch()` requires a running bot instance. Calling handler functions directly (via `handle_management()` and `handle_ai_message()`) is simpler and tests the real business logic. The routing if/elif in the test tool is the only duplication, and it's minimal.

**Behavior changes from this cleanup:**
- Config-driven `trigger_char` works in test tool (currently hardcoded to `.`)
- Config-driven `botnick` renders correctly in chat UI (currently hardcoded to `<TerraAI>`)
- Removing `is_management_command()` from the test tool flow — `.commands` go directly to `handle_management()`

---

## Execution Order

### Already done (carry-over merge `d96c55c`)

| Step | Description | Status |
|------|-------------|--------|
| 1 | Rewrite `plugin.py` with `@plugin.command` and `@plugin.rule` | ✅ Done |
| 3 | Update `help` command text | ✅ Done |
| 4 | Update README.md commands table | ✅ Done |

### Cleanup pass (remaining)

| Step | Description | Files Changed |
|------|-------------|---------------|
| C1 | Delete `handle_management()`, `is_management_command()`, `handle_setlocation()` from `bot.py`; rewrite each `@plugin.command()` handler in `plugin.py` to call `user.*`/`management.*` directly; rename `AdminCommands` → `ManagementCommands` (file + class + imports); remove unused `text` param from `should_respond()` | `terra_ai/bot.py`, `terra_ai/plugin.py`, `terra_ai/commands/admin.py` → `management.py` |
| C2 | Remove `MANAGEMENT_COMMANDS` set | `terra_ai/prompts/defaults.py` |
| C3 | Remove `is_management_command()`, `match_prompt()` from `manager.py` | `terra_ai/prompts/manager.py` |
| C4 | Delete `handle_setlocation()`, `handle_ai()` from `user.py` | `terra_ai/commands/user.py` |
| C5 | Update test tool to call real handlers + read config | `test_tool/chat.py` |
| C6 | Remove dead-code tests; rewrite `test_handle_management_*` to call handlers directly | `tests/test_commands.py`, `tests/test_integration.py` |
| C7 | Update docs (CHANGELOG, TODO) | `CHANGELOG.md`, `.agentic/TODO.md` |
| C8 | Run full suite, fix failures | all |

**Out of scope (needs discussion):**
- Custom prompts context injection (`.wea` → "sunny" as always-on behavior)

## Risks

- **Breaking existing tests** — C1-C4 remove `handle_management()` which tests call directly. C6 rewrites those tests.
- **Custom prompts behavior change** — `.wea` no longer returns "sunny" directly. Already non-functional (nothing calls `match_prompt()`).
- **Test tool config coupling** — C5 makes the test tool respect config, which is correct but means tests that relied on hardcoded `"."` need updating.
- **Plugin.py grows** — each command handler is now 3-5 lines instead of 1-line delegating to `_handle_management()`. Net code count stays similar since `handle_management()` is deleted.

## Critical Files

| File | Change |
|------|--------|
| `terra_ai/bot.py` | Delete `handle_management()`, `is_management_command()`, `handle_setlocation()`; rename `admin` → `management`; remove `text` param from `should_respond()` |
| `terra_ai/plugin.py` | Rewrite each `@plugin.command()` handler to call `user.*`/`management.*` directly; delete `_handle_management()`; update `addressed_freeform` |
| `terra_ai/commands/admin.py` → `management.py` | Rename file + class `AdminCommands` → `ManagementCommands` |
| `terra_ai/commands/user.py` | Delete `handle_setlocation()`, `handle_ai()` |
| `terra_ai/prompts/defaults.py` | Delete `MANAGEMENT_COMMANDS` set |
| `terra_ai/prompts/manager.py` | Delete `is_management_command()`, `match_prompt()`; remove import |
| `test_tool/chat.py` | Rewrite to call real handlers; read config for trigger_char/botnick; update `admin` → `management` |
| `tests/test_commands.py` | Delete `test_is_management_command`, `test_add_and_match_prompt` |
| `tests/test_integration.py` | Delete/rewrite `test_handle_management_*`; update imports for rename |
| `CHANGELOG.md` | Add cleanup entry |
| `.agentic/TODO.md` | Update rework status |

## Verification

```bash
# Dead code removed
grep -rn "handle_management\|_handle_management\|MANAGEMENT_COMMANDS\|is_management_command\|match_prompt" --include="*.py" . | grep -v .git/ | grep -v __pycache__  # should be empty

# Unit tests
python -m pytest tests/test_commands.py tests/test_database.py tests/test_integration.py -v

# Test tool tests
python -m pytest tests/test_tool.py::TestTestTool tests/test_tool.py::TestPM tests/test_tool.py::TestNoisy -v

# Interactive tests (2 pre-existing failures expected)
python -m pytest tests/test_tool.py::TestInteractiveMode -v

# Full suite
source ~/.terra-ai/.env && python -m pytest tests/ -v --ignore=tests/test_ergo.py

# Manual test tool
python test_tool/chat.py --test
```

Expected: no new failures. The 2 interactive test failures (`test_interactive_noisy_notice`, `test_interactive_accepts_pm`) are pre-existing — AI doesn't respond in test harness.

---

## Discrepancies Between Original Plan and Current State

| Original Plan | Reality | Resolution |
|---|---|---|
| Step 1: Rewrite plugin.py to SOPEL-native | Already done in `release-0.0.2` | Marked ✅ |
| Step 2: Remove `MANAGEMENT_COMMANDS` | Still exists in `defaults.py` | Cleanup step C2 |
| Step 3: Update help command | Already done | Marked ✅ |
| Step 4: Update README | Already done | Marked ✅ |
| Step 5: Update test tool | Still duplicates routing | Cleanup step C5 |
| Step 6: Update tests | Partially done (carry-over added `TestPluginRules`) | Cleanup step C6 |
| Remove `match_prompt()` | Still exists, called by nothing | Cleanup step C3 |
| `terraai/` paths in code examples | Already renamed to `terra_ai/` | Plan updated |
| `from terraai.bot import TerraAI` in examples | Already `from terra_ai.bot import TerraAI` | Plan updated |
| `.setlocation` hybrid → return confirmation string | Still returns `None` (forward to AI) | Keep as-is (original plan's "risk" was wrong) |
| Test tool SOPEL dispatch integration | Too complex for this pass | Deferred; direct handler calls suffice |
| `handle_management()` — original plan didn't mention this | 40-line if/elif routing chain in `bot.py` | **Delete it** — SOPEL handles routing now |
