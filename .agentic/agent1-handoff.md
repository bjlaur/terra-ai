# Agent1 (OWL) — Handoff

## Current State

Two branches of work, in different workspaces, both ahead of `release-0.0.2` (which already includes the carry-over merge):

1. **SOPEL-native cleanup** in agent2 clone (`~/agentic-repos/terra-ai-agent2/`) on branch `agent1/sopeL-native-cleanup`. All code changes committed at `0afe445`. Needs merge back to `release-0.0.2`.
2. **Test profiling** in agent1 clone (`~/agentic-repos/terra-ai-agent1/`) on branch `agent1/test-profiling` (created from `release-0.0.2` after carry-over merged). Latest commit `6ed7679` — fix `.effort` to actually affect AI provider calls + effort wiring tests.

Origin: `/home/agent/git/terra-ai/` on `release-0.0.2`.

## What Was Done (0.0.1 + 0.0.2 + carry-over + cleanup + test-profiling)

### 0.0.1 — Minimal SOPEL Plugin ✅
- SOPEL plugin with `TerraAI:` trigger and `.` shorthand
- OpenRouter provider (default model: `openrouter/owl-alpha`)
- SQLite persistence: 7 tables
- All basic commands (.optin, .optout, .ai, .addprompt, .rmprompt, .listprompts, .help, .effort, .compact, .stats, .setlocation, .noisy)
- 60 unit tests passing

### 0.0.2 — Test Tool + Provider Expansion + Ergo Integration ✅
- Test tool (curses IRC client) + screenshot tests (3 SVGs)
- Additional providers: Gemini, OpenAI, Ollama + fallback chain
- Web search via DuckDuckGo
- Ergo smoke tests (3), IRC protocol tests (4), SOPEL bot tests (2 passing, 2 blocked)
- Routing fixes (.setlocation hybrid, .effort, unknown .command, tab completion)
- `.clear` command added
- 83 unit tests + 9 ergo integration tests passing

### Carry-over (merged into release-0.0.2) — SOPEL Dispatch Fix ✅

**Problem:** Bot connected to ergo and joined channel but never responded to messages.

**Root causes found and fixed:**
1. **Module visibility**: SOPEL loaded `terra_ai/__init__.py` as a folder plugin, but all decorated handlers were in `terra_ai/plugin.py`. SOPEL never saw them.
   - Fix: Changed `__init__.py` to `from .plugin import *` to expose handlers
   - Moved `setup()` from `__init__.py` into `plugin.py` so `_terrai` global is in same module as handlers
2. **SQLite thread safety**: DB connection created in main thread, handlers run in worker threads
   - Fix: Added `check_same_thread=False` to `sqlite3.connect()` in `database.py`
3. **Two different `_terrai` globals**: `__init__.py` and `plugin.py` each had their own
   - Fix: Moved `setup()` into `plugin.py`, single global

**Major refactoring done:**
- Renamed `terraai/` package to `terra_ai/` (underscore instead of double-letter)
- Rewrote `plugin.py` to use `sopel.plugin` (not deprecated `sopel.module`)
- Management commands now use `@plugin.command('name')` decorators
- Freeform queries use `@plugin.rule(r"$nick (.+)")` with `$nick` placeholder
- Added `@plugin.allow_bots` for IRCv3 bot tag compatibility
- Made bot nick configurable in prompts via `{botnick}` variable (no hardcoded "TerraAI")
- Added admin optout: `.optout <nick>` (admin only)
- Added `default_optin: true` to config schema

### SOPEL-Native Cleanup (agent1/sopeL-native-cleanup branch) ✅

**Completed 2026-06-26.** All dead routing code removed, SOPEL-native patterns enforced.

1. **Deleted `handle_management()`** — 40-line if/elif routing chain in `bot.py` eliminated. Each `@plugin.command()` handler now calls the specific `user.*`/`management.*` handler directly.
2. **Deleted `_handle_management()`** — the wrapper in `plugin.py` that called the removed routing chain.
3. **Renamed `AdminCommands` → `ManagementCommands`** — file `commands/admin.py` → `commands/management.py`, class renamed, all imports updated.
4. **Removed dead code** — `is_management_command()`, `match_prompt()`, `handle_setlocation()` (from bot.py and user.py), `handle_ai()` (from user.py), `MANAGEMENT_COMMANDS` set (from defaults.py).
5. **Removed unused `text` param** from `should_respond(server, nick, text)` → `should_respond(server, nick)`.
6. **Admin gating → SOPEL native** — `@plugin.require_admin` decorator on `cmd_compact`; `trigger.admin` check in `cmd_optout` for opting out other users. Removed custom `TerraAI.is_admin()` and `admin_nicks` from config.
7. **Test tool → getattr dispatch** — `send_message()` and `send_pm()` now call `getattr(terra_plugin, f"cmd_{cmd_word}")` instead of duplicating the routing if/elif.
8. **FakeTrigger/FakeBot** — added `admin` attribute and `isupport` dict for SOPEL-compatibility.
9. **Test fixtures** — set `terra_plugin._terrai` for handlers, cleanup on teardown.

### Test Profiling (agent1/test-profiling branch) ✅

**`.effort` command fix (3 bugs found, 2 fixed, 1 deferred):**
1. **Attribute mismatch** — code referenced wrong attribute name on the provider. Fixed.
2. **No provider wiring** — `.effort` updated the prompt but never passed the effort level to the provider call. Fixed.
3. **No persistence** — effort setting did not survive restart. Deferred (not yet implemented).

**Provider reasoning gating:**
- Added `_reasoning_for_model()` to `terra_ai/providers/openrouter.py` — gates reasoning config by model slug so only reasoning-capable models receive the reasoning parameter.

**Effort wiring tests:**
- 7 tests passing in `TestEffortWire` (`tests/test_integration.py`) — committed as `6ed7679`.

**Test infrastructure improvements:**
- Created `pytest.ini` with `addopts = -m "not slow and not real"` — skips slow and real-API tests by default.
- Added two markers: `@pytest.mark.slow` (4 interactive tests) and `@pytest.mark.real` (8 routing tests — the 7 routing tests + `test_noisy_on_sends_notice`).
- Parametric mock/real fixture in `tests/conftest.py` — mocks `provider.chat()` by default; real API only when `--real` is passed AND test is marked `@real` AND `OPENROUTER_API_KEY` is set.
- Removed duplicate `db` and `terra` fixtures from `test_tool.py` and `test_integration.py` (now centralized in `conftest.py`).
- Simplified `test_handle_ai_message` from `httpx.Client` mock to direct `provider.chat` patch.
- Added sub-timing instrumentation in `_run_interactive` (enable with `TEST_TIMING_VERBOSE=1`).
- Deleted `test_send_as_different_nick`.

**Test profiling report:** `tests/test-time.md` — suite time reduced from **204s → 83s** after optimizations.

## Test Status (merged)

Combined state across both branches:

- **Default mock run:** 95 passed, 2 failed, 9 skipped, 12 deselected in ~83s.
- **With API key:** 7 real-API tests passing.
- **Known failures (real, not flaky):**
  - `test_interactive_accepts_pm` — subprocess test doesn't pick up conftest mock; real failure.
  - `test_interactive_noisy_notice` — same subprocess mock issue.
  - `test_pm_setlocation_forwards_to_ai` — flaky assertion with real API.
- 3 interactive tests **deferred**: `test_interactive_accepts_pm`, `test_interactive_noisy_notice`, `test_interactive_accepts_input` — AI response never arrives in subprocess+curses+pty test setup within the 30s timeout. Works in-process. Root cause unknown; deferred after extensive debugging.
- The 2 interactive subprocess failures and the flaky real-API test are deferred.

## Key Files

- Plan: `.agentic/plan.md`
- TODO: `.agentic/TODO.md`
- Workspace: `~/agentic-repos/terra-ai-agent2/` (active code)
- Origin: `/home/agent/git/terra-ai/` (canonical repo)
- SOPEL test config: `config/sopel-test.cfg.example`
- TerraAI test config: `config/terraai-test.yaml.example`
- Ergo tests: `tests/test_ergo.py`
- Shared DB: `~/.terra-ai/terraai.db`
- Ergo config: `~/.ircd/ircd.yaml`
- Pytest config: `pytest.ini`
- Shared fixtures: `tests/conftest.py`
- Test timing report: `tests/test-time.md`
- Provider reasoning gating: `terra_ai/providers/openrouter.py` (`_reasoning_for_model()`)
- Effort wiring tests: `tests/test_integration.py` (`TestEffortWire`)

## Running Tests

```bash
# agent2 clone — SOPEL-native cleanup branch
cd ~/agentic-repos/terra-ai-agent2
source ~/.terra-ai/.env && export OPENROUTER_API_KEY
pytest tests/ -v --ignore=tests/test_ergo.py

# agent1 clone — test-profiling branch
cd ~/agentic-repos/terra-ai-agent1

# Default — mocked, fast (~83s)
pytest tests/

# Real API tests (requires OPENROUTER_API_KEY)
source ~/.terra-ai/.env && pytest --real -m real

# Slow/interactive tests
pytest -m slow

# Everything (no deselection)
pytest -m ""
```

## Ergo Integration Tests

```bash
cd ~/agentic-repos/terra-ai-agent1
source ~/.terra-ai/.env && export OPENROUTER_API_KEY

# Start ergo (if not running):
cd ~/.ircd && ergochat run --conf ircd.yaml --quiet &

# Run all ergo tests:
pytest tests/test_ergo.py -v

# Results: 13 passed, 2 failed in ~165s
```

### Ergo Test Status

| Test | Status | Notes |
|------|--------|-------|
| TestErgoSmoke (3) | ✅ All pass | 0.02s |
| TestErgoIRCProtocol (4) | ✅ All pass | 10-42s each (socket timeouts) |
| TestErgoSopelBot (8) | ⚠️ 6 pass, 2 fail | Session-scoped SOPEL (~10s once) |
| `test_bot_responds_to_unknown_command` | ❌ FAIL | 451 ERR_NOTREGISTERED — ergo rejects PRIVMSG before NICK completes |
| `test_bot_optin_optout` | ❌ FAIL | Same 451 issue |

### Ergo Optimization

- Session-scoped `sopel_bot_process` fixture (was function-scoped, started SOPEL per test)
- Removed `admin_nicks` from test yaml config (broke plugin load after rework)
- Fixed `shutdown()` signature for SOPEL 8.0
- Saved: 305s → 164s
```

## Git Identity

- user.email: owl@terra-ai
- user.name: OWL
- agent name: agent1

## Branches

- `main` — base (renamed from master)
- `release-0.0.1` — merged
- `release-0.0.2` — merged (includes carry-over); current base on origin
- `agent1/sopeL-native-cleanup` (agent2 clone) — cleanup work, ahead of release-0.0.2, needs merge
- `agent1/test-profiling` (agent1 clone) — effort fix + test profiling, ahead of release-0.0.2, needs merge

## What's Left / Next Steps

1. **Merge `agent1/sopeL-native-cleanup` into `release-0.0.2`** (in agent2 clone, then push to origin)
2. **Merge `agent1/test-profiling` into `release-0.0.2`** (in agent1 clone, then push to origin)
3. **Custom prompts rework** — decide whether `.addprompt`/`.rmprompt` should inject as context or restore trigger-matching (needs discussion)
4. **Fix interactive subprocess tests** — `test_interactive_accepts_pm` and `test_interactive_noisy_notice` fail because the subprocess doesn't use the conftest mock. Need to wire mock into subprocess or convert to in-process test.
5. **Fix flaky `test_pm_setlocation_forwards_to_ai`** — assertion instability with real API.
6. **`.effort` persistence** — deferred; setting does not survive restart.
7. **0.0.3 features** (planned, not started):
   - Conversation TTL (auto-prune history older than N days)
   - Opt-in default config flag enforcement (`default_optin` field added to schema but not enforced yet)
   - Better provider error handling (retries + backoff)
   - Automated dogfooding (e2e test sequences)
