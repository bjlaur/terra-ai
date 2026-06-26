# Agent1 (OWL) — Handoff

## Current State

Work on `agent1/sopeL-native-cleanup` branch in agent2 clone (`~/agentic-repos/terra-ai-agent2/`).
All code changes committed at `0afe445`. Need to merge back to `release-0.0.2` and update docs.
Origin: `/home/agent/git/terra-ai/` on `release-0.0.2`.

## What Was Done (0.0.1 + 0.0.2 + carry-over + cleanup)

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

### Carry-over (agent1/carry-over-0.0.2 branch) — SOPEL Dispatch Fix ✅

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

## Test Status

- 94 passed, 9 skipped (need API key), 7 real-API tests passing (with key)
- 3 interactive tests **deferred**: `test_interactive_accepts_pm`, `test_interactive_noisy_notice`, `test_interactive_accepts_input` — AI response never arrives in subprocess+curses+pty test setup within the 30s timeout. Works in-process. Root cause unknown; deferred after extensive debugging.

## What's Left / Next Steps

1. **Merge `agent1/sopeL-native-cleanup` into `release-0.0.2`** (in agent2 clone, then push to origin)
2. **Custom prompts rework** — decide whether `.addprompt`/`.rmprompt` should inject as context or restore trigger-matching (needs discussion)
3. **Interactive test failures** — deferred, but should be investigated eventually (subprocess AI call issue)
4. **0.0.3 features** (planned, not started):
   - Conversation TTL (auto-prune history older than N days)
   - Opt-in default config flag enforcement
   - Better provider error handling (retries + backoff)
   - Automated dogfooding (e2e test sequences)

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

## Running Tests

```bash
cd ~/agentic-repos/terra-ai-agent2
source ~/.terra-ai/.env && export OPENROUTER_API_KEY
pytest tests/ -v --ignore=tests/test_ergo.py
```

## Git Identity

- user.email: owl@terra-ai
- user.name: OWL
- agent name: agent1

## Branches

- `main` — base (renamed from master)
- `release-0.0.1` — merged
- `release-0.0.2` — current base (origin)
- `agent1/sopeL-native-cleanup` — cleanup work (ahead of release-0.0.2, needs merge)
