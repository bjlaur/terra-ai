# 0.0.2 Test Requests — Manual Testing

These are manual test scenarios for the interactive test tool (`test_tool/chat.py`). Run them in a real terminal with the test tool open.

**Launch:**
```bash
cd ~/agentic-repos/terra-ai-agent2
python test_tool/chat.py
```

---

## Test Tool UI

| # | Test | Expected |
|---|---|---|
| T1 | Launch the tool | Header shows `#terra-ai (test mode)`, empty chat, input line at bottom |
| T2 | Resize the terminal | Layout adapts, no overlap or truncation |
| T3 | Type a long message (wraps) | Text wraps correctly in input line |
| T4 | `quit` / `/quit` / `exit` | Tool exits cleanly |

## Opt-in / Opt-out Flow

| # | Test | Expected |
|---|---|---|
| O1 | `.optin` | "You are now opted in" |
| O2 | Send `hello` (after opt-in) | TerraAI responds |
| O3 | `.optout` | "You are opted out. Your history has been forgotten." |
| O4 | Send `hello` (after opt-out) | No response (silently ignored) |
| O5 | `.optin` again | Opt back in, works again |

## User Commands

| # | Test | Expected |
|---|---|---|
| U1 | `.noisy` | Toggles noisy mode ON/OFF |
| U2 | `.setlocation Portland, OR` | "Your location is set to Portland, OR." |
| U3 | `.setlocation` (no args) | Error/help message |
| U4 | `.effort` | Shows current effort level |
| U5 | `.effort low` | Sets effort to low |
| U6 | `.effort ultra` | Error — invalid level |
| U7 | `.ai What is 2+2?` | AI responds (no history) |

## Prompt Management

| # | Test | Expected |
|---|---|---|
| P1 | `.addprompt wea sunny` | "Added wea." |
| P2 | `.wea` | "sunny" (custom prompt response) |
| P3 | `.listprompts` | Lists all prompts, includes `wea` |
| P4 | `.rmprompt 1` | Removes prompt #1 |
| P5 | `.listprompts` again | Removed prompt no longer listed |
| P6 | `.addprompt wea sunny` (duplicate) | "Trigger already exists." |
| P7 | `.rmprompt 999` | "No such prompt." |
| P8 | `.rmprompt abc` | Error — not a number |

## AI Conversation

| # | Test | Expected |
|---|---|---|
| A1 | `hello` | AI responds naturally |
| A2 | `what did I just say?` | AI references previous message (history works) |
| A3 | `.compact` | "Compacted history. Kept N exchanges, removed M." |
| A4 | `what did I just say?` (after compact) | AI only remembers post-compact context |
| A5 | Send 20+ messages | Chat scrolls, old messages scroll off screen |

## Edge Cases

| # | Test | Expected |
|---|---|---|
| E1 | Empty input (just enter) | No response, no crash |
| E2 | Very long single message (200+ chars) | Handles gracefully |
| E3 | Special characters: `!@#$%^&*()` | Displays correctly |
| E4 | Unicode: `héllo wörld 日本語` | Displays correctly |
| E5 | Rapid messages (spam enter) | No crashes, all messages processed |

## Known Issues to Verify

| # | Test | Expected |
|---|---|---|
| K1 | `.stats` from non-admin nick | **Currently not gated** — should it be? (potential bug) |
| K2 | `.compact` from non-admin nick | **Currently not gated** — should it be? (potential bug) |

---

**Pass criteria:** All tests marked PASS. Any FAIL or unexpected behavior → write up in testing-results.md.
