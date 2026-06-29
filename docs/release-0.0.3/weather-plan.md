# Weather Tool Plan — Agent1 (OWL)

**Branch:** `agent1/weather-tools` in `~/agentic-repos/terra-ai-agent1/`
**Source doc:** `~/terra-ai-openmeteo-tools-end-to-end-plan.md` (the "handoff doc")
**Date:** 2026-06-29
**Status:** First milestone IMPLEMENTED — see §7 for what's done.

---

## 0. Ground truth — what the handoff doc gets wrong

The handoff doc was written generically and makes several assumptions that do
not match the current TerraAI codebase. The plan below is written against the
**actual code** in `~/agentic-repos/terra-ai-agent1/` at commit `65f06a7`.

| Handoff doc assumption | Reality |
|---|---|
| §4.3 Saved user location in SQLite | **No location column exists** in the `users` table, and we are NOT adding one. Per user: "owl will know the location." The model gets location from the user's message or its own knowledge. The tool's `location` param is just passed straight from the model to the geocoder. |
| §4.4 Geocode cache table `openmeteo_geocode_cache` | Not in the DB. We can add a cache table, but it's not a prerequisite for the first milestone. Defer to after forecast works end-to-end. |
| §12 Step 2 `terra_ai/tools/result.py` + `registry.py` with a `ClientTool` Protocol | Overkill for where we are. The existing code uses a flat `TOOL_FUNCTIONS` dict in `executor.py` and a `schemas.py` with `AVAILABLE_TOOLS`. We extend that pattern first; refactor to a registry/protocol later if warranted. |
| §12 Step 3 tool-call loop already exists / just needs wiring | **No tool-call loop exists.** When we switched to server-side search we removed the loop and `chat()` now returns `message.content` directly. We must build the loop from scratch. |
| §1.1 / §12 references to `execute_tool` routing local tools | `execute_tool` exists but `TOOL_FUNCTIONS` is empty — nothing is registered. |
| §12 Step 9 `weather_reference` reads downloaded OpenAPI YAML | Defer. Not part of the first milestone. Can be a static curated table initially. |
| §14 config section `[terra_ai.tools.openmeteo]` | We use SOPEL `.cfg` sections. Config shape TBD — keep it minimal (timeout, units) and read via the existing `TerraAISection`. |
| §15 `pydantic or jsonschema`, `diskcache`, `cachetools` | Avoid new deps where possible. Use stdlib `json`, `sqlite3` (already used), `httpx` (already a project dep). No pydantic/jsonschema/cachetools for the first milestone. |

What the handoff doc gets **right** and we keep:
- Four separate LLM-facing tools: `weather_forecast`, `weather_history`, `air_quality`, `weather_reference`.
- One shared internal `openmeteo/` module with a shared HTTP client + geocoder.
- Preset-per-tool design (current, basic_forecast, rain, hourly, daily, sun, wind, full_debug).
- Normalized row-oriented output with `summary_hint`, not raw Open-Meteo JSON.
- WMO weather code → description mapping.
- Fahrenheit / mph / inch defaults.
- First milestone = `weather_forecast` end-to-end, nothing else until that works.

---

## 1. Current code state (what I'm building on)

```
terra_ai/
  tools/
    __init__.py        # exports AVAILABLE_TOOLS, OPENROUTER_WEB_SEARCH_TOOL, execute_tool
    schemas.py         # OPENROUTER_WEB_SEARCH_TOOL + legacy WEB_SEARCH_TOOL; AVAILABLE_TOOLS
    executor.py        # execute_tool(name, args) -> str; TOOL_FUNCTIONS = {} (empty)
  providers/
    base.py            # Message(role, content) with to_dict(); AIProvider.chat(messages, system_prompt, effort)
    openrouter.py      # chat() does ONE post, returns message.content. NO tool-call loop.
                       # Always attaches openrouter:web_search server-side tool.
  bot.py               # handle_ai_message() -> provider.chat(msg_objs, effort=...). No tools passed.
  context/manager.py   # compose_context(); user message prefixed with "<nick> ". No location.
  database.py          # users table has NO location column. Not adding one.
  prompts/defaults.py  # system prompt mentions provider-side web search.
test_tool/console.py   # Textual test client, routes through SOPEL dispatcher.
```

Key constraints:
- `Message.to_dict()` only emits `role` + `content`. The tool-call loop needs to
  emit `tool_calls`, `tool_call_id`, `name` — so the loop must build raw dicts
  for the roundtrip messages (the old plan's "simple approach").
- `chat()` is synchronous (uses `httpx.Client`, not async). The Open-Meteo
  client can be sync too (`httpx.Client`) to match — no need to async the whole
  provider chain. Keep it simple.
- All routing goes through SOPEL's dispatcher (per CLAUDE.md). The weather tools
  are NOT new SOPEL commands — they're LLM-facing function tools. The existing
  `-wea` custom prompt stays as the user-facing trigger; the model decides to
  call `weather_forecast`.

---

## 2. Architecture

### 2.1 Tool-call loop lives in `OpenRouterProvider.chat()`

The loop:
```
chat(messages, system_prompt, effort, tools=None):
    build payload messages (system + messages)
    reasoning = ...
    tools = tools or []  # local function-tool schemas
    always attach openrouter:web_search server-side tool alongside local tools
    loop up to MAX_TOOL_ROUNDS:
        response = post(payload)
        message = response.choices[0].message
        if message has no tool_calls:
            return message.content
        append message (with tool_calls) to payload messages
        for each tool_call:
            result_str = execute_tool(tool_call.function.name, tool_call.function.arguments)
            append {"role":"tool","tool_call_id":id,"name":name,"content":result_str}
    # fell off the loop — return whatever content we have, else error
```

Local tools and the server-side search tool coexist: both go into `payload["tools"]`.
OpenRouter executes `openrouter:web_search` server-side; local function tools
come back as `tool_calls` that we execute and feed back.

### 2.2 `bot.py` passes `AVAILABLE_TOOLS` into `chat()`

```python
from terra_ai.tools.schemas import AVAILABLE_TOOLS
response = provider.chat(msg_objs, effort=self.prompts.effort, tools=AVAILABLE_TOOLS)
```

`chat()` signature becomes:
```python
def chat(self, messages, system_prompt=None, effort="high", tools=None, max_tool_rounds=3) -> str:
```

Other providers (gemini/openai/ollama) get the same `tools`/`max_tool_rounds`
params for signature compatibility (they can ignore `tools` for now, or pass
through if they support it).

### 2.3 `Message` stays minimal; loop builds raw dicts

`Message.to_dict()` keeps emitting `{role, content}`. Inside `chat()`, the
tool-call roundtrip messages (assistant-with-tool-calls, tool results) are
appended as raw dicts, not `Message` objects. This keeps the change contained.

### 2.4 Open-Meteo module (shared internals)

```
terra_ai/tools/openmeteo/
  __init__.py      # public helpers, if any
  client.py        # OpenMeteoClient (sync httpx.Client, 8s timeout)
  geocode.py       # geocode_location(client, name) -> dict (NO db lookup)
  normalize.py     # rows_from_columns, add_weather_descriptions, field renames
  weather_codes.py # WMO code -> description
  forecast.py      # build_forecast_params(location, preset, args) + execute
  history.py       # build_history_params + execute
  air_quality.py   # build_air_quality_params + execute
  reference.py     # static curated tables (deferred)
  schemas.py       # the 4 tool schema dicts
```

Shared `ToolResult` shape (dataclass), serialized to JSON for the model:
```python
@dataclass
class ToolResult:
    ok: bool
    tool: str
    source: str
    data: dict | None = None
    summary_hint: str | None = None
    error: str | None = None
    debug: dict | None = None
```

### 2.5 No location DB lookup

`geocode_location` takes the `location` string the model supplied and geocodes
it. If `location` is null/empty, the tool returns:
```json
{"ok": false, "tool": "...", "error": "No location provided.", "summary_hint": "Ask the user what location they want."}
```
The model then asks the user. No SQLite location column, no cache table for v1.

---

## 3. First milestone: `weather_forecast` end-to-end

Per the handoff doc §17 — do ONLY this first:

```
weather_forecast with:
- geocoding
- current preset
- basic_forecast preset
- rain preset
- normalized data to Owl
- final Owl answer in IRC
- Textual test console coverage
```

### 3.1 Step-by-step

1. **Deps** — `httpx` is already a project dep. `PyYAML` only needed for
   `weather_reference` (deferred). No new deps for the first milestone.

2. **`terra_ai/tools/openmeteo/client.py`** — `OpenMeteoClient` with sync
   `httpx.Client`, 8s timeout, `get_json(url, params) -> dict`, raises on
   non-2xx. Log the URL (redact nothing — no keys in Open-Meteo URLs).

3. **`terra_ai/tools/openmeteo/weather_codes.py`** — WMO code map +
   `describe_weather_code()`.

4. **`terra_ai/tools/openmeteo/normalize.py`** — `rows_from_columns`,
   `add_weather_descriptions`, `FORECAST_FIELD_RENAMES`, `DAILY_FIELD_RENAMES`,
   unit normalization (the API already returns F/mph/inch because we request it,
   so mostly field renaming + row reshaping + description injection).

5. **`terra_ai/tools/openmeteo/geocode.py`** — `geocode_location(client, name)`.
   Hits `https://geocoding-api.open-meteo.com/v1/search`. Returns the resolved
   location dict (name, admin1, country_code, lat, lon, timezone). Raises
   `ValueError` on no results → caught by the executor → clean error `ToolResult`.

6. **`terra_ai/tools/openmeteo/forecast.py`** —
   `build_forecast_params(location, preset, args)` and
   `execute_weather_forecast(arguments, client) -> ToolResult`. Implements
   `current`, `basic_forecast`, `rain` presets (plus `hourly`, `daily`, `sun`,
   `wind`, `full_debug` as the schema already declares them — implement all, but
   the first three are the milestone).

7. **`terra_ai/tools/openmeteo/schemas.py`** — the four tool schema dicts
   (forecast, history, air_quality, reference). For the milestone, only
   `WEATHER_FORECAST_TOOL` must be correct; the others can be added as the
   other tools are implemented.

8. **`terra_ai/tools/schemas.py`** — add the Open-Meteo tools to
   `AVAILABLE_TOOLS`:
   ```python
   from terra_ai.tools.openmeteo.schemas import WEATHER_FORECAST_TOOL
   AVAILABLE_TOOLS = [OPENROUTER_WEB_SEARCH_TOOL, WEATHER_FORECAST_TOOL]
   ```

9. **`terra_ai/tools/executor.py`** — register `weather_forecast` in
   `TOOL_FUNCTIONS`. The handler calls `execute_weather_forecast` and returns
   `json.dumps(result.to_dict())` (or `result.error` string on failure).

10. **`terra_ai/providers/openrouter.py`** — restore the tool-call loop in
    `chat()`:
    - Add `tools=None`, `max_tool_rounds=3` params.
    - Merge local `tools` with the server-side `openrouter:web_search` tool.
    - On `tool_calls`, execute each via `execute_tool`, append raw dicts, loop.
    - Return final `content`.

11. **`terra_ai/providers/{gemini,openai,ollama}.py`** — add `tools`/`max_tool_rounds`
    params for signature compat (pass-through or ignore).

12. **`terra_ai/providers/base.py`** — update `AIProvider.chat()` signature to
    include `tools` and `max_tool_rounds`.

13. **`terra_ai/bot.py`** — pass `AVAILABLE_TOOLS` into `provider.chat()`.

14. **`terra_ai/prompts/defaults.py`** — update system prompt: tell the model it
    has `weather_forecast` (and later the other tools), how to choose presets,
    that it knows location from the user's message, to be concise for IRC.

15. **`test_tool/console.py`** — add weather test inputs to `--test` mode:
    `weather Detroit`, `rain tonight in Detroit?`, `weather Chicago this week`.

### 3.2 Acceptance (first milestone)

**Real HTTP all the way down — no mocks, including no AI mocks** (per CLAUDE.md
"Tests for tools use REAL HTTP" + user correction). A fake model would never
decide to call `weather_forecast`, so the tool-call loop only validates against
a live provider. Source `~/.terra-ai/.env` first.

- `test_tool/console.py --test` includes weather lines and the bot returns a
  concise real answer (live OpenRouter → live Open-Meteo).
- New `tests/test_weather.py` — split into unit-of-logic tests (real Open-Meteo
  HTTP, no AI) and end-to-end tests (real AI + real Open-Meteo):
  - **real Open-Meteo, no AI:** geocode Detroit, MI / Chicago, IL; forecast
    Detroit current / basic_forecast / rain; unknown location → clean error;
    timeout → clean error.
  - **real AI + real Open-Meteo (end-to-end):** feed `weather Detroit` to a live
    provider with `tools=[...]` and assert the model calls `weather_forecast`
    and the final answer contains a real temperature.
- **Ergo test** (`tests/test_ergo.py`): `test_bot_uses_weather_forecast_tool` —
  the live ergo + SOPEL + bot stack sends `TerraAI: weather Detroit` to a real
  IRC channel and asserts the bot's response contains a real temperature /
  weather content. Same shape as the existing `test_bot_uses_web_search_for_weather`
  but asserts the `weather_forecast` tool-call path (not server-side search).
  Run with `ERGO_TEST=1 pytest tests/test_ergo.py -v`.
- Manual console: `TerraAI: weather Detroit` → `Detroit: 91°F and clear...`
- `pytest tests/ -k "not ergo" -q` still green.

---

## 4. After the first milestone (order)

1. `air_quality` tool (presets: current, basic, smoke, uv, pollen, pollutants, full_debug).
2. `weather_history` tool (presets: basic, temperature, rain, snow, wind, daily, full_debug). Requires `start_date`/`end_date`; model passes real dates.
3. `weather_reference` tool (static curated tables → later parse OpenAPI YAML).
4. Geocode cache table `openmeteo_geocode_cache` (30-day TTL).
5. Response caching (current 5–10min, hourly/daily 15–30min, AQ 10–20min).
6. Markdown paste for long debug/reference output.
7. Refactor to `ToolRegistry` + `ClientTool` Protocol (if warranted).

---

## 5. Testing strategy

- **Real HTTP only, no AI mocks.** Per CLAUDE.md "Tests for tools use REAL
  HTTP" + user correction: no AI mocks either. A fake model never decides to
  call `weather_forecast`, so the tool-call loop only validates against a live
  provider. End-to-end tests call a real OpenRouter AI + real Open-Meteo.
- **Unit-of-logic tests** (geocode/normalize/preset-building/timeout handling)
  use real Open-Meteo HTTP but no AI — they call the tool functions directly.
- Source `~/.terra-ai/.env` before running anything.
- **No `pytest.skip()`** — if `OPENROUTER_API_KEY` is missing, fail loudly with
  instructions to source the key (per CLAUDE.md + prior user instruction).
- **No silent failures** — tool errors return a clean `ToolResult(ok=False)`;
  the model turns that into a short user-facing message, never a traceback.
- Console `--test` mode is the manual-ish smoke test; `tests/test_weather.py`
  is the automated real-HTTP suite (both kinds above).

---

## 6. Out of scope (Agent2 / deferred)

- Prompts rework.
- Noisy mode rework (Agent2 owns the design; Agent1 just needs tool lifecycle
  to be observable — `summary_hint` + logging covers it for now).
- PM routing fix.
- Provider testing (OpenAI/Gemini/Ollama).
- `weather_reference` OpenAPI YAML download/parse (deferred within Agent1 too).

---

## 7. What's been implemented (first milestone complete)

All files below are in `~/agentic-repos/terra-ai-agent1/` on branch `agent1/weather-tools`.

### New files

| File | Purpose |
|---|---|
| `terra_ai/tools/openmeteo/__init__.py` | Package docstring + `ToolResult` re-export |
| `terra_ai/tools/openmeteo/client.py` | `OpenMeteoClient` (sync httpx, 8s timeout, `get_json`) |
| `terra_ai/tools/openmeteo/result.py` | `ToolResult` dataclass (`ok`, `tool`, `source`, `data`, `summary_hint`, `error`, `debug`) |
| `terra_ai/tools/openmeteo/weather_codes.py` | WMO code → description map + `describe_weather_code()` |
| `terra_ai/tools/openmeteo/normalize.py` | `rows_from_columns`, `add_weather_descriptions`, `FORECAST_RENAMES`, `DAILY_FIELD_RENAMES`, `AIR_QUALITY_RENAMES` |
| `terra_ai/tools/openmeteo/geocode.py` | `geocode_location()` + `_clean_location_query()` (strips `, MI` suffix) |
| `terra_ai/tools/openmeteo/geocode_tool.py` | Standalone `geocode` tool — `execute_geocode()` |
| `terra_ai/tools/openmeteo/forecast.py` | `weather_forecast` — all 8 presets (current, basic_forecast, rain, hourly, daily, sun, wind, full_debug) |
| `terra_ai/tools/openmeteo/schemas.py` | 5 tool schema dicts (forecast, history, air_quality, reference, geocode) |
| `tests/test_weather.py` | 19 unit + 2 end-to-end tests (all real HTTP, no mocks) |

### Modified files

| File | Change |
|---|---|
| `terra_ai/tools/schemas.py` | `AVAILABLE_TOOLS` now includes `WEATHER_FORECAST_TOOL` + `GEOCODE_TOOL` |
| `terra_ai/tools/executor.py` | `TOOL_FUNCTIONS` registers `weather_forecast` + `geocode`; handler serializes `ToolResult` to JSON |
| `terra_ai/providers/openrouter.py` | Tool-call loop restored: `tools`/`max_tool_rounds` params, loops up to 3 rounds executing local tools |
| `terra_ai/providers/base.py` | `chat()` signature includes `tools`/`max_tool_rounds` |
| `terra_ai/providers/gemini.py` | `tools`/`max_tool_rounds` params (ignored, for compat) |
| `terra_ai/providers/openai.py` | `tools`/`max_tool_rounds` params (ignored, for compat) |
| `terra_ai/providers/ollama.py` | `tools`/`max_tool_rounds` params (ignored, for compat) |
| `terra_ai/bot.py` | Passes `AVAILABLE_TOOLS` to `provider.chat()` |
| `terra_ai/prompts/defaults.py` | System prompt mentions weather tools + geocode |
| `test_tool/console.py` | `--test` mode includes `weather Detroit`, `rain tonight in Detroit?`, `weather Chicago this week` |
| `tests/test_ergo.py` | `test_bot_uses_weather_forecast_tool` — live ergo + SOPEL + bot, asserts weather response |
| `tests/conftest.py` | `mock_chat` accepts `tools`/`max_tool_rounds` kwargs |
| `tests/test_integration.py` | Mock lambdas/spies accept `tools`/`max_tool_rounds` kwargs |
| `tests/test_commands.py` | `test_compose_context` updated: user message is `<nick> hello` not `hello` |

### Test results

- **19/19 unit-of-logic tests pass** (real Open-Meteo HTTP, no AI)
- **2/2 end-to-end tests pass** (real OpenRouter AI + real Open-Meteo, model calls `weather_forecast`)
- **137/140 total tests pass** (3 pre-existing PM failures — disabled `pm_catch_all`, not weather-related)
- Ergo test `test_bot_uses_weather_forecast_tool` added (requires live ergo server)

### Key decisions made during implementation

1. **Geocoding API quirk** — Open-Meteo's `/v1/search` returns zero results for `"Detroit, MI"` but works for `"Detroit"`. Added `_clean_location_query()` to strip `, ST` suffixes.
2. **Standalone geocode tool** — Per user request, `geocode` is a separate LLM-facing tool (not just internal to `weather_forecast`). Model can call it to "remember" coordinates.
3. **No cache table yet** — Geocode cache deferred. Can add `openmeteo_geocode_cache` table later.
4. **Sync client** — `OpenMeteoClient` uses sync `httpx.Client` to match the rest of the provider chain (no async).
5. **`Message` stays minimal** — `to_dict()` still only emits `{role, content}`. Tool-call roundtrip messages are raw dicts inside `chat()`.
