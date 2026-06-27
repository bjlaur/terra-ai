# 0.0.2 Feature — Test Tool + Provider Expansion + Ergo Integration

OWL — Updated 2026-06-25

## What We're Building

0.0.2 builds on 0.0.1 by adding the interactive test tool, additional AI providers with fallback, web search, and integration testing with ergochat.

## Scope

### In 0.0.2
- **Test tool** — irssi-like terminal UI using Textual for interactive testing
- **Test tool tests** — automated tests with screenshots + visual inspection
- **Additional providers** — Gemini, OpenAI, Ollama alongside OpenRouter
- **Provider fallback chain** — try next provider if primary fails
- **Web search** — DuckDuckGo (free, no API key)
- **Ergo integration testing** — real IRC server for end-to-end tests
  - Smoke tests: port, config, socket
  - IRC protocol tests: register, join, channel messages, private messages
  - SOPEL bot tests: real SOPEL process with TerraAI plugin, SSL/TLS to ergo
- **SOPEL + TerraAI test configs** — committed .example files for deployment
  - `config/sopel-test.cfg.example` — minimal plugin set (admin, adminchannel, ping, reload, safety, tell, coretasks, terra_ai)
  - `config/terra_ai-test.yaml.example` — test TerraAI config (separate DB path)
  - `.agentic/ircd.yaml.example` — ergo IRC server config example
- **Missing 0.0.1 commands** — `.noisy`, `.setlocation`, `.help`, `.effort`, `.compact`, `.stats`

### Architecture additions
- Test tool: `test_tool/chat.py`
- New providers: `terra_ai/providers/gemini.py`, `openai.py`, `ollama.py`
- Web search: `terra_ai/tools/web_search.py`
- Integration tests: `tests/test_ergo.py`
- Config examples: `config/sopel-test.cfg.example`, `config/terra_ai-test.yaml.example`

### SOPEL Plugin Selection
Only admin-essential plugins loaded (no games/bloat):
- `admin` — bot admin commands (join, part, quit)
- `adminchannel` — channel management (op, kick, mode)
- `ping` — CTCP ping response
- `reload` — hot-reload plugins
- `safety` — URL safety
- `tell` — message relay
- `coretasks` — SOPEL core (required)
- `terra_ai` — our plugin

No SOPEL built-in `help` — TerraAI has its own `.help`.

### Deferred to later
- Multi-server support (add `server` column to all queries)
- Rate limiting
- Containerfile polish (based on user's run script pattern)

### Carry-over Fixes (agent1/carry-over-0.0.2)

- SOPEL module visibility fix (`from .plugin import *` in `__init__.py`)
- SOPEL `@plugin.allow_bots` decorators for IRCv3 compatibility
- SQLite `check_same_thread=False` for multi-threaded handler execution
- Package rename: `terraai/` → `terra_ai/`
- SOPEL plugin renamed from `terraai` to `terra_ai`
- Configurable botnick via `{botnick}` in prompts (no hardcoded "TerraAI")
- Added `COMMAND_PREFIX` and `BOT_NICK` constants to ergo tests
- Added admin optout: `.optout <nick>` (admin only)
- Added `default_optin: true` to config schema
- Rewrote `plugin.py` to use `sopel.plugin` (not deprecated `sopel.module`)

### Test counts

Test counts: 83 → 107+

### Rework complete (2026-06-26)
- `docs/release-0.0.2/rework-plan.md` — SOPEL-native plugin architecture — **COMPLETE**
  - Deleted `handle_management()` routing layer — plugin handlers call `user.*`/`management.*` directly
  - Renamed `AdminCommands` → `ManagementCommands`
  - Removed dead code: `is_management_command()`, `match_prompt()`, `MANAGEMENT_COMMANDS` set
  - Admin gating → SOPEL's `trigger.admin` / `@plugin.require_admin`; removed `TerraAI.is_admin()` and `admin_nicks`
  - Test tool → `getattr(terra_plugin, f"cmd_{name}")` dispatch
- Custom prompts (`.addprompt`, `.rmprompt`, `match_prompt()`) — TBD, needs discussion (next task)

### Web search + PM routing (2026-06-27) — **COMPLETE**
- Replaced DuckDuckGo web search with OpenRouter server-side `openrouter:web_search` tool
- Added PM catch-all rule (`@rule("(.+)")`) for bare PM text
- Fixed timeout type bug (int cast in all providers)
- 137 tests passing (mock + real + ergo)
