# Console Rewrite — Implementation Plan

**Date:** 2026-06-26
**Branch:** `agent2/redo-console-and-tests`
**Spec:** `docs/release-0.0.2/console-feature.md` (the source of truth)
**Test matrix:** `docs/release-0.0.2/testing-agent2.md` + `testing-agent2-v2.md`
**Status:** Not started

---

## Context

The previous `test_tool/chat.py` + `tests/test_tool.py` + `test_tool/screenshot_test.py` are FUBAR. The interactive main loop's `read_line()` blocked waiting for Enter, so the loop never polled for background AI results — and the test harness couldn't drive the UI. The user decided to rewrite from scratch.

The rewrite is fully specced in `console-feature.md`. **This plan is the implementation roadmap** for that spec. Nothing here contradicts the spec; it just breaks the spec into executable steps.

**Key change from the spec's original version:** The console now uses **Textual** instead of curses. This is the user's explicit decision (2026-06-26). Textual gives us:
- A test pilot (`app.run_test()`) that can drive the UI headlessly
- No pty/curses/httpx deadlock

**Phase 1 vs Phase 2:** The rewrite has two phases:
- **Phase 1** (this plan): Single chat window, synchronous AI calls, unit + interactive tests
- **Phase 2** (future): PM tabs with `Ctrl+X` switching, async AI calls, SVG screenshot tests

---

## Files to delete

All tracked in git on `release-0.0.2`, so `git rm` is clean:

- `test_tool/chat.py` — broken curses version; replaced by `console.py`
- `test_tool/screenshot_test.py` — standalone Textual script that didn't use the real console; will be deleted in Phase 1 (screenshot tests deferred to Phase 2)
- `tests/test_tool.py` — references `test_tool.chat`; replaced by `tests/test_console.py`
- `test_tool/screenshots/` — stale SVGs from the old Textual app; will be regenerated in Phase 2
- `test_tool/__init__.py` — keep (package marker still needed)

## Files to create

### Phase 1: `test_tool/console.py` (the console)

A single file containing:

```python
# Imports: asyncio, logging, sys, os, time
# Textual: from textual.app import App
#          from textual.widgets import Static, Input
# TerraAI: from terra_ai import plugin as terra_plugin
#          from terra_ai.bot import TerraAI
#          from terra_ai.config import TerraAISection

def _default_test_config() -> SimpleNamespace: ...        # spec §7.4
class FakeTrigger: ...                                     # spec §7.2
class FakeBot: ...                                         # spec §7.3
class TerraAITestClient: ...                               # spec §7.5
    def __init__(self, config_path="config/terraai.yaml"): ...
    def _load_env(self): ...
    def _load_config(self, path): ...
    def send_message(self, text) -> list[str]: ...
    def send_as(self, nick, text) -> list[str]: ...
    def send_pm(self, nick, text) -> dict: ...

class TerraAIApp(App):                                    # Textual TUI (Phase 1: single chat window)
    CSS = "..."                                           # styling
    def __init__(self, client: TerraAITestClient): ...
    def compose(self): ...                                # yields Header, Chat (Static), Input
    def on_input_submitted(self, event): ...             # main dispatch
    def _dispatch(self, text, is_pm): ...                # routing logic
    def _render_response(self, result, notices): ...     # update Chat Static
    def _ts(self) -> str: ...                             # [HH:MM] timestamp
    def _handle_quit(self): ...
    def _handle_tab_completion(self): ...

# Phase 2: TerraAIApp with TabbedContent
# class TerraAIApp(App):
#     CSS = "..."
#     BINDINGS = [Binding("ctrl+x", "switch_tab", "Tab")]
#     def compose(self): ...                                # yields Header, TabbedContent(Channel, PM), Input
#     def action_switch_tab(self): ...                      # Ctrl+X handler

def run_interactive(): ...                                # entry point: TerraAIApp().run()

if __name__ == "__main__":
    if "--test" in sys.argv:
        # non-interactive mode (spec §7.6)
    else:
        run_interactive()
```

**Key design decisions:**
- **Textual, not curses.** No `curses.wrapper()`, no `stdscr.getch()`, no `KEY_RESIZE` handling. Textual handles all of this.
- **Synchronous AI in `on_input_submitted`.** The AI call runs on the main thread inside Textual's event loop. UI freezes 2-10s. Acceptable for a testing tool. No worker process needed (the curses-specific deadlock doesn't apply).
- **No routing in console.** `getattr(terra_plugin, f"cmd_{word}")` dispatch only. Everything else → `terra_plugin.addressed_freeform(bot, trigger)`.
- **PMs via `/msg`.** Console parses `/msg <text>` and sets `is_pm=True` on the trigger.
- **Notices rendered with `-!-` prefix** (irssi-style). `bot.notices` drained after each call.
- **Timestamps `[HH:MM]`** via `time.strftime`.
- **Tab completion** in the Input widget: start-of-line → `TerraAI: `, mid-line → `TerraAI `.
- **Input history** maintained in the app state; `↑`/`↓` bound to recall previous inputs.
- **Quit:** `Ctrl+Q`, `/quit`, `/exit`, `Ctrl+D`, `Ctrl+C`.

### 2. `tests/test_console.py` (unit + interactive tests)

Imports from `test_tool.console` (not `.chat`). Uses existing `tests/conftest.py` fixtures (`db`, `terra`).

**TestTestTool:**
- `test_send_message` — `.optin` → "opted in"
- `test_regular_message_ignored` — `hello` → no response
- `test_async_ai_call` — `TerraAI: hello` → non-empty (mock by default; real with `--real`)
- `test_unknown_command_routes_to_ai` — `.what's 2+2` → non-empty
- `test_help_command` — `.help` → contains `.optin`

**TestPM:**
- `test_pm_trigger_routes_to_ai`
- `test_pm_management_command`
- `test_pm_help_command`
- `test_pm_unknown_command_routes_to_ai`
- `test_ai_command_context_free`
- `test_pm_direct_message`
- `test_pm_setlocation_forwards_to_ai`
- `test_clear_command`
- `test_compact_admin_only_for_non_admin`

**TestNoisy:**
- `test_noisy_toggle`
- `test_noisy_off_no_notice`
- `test_noisy_on_sends_notice`

**TestInteractiveMode** (uses Textual's `run_test()` pilot — no pty subprocess):
- `test_interactive_launches_and_exits`
- `test_interactive_accepts_input`
- `test_interactive_tab_completes_trigger`
- `test_interactive_tab_completes_midline`
- `test_interactive_accepts_pm`
- `test_interactive_noisy_notice`
- `test_interactive_empty_input`
- `test_interactive_ctrl_d_exits`
- `test_interactive_history_navigation`

**TestRealAPI** (skipped unless `--real` + key set):
- `test_real_effort_level`
- `test_real_unknown_command_goes_to_ai`
- `test_real_noisy_toggle`
- `test_real_setlocation_goes_to_ai`
- `test_real_pm_trigger_responds`
- `test_real_pm_effort_level`
- `test_real_noisy_sends_notice_on_ai_message`

**Interactive test harness** — uses Textual's `run_test()`:

```python
@pytest.mark.asyncio
async def test_interactive_accepts_pm():
    client = TerraAITestClient()
    app = TerraAIApp(client=client)
    async with app.run_test() as pilot:
        await pilot.type("#input", "/msg hello")
        await pilot.press("enter")
        await pilot.pause(2)
        # Verify the Chat widget contains the PM
        chat = app.query_one("#chat", Static)
        assert "[PM]" in chat.renderable
```

No pty, no subprocess, no polling harness. The pilot drives the real app headlessly.

### Phase 2: PM tabs + SVG screenshot tests

**Two changes for Phase 2:**

1. **PM tabs via `TabbedContent`** — When switching to the tabbed layout, we can **remove the `[PM]` prefix markings** from messages. Instead of displaying `[PM] <nick> hello` in the chat, PMs go into the PM tab as just `<nick> hello` (no prefix needed — the tab title "PM" provides context). Channel messages stay in the Channel tab without any prefix.

2. **SVG screenshot tests** — Uses the same `run_test()` pilot pattern. After driving the app, calls `app.export_screenshot()` and parses the SVG to verify content.

> **Blocker:** Textual 8.2.7's `export_screenshot()` does NOT capture `RichLog` content. Documented in `~/textual-svg-export-issue.md`. Phase 2 will need to either resolve this or use a different verification strategy.

**SVG tests:**
- `test_initial_state` — header `#terra-ai`, empty chat, input line
- `test_after_message` — user message + bot response visible
- `test_pm_sends_with_prefix` — `[PM] <tester> hello`
- `test_notice_shows_thinking` — `-!- Thinking...`
- `test_noisy_toggle_shows_notice` — "Noisy mode ON/OFF"
- `test_help_shows_command_list`
- `test_tab_completion`
- `test_input_history`
- `test_management_commands_work`

**SVG parsing helper:**

```python
def extract_svg_texts(svg_str: str) -> list[str]:
    """Extract all text content from an SVG string."""
    import re, html
    svg = html.unescape(svg_str)
    return [m.group(1) for m in re.finditer(r'<text[^>]*>([^<]*)</text>', svg)]
```

## Files to modify

- `pytest.ini` — add `asyncio_mode = auto` and `asyncio` marker (if using pytest-asyncio). Or use `asyncio.run()` directly in tests.
- `tests/conftest.py` — no change needed (fixtures are provider-agnostic)
- `requirements.txt` / `pyproject.toml` — add `textual` as a dependency (if not already present)

## Implementation order

### Phase 1 (current)
1. ~~**Delete** the 3 old files + `screenshots/` dir~~ DONE
2. ~~**Write `test_tool/console.py`**~~ DONE — single chat window, synchronous AI
3. ~~**Write `tests/test_console.py`**~~ DONE — 14 tests passing (5 unit + 5 interactive + 4 noisy/PM)
4. **Run full suite** — `pytest tests/test_console.py -v`
5. **Commit** — ask user first

### Phase 2 (future)
6. Add PM tabs with `Ctrl+X` switching (using `TabbedContent`)
7. Write `tests/test_console_screenshots.py` — SVG export tests (blocked on RichLog SVG issue)
8. Add async AI calls if needed

## Verification

```bash
# Unit tests (mock provider, no key needed)
cd ~/agentic-repos/terra-ai-agent2
pytest tests/test_console.py -v -m "not real and not slow and not broken"

# Real API tests (needs key)
source ~/.terra-ai/.env && pytest tests/test_console.py -v -m real

# Screenshot tests
pytest tests/test_console_screenshots.py -v

# Manual interactive test
python test_tool/console.py
# Type: .optin, TerraAI: hello, .noisy, /msg hello, /quit
```

## Open questions

1. **pytest-asyncio setup** — DONE. `asyncio_mode = auto` added to `pytest.ini`. Tests use `@pytest.mark.asyncio`.
2. **Textual SVG export + RichLog** — BLOCKING screenshot tests. `App.export_screenshot()` does NOT capture `RichLog` content in Textual 8.2.7. Documented in `~/textual-svg-export-issue.md`. Need to either:
   - Find a widget that SVG export captures (Static with update() works, but can't show scrolling history easily)
   - Use a different verification strategy for screenshot tests (e.g., verify via `render_lines()` instead of SVG)
3. **Phase 2 async** — deferred unless Phase 1 proves to have UI jank. The spec keeps the Phase 2 description as a fallback.
4. **TabbedContent API** — Need to verify the exact API for switching tabs programmatically and getting the active tab.

## Out of scope

- Custom prompts (`.addprompt`, `.rmprompt`, `.listprompts`) — deferred per `deferred-testing-agent2.md`
- `.stats` admin gating — needs decision
- `.compact` from non-admin — already resolved (gated via `@plugin.require_admin`)
