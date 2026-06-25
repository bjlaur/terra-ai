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
| 3a  | Tab completes bot nick: `Ter<Tab>` → `TerraAI`                | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 4   | `.optin` → "You are now opted in"                             | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 5   | Send `hello` (regular message) — ignored, no response         | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 5a  | `TerraAI: hello` → AI responds (trigger phrase)               | [x]     | [ x]                                                                                         | **pass**    | —                                                |                         |                                                                               |
| 6   | `.optout` → "You are opted out"                               | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 7   | Send `hello` (after opt-out) → no response                    | [x]     | [x]                                                                                          | skip        | —                                                |                         |                                                                               |
| 8   | `.noisy` → toggles ON/OFF                                     | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 9   | `.setlocation Portland, OR` → goes to AI                      | [x]     | [x]                                                                                          | skip        | —                                                |                         | Fixed: hybrid routing now forwards to AI (chat.py, plugin.py)                   |
| 10  | `.setlocation` (no args) → goes to AI                         | [x]     | [x]                                                                                          | skip        | —                                                |                         | Fixed: handle_setlocation returns None even without args                       |
| 11  | `.effort` → shows current level                               | [x]     | [x]                                                                                          | skip        | —                                                |                         | Fixed: added "effort" to MANAGEMENT_COMMANDS set                               |
| 12  | `.effort low` → sets level                                    | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 13  | `.effort ultra` → error (invalid)                             | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 14  | `.ai What is 2+2?` → AI responds (no history)                 | [x]     | [ x]                                                                                         | **pass**    | —                                                |                         |                                                                               |
| 15  | `.addprompt wea sunny` → "Added wea."                         | [x]     | skip. this is a bad way to test this. I'll figure out a good way later.                      | skip        | —                                                |                         |                                                                               |
| 16  | `.wea` → responds with custom prompt                        | [x]     | [x]                                                                                          | skip        | —                                                |                         | Fixed: added match_prompt() check to test_tool/chat.py send_message()         |
| 17  | `.listprompts` → lists prompts                                | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 18  | `.rmprompt 1` → removes prompt                                | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 19  | `.addprompt wea sunny` (dup) → error                          | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 20  | `.rmprompt 999` → "No such prompt"                            | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
| 21  | `.compact` → compacts history                                 | [x]     | [ ]                                                                                          | skip        | —                                                |                         |                                                                               |
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

## Round 2 — Agent 2 (test tool feedback fixes)

| #   | Test                                                          | Harness | Manual                                                                                       | --real test | Why no harness?                                  | Dev notes               | Agent notes                                                                   |
| --- | ------------------------------------------------------------- | ------- | -------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------ | ----------------------- | ----------------------------------------------------------------------------- |
| 9   | `.setlocation Portland, OR` → goes to AI                      | [x]     | [x]                                                                                          | skip        | —                                                |                         | Fixed: hybrid routing forwards to AI (chat.py, plugin.py)                      |
| 10  | `.setlocation` (no args) → goes to AI                         | [x]     | [x]                                                                                          | skip        | —                                                |                         | Fixed: handle_setlocation returns None even without args                       |
| 11  | `.effort` → shows current level                               | [x]     | [x]                                                                                          | skip        | —                                                |                         | Fixed: added "effort" to MANAGEMENT_COMMANDS set                               |
| 16  | `.wea` → responds with custom prompt                        | [x]     | [x]                                                                                          | skip        | —                                                |                         | Fixed: added match_prompt() check to test_tool/chat.py send_message()         |
| 27  | Resize terminal → layout adapts, input visible               | [x]     | [ ]                                                                                          | skip        | Needs SIGWINCH/KEY_RESIZE harness (pty + resize) |                         | Needs fix: handle KEY_RESIZE, recreate windows, redraw                        |

---

## Python Code Comments (tracked outside rounds)

- [ ] Add inline comments to non-obvious sections of `test_tool/chat.py` (curses layout, fake bot/trigger pattern, message routing).

---

## Summary

**Passed (harness):** 1–32, 3a

**Passed (--real):** 5a, 14, 24, 25

**Manual feedback (needs attention):**
- ~~9: `.setlocation` not sent to AI~~ → **FIXED** (hybrid routing in chat.py + plugin.py)
- ~~10: `.setlocation` (no args) should go to AI~~ → **FIXED** (handle_setlocation returns None)
- ~~11: `.effort` no response~~ → **FIXED** (added "effort" to MANAGEMENT_COMMANDS)
- ~~16: `.wea` no response~~ → **FIXED** (added match_prompt() to test_tool routing)
- 27: resize cuts off text, input box text invisible

**Skip (--real not needed):** 1–4, 6–13, 15–23, 26–32 (pure UI/local logic)
