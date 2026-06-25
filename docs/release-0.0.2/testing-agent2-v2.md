# 0.0.2 — Test Tool Manual Testing (v2)

**Legend:**
- [x] = passed (verified)
- [ ] = not tested yet
- **FAIL** = broken, needs fix

**Columns:**
- **Harness** — `[x]` if pytest/automated test covers this
- **Manual** — `[x]` if verified in the test tool (`python test_tool/chat.py`)
- **--real** — `pass` / `fail` / `skip` (run against real API)
- **Mine** — `[x]` if **you** (the human developer) have manually verified this yourself
- **Why no harness?** — Why no pytest test exists (or `—` if it does)
- **Dev notes` — For the human developer to fill in. Agents: do NOT write here.
- **Agent notes** — Agent writes here with fix descriptions and test results

---

## Core Routing

| #   | Test                                                          | Harness | Manual | --real | Mine | Why no harness? | Dev notes | Agent notes |
| --- | ------------------------------------------------------------- | ------- | ------ | ------ | ---- | ---------------- | --------- | ----------- |
| 1   | Tool launches, shows header `#terra-ai (test mode)`           | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 2   | Empty chat on launch, input line at bottom                    | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 3   | `quit` / `/quit` / `exit` exits cleanly                       | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 3a  | Tab completes bot nick: `Ter<Tab>` → `TerraAI: `             | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 4   | `.optin` → "You are now opted in"                             | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 5   | Send `hello` (regular message) — ignored, no response         | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 5a  | `TerraAI: hello` → AI responds (trigger phrase)               | [x]     | [x]    | **pass** | [ ] | —                |           |             |
| 6   | `.optout` → "You are opted out"                               | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 7   | Send `hello` (after opt-out) → no response                    | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 8   | `.noisy` → toggles ON/OFF                                     | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 9   | `.setlocation Portland, OR` → goes to AI                      | [x]     | [x]    | skip   | [ ]  | —                |           | Hybrid routing forwards to AI |
| 10  | `.setlocation` (no args) → goes to AI                         | [x]     | [x]    | skip   | [ ]  | —                |           | handle_setlocation returns None |
| 11  | `.effort` → shows current level                               | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 12  | `.effort low` → sets level                                    | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 13  | `.effort ultra` → error (invalid)                             | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 14  | `.ai What is 2+2?` → AI responds (no history)                 | [x]     | [x]    | **pass** | [ ] | —                |           |             |
| 15  | `.addprompt greet hello` → "Added wea."                         | [x]     | [ ]    | skip   | [ ]  | —                |           | Custom prompts TBD |
| 16  | Unknown `.command` → routes to AI (not answered locally)      | [x]     | [x]    | skip   | [ ]  | —                |           | .command fallback |
| 17  | `.listprompts` → lists prompts                                | [x]     | [ ]    | skip   | [ ]  | —                |           | Custom prompts TBD |
| 18  | `.rmprompt 1` → removes prompt                                | [x]     | [ ]    | skip   | [ ]  | —                |           | Custom prompts TBD |
| 19  | `.addprompt greet hello` (dup) → error                          | [x]     | [ ]    | skip   | [ ]  | —                |           | Custom prompts TBD |
| 20  | `.rmprompt 999` → "No such prompt"                            | [x]     | [ ]    | skip   | [ ]  | —                |           | Custom prompts TBD |
| 21  | `.compact` → compacts history                                 | [x]     | [ ]    | skip   | [ ]  | —                |           |             |
| 21a | `.clear` → wipes session, starts fresh                        | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 22  | `.stats` → shows stats                                        | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 23  | `.help` → shows command list                                  | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 24  | AI remembers previous message (history, via TerraAI: trigger) | [x]     | [ ]    | **pass** | [ ] | —                |           |             |
| 25  | AI forgets after `.compact`                                   | [x]     | [ ]    | **pass** | [ ] | —                |           |             |

## PM (Private Messages)

| #   | Test                                                          | Harness | Manual | --real | Mine | Why no harness? | Dev notes | Agent notes |
| --- | ------------------------------------------------------------- | ------- | ------ | ------ | ---- | ---------------- | --------- | ----------- |
| 35  | PM: `TerraAI: hello` → AI responds                            | [x]     | [ ]    | **pass** | [ ] | —                |           | PMs are direct-to-bot |
| 36  | PM: `.optin` → "opted in"                                     | [x]     | [ ]    | skip   | [ ]  | —                |           |             |
| 37  | PM: `.what's 2+2` → routes to AI                              | [x]     | [ ]    | skip   | [ ]  | —                |           |             |
| 38  | PM: `.effort low` → confirms                                  | [x]     | [ ]    | **pass** | [ ] | —                |           |             |
| 39  | PM: `.help` works (no trigger phrase needed)                  | [x]     | [ ]    | skip   | [ ]  | —                |           |             |
| 40  | PM: `hello` → AI responds directly                            | [x]     | [ ]    | **pass** | [ ] | —                |           | No trigger phrase needed |
| 41  | PM: `.clear` → wipes session                                  | [x]     | [ ]    | skip   | [ ]  | —                |           |             |
| 42  | PM: `.compact` from non-admin → "Permission denied"           | [x]     | [ ]    | skip   | [ ]  | —                |           |             |

## Noisy Mode

| #   | Test                                                          | Harness | Manual | --real | Mine | Why no harness? | Dev notes | Agent notes |
| --- | ------------------------------------------------------------- | ------- | ------ | ------ | ---- | ---------------- | --------- | ----------- |
| 43  | Noisy OFF → no notices sent                                   | [x]     | [ ]    | skip   | [ ]  | —                |           |             |
| 44  | Noisy ON → "Thinking..." notice before AI call                 | [x]     | [ ]    | **pass** | [ ] | —                |           |             |
| 45  | Notice shown in channel with `-!-` prefix (irssi-style)       | [ ]     | [ ]    | skip   | [ ]  | Visual check     |           |             |
| 46  | Notices captured per-call (don't accumulate)                  | [x]     | [ ]    | skip   | [ ]  | —                |           |             |

## Resize & Display

| #   | Test                                                          | Harness | Manual | --real | Mine | Why no harness? | Dev notes | Agent notes |
| --- | ------------------------------------------------------------- | ------- | ------ | ------ | ---- | ---------------- | --------- | ----------- |
| 47  | Resize: narrow (40 cols) → layout adapts                      | [x]     | [ ]    | skip   | [ ]  | Screenshot test  |           |             |
| 48  | Resize: wide (120 cols) → layout uses space                  | [x]     | [ ]    | skip   | [ ]  | Screenshot test  |           |             |
| 49  | Long message wraps correctly                                  | [x]     | [ ]    | pass   | [ ]  | Screenshot test  |           | Unblocked by resize fix |
| 50  | All messages show `[HH:MM]` timestamp                         | [ ]     | [ ]    | skip   | [ ]  | Visual check     |           |             |
| 51  | Empty input (just enter) → no crash                           | [x]     | [x]    | skip   | [ ]  | —                |           |             |

## Interactive Mode

| #   | Test                                                          | Harness | Manual | --real | Mine | Why no harness? | Dev notes | Agent notes |
| --- | ------------------------------------------------------------- | ------- | ------ | ------ | ---- | ---------------- | --------- | ----------- |
| 52  | Interactive mode launches and exits                           | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 53  | Interactive mode accepts input                                | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 54  | Tab completes `Ter<Tab>` → `TerraAI: ` in input line          | [x]     | [x]    | skip   | [ ]  | —                |           |             |
| 55  | Tab mid-line `Ter<Tab>` → completes to `TerraAI` (just nick) | [ ]     | [ ]    | skip   | [ ]  | Manual test      |           |             |
| 56  | `/msg <text>` in interactive mode → sends as PM               | [ ]     | [ ]    | skip   | [ ]  | Manual test      |           |             |
| 57  | AI calls don't block UI — can type during response             | [ ]     | [ ]    | skip   | [ ]  | Manual test      |           | Background thread |
| 58  | Results render when ready (even while typing)                  | [ ]     | [ ]    | skip   | [ ]  | Manual test      |           | maybe_finish_call polls |
| 59  | Async AI call works (background thread, SQLite cross-thread)   | [x]     | [ ]    | **pass** | [ ]  | —                |           | check_same_thread=False |

## --real API Tests

| #   | Test                                                            | Harness | Manual | --real | Mine | Why no harness? | Dev notes | Agent notes |
| --- | --------------------------------------------------------------- | ------- | ------ | ------ | ---- | ---------------- | --------- | ----------- |
| R1  | `.effort low` → AI confirms level change                        | [x]     | [ ]    | **pass** | [ ] | —                |           |             |
| R2  | Unknown `.command` → AI responds                                | [x]     | [ ]    | **pass** | [ ] | —                |           |             |
| R3  | `.noisy` → toggles ON then OFF                                  | [x]     | [ ]    | **pass** | [ ] | —                |           |             |
| R4  | `.setlocation Portland, OR` → AI responds (not direct confirm)  | [x]     | [ ]    | **pass** | [ ] | —                |           |             |
| R5  | Tab completes `Ter<Tab>` → `TerraAI: ` in input line            | [x]     | [ ]    | skip   | [ ]  | —                |           |             |
| R6  | PM: `TerraAI: hello` → AI responds                              | [x]     | [ ]    | **pass** | [ ] | —                |           |             |
| R7  | PM: `.effort low` → confirms                                    | [x]     | [ ]    | **pass** | [ ] | —                |           |             |
| R8  | Noisy ON → "Thinking..." notice sent                            | [x]     | [ ]    | **pass** | [ ] | —                |           |             |

## Screenshots

| #   | Test                                                          | Harness | Manual | --real | Mine | Why no harness? | Dev notes | Agent notes |
| --- | ------------------------------------------------------------- | ------- | ------ | ------ | ---- | ---------------- | --------- | ----------- |
| S1  | Initial state: header, empty chat, input line                 | [x]     | [ ]    | skip   | [ ]  | Screenshot       |           | initial.svg |
| S2  | After message: user message + bot response                    | [x]     | [ ]    | skip   | [ ]  | Screenshot       |           | after-message.svg |
| S3  | Listprompts: prompt list displayed                            | [x]     | [ ]    | skip   | [ ]  | Screenshot       |           | listprompts.svg |
| S4  | Long message wraps                                            | [x]     | [ ]    | skip   | [ ]  | Screenshot       |           | long-message-wrap.svg |
| S5  | Resize narrow (40 cols)                                       | [x]     | [ ]    | skip   | [ ]  | Screenshot       |           | resize-narrow.svg |
| S6  | Resize wide (120 cols)                                        | [x]     | [ ]    | skip   | [ ]  | Screenshot       |           | resize-wide.svg |
| S7  | PM mode (/msg)                                                | [x]     | [ ]    | skip   | [ ]  | Screenshot       |           | pm-message.svg |
| S8  | Noisy mode (:noisy)                                           | [x]     | [ ]    | skip   | [ ]  | Screenshot       |           | noisy-notice.svg |

## Edge Cases & Misc

| #   | Test                                                          | Harness | Manual | --real | Mine | Why no harness? | Dev notes | Agent notes |
| --- | ------------------------------------------------------------- | ------- | ------ | ------ | ---- | ---------------- | --------- | ----------- |
| E1  | Special characters `!@#$%^&*()`                               | [x]     | [ ]    | skip   | [ ]  | —                |           | Low priority |
| E2  | Unicode `héllo wörld 日本語`                                     | [x]     | [ ]    | skip   | [ ]  | —                |           | Low priority |
| E3  | `.stats` from non-admin nick                                  | [x]     | [ ]    | skip   | [ ]  | —                |           | Needs admin-gate decision |
| E4  | `--real tests: missing key → "GO SOURCE .env YOU DOLT!"        | [x]     | [ ]    | skip   | [ ]  | —                |           |             |
| E5  | Test tool does NOT enforce opt-in/out (core bot concern)       | [x]     | [ ]    | skip   | [ ]  | —                |           | Removed should_respond() |

---

## Summary

**Total tests:** 63 (excluding screenshots)

**Passed (harness):** 1–32, 3a, 35–38, 40–44, 46–48, 51, 52–54, E1–E5

**Passed (--real):** 5a, 14, 24, 25, 35, 38, 40, 44, R1–R4, R6–R8

**Passed (screenshot):** S1–S8

**Passed (manual):** 1–3, 3a, 5–14, 21a, 22, 23, 51, 52–53, 54

**Need your verification (Mine = [ ]):** Everything with `[ ]` in the Mine column

**Out of scope (needs discussion):**
- Custom prompts (#15, 17–20) — TBD
- `.stats` admin gating (#E3) — needs decision
