# Release 0.0.3 — Plan

## Goal

Fix deferred items from 0.0.2 and add the first custom local tool (weather) to validate the tool-calling architecture.

---

## 1. Prompts Rework

**Status:** Needs explanation — there's a misunderstanding about how custom prompts work that needs to be discussed before implementation.

**TODO:** User will explain the issue in detail.

---

## 2. First Custom Tool — Weather

**Goal:** Add a `weather` tool as the first custom local tool (not relying on OpenRouter's server-side search). This validates the tool-calling architecture for future tools.

**Status:** ✅ **IMPLEMENTED** (Agent1, branch `agent1/weather-tools` in `~/agentic-repos/terra-ai-agent1/`)

### What was built
- `weather_forecast` tool with all 8 presets (current, basic_forecast, rain, hourly, daily, sun, wind, full_debug)
- `geocode` standalone tool for resolving place names to coordinates
- Tool-call loop restored in `OpenRouterProvider.chat()` (max 3 rounds)
- `ToolResult` shared format (dataclass → JSON for the model)
- Normalized row-oriented output with `summary_hint`, not raw Open-Meteo JSON
- WMO weather code → description mapping
- Fahrenheit / mph / inch defaults
- 19 unit-of-logic tests + 2 end-to-end tests (all real HTTP, no mocks)
- Ergo integration test (`test_bot_uses_weather_forecast_tool`)

### Remaining (not yet implemented)
- `weather_history` tool
- `air_quality` tool
- `weather_reference` tool (static tables → later parse OpenAPI YAML)
- Geocode cache table (30-day TTL)
- Response caching (5–30 min depending on data type)
- Markdown paste for long debug/reference output

### Handoff doc
Full plan: `docs/release-0.0.3/openmeteo-tools-end-to-end-plan.md`
Implementation notes: `docs/release-0.0.3/weather-plan.md` §7

---

## 3. Noisy Mode Rework

**Status:** Noisy mode is supposed to show "steps the AI is doing" but currently we don't have steps. This is related to #2 — once the weather tool works, noisy mode should show tool calls in progress.

### Current problem
- Today noisy just says "Thinking..." before the AI call
- With tools, there should be more granular updates: "Searching...", "Found results", etc.
- Exact design TBD — how do we surface tool-call progress?

### Relationship to #2
- Weather tool gives us a concrete use case for noisy steps
- Can design noisy behavior around real tool-call lifecycle

---

## 4. Other Deferred Issues

### Console UI
- #11 Special characters `!@#$%^&*()` — differed, not tested
- #12 Unicode `héllo wörld 日本語` — differed, not tested
- #15 Interactive: Ctrl+D exits — fail (user uses ctrl+c, low priority)
- #16-26 Screenshots (11 tests) — none manually verified
- Chatbox should be scrollable with page up/down (from dev notes)

### Channel Commands (all differed — need manual re-verification)
- #33 `.noisy` → toggles ON/OFF
- #34 `.effort` → shows current level
- #35 `.effort low` → sets level
- #36 `.effort ultra` → error (invalid)
- #37 `.setlocation Portland, OR` → goes to AI
- #38 `.setlocation` (no args) → goes to AI
- #39 `.compact` → compacts history
- #40 `.compact` non-admin → "Permission denied"
- #42 `.stats` → shows stats (FAIL — broken)
- #44 `.addprompt <trigger> <text>` → added
- #45 `.addprompt` duplicate → error
- #46 `.listprompts` → lists prompts
- #47 `.rmprompt 1` → removes prompt
- #48 `.rmprompt 999` → "No such prompt"
- #50 AI forgets after `.compact`
- #52 Nickname self-check (user asked "what's this?")

### PM Routing
- #54 PM bare `hello` → AI responds (no trigger) — disabled
- #55 PM `.optin` → "opted in"
- #56 PM `.optout` → "opted out"
- #57 PM `.help` → shows commands
- #58 PM unknown `.command` → routes to AI
- #59 PM `.effort low` → confirms
- #60 PM `.noisy` → toggles
- #61 PM `.setlocation` → forwards to AI
- #62 PM `.clear` → wipes session
- Responding twice on PM — duplicate dispatch bug
- Not-opted-in PMs should get "you must opt in first" message

### Web Search
- #67 Model decides when to search vs answer — differed
- Weather query sometimes responds twice (duplicate message on PM)

### Providers (all differed — need manual re-verification)
- #69 OpenRouter chat (no system prompt)
- #72 OpenAI chat
- #74 Gemini chat
- #76 Ollama chat

### System Prompts
- Fake conversation uses `<nick>` but user messages now prefix with `<nick> — needs verification that AI correctly identifies speakers

---

## Done

- [ ] Prompts rework (after discussion)
- [x] Weather tool — first custom local tool (Agent1, `agent1/weather-tools` branch)
- [ ] Noisy mode rework (works with tool lifecycle)
- [ ] Other deferred items (see #4 above)
