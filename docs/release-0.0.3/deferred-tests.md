# Deferred Tests — 0.0.3

These tests were deferred from 0.0.2 and need to be fixed in 0.0.3.

---

## Weather Tool (IMPLEMENTED)

The first custom local tool (weather_forecast + geocode) is implemented and
tested in the Agent1 workspace (`~/agentic-repos/terra-ai-agent1/`,
branch `agent1/weather-tools`). This validated the tool-call architecture.

### What's done
- `weather_forecast` with 8 presets
- `geocode` standalone tool
- Tool-call loop in OpenRouter provider
- 19 unit + 2 end-to-end tests (all real HTTP)
- Ergo integration test

### Still to do (Agent1)
- `weather_history` tool
- `air_quality` tool
- `weather_reference` tool
- Geocode cache table
- Response caching
- Markdown paste for long output

---

## PM Routing (critical)

Bare PMs (no prefix, no nick) currently don't reach the AI. `pm_catch_all`
was disabled because it caused duplicate responses and opt-in/opt-out issues.

### What's needed
- `pm_catch_all` should route bare PM text to the AI
- Must NOT fire for channel messages (sender starts with `#`)
- Must NOT fire for messages that match other rules (prefixed commands, addressed freeform)
- Must respect opt-in/opt-out state
- Must send opt-in/opt-out replies as PMs (not notices)
- Must NOT cause duplicate responses when combined with other rules

### Tests to fix
- `test_pm_bare_message_routes_to_ai_mock` (test_console.py)
- `test_pm_bare_message_routes_to_ai_real` (test_console.py)
- `test_bot_responds_to_bare_pm` (test_ergo.py)

---

## AI Message Logging

Need to log all messages sent to and received from the AI for debugging.
Currently only basic logging exists. Should capture:
- Full payload sent to provider
- Full response received
- Token usage / server_tool_use stats

---

## Context Seed `<nick>` Prefix

The fake conversation tells the AI to expect `<nick>` prefixes, but user
messages were being sent without them. Fixed in `compose_context()` but
needs verification that the AI now correctly identifies speakers.

---

## Other Deferred Items

From 0.0.2:
- Custom prompts rework (`.addprompt`, `.rmprompt`, `match_prompt()`)
- 3 interactive tests (subprocess+curses+pty harness limitation)
- `.stats` from non-admin nick (needs admin-gate decision)
- Special characters / Unicode manual testing
