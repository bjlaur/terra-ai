# Agent2 Phase 2 Handoff — Console Rewrite + Routing Refactor

**Date:** 2026-06-27
**Branch:** `agent2/console-phase2`
**Agent:** OWL
**Status:** Phase 2 complete + routing refactor in progress (uncommitted)

---

## Phase 1 (complete, pushed to `agent2/redo-console-and-tests`)

- Rewrote `test_tool/chat.py` → `test_tool/console.py` using Textual (not curses)
- Created `tests/test_console.py` (unit + interactive) and `tests/test_console_screenshots.py` (pilot-driven)
- Mock/real test split via `@pytest.mark.mock` / `@pytest.mark.real` + `--real` flag
- 114 mock tests pass, 12 real tests available

## Phase 2 (complete, committed `cb9979e`)

- TabbedContent with Channel/PM tabs, no `[PM]` prefix
- Per-tab `app.messages = {"channel": [], "pm": []}`
- F1/F2 + Alt+Left/Alt+Right tab switching
- PM tab implies `/msg` routing (no prefix needed when in PM tab)
- Async worker (`run_worker` + `asyncio.to_thread`) so UI doesn't block on AI calls

## Current Work — Routing Refactor (uncommitted, in progress)

**Problem found during manual testing:**
1. `send_message()`/`send_pm()` duplicated routing that belongs in plugin.py (violates spec §5.3)
2. Tab completion replaced entire input instead of completing word at cursor
3. `FakeTrigger.group()` hardcoded `.` and `-` prefixes instead of using config
4. `trigger_char` default was `.`, should be `-`
5. No test verifying UI stays responsive during AI call

**Fixes applied so far:**
- `send_message()`/`send_pm()` now delegate ALL routing to `plugin.handle_channel_message()` / `plugin.handle_pm_message()` in `terra_ai/plugin.py`
- `FakeTrigger.group()` reads prefix from `plugin._get_terra().prompts.trigger_char` (no hardcoded chars)
- `_default_test_config()` reads `trigger_phrase` and `bot_nick` from env vars (`TERRAI_TRIGGER_PHRASE`, `TERRAI_BOT_NICK`)
- Tab completion rewritten: completes word at cursor, case-insensitive prefix match, `self.bell()` on no match
- Tests updated to read `client.trigger_char` and `client.terra.config.trigger_phrase` instead of hardcoding

**Still broken (interrupted mid-edit):**
- `TerraAITestClient.__init__` has a broken edit — `self.trigger_char` removal left malformed code
- `plugin.py._cmd_word()` updated to use config prefix
- `tests/conftest.py` trigger_char changed to `-`
- `tests/test_commands.py` trigger_char changed to `-`
- Tests NOT yet run after these changes — likely broken

---

## Key Architecture Decisions

1. **No routing in console** — `send_message()`/`send_pm()` build `FakeTrigger`, call `plugin.handle_channel_message()`/`handle_pm_message()`. ALL routing (trigger prefix, command lookup, management vs AI, trigger phrase) lives in plugin.py via SOPEL decorators.
2. **No hardcoded trigger char/phrase** — `FakeTrigger.group()` reads prefix from `plugin._get_terra().prompts.trigger_char`. Config defaults come from env vars.
3. **F1/F2 for tabs** — Ctrl+B/Ctrl+P don't work (Input widget captures Ctrl+letter)
4. **Async AI calls** — `run_worker` + `asyncio.to_thread` keeps UI responsive
5. **Assert against `app.messages`** — SVG export can't capture dynamic Static content

---

## File Map

| File | Status |
|------|--------|
| `test_tool/console.py` | MODIFIED — routing removed, tab completion fixed, **has broken edit in `__init__`** |
| `terra_ai/plugin.py` | MODIFIED — `_cmd_word()` uses config prefix, added `handle_channel_message()`/`handle_pm_message()` |
| `tests/test_console.py` | MODIFIED — reads trigger_char/phrase from client config |
| `tests/test_console_screenshots.py` | MODIFIED — reads trigger_char/phrase from app config |
| `tests/conftest.py` | MODIFIED — trigger_char=`-` |
| `tests/test_commands.py` | MODIFIED — trigger_char=`-` |

---

## How to Continue

1. **Fix the broken edit** in `TerraAITestClient.__init__` (around line 137-147) — remove `self.trigger_char` line that got mangled
2. **Run tests:** `cd ~/agentic-repos/terra-ai-agent2 && python -m pytest --ignore=tests/test_ergo.py -q`
3. **Fix any test failures** — tests read `client.trigger_char` but that attribute was removed; need to get it from `client.terra.prompts.trigger_char` instead
4. **Update docs** — `console-feature.md` and `console-plan.md` need updates for the routing refactor
5. **Commit and push**

---

## Verification

```bash
cd ~/agentic-repos/terra-ai-agent2

# Mock tests
pytest tests/test_console.py tests/test_console_screenshots.py -v

# Full suite
pytest --ignore=tests/test_ergo.py -q

# Real API tests
source ~/.terra-ai/.env && pytest tests/test_console.py -v --real -m real

# Manual interactive
python test_tool/console.py
```
