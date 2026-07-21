# TODO.md

## terra-ai TODO list

This file is the active roadmap. Completed items move to the changelog.
Only pending/unfinished work stays in the active sections below.

---

## Every commit MUST update `TODO.md`, `CHANGELOG.md`, and `.agentic/plan.md`.

---

## Active: 0.0.2 — SOPEL-Native Plugin Cleanup

### Done ✅
- [x] Real-world four-model benchmark workflow using normal `--real` and Ergo
  suites, exact response capture, end-to-end timings, JSON/JSONL/Markdown
  reports and model overrides; the Codex execution handoff is delivered separately
- [x] Console phase 2: route through SOPEL's real rule dispatcher via `dispatch_line()`
- [x] Removed `trigger_char` and `trigger_phrase` from config, PromptManager, bot, and all tests
- [x] Removed `load_config()` / YAML config path — `setup()` reads `bot.config.terraai` directly
- [x] Rebuilt `FakeBot` with real SOPEL `RulesManager` — same dispatch path as production
- [x] Removed `FakeTrigger` — SOPEL's `Trigger` handles prefix stripping via regex
- [x] Removed hardcoded "Thinking..." from TUI — notices come from plugin handlers only
- [x] Tab completion: prefix-aware, nick gets colon at start-of-line, space mid-line
- [x] Help text uses configurable `help_prefix` instead of hardcoded `.`
- [x] Ergo test fixtures use SOPEL `.cfg` `[terraai]` section (no separate YAML)
- [x] 16/16 ergo integration tests passing with live ergochat
- [x] 116 unit tests passing, 0 failures
- [x] SOPEL-native cleanup: deleted `handle_management()` routing layer, plugin commands call `user.*`/`management.*` directly
- [x] Renamed `AdminCommands` → `ManagementCommands` (file + class)
- [x] Removed dead code: `is_management_command()`, `match_prompt()`, `handle_setlocation()`, `handle_ai()`, `MANAGEMENT_COMMANDS` set
- [x] Removed unused `text` param from `should_respond()`
- [x] Test tool calls real plugin handlers via `getattr(terra_plugin, f"cmd_{name}")` dispatch
- [x] Test tool reads config for trigger_char/botnick instead of hardcoding
- [x] Updated tests to call handlers directly (no more `handle_management()`)
- [x] Admin gating switched to SOPEL's `trigger.admin` / `@plugin.require_admin`
- [x] Removed `TerraAI.is_admin()` and `admin_nicks` from config schema
- [x] Rework plan executed — all cleanup steps C1–C8 complete
- [x] 94 unit tests passing, 7 real-API tests passing
- [x] Ergo smoke tests (port, config, socket) — 3 passing
- [x] Ergo IRC protocol tests (register, join, channel msg, private msg) — 4 passing
- [x] SOPEL bot integration tests (connects, joins channel) — 2 passing
- [x] 0.0.2 docs: CHANGELOG.md, feature.md, testing-agent2.md, testing-results.md
- [x] Routing: .setlocation hybrid, unknown .command fallback, .effort in MANAGEMENT_COMMANDS, tab completion
- [x] .clear command — wipe conversation history
- [x] PM support — send_pm() with is_pm=True, trigger phrase not needed
- [x] Noisy mode — "Thinking..." notice in channel with -!- prefix
- [x] Compact gate — .compact admin-only
- [x] Resize fix — KEY_RESIZE handler recreates windows
- [x] Async AI calls — background thread, non-blocking
- [x] Timestamps [HH:MM] on all messages
- [x] --real API tests (4 passing): effort, unknown command, noisy, setlocation
- [x] --real PM tests (2 passing): PM trigger, PM effort
- [x] Screenshot tests (8 SVGs): initial, after-message, listprompts, long-message-wrap, resize-narrow, resize-wide, pm-message, noisy-notice
- [x] Polling harness for interactive tests (`_run_interactive_poll()`) — polls for expected output
- [x] SQLite threading fix — `check_same_thread=False` for async AI calls
- [x] New tests: test_async_ai_call (real API), test_interactive_accepts_pm, test_interactive_noisy_notice, test_pm_direct_message, test_pm_setlocation_forwards_to_ai, test_interactive_empty_input, test_interactive_ctrl_d_exits, test_interactive_history_navigation
- [x] `docs/misc/claude-didn't-listen.md` — report on async testing gap
- [x] `docs/release-0.0.2/testing-agent2-v2.md` — comprehensive 68-test checklist
- [x] Fix terraai/plugin.py setup() to read config from bot.config.terraai
- [x] SOPEL test config examples committed (sopel-test.cfg.example, terraai-test.yaml.example)
- [x] Minimal plugin set: admin, adminchannel, ping, reload, safety, tell, terraai
- [x] SOPEL dispatch fix (module visibility, allow_bots, thread safety) — IRCv3 capability issue resolved
- [x] Bot connects, joins, and responds to PRIVMSG (SOPEL bot message dispatch)
- [x] Unit tests for SOPEL bot end-to-end pass (ergo integration tests gated behind running server)
- [x] Package rename terraai → terra_ai
- [x] Configurable botnick via {botnick}
- [x] Added COMMAND_PREFIX and BOT_NICK constants to ergo tests
- [x] HARD RULES 14+15 fix: removed all hardcoded "TerraAI" nicks and "." prefixes from logic code
- [x] `.effort` fix — unified attribute (was split between TerraAI._effort and PromptManager.effort)
- [x] Effort wiring into OpenRouter provider — `_reasoning_for_model()` gates reasoning by model slug
- [x] 7 effort-wiring tests passing in `TestEffortWire`
- [x] Test profiling — `tests/test-time.md` timing report (204s → 83s after optimizations)
- [x] `@pytest.mark.slow` on 4 interactive tests + `pytest.ini` with `addopts = -m "not slow and not real"`
- [x] Parametric mock/real fixture in `tests/conftest.py` — mock by default, `--real` flag for real API
- [x] 8 routing tests marked `@pytest.mark.real` — mock by default, hit API with `pytest --real -m real`
- [x] Deleted `test_send_as_different_nick` (not mimicking real IRC)
- [x] Sub-timing instrumentation in `_run_interactive` (`TEST_TIMING_VERBOSE=1`)

### Done (Ergo Test Profiling) ✅
- [x] Ergo smoke tests (3), IRC protocol tests (4), SOPEL bot tests (9/9 pass) — 16/16 passing
- [x] Session-scoped SOPEL fixture — saves 60s+ vs starting SOPEL per test
- [x] Removed `admin_nicks` from test config (was breaking SOPEL plugin load after rework)
- [x] Fixed SOPEL `shutdown()` signature (SOPEL 8.0 calls with arg)
- [x] Total suite time: 305s → 122s (session scope)
- [x] Fixed IRC test client handshake (wait for 001/366 instead of sleeping)
- [x] Added unknown-command fallback handler (`prefixed_freeform_fallback`) using `@plugin.rule_lazy`
- [x] Added `test_bot_reports_error_on_ai_failure` — verifies bot sends `Error:` when AI provider fails
- [x] Fixed `cmd_optin` guard bug — removed `_guard` from all management commands
- [x] Added `_irc_error_handler` decorator — all plugin handlers log + send `Error:` on crash
- [x] Added `logger.error` to prompts/manager.py, web_search.py, providers/ollama.py
- [x] Fixed `"AI provider not configured."` → `"Error: AI provider not configured."` in bot.py
- [x] Documented ergo test setup in `docs/misc/ergo-test-guide.md`

### Deferred
- [ ] Fix interactive test failures (test_interactive_accepts_pm, test_interactive_noisy_notice) — AI response never arrives in subprocess+curses+pty within 30s timeout. Works in-process. Marked `@pytest.mark.broken`.
- [ ] Custom prompts rework (.addprompt, .rmprompt, .listprompts) — needs discussion

### In Progress
- [ ] Rework plan — `docs/release-0.0.2/rework-plan.md` — drafted, not started

### Pending (0.0.2)
- [ ] SSL/TLS support for ergo (broken with self-signed cert + CAP negotiation)

### Manual testing needed
- See `docs/release-0.0.2/testing-agent2-v2.md` — human needs to mark [x] in "Mine" column

---

## Done: 0.0.2 — Carry-over + Test Tool + Provider Expansion ✅

All items from the carry-over merge and agent2's original 0.0.2 work are done.
See CHANGELOG.md for the full list.

---

## Done: 0.0.1 — Minimal SOPEL Plugin ✅

All phases 1-5 complete.

---

## Pending (0.0.3+)

See `docs/future-release/release-plan.md` for the full deferred features list.

High priority:
- SOPEL bot end-to-end verification on a running server (responds to .help, TerraAI: trigger)
- Context compaction (.compact) — fully working
- Multi-server support
- Rate limiting
- Containerfile polish
