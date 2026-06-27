# CHANGELOG.md

## 0.0.2 — In Progress

### Agent 1 (OWL) — Carry-over: SOPEL dispatch fix + package rename

#### Fixes
- **SOPEL module visibility** — SOPEL loaded `terra_ai/__init__.py` as a folder plugin, but all decorated handlers were in `plugin.py`. Fixed by making `__init__.py` re-export via `from .plugin import *`
- **SOPEL IRCv3 message dispatch** — added `@plugin.allow_bots` decorators so SOPEL forwards bot-tagged messages to handlers
- **SQLite thread safety** — handlers run in worker threads; added `check_same_thread=False` to `sqlite3.connect()` in `database.py`
- **Single `_terrai` global** — moved `setup()` from `__init__.py` into `plugin.py` so the global is in the same module as handlers

#### Refactoring
- Renamed `terraai/` package to `terra_ai/` (underscore)
- Renamed plugin from `terraai` to `terra_ai` in SOPEL config
- Rewrote `plugin.py` to use `sopel.plugin` (not deprecated `sopel.module`)
- Management commands now use `@plugin.command()` decorators
- Freeform queries use `@plugin.rule(r"$nick (.+)")` with `$nick` placeholder
- SOPEL config now uses `prefix = -` (not `.`)
- Made bot nick configurable in prompts via `{botnick}` variable (no hardcoded "TerraAI")
- Added `COMMAND_PREFIX` and `BOT_NICK` constants to ergo tests (no hardcoded values)
- Added admin optout: `.optout <nick>` (admin only)
- Added `default_optin: true` to config schema

#### HARD RULES 14+15 compliance
- Removed all hardcoded "TerraAI" nick fallbacks from logic code (`config.py`, `prompts/manager.py`, `bot.py`, `test_tool/chat.py`)
- Removed all hardcoded "." prefix from string normalization and routing logic
- Bot now reads `bot_nick` and `trigger_phrase` from config at runtime; empty string default means self-check is disabled when not configured
- Test tool reads both values from config instead of hardcoding

#### Testing
- 94 unit tests passing (after cleanup), 7 real-API tests passing (with key)
- All non-ergo tests passing
- Package renamed throughout all imports and references

### Agent 1 (OWL) — Provider expansion, web search, ergo integration

#### Features
- Test tool (`test_tool/chat.py`, formerly `irc_client.py`) — irssi-like terminal UI via Textual
- Screenshot tests (`test_tool/screenshot_test.py`) — 8 SVGs, visual inspection
- Additional providers: Gemini, OpenAI, Ollama
- Provider fallback chain in registry
- Web search via DuckDuckGo (free, no API key)
- ergochat integration tests — smoke, IRC protocol, SOPEL bot end-to-end
- SOPEL test config examples committed (`config/sopel-test.cfg.example`, `config/terraai-test.yaml.example`)
- `python-textual` added to PACKAGES.md

#### Testing
- 94 unit tests passing (after cleanup), 7 real-API tests passing (with key) (database, providers, prompts, context, bot, providers_extended, test_tool)
- 15 ergo integration tests (require live ergochat server)

### Agent 2 — Console rewrite: SOPEL dispatch, remove trigger_char/phrase

#### Features
- `.clear` command — wipe conversation history and start fresh session
- `.setlocation` hybrid routing — stores prompt locally, forwards to AI for response
- `.effort [level]` — set reasoning effort (low/medium/high/xhigh/max)
- Unknown `.command` routing — anything starting with `.` that isn't a management command goes to AI
- Tab completion — `Ter<Tab>` completes to `TerraAI: ` (mid-line too)
- Custom prompt local matching removed — `.wea` and similar now route to AI
- PM support — `/msg` sends direct-to-bot, no trigger phrase needed
- Noisy mode — "Thinking..." notice shown in channel with `-!-` prefix
- Async AI calls — UI no longer freezes during API calls
- Timestamps `[HH:MM]` on all messages
- Compact gate — `.compact` restricted to admin only
- Resize fix — terminal resize handled correctly
- Polling harness for interactive tests (`_run_interactive_poll()`) — polls for expected output instead of fixed delays
- SQLite threading fix — `check_same_thread=False` for async AI calls
- New tests: test_async_ai_call (real API), test_interactive_accepts_pm, test_interactive_noisy_notice, test_pm_direct_message, test_pm_setlocation_forwards_to_ai, test_interactive_empty_input, test_interactive_ctrl_d_exits, test_interactive_history_navigation
- `docs/misc/claude-didn't-listen.md` — report on async testing gap

#### Cleanup (OWL)
- Deleted `handle_management()` routing layer from `bot.py` — plugin command handlers now call `user.*`/`management.*` handlers directly
- Renamed `AdminCommands` → `ManagementCommands` (file: `commands/admin.py` → `commands/management.py`)
- Removed dead code: `is_management_command()`, `match_prompt()`, `handle_setlocation()`, `handle_ai()`, `MANAGEMENT_COMMANDS` set
- Removed unused `text` param from `TerraAI.should_respond()`
- Test tool now calls real plugin handlers via `getattr(terra_plugin, f"cmd_{name}")` dispatch — no duplicated routing
- Test tool reads `trigger_char`/`botnick` from config instead of hardcoding
- Admin gating switched from config-driven `admin_nicks` list to SOPEL's `trigger.admin` / `@plugin.require_admin` — `.compact` uses the decorator; `.optout <nick>` checks `trigger.admin` in the handler
- Removed `TerraAI.is_admin()` and `admin_nicks` from config schema

#### Bug Fixes
- `.effort` no response — added "effort" to MANAGEMENT_COMMANDS set
- `.setlocation` (no args) — now correctly forwards to AI instead of erroring
- Tab completion — changed from "TerraAI" to "TerraAI: " (trigger phrase)
- `.wea` / unknown `.command` no response — added `.command` → AI routing
- Resize cuts off text — KEY_RESIZE handler recreates windows + redraws
- Test tool duplicated routing — rework plan drafted to use single `dispatch()`

#### Testing
- 94 unit tests passing (after cleanup), 7 real-API tests passing (with key)
- `--real` API tests passing (7/7): effort, unknown command, noisy, setlocation, PM trigger, PM effort, noisy notice
- Screenshot tests passing (8 SVGs): resize, wrap, PM, noisy
- 68 manual tests documented in `docs/release-0.0.2/testing-agent2-v2.md`
- Polling harness written for interactive tests (1 passing, 1 failing in test env)
- Rework plan drafted in `docs/release-0.0.2/rework-plan.md`
- Deferred tests tracked in `docs/release-0.0.2/deferred-testing-agent2.md`
- Async testing report in `docs/misc/claude-didn't-listen.md`
- **3 interactive tests deferred** (2026-06-26): `test_interactive_accepts_pm`, `test_interactive_noisy_notice`, `test_interactive_accepts_input` — AI response never arrives in subprocess+curses+pty within 30s timeout. Works in-process. Root cause unknown.

### Agent 2 — Console phase 2: SOPEL dispatch, remove trigger_char/phrase (2026-06-27)

#### Breaking Changes
- **Removed `trigger_char` and `trigger_phrase`** from `TerraAISection` config — SOPEL's `settings.core.prefix` and `$nick` rules handle all routing now
- **Removed `load_config()`** from `config.py` — `setup()` reads `bot.config.terraai` directly; no separate YAML config needed
- **Removed YAML config path** — ergo test fixtures now use SOPEL `.cfg` `[terraai]` section exclusively

#### Routing
- Added `dispatch_line(bot, nick, line, is_pm=False)` in `plugin.py` — routes through SOPEL's real rule dispatcher (PreTrigger → get_triggered_rules → rule.execute)
- Rebuilt `FakeBot` with real SOPEL `RulesManager` — test console follows the exact same dispatch path as production IRC
- Removed legacy shims: `handle_channel_message`, `handle_pm_message`, `_cmd_word`, `_notify_thinking`
- Added thinking notice (`bot.notice("Thinking...", nick)`) directly to `addressed_freeform` and `unknown_prefixed_command_to_ai` handlers
- Fixed hardcoded `.setlocation` prefix → `setlocation` (SOPEL already strips prefix)

#### Prompts
- Removed `${triggerchar}` placeholders from `defaults.py` — replaced with real examples (`-wea`)
- Removed `trigger_char` parameter/property from `PromptManager`
- Removed auto-prefix logic from `add_prompt()` / `remove_prompt()`

#### Console (test_tool/console.py)
- Removed `FakeTrigger` entirely — SOPEL's `Trigger` does prefix stripping via regex
- Removed hardcoded "Thinking..." line from TUI — notices come from plugin handlers only
- Removed "Thinking..." duplicate filter in `_dispatch` — handler owns the notice
- Tab completion: prefix-aware (strips `-` for matching, re-adds in completion)
- Tab completion: nick at start-of-line gets colon (`Ter<Tab>` → `TerraAI: `), mid-line gets space (`Hello Ter<Tab>` → `Hello TerraAI `)
- Console config derived from `_Core`/`_Settings` defaults — no YAML/INI file needed

#### Config
- Help text uses configurable `help_prefix` (default `"-"`) instead of hardcoded `"."`

#### Ergo Tests
- Removed YAML config files — all settings in SOPEL `.cfg` `[terraai]` section
- 16/16 ergo integration tests passing with live ergochat

#### Testing
- 116 unit tests passing, 0 failures
- New tab completion tests with exact-match assertions
- All `trigger_char`/`trigger_phrase` references removed from test fixtures

---

## 0.0.1 — TBD

Initial release. Minimal SOPEL plugin with one provider and basic commands.

### Features
- Responds to `TerraAI:` trigger phrase and `.` shorthand
- OpenRouter provider (default)
- SQLite persistence: 7 tables (users, conversation_history, sessions, compactions, prompts, command_stats, performance_stats)
- Fake conversation injected as context seed
- Commands: `.optin`, `.optout`, `.ai`, `.addprompt`, `.rmprompt`, `.listprompts`, `.help`, `.effort`, `.compact`, `.stats`, `.setlocation`, `.noisy`
- pytest suite with real API calls (60 tests)

### Testing
- 60 unit tests passing (database, providers, prompts, context, bot)
