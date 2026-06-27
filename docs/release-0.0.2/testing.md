# 0.0.2 — Testing Checklist

## Legend

- [x] = passed
- [ ] = not tested yet

- **FAIL** = broken, needs fix

## Columns

- **Harness** — `[x]` if pytest/automated test covers this, `[ ]` if not.
- **Manual** — `[x]` if verified live (test tool or ergo), `[ ]` if not yet tested manually.
- **--real test** — `pass` / `fail` / `skip`. Run against real API (not mocked). Skip only if the test is NOT AI-dependent (pure UI/local logic doesn't need it).
- **Why no harness?** — Briefly explain why a pytest test doesn't exist (or `—` if it does).
- **Why no --real test?** — Reason for skip, or `—` if --real was run.
- **Dev notes** — Leave BLANK. This is for the **human developer** (you) to fill in during manual testing. Agents: do NOT write in this column.
- **Agent notes** — Agent writes here with fix descriptions, test results, and status updates.

---

## Console (test_tool/console.py)

| #   | Test                                           | Harness | Manual | --real test | Why no harness?                   | Why no --real test? | Dev notes | Agent notes |
| --- | ---------------------------------------------- | ------- | ------ | ----------- | --------------------------------- | ------------------- | --------- | ----------- |
| 1   | Tool launches, shows header                    | [x]     | [ x]   | skip        | —                                 | —                   |           |             |
| 2   | Empty input → no crash                         | [x]     | [x ]   | skip        | —                                 | —                   |           |             |
| 3   | `quit`/`exit` exits cleanly                    | [x]     | x[ ]   | skip        | —                                 | —                   |           |             |
| 4   | Tab: nick at start-of-line → `TerraAI: `       | [x]     | [ ]x   | skip        | —                                 | —                   |           |             |
| 5   | Tab: nick mid-line → `TerraAI `                | [x]     | [ ]x   | skip        | —                                 | —                   |           |             |
| 6   | Tab: command completion `-op<Tab>` → `-optin ` | [x]     | [ ]x   | skip        | —                                 | —                   |           |             |
| 7   | Tab: no match → bell                           | [x]     | [ ]x   | skip        | —                                 | —                   |           |             |
| 8   | History: `KEY_UP` recalls previous input       | [x]     | [ ]x   | skip        | —                                 | —                   |           |             |
| 9   | Resize: layout adapts                          | [x]     | [ ]x   | skip        | —                                 | —                   |           |             |
| 10  | Long message wraps correctly                   | [x]     | [ ]x   | skip        | —                                 | —                   |           |             |
| 11  | Special characters `!@#$%^&*()`                | [x]     | [ ]    | skip        | differ                            | —                   |           |             |
| 12  | Unicode `héllo wörld 日本語`                      | [x]     | [ ]    | skip        | differ                            | —                   |           |             |
| 13  | Interactive: accepts input                     | [x]     | [ ]x   | skip        | —                                 | —                   |           |             |
| 14  | Interactive: accepts PM                        | [x]     | [ ]x   | skip        | —                                 | —                   |           |             |
| 15  | Interactive: Ctrl+D exits                      | [x]     | [ ]    | skip        | fail but don't care. I use ctrl+c | —                   |           |             |
| 16  | Screenshot: initial state                      | [x]     | [ ]    | skip        | —                                 | —                   |           |             |
| 17  | Screenshot: after message                      | [x]     | [ ]    | skip        | —                                 | —                   |           |             |
| 18  | Screenshot: PM tab                             | [x]     | [ ]    | skip        | —                                 | —                   |           |             |
| 19  | Screenshot: thinking notice                    | [x]     | [ ]    | skip        | —                                 | —                   |           |             |
| 20  | Screenshot: noisy toggle notice                | [x]     | [ ]    | skip        | —                                 | —                   |           |             |
| 21  | Screenshot: command list                       | [x]     | [ ]    | skip        | —                                 | —                   |           |             |
| 22  | Screenshot: start-of-line tab                  | [x]     | [ ]    | skip        | —                                 | —                   |           |             |
| 23  | Screenshot: mid-line tab                       | [x]     | [ ]    | skip        | —                                 | —                   |           |             |
| 24  | Screenshot: command tab                        | [x]     | [ ]    | skip        | —                                 | —                   |           |             |
| 25  | Screenshot: input history                      | [x]     | [ ]    | skip        | —                                 | —                   |           |             |
| 26  | Screenshot: F1/F2 tabs                         | [x]     | [ ]    | skip        | —                                 | —                   |           |             |

## Channel Messages

| #   | Test                                       | Harness | Manual       | --real test | Why no harness? | Why no --real test? | Dev notes | Agent notes |
| --- | ------------------------------------------ | ------- | ------------ | ----------- | --------------- | ------------------- | --------- | ----------- |
| 27  | `.optin` → opt-in confirmation             | [x]     | [ ]x         | skip        | —               | —                   |           |             |
| 28  | `.optout` → opt-out confirmation           | [x]     | [ ]x         | skip        | —               | —                   |           |             |
| 29  | Regular message (no prefix) → ignored      | [x]     | [ ]x         | skip        | —               | —                   |           |             |
| 30  | `TerraAI: hello` → AI responds             | [x]     | [ ]x         | skip        | —               | —                   |           |             |
| 31  | Unknown `.command` → routes to AI          | [x]     | [ ]          | skip        | —               | —                   |           |             |
| 32  | `.ai <prompt>` → AI responds (no history)  | [x]     | [ ]          | skip        | —               | —                   |           |             |
| 33  | `.noisy` → toggles ON/OFF                  | [x]     | differ       | skip        | —               | —                   |           |             |
| 34  | `.effort` → shows current level            | [x]     | differ       | skip        | —               | —                   |           |             |
| 35  | `.effort low` → sets level                 | [x]     | differ       | skip        | —               | —                   |           |             |
| 36  | `.effort ultra` → error (invalid)          | [x]     | differ       | skip        | —               | —                   |           |             |
| 37  | `.setlocation Portland, OR` → goes to AI   | [x]     | differ       | skip        | —               | —                   |           |             |
| 38  | `.setlocation` (no args) → goes to AI      | [x]     | differ       | skip        | —               | —                   |           |             |
| 39  | `.compact` → compacts history              | [x]     | differ       | skip        | —               | —                   |           |             |
| 40  | `.compact` non-admin → "Permission denied" | [x]     | differ       | skip        | —               | —                   |           |             |
| 41  | `.clear` → wipes session                   | [x]     | [ ]c         | skip        | —               | —                   |           |             |
| 42  | `.stats` → shows stats                     | [x]     | fail, differ | skip        | —               | —                   |           |             |
| 43  | `.help` → shows command list               | [x]     | [ ]x         | skip        | —               | —                   |           |             |
| 44  | `.addprompt <trigger> <text>` → added      | [x]     | differ       | skip        | —               | —                   |           |             |
| 45  | `.addprompt` duplicate → error             | [x]     | differ[ ]    | skip        | —               | —                   |           |             |
| 46  | `.listprompts` → lists prompts             | [x]     | [ ]differ    | skip        | —               | —                   |           |             |
| 47  | `.rmprompt 1` → removes prompt             | [x]     | [ ]differ    | skip        | —               | —                   |           |             |
| 48  | `.rmprompt 999` → "No such prompt"         | [x]     | [ ]differ    | skip        | —               | —                   |           |             |
| 49  | AI remembers conversation history          | [x]     | [ ]x         | **pass**    | —               | —                   |           |             |
| 50  | AI forgets after `.compact`                | [x]     | differ       | **pass**    | —               | —                   |           |             |
| 51  | Opt-out blocks AI responses                | [x]     | [ ]x         | skip        | —               | —                   |           |             |
| 52  | Nickname self-check                        | [x]     | [ ]          | skip        | what's this?    | —                   |           |             |

FAIL:

the chatbox should be scrollable with page up and down.
it should scroll when you run out of room

## PM Routing

| #   | Test                                       | Harness | Manual | --real test | Why no harness? | Why no --real test? | Dev notes | Agent notes |
| --- | ------------------------------------------ | ------- | ------ | ----------- | --------------- | ------------------- | --------- | ----------- |
| 53  | PM `TerraAI: hello` → AI responds          | [x]     | x      | skip        | —               | —                   |           |             |
| 54  | PM bare `hello` → AI responds (no trigger) | [x]     | [ ] x  | skip        | —               | —                   |           |             |
| 55  | PM `.optin` → "opted in"                   | [x]     | [ ] x  | skip        | —               | —                   |           |             |
| 56  | PM `.optout` → "opted out"                 | [x]     | [ ]    | skip        | —               | —                   |           |             |
| 57  | PM `.help` → shows commands                | [x]     | [ ]    | skip        | —               | —                   |           |             |
| 58  | PM unknown `.command` → routes to AI       | [x]     | [ ]    | skip        | —               | —                   |           |             |
| 59  | PM `.effort low` → confirms                | [x]     | [ ]    | skip        | —               | —                   |           |             |
| 60  | PM `.noisy` → toggles                      | [x]     | [ ]    | skip        | —               | —                   |           |             |
| 61  | PM `.setlocation` → forwards to AI         | [x]     | [ ]    | skip        | —               | —                   |           |             |
| 62  | PM `.clear` → wipes session                | [x]     | [ ]    | skip        | —               | —                   |           |             |

FAIL
If you are not optted and you pm the bot, it should say something like "you must opt in blah blah"



## Web Search

| #   | Test                                               | Harness | Manual | --real test | Why no harness? | Why no --real test?              | Dev notes | Agent notes |
| --- | -------------------------------------------------- | ------- | ------ | ----------- | --------------- | -------------------------------- | --------- | ----------- |
| 63  | Schema type is `openrouter:web_search`             | [x]     | —      | skip        | —               | No AI needed (pure schema check) |           |             |
| 64  | Schema has engine/max_results/max_total_results    | [x]     | —      | skip        | —               | No AI needed (pure schema check) |           |             |
| 65  | Weather query → search + weather content           | [x]     | [ ]x   | **pass**    | —               | —                                |           |             |
| 66  | Trivial query (2+2) → model answers without search | [x]     | [ ]x   | **pass**    | —               | —                                |           |             |
| 67  | Model decides when to search vs answer             | [x]     | differ | **pass**    | —               | —                                |           |             |

FAIL, responding twice on PM??
[21:27] <TerraAI> Chicago, IL weather now:                                                    
73°F, partly cloudy. High 74°F / Low 59°F. Humidity 69%, wind 10 mph NE. No rain expected. UV 
Index 7.1. Sunrise 5:17 AM, Sunset 8:29 PM.                                                   
[21:27] <TerraAI> Chicago, IL weather now:                                                    
73°F, partly cloudy. High 74°F / Low 59°F. Humidity 69%, wind 10 mph NE. No rain expected. UV 
Index 7.1. Sunrise 5:17 AM, Sunset 8:29 PM.   
responding twice on PM



## Providers



differed all of these

| #   | Test                                 | Harness | Manual | --real test | Why no harness? | Why no --real test? | Dev notes | Agent notes |
| --- | ------------------------------------ | ------- | ------ | ----------- | --------------- | ------------------- | --------- | ----------- |
| 68  | OpenRouter chat (with system prompt) | [x]     | —      | **pass**    | —               | —                   |           |             |
| 69  | OpenRouter chat (no system prompt)   | [x]     | —      | skip        | —               | Needs live API key  |           |             |
| 70  | OpenRouter is_available (with key)   | [x]     | —      | skip        | —               | Pure logic          |           |             |
| 71  | OpenRouter is_available (no key)     | [x]     | —      | skip        | —               | Pure logic          |           |             |
| 72  | OpenAI chat                          | [x]     | —      | skip        | —               | No API key in env   |           |             |
| 73  | OpenAI is_available                  | [x]     | —      | skip        | —               | Pure logic          |           |             |
| 74  | Gemini chat                          | [x]     | —      | skip        | —               | No API key in env   |           |             |
| 75  | Gemini is_available                  | [x]     | —      | skip        | —               | Pure logic          |           |             |
| 76  | Ollama chat                          | [x]     | —      | skip        | —               | Ollama not running  |           |             |
| 77  | Ollama is_available                  | [x]     | —      | skip        | —               | Ollama not running  |           |             |
| 78  | Registry set/get                     | [x]     | —      | skip        | —               | Pure logic          |           |             |
| 79  | Registry fallback                    | [x]     | —      | skip        | —               | Pure logic          |           |             |

## Database



manual testing not needed

| #   | Test                                        | Harness | Manual | --real test | Why no harness? | Why no --real test? | Dev notes | Agent notes |
| --- | ------------------------------------------- | ------- | ------ | ----------- | --------------- | ------------------- | --------- | ----------- |
| 80  | SQLite CRUD (users, history, sessions, etc) | [x]     | —      | skip        | —               | Pure logic          |           |             |
| 81  | WAL mode                                    | [x]     | —      | skip        | —               | Pure logic          |           |             |
| 82  | Multi-server isolation                      | [x]     | —      | skip        | —               | Pure logic          |           |             |
| 83  | Performance stats logging                   | [x]     | —      | skip        | —               | Pure logic          |           |             |
| 84  | Command stats logging                       | [x]     | —      | skip        | —               | Pure logic          |           |             |

## Config



skipping manual testing

| #   | Test                                      | Harness | Manual | --real test | Why no harness? | Why no --real test? | Dev notes | Agent notes |
| --- | ----------------------------------------- | ------- | ------ | ----------- | --------------- | ------------------- | --------- | ----------- |
| 85  | TerraAISection reads from SOPEL `.cfg`    | [x]     | —      | **pass**    | —               | —                   |           |             |
| 86  | Setup reads `bot.config.terraai` directly | [x]     | —      | **pass**    | —               | —                   |           |             |
| 87  | Configurable help_prefix                  | [x]     | —      | skip        | —               | Pure logic          |           |             |

## Ergo Integration



skipping these for now.

Requires `ERGO_TEST=1` and ergochat running on localhost:6667.

| #   | Test                                | Harness | Manual | --real test | Why no harness? | Why no --real test? | Dev notes | Agent notes |
| --- | ----------------------------------- | ------- | ------ | ----------- | --------------- | ------------------- | --------- | ----------- |
| 88  | Smoke: ergo port open               | [x]     | —      | **pass**    | —               | —                   |           |             |
| 89  | Smoke: ergo config exists           | [x]     | —      | **pass**    | —               | —                   |           |             |
| 90  | Smoke: socket connect               | [x]     | —      | **pass**    | —               | —                   |           |             |
| 91  | IRC: register nick                  | [x]     | —      | **pass**    | —               | —                   |           |             |
| 92  | IRC: join channel                   | [x]     | —      | **pass**    | —               | —                   |           |             |
| 93  | IRC: send/receive channel message   | [x]     | —      | **pass**    | —               | —                   |           |             |
| 94  | IRC: private message                | [x]     | —      | **pass**    | —               | —                   |           |             |
| 95  | Bot: connects to ergo               | [x]     | —      | **pass**    | —               | —                   |           |             |
| 96  | Bot: joins channel                  | [x]     | —      | **pass**    | —               | —                   |           |             |
| 97  | Bot: responds to `.help`            | [x]     | —      | **pass**    | —               | —                   |           |             |
| 98  | Bot: responds to `TerraAI:` trigger | [x]     | —      | **pass**    | —               | —                   |           |             |
| 99  | Bot: responds to unknown `.command` | [x]     | —      | **pass**    | —               | —                   |           |             |
| 100 | Bot: ignores regular messages       | [x]     | —      | **pass**    | —               | —                   |           |             |
| 101 | Bot: responds to bare PM            | [x]     | —      | **pass**    | —               | —                   |           |             |
| 102 | Bot: uses web search for weather    | [x]     | —      | **pass**    | —               | —                   |           |             |
| 103 | Bot: reports error on AI failure    | [x]     | —      | **pass**    | —               | —                   |           |             |
| 104 | Bot: `.noisy` toggle                | [x]     | —      | **pass**    | —               | —                   |           |             |
| 105 | Bot: `.optin`/`.optout`             | [x]     | —      | **pass**    | —               | —                   |           |             |
