# Plan: Fix verification failures + remove duplicate routing from the console

**Date:** 2026-06-27
**Branch:** `agent2/console-phase2`
**Agent:** OWL (agent2)
**Status:** in progress
**Anchors:** `~/verification_results.md` (the spec); `routing-duplication-report.md`
(what's duplicated); SOPEL source in `~/git/sopel` (ground truth).

## Scope

Two goals, console-focused:

1. **Make every row in `verification_results.md` pass.** The file's line-numbers
   are stale (they describe an older revision); this plan restates each row as a
   *requirement* and fixes the current code to satisfy it.
2. **Remove the console's duplicate routing.** `test_tool/console.py` hand-rolls
   prefix-stripping, command dispatch, and trigger-phrase matching that SOPEL
   already does via decorators. Route the console through SOPEL's dispatcher
   instead. (Main-plugin duplication in `config.py`/`bot.py` is tracked
   separately in `routing-duplication-report.md`; this plan only touches the
   console side plus the one thin `plugin.py` hook the console needs.)

## Requirements (from verification_results.md, restated)

| # | Requirement | Current state |
|---|---|---|
| R1 | **No routing in the console** — console just builds a trigger and calls a handler. | ✘ `send_message`/`send_pm` build `FakeTrigger` and call `handle_*_message`, which re-implement routing. |
| R2 | **`FakeTrigger.group()` must not hardcode `.`/`-`/`:`** — the console shouldn't know the prefix at all; SOPEL owns it. | ✘ reads `prompts.trigger_char` (a redundant field) with a hardcoded `-` fallback. |
| R3 | **Tab completes word at cursor, not whole input.** | ✘ replaces entire input. |
| R4 | **Start-of-line Tab → `TerraAI:`.** | ⚠ only works for empty input. |
| R5 | **Mid-line after space → `TerraAI`.** | ⚠ appends at end, not at cursor. |
| R6 | **Mid-word completion.** | ✘ `hello Ter` → `hello TerTerraAI `. |
| R7 | **Case-insensitive prefix matching.** | ✘ none. |
| R8 | **Bell on no match.** | ✘ no `self.bell()`. |
| R9 | **Notices have their own color pair** (CSS for `-!-` rows). | ✘ unstyled. |
| R10 | **Alt+Left / Alt+Right tab switching is tested.** | ⚠ bindings exist, no test. |
| R11 | **Test that UI stays responsive during AI call.** | ✘ no such test. |
| R12 | **Implicit-PM-routing test exists.** | ✓ already present. |

> **The console must not know the prefix character.** SOPEL owns `core.prefix`;
> the console neither reads it nor hardcodes it. Tab completion uses the bot *nick*
> (which the console already has via `client.terra.config.bot_nick`), not any prefix.

## Design: route the console through SOPEL

The console will mirror production's dispatch path (`~/git/sopel`):

1. `PreTrigger(bot_nick, raw_line)` — only needs nick + line.
2. `bot.rules.get_triggered_rules(bot, pretrigger)` — rules registered at import
   by `@command` / `@rule_lazy` / `@rule` decorators. Returns `[(rule, match)]`.
3. For each: `Trigger(bot.settings, pretrigger, match, account=None)` (SOPEL
   already stripped the prefix via the rule's regex), wrap bot in
   `SopelWrapper(bot, trigger)`, call `rule.execute(...)` → real handler runs.

`FakeBot` gains `settings` (real `sopel.config.Config` with a `[core]` section:
`nick="TerraAI"`, `prefix="."`) and `rules` (real `RulesManager` populated by
importing `terra_ai.plugin`). Keeps `say`/`reply`/`notice`/`isupport`/`messages`/`notices`.

A single new entry point in `plugin.py` — `dispatch_line(bot, nick, line, is_pm)` —
runs steps 1-3 and returns `{"say": [...], "notice": [...]}`. The console calls it
directly. `FakeTrigger`, `handle_channel_message`, `handle_pm_message`, and the
`trigger_char`/`trigger_phrase` reads all leave the console. **The console never
reads or hardcodes the prefix** — SOPEL strips it inside `Trigger` via the rule
regex built from `core.prefix`.

## Files to change

| File | Change |
|---|---|
| `terra_ai/plugin.py` | Add `dispatch_line(bot, nick, line, is_pm=False)`. |
| `test_tool/console.py` | `FakeBot` exposes `settings` + `rules`. Drop `FakeTrigger`. `send_*` call `dispatch_line`. Fix tab completion (R3-R8). Add notice color styling (R9). Drop `trigger_char`/`trigger_phrase` reads. |
| `tests/conftest.py` | Drop `trigger_char`/`trigger_phrase` from `_make_test_config`. |
| `tests/test_commands.py` | Drop `trigger_char="-"` from `prompts` fixture. |
| `tests/test_console.py` | Replace `client.trigger_char` / `client.terra.config.trigger_phrase` reads with a shared helper. Add Alt+Left/Right test (R10) + UI-responsive-during-AI test (R11). |
| `tests/test_console_screenshots.py` | Same read-replacement; rewrite tab-completion tests (R3-R8). |
| `docs/release-0.0.2/console-feature.md` + `console-plan.md` | Describe SOPEL-sourced prefix + `$nick` addressing; remove `trigger_char`/`trigger_phrase` spec blocks. |

## Step-by-step

### Step 1 — Add `dispatch_line` in plugin.py
- [ ] Add `dispatch_line(bot, nick, line, is_pm=False)`:
  - `pretrigger = PreTrigger(bot.settings.core.nick, line)`
  - for each `(rule, match) in bot.rules.get_triggered_rules(bot, pretrigger)`:
    `trigger = Trigger(bot.settings, pretrigger, match, account=None)`;
    `wrapper = <minimal SopelWrapper>(bot, trigger)`; `rule.execute(wrapper, trigger)`
  - return `{"say": list(bot.messages), "notice": list(bot.notices)}`
- [ ] Additive only — do NOT delete `handle_*_message`/`FakeTrigger` yet (tests
  still use them). Run `pytest --ignore=tests/test_ergo.py -q`.

### Step 2 — Rebuild `FakeBot` with `settings` + `rules`
- [ ] Construct a minimal `sopel.config.Config` with `[core]` (`nick="TerraAI"`,
  `prefix="."`) → `self.settings`.
- [ ] `self.rules` = `RulesManager` populated with the plugin's registered rules
  (verify population mechanism at implementation — see risk §1).
- [ ] Keep `messages`, `notices`, `isupport`, `say`/`reply`/`notice`.
- [ ] Sanity-check: `bot.settings.core.prefix` is defined and `bot.rules` has the
  terraai command rules.

### Step 3 — Wire console to `dispatch_line`, drop `FakeTrigger`
- [ ] `TerraAITestClient.__init__`: drop `self.trigger_char`.
- [ ] `send_message` / `send_as` / `send_pm`: remove `FakeTrigger` +
  `handle_*_message`; call
  `terra_plugin.dispatch_line(self.bot, nick, text, is_pm=...)`.
- [ ] Delete the `FakeTrigger` class.
- [ ] Run `pytest --ignore=tests/test_ergo.py -q`.

### Step 4 — Fix tab completion (R4-R9)
- [ ] Rewrite `TerraAIApp._handle_tab_completion`:
  - find word start by scanning back from cursor over non-space chars
  - start-of-line → `botnick + ": "`; mid-line → `botnick + " "`
  - case-insensitive prefix match of partial against the nick
  - no match → `self.bell()`, leave input unchanged
- [ ] Drop `self.trigger_phrase` (completion uses the bot nick, which SOPEL
  sources automatically).
- [ ] Update `test_console_screenshots.py` tab-completion tests.

### Step 5 — Notice styling (R9)
- [ ] Add CSS for `-!-` notice rows in `TerraAIApp.CSS` (distinct color pair).
- [ ] Confirm notices render with the new style in a screenshot test.

### Step 6 — Update tests + add missing ones (R10, R11)
- [ ] `conftest.py`: drop `trigger_char`/`trigger_phrase` from `_make_test_config`.
- [ ] `test_commands.py`: drop `trigger_char="-"` from `prompts` fixture.
- [ ] Add shared helper; replace every `client.trigger_char` /
  `client.terra.config.trigger_phrase` read in `test_console.py` +
  `test_console_screenshots.py`.
- [ ] Add `test_alt_left_alt_right_switch_tabs` (R10).
- [ ] Add `test_ui_responsive_during_ai_call` (R11): type a message, assert a
  "Thinking..." row renders before the AI response.
- [ ] Run `pytest --ignore=tests/test_ergo.py -q` after each sub-step.

### Step 7 — Update docs
- [ ] `console-feature.md` + `console-plan.md`: describe SOPEL-sourced prefix
  (`settings.core.prefix`, default `.`) and `$nick` addressing; remove the
  `_default_test_config` `trigger_char`/`trigger_phrase` spec blocks.

## Verification (run after every step)

```bash
cd ~/agentic-repos/terra-ai-agent2

pytest --ignore=tests/test_ergo.py -q          # mock suite (must be green)
pytest tests/test_ergo.py -q                  # SOPEL integration (must still pass)
source ~/.terra-ai/.env && pytest tests/test_console.py -v --real -m real   # real API (optional)
python test_tool/console.py                   # manual interactive
```

## Risks

1. **Populating `FakeBot.rules`.** `RulesManager` is normally filled by SOPEL's
   plugin loader; importing `terra_ai.plugin` registers decorators into a
   module-level manager. `bot.rules` must point at a manager containing *our*
   rules (ideally only ours). Verify at implementation whether to register rules
   directly onto a fresh `Manager` or reuse SOPEL's loader.
2. **`SopelWrapper(bot, trigger)`** proxies `say`/`notice`/`isupport` to whatever
   it's given. Confirm the proxy works when they're plain methods / a plain
   `isupport` dict rather than a full `Sopel` instance.
3. **`bot.settings.core.prefix`** — SOPEL's default is the regex `\\.`. The
   console's config must include a `[core]` section so the prefix is defined.
   `_prefix_fallback_loader` (plugin.py:252) already demonstrates this works.
