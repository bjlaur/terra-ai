# Agent1 (OWL) — Handoff

## Current State

All work merged to `release-0.0.2` on origin. Workspace: `~/agentic-repos/terra-ai-agent1/`.
Branch: `agent1/carry-over-0.0.2` (created from release-0.0.2).

## What Was Done (0.0.1 + 0.0.2 + carry-over)

### 0.0.1 — Minimal SOPEL Plugin ✅
- SOPEL plugin with `TerraAI:` trigger and `.` shorthand
- OpenRouter provider (default model: `openrouter/owl-alpha`)
- SQLite persistence: 7 tables
- All basic commands (.optin, .optout, .ai, .addprompt, .rmprompt, .listprompts, .help, .effort, .compact, .stats, .setlocation, .noisy)
- 60 unit tests passing

### 0.0.2 — Test Tool + Provider Expansion + Ergo Integration ✅
- Test tool (Textual IRC client) + screenshot tests (3 SVGs)
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
- Renamed plugin from `terraai` to `terra_ai` in SOPEL config
- Rewrote `plugin.py` to use `sopel.plugin` (not deprecated `sopel.module`)
- Management commands now use `@plugin.command('name')` decorators
- Freeform queries use `@plugin.rule(r"$nick (.+)")` with `$nick` placeholder
- Added `@plugin.allow_bots` for IRCv3 bot tag compatibility
- SOPEL config now uses `prefix = -` (not `.`)
- Added `default_optin: true` to config schema
- Added admin optout of other nicks: `.optout <nick>` (admin only)
- Made bot nick configurable in prompts via `{botnick}` variable (no hardcoded "TerraAI")
- Added `COMMAND_PREFIX` and `BOT_NICK` constants to ergo tests (no hardcoded values)
- Added rules 14 + 15 to DEVELOPMENT.md about no hardcoded nicks/prefixes

**Verified working:**
- `-help` → lists commands ✓
- `-optin` / `-optout` → opt in/out ✓
- `TerraAI: hello` → AI responds via real API ✓
- Opt-out correctly suppresses responses ✓

## Key Files Modified (carry-over)

- `terra_ai/__init__.py` — thin re-export: `from .plugin import *`
- `terra_ai/plugin.py` — all handlers, setup(), shutdown(), @plugin.command(), @plugin.rule()
- `terra_ai/bot.py` — passes config to PromptManager, updated optout dispatch
- `terra_ai/commands/user.py` — `.optout` supports admin optout of other nicks
- `terra_ai/config.py` — added `default_optin: bool = True`
- `terra_ai/database.py` — `check_same_thread=False`
- `terra_ai/prompts/defaults.py` — `{botnick}` variable instead of hardcoded "TerraAI"
- `terra_ai/prompts/manager.py` — interpolates `{botnick}` in system prompt and context seed
- `config/sopel-test.cfg.example` — `prefix = -`, `help_prefix = -`, `terra_ai` in enable list
- `tests/test_ergo.py` — uses `COMMAND_PREFIX` and `BOT_NICK` constants
- `tests/test_integration.py` — updated TestPluginRules for new handler names
- `.agentic/DEVELOPMENT.md` — added rules 14 (no hardcoded nick) and 15 (no hardcoded prefix)
- `docs/misc/claude-didn't-listen.md` — report about hardcoded prefix mistake

## Test Status

- 94 passed, 5 failed (ergo bot tests need re-run after latest fixes), 6 skipped
- The 5 failures are in TestErgoSopelBot — likely now passing after the latest fixes (nick interpolation, test constants)
- Need to re-run full suite to confirm

## What's Left / Next Steps

1. **Re-run full test suite** — verify all pass after latest changes
2. **Commit** the carry-over work on branch `agent1/carry-over-0.0.2`
3. **0.0.3 features** (planned, not started):
   - Conversation TTL (auto-prune history older than N days)
   - Opt-in default config flag (`default_optin` field added to schema but not enforced yet)
   - Better provider error handling (retries + backoff)
   - Automated dogfooding (e2e test sequences)

## Key Files

- Plan: `.agentic/plan.md`
- TODO: `.agentic/TODO.md`
- Workspace: `~/agentic-repos/terra-ai-agent1/`
- Origin: `/home/agent/git/terra-ai/`
- SOPEL test config: `config/sopel-test.cfg.example`
- TerraAI test config: `config/terraai-test.yaml.example`
- Ergo tests: `tests/test_ergo.py`
- Shared DB: `~/.terra-ai/terraai.db`
- Ergo config: `~/.ircd/ircd.yaml`

## Running Tests

```bash
cd ~/agentic-repos/terra-ai-agent1
source ~/.terra-ai/.env && export OPENROUTER_API_KEY
pytest tests/ -v
```

## Ergo Integration Tests

```bash
cd ~/agentic-repos/terra-ai-agent1
source ~/.terra-ai/.env && export OPENROUTER_API_KEY
ERGO_TEST=1 pytest tests/test_ergo.py -v
```

## Git Identity

- user.email: owl@terra-ai
- user.name: OWL
- agent name: agent1

## Branches

- `main` — base (renamed from master)
- `release-0.0.1` — merged
- `release-0.0.2` — current base
- `agent1/carry-over-0.0.2` — current branch (carry-over work)
