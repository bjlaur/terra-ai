# TODO.md

## terra-ai TODO list

This file is the active roadmap. Completed items move to the changelog.
Only pending/unfinished work stays in the active sections below.

---

## Every commit MUST update `TODO.md`, `CHANGELOG.md`, and `.agentic/plan.md`.

---

## Active: 0.0.2 — Test Tool & Provider Expansion

### Done ✅
- [x] Ergo smoke tests (port, config, socket) — 3 passing
- [x] Ergo IRC protocol tests (register, join, channel msg, private msg) — 4 passing
- [x] SOPEL bot integration tests (connects, joins channel) — 2 passing
- [x] 0.0.2 docs: CHANGELOG.md, feature.md, testing-agent2.md
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
- [x] 0.0.2 docs: CHANGELOG.md, feature.md, testing-results.md
- [x] SOPEL dispatch fix (module visibility, allow_bots, thread safety) — IRCv3 capability issue resolved
- [x] Bot connects, joins, and responds to PRIVMSG (SOPEL bot message dispatch)
- [x] Unit tests for SOPEL bot end-to-end pass (ergo integration tests gated behind running server)
- [x] Package rename terraai → terra_ai
- [x] Configurable botnick via {botnick}
- [x] Added COMMAND_PREFIX and BOT_NICK constants to ergo tests
- [x] HARD RULES 14+15 fix: removed all hardcoded "TerraAI" nicks and "." prefixes from logic code

### In Progress
- [ ] Rework plan — `docs/release-0.0.2/rework-plan.md`
  - Extract `dispatch()` into `bot.py`
  - Slim `plugin.py` to thin wrapper
  - Test tool calls `dispatch()` directly
  - Remove MANAGEMENT_COMMANDS set
  - **Status:** Drafted, not started — awaiting merge
- [ ] Fix test_interactive_noisy_notice — AI not responding in test harness (works live)

### Pending (0.0.2)
- [ ] Verify SOPEL bot end-to-end (responds to .help, TerraAI: trigger) on a running server
- [ ] SSL/TLS support for ergo (broken with self-signed cert + CAP negotiation)
- [ ] Custom prompts rework (.addprompt, .rmprompt, .listprompts, match_prompt) — needs discussion

### Manual testing needed
- See `docs/release-0.0.2/testing-agent2-v2.md` — human needs to mark [x] in "Mine" column

---

## Done: 0.0.1 — Minimal SOPEL Plugin ✅

All phases 1-5 complete.

---

## Pending (0.0.3+)

See `docs/future-release/release-plan.md` for the full deferred features list.

High priority:
- SOPEL IRCv3 message dispatch fix merged (end-to-end verification still pending)
- Context compaction (.compact) — fully working
- Multi-server support
- Rate limiting
- Containerfile polish
