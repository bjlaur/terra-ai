# TODO.md

## terra-ai TODO list

This file is the active roadmap. Completed items move to the changelog.
Only pending/unfinished work stays in the active sections below.

---

## Every commit MUST update `TODO.md`, `CHANGELOG.md`, and `.agentic/plan.md`.

---

## Active: 0.0.2 — SOPEL-Native Plugin Cleanup

### Done ✅
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

### Deferred
- [ ] Fix interactive test failures (test_interactive_accepts_pm, test_interactive_noisy_notice, test_interactive_accepts_input) — AI response never arrives in subprocess+curses+pty within 30s timeout. Root cause unknown. Works in-process. Deferred 2026-06-26 after extensive debugging.
- [ ] Custom prompts rework (.addprompt, .rmprompt, .listprompts) — needs discussion (separate task after cleanup)

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
