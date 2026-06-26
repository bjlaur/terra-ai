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

## Interactive Tests — DEFERRED

Three interactive tests fail because the AI response never arrives within the subprocess+curses+pty test setup's 30-second timeout:

- `test_interactive_accepts_pm`
- `test_interactive_noisy_notice`
- `test_interactive_accepts_input`

The AI call works fine in-process (returns in <2s). The issue is specific to the subprocess launched by pty. Deferred 2026-06-26 after extensive debugging.

---

## Key Decisions Made

1. **PMs are always direct-to-bot** — no trigger phrase needed in PMs
2. **`.setlocation` hybrid is kept** — `cmd_setlocation` stores locally then forwards to AI
3. **Custom prompts TBD** — `match_prompt()` removed. Needs separate discussion.
4. **Test tool calls real plugin handlers** — via `getattr(terra_plugin, f"cmd_{name}")` dispatch
5. **Opt-in/opt-out is core bot concern** — test tool should not enforce it
6. **`MANAGEMENT_COMMANDS` set removed** — SOPEL tracks via decorators
7. **Admin gating uses SOPEL native** — `trigger.admin` / `@plugin.require_admin`, not custom `admin_nicks`

---

## What Needs Doing

1. **Custom prompts discussion** — decide what happens to `.addprompt`/`.rmprompt`
2. **Interactive test failures** — deferred, investigate subprocess AI call issue
3. **Manual testing** — human needs to fill in "Mine" column in testing-agent2-v2.md

---

## How to Continue

1. Check out `agent1/sopeL-native-cleanup` branch (or merge to release-0.0.2)
2. Run tests: `source ~/.terra-ai/.env && python -m pytest tests/ -v --ignore=tests/test_ergo.py`
3. Run interactive: `python test_tool/chat.py`
4. Run screenshots: `python test_tool/screenshot_test.py`
5. See `docs/release-0.0.2/testing-agent2-v2.md` for full checklist
