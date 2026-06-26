# Agent2 Handoff — Test Tool Testing (0.0.2)

**Date:** 2026-06-25 (updated 2026-06-26 by OWL)
**Agent:** agent2 (original), OWL (cleanup pass)
**Branch:** `agent2/prompts-and-ux-fixes` (original), merged into `release-0.0.2`
**Clone:** `~/agentic-repos/terra-ai-agent2/`
**Status:** Complete — all routing/UI features done; SOPEL-native cleanup applied by OWL

---

## What Was Done

### Routing Fixes
- `.setlocation` — hybrid routing: stores prompt locally, forwards to AI for response
- `.effort` — added to MANAGEMENT_COMMANDS so it dispatches locally
- Unknown `.commands` — any `.command` not in management list now routes to AI
- Tab completion — `Ter<Tab>` at start of line → `TerraAI: `, mid-line → `TerraAI`
- Custom prompt local matching removed — `.wea` and similar now go to AI

### New Command
- `.clear` — wipes conversation history by rotating to a fresh session_id

### PM Support
- `send_pm()` with `is_pm=True` — PMs are direct-to-bot, no trigger phrase needed
- `/msg <text>` in interactive mode sends as PM
- PMs display with `[PM]` prefix in chat

### Noisy Mode
- "Thinking..." notice sent before AI calls when noisy is ON
- Notices shown in channel with `-!-` prefix (irssi-style)
- Notices captured per-call (don't accumulate)

### UI Improvements
- Async AI calls — background thread, UI doesn't freeze
- Timestamps `[HH:MM]` on all messages
- Resize fix — KEY_RESIZE handler recreates curses windows
- Compact gate — `.compact` restricted to admin only

### Test Changes
- 100+ unit tests passing
- 7 --real tests passing (effort, unknown command, noisy, setlocation, PM trigger, PM effort, noisy notice)
- 8 screenshot SVGs passing
- Added `test_async_ai_call` — verifies background thread + SQLite cross-thread (passes with real API)
- Added interactive tests with polling harness
- Added SQLite threading fix (`check_same_thread=False`) + `test_async_ai_call` with real API

### SOPEL-Native Cleanup (by OWL, 2026-06-26)
- Deleted `handle_management()` routing layer — plugin handlers call `user.*`/`management.*` directly
- Renamed `AdminCommands` → `ManagementCommands`
- Removed dead code: `is_management_command()`, `match_prompt()`, `handle_setlocation()`, `handle_ai()`, `MANAGEMENT_COMMANDS` set
- Admin gating → SOPEL's `trigger.admin` / `@plugin.require_admin`; removed `TerraAI.is_admin()` and `admin_nicks`
- Test tool → `getattr(terra_plugin, f"cmd_{name}")` dispatch (no duplicated routing)
- 94 unit tests passing, 7 real-API tests passing

---

## Interactive Tests — RESOLVED

Previously deferred (subprocess+curses+pty deadlock). Resolved by rewriting to Textual — the test pilot (`app.run_test()`) drives the UI headlessly without pty. All 5 interactive tests pass in mock mode, 8 real tests added.

---

## Real/Mock Test Split — IMPLEMENTED

All tests that can hit the API have both `@pytest.mark.mock` and `@pytest.mark.real` versions. See `docs/release-0.0.2/real-test-plan.md`.

**Rules:**
- `@pytest.mark.mock` → always mock (even with `--real`)
- `@pytest.mark.real` → requires `--real` + `OPENROUTER_API_KEY`
- No marker → defaults to mock

**Run commands:**
- `pytest` — all mock tests
- `pytest --real -m real` — only real API tests
- `pytest --real` — everything

**Counts:** 110 mock tests pass, 12 real tests available (7 skipped without `--real`).

---

## Console Rewrite — IMPLEMENTED

Rewritten from curses to Textual. See `docs/release-0.0.2/console-feature.md` and `docs/release-0.0.2/console-plan.md`.

- `test_tool/console.py` — Textual TUI (was `chat.py` + curses)
- `tests/test_console.py` — 22 tests (mock + interactive)
- `tests/test_console_screenshots.py` — 9 tests (pilot-driven, asserts `app.messages`)
- Screenshots tests use `app.messages` directly, NOT SVG parsing (see `~/textual-richlog-svg-export-report.md`)

---

## Key Decisions Made

1. **PMs are always direct-to-bot** — no trigger phrase needed in PMs
2. **`.setlocation` hybrid is kept** — `cmd_setlocation` stores locally then forwards to AI
3. **Custom prompts TBD** — `match_prompt()` removed. Needs separate discussion.
4. **Test tool calls real plugin handlers** — via `getattr(terra_plugin, f"cmd_{name}")` dispatch
5. **Opt-in/opt-out is core bot concern** — test tool should not enforce it
6. **`MANAGEMENT_COMMANDS` set removed** — SOPEL tracks via decorators
7. **Admin gating uses SOPEL native** — `trigger.admin` / `@plugin.require_admin`, not custom `admin_nicks`
8. **Textual (not curses)** — gives SVG export + test pilot for headless automation
9. **Phase 2 async worker not needed** — Textual's event loop doesn't have the httpx+pty deadlock

---

## What Needs Doing

1. **Custom prompts discussion** — decide what happens to `.addprompt`/`.rmprompt`
2. **Manual testing** — human needs to fill in "Mine" column in testing-agent2-v2.md
3. **Phase 2** — PM tabs via `TabbedContent`, drop `[PM]` prefix, SVG screenshot tests
4. **Update main repo** — merge `agent2/redo-console-and-tests` to `release-0.0.2`

---

## How to Continue

1. Preview mock tests: `cd ~/agentic-repos/terra-ai-agent2 && python -m pytest tests/test_console.py tests/test_console_screenshots.py -v`
2. Run real API tests: `source ~/.terra-ai/.env && python -m pytest tests/test_console.py -v --real -m real`
3. Run interactive console: `python test_tool/console.py`
4. See `docs/release-0.0.2/testing-agent2-v2.md` for full checklist
