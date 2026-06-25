# Agent2 Handoff — Test Tool Testing (0.0.2)

**Date:** 2026-06-25
**Agent:** agent2
**Branch:** `agent2/prompts-and-ux-fixes`
**Clone:** `~/agentic-repos/terra-ai-agent2/`
**Status:** Mid-flight — rework plan drafted, not yet executed

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
- Added `test_async_ai_call` — verifies background thread + SQLite cross-thread
- Added `test_interactive_tab_completes_midline`
- Added `test_interactive_accepts_pm` — uses polling harness
- Added `test_interactive_noisy_notice` — uses polling harness
- Added `_run_interactive_poll()` helper — polls for expected output before sending next input
- Removed opt-out gate from test tool (core bot concern, not test tool)
- Created `testing-agent2-v2.md` — comprehensive 63-test checklist with "Mine" column for human

### Docs Updated
- CHANGELOG.md — agent2 section with all features
- testing-agent2.md — Rounds 1-7
- testing-agent2-v2.md — comprehensive checklist
- feature.md — rework plan tracked
- release-plan.md — status updated
- rework-plan.md — SOPEL-native plugin architecture plan
- claude-didn't-listen.md — report on async testing gap

---

## Current Work (in progress, not committed)

### Polling Harness for Interactive Tests
The interactive test harness (`_run_interactive`) feeds fixed inputs with delays. This breaks for async AI calls that take >3 seconds. I wrote `_run_interactive_poll()` which:
- Sends one input at a time
- Polls stdout every 0.5s for expected output
- Sends next input only after finding the expected string
- Configurable timeout (default 30s)

Updated tests to use it:
- `test_interactive_accepts_pm` — polls for `[PM]`
- `test_interactive_noisy_notice` — polls for `-!- Thinking`

**Status:** Code written, NOT yet verified (test run was interrupted)

### SQLite Threading Fix
- `terraai/database.py` line 26: added `check_same_thread=False` to `sqlite3.connect()`
- Required because async AI calls run in background thread but DB was created on main thread
- Committed and verified

---

## Key Decisions Made

1. **PMs are always direct-to-bot** — no trigger phrase needed in PMs
2. **`.setlocation` hybrid is kept** — returns None from handle_management, plugin forwards to AI
3. **Custom prompts TBD** — removed trigger matching, context injection only. Needs separate discussion.
4. **Test tool should NOT duplicate routing** — rework plan drafted to use single `dispatch()` method
5. **Opt-in/opt-out is core bot concern** — test tool should not enforce it
6. **MANAGEMENT_COMMANDS set should be removed** — SOPEL tracks commands via `@plugin.command()` decorators

---

## Rework Plan (drafted, NOT started)

See `docs/release-0.0.2/rework-plan.md` for full details. Summary:

1. Rewrite `plugin.py` with `@plugin.command()` and `@plugin.rule(r'$nick (.+)')`
2. Remove `MANAGEMENT_COMMANDS` set from `prompts/defaults.py`
3. Slim `plugin.py` from ~137 lines to ~30 (thin SOPEL wrapper)
4. Test tool calls real handlers — no duplicated routing
5. Custom prompts — TBD, needs discussion

---

## Branch & Commits

Branch: `agent2/prompts-and-ux-fixes` (ahead of `release-0.0.2`)

Commits (most recent first):
- `fd0ad50` — Update testing-agent2.md Round 7 + cleanup deferred list
- `524fcb4` — Add rework-plan.md: SOPEL-native plugin architecture
- `c116970` — Fix SQLite threading for async AI calls, add async test, fix tab completion
- `d9a7651` — Fix mid-line tab completion expectation, update README commands
- `a8aa5bd` — Update docs: SOPEL-native rework plan, new testing checklist
- `34578d2` — Async AI calls in test tool — UI no longer freezes
- `aa05b98` — PM routing: treat all PMs as direct messages, fix tab complete, yell about .env
- `10bf1f2` — Update testing-agent2.md Round 5: timestamps, notices, interactive /msg
- `eb94bc5` — Add irssi-style timestamps and notice display
- `f3f847a` — Add /msg PM support to interactive mode, PM + noisy screenshots
- `aa50324` — Add PM support, noisy notices, compact admin gate, resize fix, 13 tests

---

## Files Modified (this session)

| File | Change |
|------|--------|
| `test_tool/chat.py` | Async AI, PM support, noisy notices, timestamps, resize fix, tab completion |
| `tests/test_tool.py` | 10+ new tests, polling harness |
| `test_tool/screenshot_test.py` | PM + noisy screenshot capture |
| `terraai/database.py` | `check_same_thread=False` for async |
| `terraai/bot.py` | `.compact` admin gate |
| `terraai/plugin.py` | "Thinking..." notice for noisy users |
| `docs/release-0.0.2/rework-plan.md` | SOPEL-native restructure plan |
| `docs/release-0.0.2/testing-agent2-v2.md` | Comprehensive 63-test checklist |
| `docs/misc/claude-didn't-listen.md` | Report on async testing gap |

---

## What Needs Doing

1. **Verify polling harness** — run `test_interactive_noisy_notice` and `test_interactive_accepts_pm`
2. **Execute rework plan** — SOPEL-native plugin architecture
3. **Custom prompts discussion** — decide what happens to `.addprompt`/`.rmprompt`
4. **Admin gating decision** — should `.stats` be admin-only too?
5. **Manual testing** — human needs to fill in "Mine" column in testing-agent2-v2.md

---

## How to Continue

1. Check out `agent2/prompts-and-ux-fixes` branch
2. Run tests: `source ~/.terra-ai/.env && python -m pytest tests/test_tool.py -v`
3. Run interactive: `python test_tool/chat.py`
4. Run screenshots: `python test_tool/screenshot_test.py`
5. See `docs/release-0.0.2/testing-agent2-v2.md` for full checklist
6. See `docs/release-0.0.2/rework-plan.md` for next big task
