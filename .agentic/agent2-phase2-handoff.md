# Agent2 Phase 2 Handoff — Console Tabbed UI + Real/Mock Test Split

**Date:** 2026-06-27
**Branch:** `agent2/console-phase2` (branched from `agent2/redo-console-and-tests`)
**Previous branch:** `agent2/redo-console-and-tests` (pushed to origin, merged work)
**Agent:** OWL
**Status:** Phase 2 complete — all tests passing, docs updated

---

## What Was Done (Phase 1 — complete, pushed)

### Console Rewrite (curses → Textual)
- Deleted: `test_tool/chat.py`, `test_tool/screenshot_test.py`, `tests/test_tool.py`, `test_tool/screenshots/`
- Created: `test_tool/console.py` (Textual TUI), `tests/test_console.py`, `tests/test_console_screenshots.py`
- 110 mock tests pass, 12 real tests available with `--real`
- Tab completion (`Ter<Tab>` → `TerraAI:`) and history navigation (Up/Down) work

### Real/Mock Test Split
- `conftest.py`: `@pytest.mark.mock` always mocks, `@pytest.mark.real` requires `--real` + key
- `pytest.ini`: added `mock` marker
- All AI-hitting tests have both mock and real versions
- Tests: `pytest` (mock), `pytest --real -m real` (real only), `pytest --real` (everything)

### Docs
- `docs/release-0.0.2/console-feature.md` — full feature spec
- `docs/release-0.0.2/console-plan.md` — implementation plan
- `docs/release-0.0.2/real-test-plan.md` — mock/real test split design
- `docs/release-0.0.2/httpx-curses-pty-hang-analysis.md` — root cause analysis
- `.agentic/agent2-handoff.md` — updated to reflect Phase 1 completion

---

## What's In Progress (Phase 2 — local, uncommitted)

### Tabbed UI Rewrite
**File:** `test_tool/console.py` (modified)

Changes:
- Replaced single `#chat` Static with `TabbedContent` containing two `TabPane`s:
  - `TabPane("Channel", id="channel")` with `Static(id="channel-log")`
  - `TabPane("PM", id="pm")` with `Static(id="pm-log")`
- Messages tracked per-tab: `app.messages = {"channel": [], "pm": []}`
- `/msg hello` routes to PM tab (no `[PM]` prefix — tab title provides context)
- Normal messages route to whichever tab is active
- Keyboard shortcuts: `F1` → Channel, `F2` → PM (Ctrl+B/Ctrl+P don't work with Input widget)
- `_append_to_tab(tab, msg)` helper updates the correct Static widget

**Tests updated:** Both `tests/test_console_screenshots.py` and `tests/test_console.py` now use per-tab assertions.
- Screenshot tests renamed `test_pm_sends_with_prefix` → `test_pm_routes_to_pm_tab`
- Added `test_f1_switches_to_channel` and `test_f2_switches_to_pm`
- 112 mock tests + 12 real tests all passing

### SVG Export — Confirmed Impossible
See `~/textual-richlog-svg-export-report.md`. Textual 8.2.7's `export_screenshot()` does NOT capture dynamically-updated Static/Log/RichLog content. Tests must assert against widget state (`app.messages`) directly. SVG screenshots saved as debug artifacts only.

---

## What Needs Doing

All Phase 2 work is done. Next steps:
1. **Commit and push** — all changes ready
2. **Merge to release-0.0.2** — after review

---

## Key Decisions

1. **Textual (not curses)** — gives test pilot + no pty deadlock
2. **TabbedContent for PMs** — clean separation, no `[PM]` prefix needed
3. **Assert against `app.messages` dict** — SVG export can't capture dynamic content; per-tab dict `{"channel": [], "pm": []}`
4. **Phase 2 async worker not needed** — Textual's event loop avoids httpx+pty deadlock
5. **Mock/real split via markers** — same test functions, markers decide mode
6. **F1/F2 for tab switching** — Ctrl+B/Ctrl+P don't work because Textual's Input widget consumes Ctrl+letter keys before App bindings see them

---

## File Map

| File | Status |
|------|--------|
| `test_tool/console.py` | MODIFIED (tabbed UI, F1/F2 shortcuts) |
| `test_tool/__init__.py` | OK |
| `tests/test_console.py` | UPDATED (per-tab assertions for interactive PM test) |
| `tests/test_console_screenshots.py` | UPDATED (per-tab assertions, F1/F2 tab switch tests) |
| `tests/conftest.py` | OK (mock/real split done) |
| `pytest.ini` | OK |
| `docs/release-0.0.2/console-feature.md` | UPDATED (F1/F2, no [PM] prefix, per-tab assertions) |
| `docs/release-0.0.2/console-plan.md` | UPDATED (Phase 2 complete) |
| `docs/release-0.0.2/real-test-plan.md` | OK |
| `.agentic/agent2-handoff.md` | OK |

---

## Verification

```bash
cd ~/agentic-repos/terra-ai-agent2

# Mock tests (default)
pytest tests/test_console.py tests/test_console_screenshots.py -v

# Real API tests
source ~/.terra-ai/.env && pytest tests/test_console.py -v --real -m real

# Manual interactive
python test_tool/console.py
# Type: .optin, hello (channel), /msg hello (PM tab), Ctrl+B/Ctrl+P to switch
```
