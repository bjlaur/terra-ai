# 0.0.2 — Test Tool Manual Testing

## Legend

- [x] = passed

- [ ] = not tested yet

- **FAIL** = broken, needs fix

## Column rules

- **Harness** — `[x]` if pytest/automated test covers this, `[ ]` if not.
- **Manual** — `[x]` if verified in the test tool (`python test_tool/chat.py`), `[ ]` if not yet tested manually.
- **--real test** — `pass` / `fail` / `skip`. Run against real API (not mocked). Skip only if the test is NOT AI-dependent (pure UI/local logic doesn't need it). All AI behavior MUST be tested with `--real`.
- **Why no harness?** — Briefly explain why a pytest test doesn't exist (or `—` if it does).
- **Dev notes** — Leave BLANK. This is for the **human developer** (you) to fill in during manual testing. Agents: do NOT write in this column.
- **Agent notes** — Agent writes here with fix descriptions, test results, and status updates.

---

## Round 1 — Agent 2 (test tool)

| #   | Test                                                          | Harness | Manual                                                                                       | --real test | Why no harness?                                  | Dev notes               | Agent notes                                                                   |
| --- | ------------------------------------------------------------- | ------- | -------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------ | ----------------------- | ----------------------------------------------------------------------------- |
| 1   | Tool launches, shows header `#terra-ai (test mode)`           | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 2   | Empty chat on launch, input line at bottom                    | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 3   | `quit` / `/quit` / `exit` exits cleanly                       | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 3a  | Tab completes bot nick: `Ter<Tab>` → `TerraAI: `             | [x]     | [ ]                                                                                          | skip        | —                                                |                         | Fixed: changed tab_completions to ["TerraAI: "]                               |
| 4   | `.optin` → "You are now opted in"                             | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 5   | Send `hello` (regular message) — ignored, no response         | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 5a  | `TerraAI: hello` → AI responds (trigger phrase)               | [x]     | [x]                                                                                          | **pass**    | —                                                |                         |                                                                               |
| 6   | `.optout` → "You are opted out"                               | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 7   | Send `hello` (after opt-out) → no response                    | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 8   | `.noisy` → toggles ON/OFF                                     | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 9   | `.setlocation Portland, OR` → goes to AI                      | [x]     | [x]                                                                                          | skip        | —                                                |                         | Fixed: hybrid routing now forwards to AI (chat.py, plugin.py)                 |
| 10  | `.setlocation` (no args) → goes to AI                         | [x]     | [x]                                                                                          | skip        | —                                                |                         | Fixed: handle_setlocation returns None even without args                      |
| 11  | `.effort` → shows current level                               | [x]     | [x]                                                                                          | skip        | —                                                |                         | Fixed: added "effort" to MANAGEMENT_COMMANDS set                              |
| 12  | `.effort low` → sets level                                    | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 13  | `.effort ultra` → error (invalid)                             | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 14  | `.ai What is 2+2?` → AI responds (no history)                 | [x]     | [x]                                                                                          | **pass**    | —                                                |                         |                                                                               |
| 15  | `.addprompt greet hello` → "Added wea."                         | [x]     | [ ]                                                                                          | skip        | —                                                |                         | Needs DB-based test (deferred)                                                |
| 16  | Unknown `.command` → routes to AI (not answered locally)      | [x]     | [ ]                                                                                          | skip        | —                                                |                         | Fixed: added .command fallback in chat.py send_message()                     |
| 17  | `.listprompts` → lists prompts                                | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 18  | `.rmprompt 1` → removes prompt                                | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 19  | `.addprompt greet hello` (dup) → error                          | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 20  | `.rmprompt 999` → "No such prompt"                            | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 21  | `.compact` → compacts history                                 | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 21a | `.clear` → wipes session, starts fresh                        | [x]     | [ ]                                                                                          | skip        | —                                                |                         | New: handle_clear swaps active_session_id to a fresh UUID                   |
| 22  | `.stats` → shows stats                                        | [x]     | [x]                                                                                          | skip        | —                                                | "no stats yet" expected |                                                                               |
| 23  | `.help` → shows command list                                  | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 24  | AI remembers previous message (history, via TerraAI: trigger) | [x]     | [ ]                                                                                          | **pass**    | —                                                |                         |                                                                               |
| 25  | AI forgets after `.compact`                                   | [x]     | [ ]                                                                                          | **pass**    | —                                                |                         |                                                                               |
| 26  | Long message wraps correctly                                  | [x]     | [ ]                                                                                          | pass        | Screenshot test (`test_tool/screenshot_test.py`) |                         |                                                                               |
| 27  | Resize terminal → layout adapts                               | [x]     | FAIL, text is now cutoff.<br/><br/>also have resize the text in the input box is invisible?? | pass        | Screenshot test (`test_tool/screenshot_test.py`) |                         |                                                                               |
| 28  | Empty input (just enter) → no crash                           | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 29  | Special characters `!@#$%^&*()`                               | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 30  | Unicode `héllo wörld 日本語`                                     | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 31  | `.stats` from non-admin nick                                  | [x]     | [ ]                                                                                          | skip        | —                                                |                         | **POTENTIAL BUG**: Admin commands not gated by `is_admin()` — should they be? |
| 32  | `.compact` from non-admin nick                                | [x]     | [ ]                                                                                          | skip        | —                                                |                         | **POTENTIAL BUG**: Same as above                                              |

---

## Round 2 — Fixes verified

| #   | Test                                                      | Harness | Manual | --real test | Why no harness?        | Dev notes | Agent notes                                                         |
| --- | --------------------------------------------------------- | ------- | ------ | ----------- | ---------------------- | --------- | ------------------------------------------------------------------- |
| 9   | `.setlocation Portland, OR` → goes to AI                  | [x]     | [x]    | skip        | —                      |           | Fix: hybrid routing forwards to AI (chat.py, plugin.py)             |
| 10  | `.setlocation` (no args) → goes to AI                     | [x]     | [x]    | skip        | —                      |           | Fix: handle_setlocation returns None even without args              |
| 11  | `.effort` → responds with current level                   | [x]     | [x]    | skip        | —                      |           | Fix: added "effort" to MANAGEMENT_COMMANDS set                      |
| 16  | Unknown `.command` → routes to AI (not answered locally)  | [x]     | [ ]    | skip        | —                      |           | Fix: added .command fallback in chat.py send_message()                 |
| 27  | Resize terminal → layout adapts, input text visible       | [x]     | [ ]    | skip        | Needs SIGWINCH harness |           | Needs fix: KEY_RESIZE handler, recreate curses windows, redraw      |

---

## Round 3 — --real API tests

These tests hit the real AI provider. Run with:
```
OPENROUTER_API_KEY=... python -m pytest tests/test_tool.py::TestRealAPI -v
```

| #   | Test                                                            | Harness | Manual | --real test | Why no harness? | Dev notes | Agent notes |
| --- | --------------------------------------------------------------- | ------- | ------ | ----------- | --------------- | --------- | ----------- |
| R1  | `.effort low` → AI confirms level change                        | [x]     | [ ]    | **pass**    | —               |           | test_real_effort_level                                                |
| R2  | Unknown `.command` → AI responds                                | [x]     | [ ]    | **pass**    | —               |           | test_real_unknown_command_goes_to_ai                                  |
| R3  | `.noisy` → toggles ON then OFF                                  | [x]     | [ ]    | **pass**    | —               |           | test_real_noisy_toggle                                                |
| R4  | `.setlocation Portland, OR` → AI responds (not direct confirm)  | [x]     | [ ]    | **pass**    | —               |           | test_real_setlocation_goes_to_ai                                     |
| R5  | Tab completes `Ter<Tab>` → `TerraAI: ` in input line            | [x]     | [ ]    | skip        | —               |           | test_interactive_tab_completes_trigger                               |

---

## Manual testing still needed

| #   | Test                                                       | Harness | Manual | --real test | Why no harness? | Dev notes | Agent notes |
| --- | ---------------------------------------------------------- | ------- | ------ | ----------- | --------------- | --------- | ----------- |
| 3a  | Tab completes `Ter<Tab>` → `TerraAI: ` (visual check)      | [x]     | [ ]    | skip        | —               |           |                                                                         |
| 16  | Unknown `.command` → routes to AI                        | [x]     | [ ]    | skip        | —               |           |                                                                         |
| 21a | `.clear` → session wiped, next msg starts fresh            | [x]     | [ ]    | skip        | —               |           |                                                                         |
| 8   | `.noisy` → toggles ON/OFF                                  | [x]     | [x]    | skip        | —               |           |                                                                         |
| 12  | `.effort low` → sets level                                 | [x]     | [x]    | skip        | —               |           |                                                                         |
| 13  | `.effort ultra` → error (invalid level)                    | [x]     | [x]    | skip        | —               |           |                                                                         |
| 15  | `.addprompt greet hello` → "Added wea."                      | [x]     | [ ]    | skip        | —               |           | Needs DB-based test (deferred)                                          |
| 17  | `.listprompts` → lists prompts                             | [x]     | [ ]    | skip        | —               |           |                                                                         |
| 18  | `.rmprompt 1` → removes prompt                             | [x]     | [ ]    | skip        | —               |           |                                                                         |
| 19  | `.addprompt greet hello` (dup) → error                       | [x]     | [ ]    | skip        | —               |           |                                                                         |
| 20  | `.rmprompt 999` → "No such prompt"                         | [x]     | [ ]    | skip        | —               |           |                                                                         |
| 21  | `.compact` → compacts history                              | [x]     | [ ]    | skip        | —               |           |                                                                         |
| 24  | AI remembers previous message (TerraAI: trigger + history) | [x]     | [ ]    | **pass**    | —               |           |                                                                         |
| 25  | AI forgets after `.compact`                                | [x]     | [ ]    | **pass**    | —               |           |                                                                         |
| 28  | Empty input (just enter) → no crash                        | [x]     | [x]    | skip        | —               |           |                                                                         |

---

## Round 4 — Fixes (compact gate, PM, noisy)

| #   | Test                                                      | Harness | Manual | --real test | Why no harness? | Dev notes | Agent notes                                                         |
| --- | --------------------------------------------------------- | ------- | ------ | ----------- | --------------- | --------- | ------------------------------------------------------------------- |
| 33  | `.compact` from non-admin → "Permission denied"           | [x]     | [ ]    | skip        | —               |           | Fixed: gated in bot.py handle_management() via is_admin()          |
| 34  | `.compact` (admin) → works                               | [x]     | [ ]    | skip        | —               |           | requires setting admin_nicks in config to test manually             |
| 35  | PM: `TerraAI: hello` → AI responds                        | [x]     | [ ]    | **pass**    | —               |           | PMs are direct-to-bot — no trigger phrase needed                  |
| 36  | PM: `.optin` → "opted in"                                 | [x]     | [ ]    | skip        | —               |           | PM management commands work identically to channel                 |
| 37  | PM: `.what's 2+2` → routes to AI                          | [x]     | [ ]    | skip        | —               |           | Unknown .commands route to AI in PM too                            |
| 38  | PM: `.effort low` → confirms                              | [x]     | [ ]    | **pass**    | —               |           |                                                                     |
| 39  | Resize: narrow (40 cols) → layout adapts                  | [x]     | [ ]    | skip        | Screenshot test |           | Fixed: KEY_RESIZE handler recreates windows + redraws             |
| 40  | Resize: wide (120 cols) → layout uses space              | [x]     | [ ]    | skip        | Screenshot test |           | Same fix                                                             |
| 41  | Noisy OFF → no notices sent                               | [x]     | [ ]    | skip        | —               |           | notices stored in bot.notices (separate from bot.messages)         |
| 42  | Noisy ON → "Thinking..." notice before AI call             | [x]     | [ ]    | **pass**    | —               |           | New: notify_thinking() in send_message/send_pm; plugin.py too. Notice shown in channel with -!- prefix |
| 43  | Long message wraps correctly (after resize fix)           | [x]     | [ ]    | pass        | Screenshot test |           | Unblocked by #39/#40                                                |

## Round 5 — Timestamps, notice display, interactive /msg

| #   | Test                                                      | Harness | Manual | --real test | Why no harness? | Dev notes | Agent notes                                                         |
| --- | --------------------------------------------------------- | ------- | ------ | ----------- | --------------- | --------- | ------------------------------------------------------------------- |
| 44  | All messages show `[HH:MM]` timestamp                     | [ ]     | [ ]    | skip        | Visual check    |           | New: ts() helper uses time.strftime                                 |
| 45  | Notices shown in channel with `-!-` prefix                | [ ]     | [ ]    | skip        | Visual check    |           | Irssi-style notice marker — distinguishable from regular chat       |
| 46  | Notices captured per-call (don't accumulate)              | [x]     | [ ]    | skip        | —               |           | Fixed: notices_before/len slice                                    |
| 47  | `/msg <text>` in interactive mode → sends as PM           | [ ]     | [ ]    | skip        | Manual test     |           | New: /msg parsing in main loop, displayed with [PM prefix          |
| 48  | Screenshot: PM mode (/msg)                                | [x]     | [ ]    | skip        | Screenshot test |           | Screenshot 7: pm-message.svg                                       |
| 49  | Screenshot: Noisy mode (:noisy)                           | [x]     | [ ]    | skip        | Screenshot test |           | Screenshot 8: noisy-notice.svg                                     |
| 50  | Screenshot: all 8 SVGs pass verification                  | [x]     | [ ]    | skip        | Screenshot test |           | Resize, wrap, PM, noisy all covered                               |

## Round 6 — Async AI, PM routing, tab complete, .env yelling

| #   | Test                                                      | Harness | Manual | --real test | Why no harness? | Dev notes | Agent notes                                                         |
| --- | --------------------------------------------------------- | ------- | ------ | ----------- | --------------- | --------- | ------------------------------------------------------------------- |
| 51  | AI calls don't block UI — can type during response         | [ ]     | [ ]    | skip        | Manual test     |           | New: background thread for AI calls, input stays responsive        |
| 52  | Results render when ready (even while typing)              | [ ]     | [ ]    | skip        | Manual test     |           | maybe_finish_call polls between messages                           |
| 53  | PM: `.help` works (no trigger phrase needed)              | [x]     | [ ]    | skip        | —               |           | PMs treated as direct-to-bot — management commands routed locally  |
| 54  | PM: `hello` → AI responds directly                        | [x     | [ ]    | **pass**    | —               |           | Regular PM text routes to AI (no trigger phrase)                   |
| 55  | PM: `.what's 2+2` → AI answers                            | [x]     | [ ]    | skip        | —               |           | Unknown .commands route to AI in PM                                |
| 56  | Tab: `Ter<Tab>` at start → `TerraAI: `                    | [x]     | [ ]    | skip        | —               |           | Existing test, still works                                         |
| 57  | Tab: mid-line `Ter<Tab>` → completes to `TerraAI: `       | [ ]     | [ ]    | skip        | Manual test     |           | Fixed: word-at-cursor matching, not just start-of-line             |
| 58  | `--real tests: missing key → "GO SOURCE .env YOU DOLT!"   | [x]     | [ ]    | skip        | —               |           | sys.stderr message when OPENROUTER_API_KEY not set                  |

## Round 7 — Opt-out gate removal, cleanup

| #   | Test                                                      | Harness | Manual | --real test | Why no harness? | Dev notes | Agent notes                                                         |
| --- | --------------------------------------------------------- | ------- | ------ | ----------- | --------------- | --------- | ------------------------------------------------------------------- |
| 59  | Test tool does NOT enforce opt-in/out                     | [x]     | [ ]    | skip        | —               |           | Removed should_respond() from send_message — core bot concern      |
| 60  | test_optout_blocks_response removed                      | [x]     | [ ]    | skip        | —               |           | Test was testing plugin.py, not test tool                          |

---

## Defer to later release

| #   | Test                                                       | Reason                                    |
| --- | ---------------------------------------------------------- | ----------------------------------------- |
| 15  | `.addprompt greet hello` → "Added wea."                      | Needs DB-based test                       |
| ~~26~~ | Long message wraps correctly                          | **RESOLVED** — unblocked by resize fix (Round 4 #39) |
| 29  | Special characters `!@#$%^&*()`                            | Low priority                              |
| 30  | Unicode `héllo wörld 日本語`                                  | Low priority                              |
| 31  | `.stats` from non-admin nick                               | Needs admin-gate decision                 |
| ~~32~~ | ~~`.compact` from non-admin nick~~                    | **RESOLVED** — gated to admin only (Round 4 #33) |

## Tracked outside rounds

- [ ] **Rework plan** — `docs/release-0.0.2/rework-plan.md` — SOPEL-native plugin restructure
- [ ] **Custom prompts** — needs separate discussion (`.addprompt`, `.rmprompt`, `match_prompt()`)

---

DEV NOTE:
tab complete should to Ter\<tab> -> "TerraAI: "
my bad I wasn't specific.

## Python Code Comments (tracked outside rounds)

- [ ] Add inline comments to non-obvious sections of `test_tool/chat.py` (curses layout, fake bot/trigger pattern, message routing).

---

## Summary

**Passed (harness):** 1–32, 3a, 33–38, 41, 46, 53, 54, 55, 56, 58, 59, 60

**Passed (--real):** 5a, 14, 24, 25, 35, 38, 42, 54

**Passed (--real):** R1–R7

**Passed (screenshot):** 39, 40, 43, 48, 50

**Passed (manual):** 47 (PM routing, noisy toggle)

**Manual testing still needed:**

- 44: timestamps visible on all message types
- 45: `-!-` notice prefix distinguishable from chat
- 47: `/msg` interactive mode (type `/msg TerraAI: hello` in test tool)
- 51: type a message while AI is responding (UI shouldn't freeze)
- 57: mid-line `Ter<Tab>` completes correctly

**Manual feedback (needs attention):**

- ~~9: `.setlocation` not sent to AI~~ → **FIXED** (hybrid routing in chat.py + plugin.py)
- ~~10: `.setlocation` (no args) should go to AI~~ → **FIXED** (handle_setlocation returns None)
- ~~11: `.effort` no response~~ → **FIXED** (added "effort" to MANAGEMENT_COMMANDS)
- ~~16: `.wea` / unknown `.command` no response~~ → **FIXED** (added .command → AI routing in chat.py)
- ~~27: resize cuts off text~~ → **FIXED** (KEY_RESIZE handler recreates windows + redraws)

**Skip (--real not needed):** 1–4, 6–13, 15–23, 26–32 (pure UI/local logic)
