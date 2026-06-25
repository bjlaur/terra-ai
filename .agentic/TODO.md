# TODO.md

## terra-ai TODO list

This file is the active roadmap. Completed items move to the changelog.
Only pending/unfinished work stays in the active sections below.

---

## Every commit MUST update `TODO.md`, `CHANGELOG.md`, and `.agentic/plan.md`.

---

## Active: 0.0.2 — Ergo Integration + Test Config

### Done ✅
- [x] Fix ergo test typo: `ergo_running()` → `ergo_available()`
- [x] Ergo smoke tests (port, config, socket) — 3 passing
- [x] Ergo IRC protocol tests (register, join, channel msg, private msg) — 4 passing
- [x] SOPEL bot integration tests (connects, joins channel) — 2 passing
- [x] Fix terraai/plugin.py setup() to read config from bot.config.terraai
- [x] SOPEL test config examples committed (sopel-test.cfg.example, terraai-test.yaml.example)
- [x] Minimal plugin set: admin, adminchannel, ping, reload, safety, tell, terraai
- [x] 0.0.2 docs: CHANGELOG.md, feature.md, testing-results.md

### In Progress
- [ ] SOPEL bot message dispatch — bot connects + joins but doesn't respond to PRIVMSG
  - Likely IRCv3 capability issue with echo-message/server-time
  - Same issue both agents are hitting; needs deeper SOPEL debug

### Pending (0.0.2)
- [ ] Complete SOPEL bot end-to-end tests (responds to .help, TerraAI: trigger)
- [ ] SSL/TLS support for ergo (broken with self-signed cert + CAP negotiation)

---

## Done: 0.0.1 — Minimal SOPEL Plugin ✅

All phases 1-5 complete. Phase 6 (docs) partial.

---

## Pending (0.0.3+)

See `docs/future-release/release-plan.md` for the full deferred features list.

High priority:
- Fix SOPEL IRCv3 message dispatch (blocking for bot end-to-end)
- Context compaction (.compact) — fully working
- Multi-server support
- Rate limiting
- Containerfile polish

0.0.2 test tool testing:
- [ ] Write DB-based tests for `.addprompt` / `.rmprompt` (check prompts table directly so user can verify manually)
- [ ] Run --real API tests (R1–R5) with OPENROUTER_API_KEY set
