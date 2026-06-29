# TerraAI Open-Meteo Tooling — End-to-End Implementation Plan

This is a Claude handoff document for adding Open-Meteo-powered tools to TerraAI.

It is intentionally specific. It explains:

1. How OpenAI-compatible / OpenRouter-compatible tool calling works.
2. How TerraAI should implement client-side tools.
3. What weather-related functionality we are adding.
4. Why forecast, historical weather, air quality, and API reference should be separate Owl-facing tools.
5. Exact Open-Meteo API endpoints.
6. Exact presets and what each preset should request.
7. What TerraAI should send back to Owl after each tool call.
8. How Owl should use the tool result to generate a concise IRC answer.
9. How to test the implementation.

---

## 0. TerraAI Constraints

TerraAI is an IRC-native Sopel bot. Users talk to it by addressing it by nick or with prefix commands, for example:

```text
TerraAI: what's the weather?
-wea chicago
TerraAI: rain tonight?
```

Important constraints:

- IRC has a short line limit, so final answers must be concise.
- TerraAI has user location memory, so weather tools should use saved location if the user omits a location.
- TerraAI uses OpenRouter / OpenAI-compatible chat completions.
- TerraAI supports function/tool calling.
- The LLM should choose when to call tools.
- TerraAI executes tools locally.
- Tool output should be structured data, not final prose.
- Owl should format the final IRC answer from the structured tool result.
- Long output should eventually go to a rendered Markdown paste tool, not IRC.

---

# 1. How Tools Work

## 1.1 End-to-end tool call flow

Tool calling works like this:

```text
User message
→ TerraAI builds the LLM request
→ TerraAI includes normal messages plus available tool schemas
→ Owl decides whether to answer directly or request a tool call
→ OpenRouter returns a tool call request
→ TerraAI validates the requested tool name and JSON arguments
→ TerraAI executes the matching local Python function
→ TerraAI sends the tool result back to the model as a tool message
→ Owl writes the final answer
→ TerraAI enforces IRC length limits
→ TerraAI sends final answer to IRC
```

Important: the model does not execute Python. TerraAI does.

## 1.2 Tool responsibilities

The tool should:

- Validate inputs.
- Call the external API.
- Normalize the raw API response.
- Return structured data.
- Include a compact fallback `summary_hint`.
- Include source/provider metadata.
- Avoid writing the final human-facing prose.

The tool should not:

- Hardcode the final IRC answer in most cases.
- Dump raw Open-Meteo JSON directly to Owl.
- Return every possible field unless a debug/reference preset was requested.
- Ask follow-up questions itself.
- Access arbitrary URLs or internal network resources.

## 1.3 Owl responsibilities

Owl should:

- Choose the smallest tool/preset that can answer the user.
- Use the structured data to answer the actual question.
- Mention only relevant weather fields.
- Keep the final answer concise for IRC.
- Avoid listing every field.
- Ask for location only when no location was provided and no saved location exists.
- Use historical weather only for past dates.
- Use air quality only for pollution/AQI/smoke/UV/pollen questions.
- Use API reference only for developer/debug questions about available API variables.

## 1.4 TerraAI responsibilities after Owl answers

TerraAI should:

- Enforce max IRC output length.
- Split or truncate if needed.
- Eventually publish long output to rendered Markdown paste.
- Log tool calls, latency, and failures.
- Cache API responses where sensible.
- Never expose secrets or raw internal exceptions to IRC.

---

# 2. Functionality We Are Adding

Add four Owl-facing tools:

| Tool | Purpose | Open-Meteo endpoint |
|---|---|---|
| `weather_forecast` | Current and future weather | `https://api.open-meteo.com/v1/forecast` |
| `weather_history` | Past weather by date/range | `https://archive-api.open-meteo.com/v1/archive` |
| `air_quality` | AQI, PM2.5, ozone, smoke, UV, pollen | `https://air-quality-api.open-meteo.com/v1/air-quality` |
| `weather_reference` | Developer/debug inventory of Open-Meteo capabilities | Local downloaded OpenAPI YAML files |

These should be separate LLM-facing tools because it makes tool choice easier for Owl.

Bad design:

```python
weather(location, preset="forecast|history|air_quality|reference|...")
```

Better design:

```python
weather_forecast(...)
weather_history(...)
air_quality(...)
weather_reference(...)
```

Internally they should share code:

```text
terra_ai/
  tools/
    registry.py
    result.py
    openmeteo/
      __init__.py
      client.py
      geocode.py
      normalize.py
      weather_codes.py
      forecast.py
      history.py
      air_quality.py
      reference.py
      schemas.py
```

The model sees four clear tools. The codebase uses one shared Open-Meteo module.

---

# 3. Shared Tool Result Format

Use one result shape for every tool.

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ToolResult:
    ok: bool
    tool: str
    source: str
    data: dict[str, Any] | None = None
    summary_hint: str | None = None
    error: str | None = None
    debug: dict[str, Any] | None = None
```

Then serialize to JSON before sending to Owl:

```json
{
  "ok": true,
  "tool": "weather_forecast",
  "source": "open-meteo",
  "data": {},
  "summary_hint": "Answer the user's actual forecast question concisely for IRC. Use only relevant fields.",
  "debug": {
    "provider_url": "https://api.open-meteo.com/v1/forecast",
    "preset": "basic_forecast",
    "cached": false,
    "duration_ms": 382
  }
}
```

## 3.1 What to send to Owl

Send Owl normalized data, not raw Open-Meteo JSON.

Reason:

Open-Meteo returns hourly and daily data in a column-oriented shape:

```json
{
  "hourly": {
    "time": ["2026-06-29T00:00", "2026-06-29T01:00"],
    "temperature_2m": [72.1, 71.6],
    "precipitation_probability": [10, 20]
  }
}
```

Owl will reason more reliably with row-oriented data:

```json
{
  "hourly": [
    {
      "time": "2026-06-29T00:00",
      "temperature_f": 72.1,
      "precip_probability_percent": 10
    },
    {
      "time": "2026-06-29T01:00",
      "temperature_f": 71.6,
      "precip_probability_percent": 20
    }
  ]
}
```

Normalize arrays before sending the tool result back to Owl.

---

# 4. Shared Open-Meteo API Layer

## 4.1 Shared HTTP client

Create:

```text
terra_ai/tools/openmeteo/client.py
```

Use `httpx.AsyncClient`.

```python
import httpx

class OpenMeteoClient:
    def __init__(self, timeout_s: float = 8.0):
        self.timeout_s = timeout_s

    async def get_json(self, url: str, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
```

Add later:

- retry on transient 5xx
- rate limiting
- cache
- debug logging
- request URL redaction if needed

## 4.2 Shared geocoding

Create:

```text
terra_ai/tools/openmeteo/geocode.py
```

Endpoint:

```text
GET https://geocoding-api.open-meteo.com/v1/search
```

Useful parameters:

| Parameter | Value |
|---|---|
| `name` | User-provided place string |
| `count` | `5` |
| `language` | `en` |
| `format` | `json` |
| `countryCode` | Optional, e.g. `US` if we infer it |

Example:

```text
https://geocoding-api.open-meteo.com/v1/search?name=Detroit%2C%20MI&count=5&language=en&format=json&countryCode=US
```

Implementation:

```python
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

async def geocode_location(client: OpenMeteoClient, name: str, country_code: str | None = None) -> dict:
    params = {
        "name": name,
        "count": 5,
        "language": "en",
        "format": "json",
    }
    if country_code:
        params["countryCode"] = country_code

    data = await client.get_json(GEOCODING_URL, params)
    results = data.get("results") or []

    if not results:
        raise ValueError(f"No location found for {name!r}")

    # v1: pick first result.
    # Later: use population/country/admin matching to choose better.
    best = results[0]

    return {
        "name": best.get("name"),
        "admin1": best.get("admin1"),
        "admin2": best.get("admin2"),
        "country": best.get("country"),
        "country_code": best.get("country_code"),
        "timezone": best.get("timezone"),
        "latitude": best.get("latitude"),
        "longitude": best.get("longitude"),
        "elevation": best.get("elevation"),
        "population": best.get("population"),
        "raw": best,
    }
```

## 4.3 Saved user location

If `location` is omitted:

1. Look up saved location for nick/user in TerraAI SQLite.
2. If saved location has lat/lon/timezone, use it.
3. If saved location is text only, geocode it and update cache.
4. If no saved location exists, return a tool error telling Owl to ask for location.

Tool error example sent to Owl:

```json
{
  "ok": false,
  "tool": "weather_forecast",
  "source": "open-meteo",
  "error": "No location was provided and this user has no saved location.",
  "summary_hint": "Ask the user what location they want weather for."
}
```

Then Owl should say something like:

```text
What location should I check?
```

## 4.4 Location cache

Cache geocoding results.

SQLite table:

```sql
CREATE TABLE IF NOT EXISTS openmeteo_geocode_cache (
    cache_key TEXT PRIMARY KEY,
    location_query TEXT NOT NULL,
    country_code TEXT,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL
);
```

Cache key:

```text
lowercase(trim(location_query)) + "|" + country_code_or_blank
```

Geocoding can be cached for a long time, e.g. 30 days or more.

---

# 5. Weather Forecast Tool

## 5.1 Tool purpose

Use `weather_forecast` for current or future weather:

- current conditions
- generic forecast
- rain tonight
- snow tomorrow
- wind
- sunrise/sunset
- hourly forecast
- daily forecast
- week forecast

Do not use it for:

- past weather
- historical rainfall
- air quality / AQI / smoke / PM2.5
- developer questions about API variables

## 5.2 Tool schema

```python
WEATHER_FORECAST_TOOL = {
    "type": "function",
    "function": {
        "name": "weather_forecast",
        "description": (
            "Use for current or future weather, including current conditions, "
            "forecast, rain tonight, snow tomorrow, storms, wind, sunrise/sunset, "
            "hourly forecast, and daily forecast. Do not use for past weather or air quality."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": ["string", "null"],
                    "description": (
                        "City/place to check, e.g. 'Detroit, MI' or 'Chicago, IL'. "
                        "If omitted, TerraAI should use saved user location if available."
                    ),
                },
                "preset": {
                    "type": "string",
                    "enum": [
                        "current",
                        "basic_forecast",
                        "rain",
                        "hourly",
                        "daily",
                        "sun",
                        "wind",
                        "full_debug"
                    ],
                    "default": "basic_forecast",
                    "description": (
                        "Choose the smallest preset that answers the user. "
                        "Use current for right now, rain for rain/snow/storm questions, "
                        "daily for multi-day forecasts, sun for sunrise/sunset, wind for wind questions, "
                        "full_debug only for developer/test-console inspection."
                    ),
                },
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 16,
                    "default": 3,
                    "description": "Forecast days to request. Max 16.",
                },
                "hours": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                    "maximum": 168,
                    "default": None,
                    "description": "Optional number of forecast hours to request.",
                },
            },
            "required": [],
        },
    },
}
```

## 5.3 Endpoint

```text
GET https://api.open-meteo.com/v1/forecast
```

Base required parameters:

```text
latitude=<float>
longitude=<float>
timezone=auto
temperature_unit=fahrenheit
wind_speed_unit=mph
precipitation_unit=inch
```

Use Fahrenheit/mph/inches by default for US locations. Later, allow user preference.

## 5.4 Forecast presets

### Preset: `current`

Use for:

```text
weather now
what is it like outside?
temperature in Chicago
is it raining right now?
```

Request:

```text
current=
temperature_2m,
relative_humidity_2m,
apparent_temperature,
is_day,
precipitation,
rain,
showers,
snowfall,
weather_code,
cloud_cover,
pressure_msl,
surface_pressure,
wind_speed_10m,
wind_direction_10m,
wind_gusts_10m
```

URL example:

```text
https://api.open-meteo.com/v1/forecast?latitude=42.3314&longitude=-83.0458&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto
```

### Preset: `basic_forecast`

Default for:

```text
weather Detroit
forecast for Chicago
weather tomorrow
```

Request:

```text
current=
temperature_2m,
apparent_temperature,
relative_humidity_2m,
precipitation,
rain,
weather_code,
cloud_cover,
wind_speed_10m,
wind_gusts_10m

hourly=
temperature_2m,
apparent_temperature,
precipitation_probability,
precipitation,
rain,
showers,
snowfall,
weather_code,
cloud_cover,
wind_speed_10m,
wind_gusts_10m

daily=
weather_code,
temperature_2m_max,
temperature_2m_min,
precipitation_probability_max,
precipitation_sum,
rain_sum,
showers_sum,
snowfall_sum,
sunrise,
sunset,
wind_speed_10m_max,
wind_gusts_10m_max
```

Use:

```text
forecast_days=3
forecast_hours=24
```

URL example:

```text
https://api.open-meteo.com/v1/forecast?latitude=42.3314&longitude=-83.0458&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,rain,weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m&hourly=temperature_2m,apparent_temperature,precipitation_probability,precipitation,rain,showers,snowfall,weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,rain_sum,showers_sum,snowfall_sum,sunrise,sunset,wind_speed_10m_max,wind_gusts_10m_max&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto&forecast_days=3&forecast_hours=24
```

### Preset: `rain`

Use for:

```text
rain tonight?
will it storm?
snow tomorrow?
is it going to rain this afternoon?
```

Request:

```text
current=
temperature_2m,
weather_code,
precipitation,
rain,
showers,
snowfall,
cloud_cover

hourly=
temperature_2m,
apparent_temperature,
precipitation_probability,
precipitation,
rain,
showers,
snowfall,
weather_code,
cloud_cover,
wind_speed_10m,
wind_gusts_10m

daily=
precipitation_probability_max,
precipitation_sum,
rain_sum,
showers_sum,
snowfall_sum,
weather_code,
sunset
```

Default:

```text
forecast_hours=24
forecast_days=2
```

If the user says “tonight,” TerraAI should still return hourly data; Owl can inspect local times and answer for evening/overnight.

URL example:

```text
https://api.open-meteo.com/v1/forecast?latitude=42.3314&longitude=-83.0458&current=temperature_2m,weather_code,precipitation,rain,showers,snowfall,cloud_cover&hourly=temperature_2m,apparent_temperature,precipitation_probability,precipitation,rain,showers,snowfall,weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m&daily=precipitation_probability_max,precipitation_sum,rain_sum,showers_sum,snowfall_sum,weather_code,sunset&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto&forecast_days=2&forecast_hours=24
```

### Preset: `hourly`

Use for:

```text
hourly forecast
weather this evening
what will it be like from 5-9pm?
```

Request the same hourly set as `basic_forecast`, but allow more hours.

Default:

```text
forecast_hours=48
forecast_days=3
```

### Preset: `daily`

Use for:

```text
forecast this week
weather next weekend
10 day forecast
```

Request:

```text
daily=
weather_code,
temperature_2m_max,
temperature_2m_min,
apparent_temperature_max,
apparent_temperature_min,
sunrise,
sunset,
daylight_duration,
sunshine_duration,
uv_index_max,
uv_index_clear_sky_max,
rain_sum,
showers_sum,
snowfall_sum,
precipitation_sum,
precipitation_hours,
precipitation_probability_max,
wind_speed_10m_max,
wind_gusts_10m_max,
wind_direction_10m_dominant
```

Default:

```text
forecast_days=7
```

Allow max:

```text
forecast_days=16
```

### Preset: `sun`

Use for:

```text
sunrise?
sunset?
how much daylight?
```

Request:

```text
daily=
sunrise,
sunset,
daylight_duration,
sunshine_duration
```

Default:

```text
forecast_days=3
```

### Preset: `wind`

Use for:

```text
how windy is it?
wind tomorrow?
gusts tonight?
```

Request:

```text
current=
wind_speed_10m,
wind_direction_10m,
wind_gusts_10m,
weather_code,
temperature_2m

hourly=
wind_speed_10m,
wind_direction_10m,
wind_gusts_10m,
temperature_2m,
weather_code

daily=
wind_speed_10m_max,
wind_gusts_10m_max,
wind_direction_10m_dominant
```

Default:

```text
forecast_hours=24
forecast_days=3
```

### Preset: `full_debug`

Use only for:

```text
weather debug Detroit
what can the forecast API return for Detroit?
test the weather API
```

This is not for normal IRC answers.

Request a large but still reasonable variable set:

```text
current=
temperature_2m,
relative_humidity_2m,
apparent_temperature,
is_day,
precipitation,
rain,
showers,
snowfall,
weather_code,
cloud_cover,
pressure_msl,
surface_pressure,
wind_speed_10m,
wind_direction_10m,
wind_gusts_10m

hourly=
temperature_2m,
relative_humidity_2m,
dew_point_2m,
apparent_temperature,
precipitation_probability,
precipitation,
rain,
showers,
snowfall,
snow_depth,
weather_code,
pressure_msl,
surface_pressure,
cloud_cover,
cloud_cover_low,
cloud_cover_mid,
cloud_cover_high,
visibility,
evapotranspiration,
et0_fao_evapotranspiration,
vapour_pressure_deficit,
wind_speed_10m,
wind_speed_80m,
wind_speed_120m,
wind_speed_180m,
wind_direction_10m,
wind_direction_80m,
wind_direction_120m,
wind_direction_180m,
wind_gusts_10m,
temperature_80m,
temperature_120m,
temperature_180m,
soil_temperature_0cm,
soil_temperature_6cm,
soil_temperature_18cm,
soil_temperature_54cm,
soil_moisture_0_to_1cm,
soil_moisture_1_to_3cm,
soil_moisture_3_to_9cm,
soil_moisture_9_to_27cm,
soil_moisture_27_to_81cm,
uv_index,
uv_index_clear_sky,
is_day,
sunshine_duration,
wet_bulb_temperature_2m,
total_column_integrated_water_vapour,
cape,
lifted_index,
convective_inhibition,
freezing_level_height,
boundary_layer_height

daily=
weather_code,
temperature_2m_max,
temperature_2m_min,
apparent_temperature_max,
apparent_temperature_min,
sunrise,
sunset,
daylight_duration,
sunshine_duration,
uv_index_max,
uv_index_clear_sky_max,
rain_sum,
showers_sum,
snowfall_sum,
precipitation_sum,
precipitation_hours,
precipitation_probability_max,
wind_speed_10m_max,
wind_gusts_10m_max,
wind_direction_10m_dominant,
shortwave_radiation_sum,
et0_fao_evapotranspiration,
temperature_2m_mean,
apparent_temperature_mean,
cloud_cover_mean,
cloud_cover_max,
cloud_cover_min,
dew_point_2m_mean,
dew_point_2m_max,
dew_point_2m_min,
precipitation_probability_mean,
precipitation_probability_min,
relative_humidity_2m_mean,
relative_humidity_2m_max,
relative_humidity_2m_min,
pressure_msl_mean,
pressure_msl_max,
pressure_msl_min,
surface_pressure_mean,
surface_pressure_max,
surface_pressure_min,
visibility_mean,
visibility_min,
visibility_max,
wind_gusts_10m_mean,
wind_speed_10m_mean,
wind_gusts_10m_min,
wind_speed_10m_min,
wet_bulb_temperature_2m_mean,
wet_bulb_temperature_2m_max,
wet_bulb_temperature_2m_min
```

Use:

```text
forecast_days=7
```

Do not send all of this to IRC. If used from test console, print or paste structured data.

## 5.5 What `weather_forecast` sends back to Owl

Normalized result example:

```json
{
  "ok": true,
  "tool": "weather_forecast",
  "source": "open-meteo",
  "preset": "rain",
  "location": {
    "query": "Detroit, MI",
    "name": "Detroit",
    "admin1": "Michigan",
    "country_code": "US",
    "timezone": "America/Detroit",
    "latitude": 42.3314,
    "longitude": -83.0458
  },
  "units": {
    "temperature": "°F",
    "wind_speed": "mph",
    "precipitation": "inch"
  },
  "current": {
    "time": "2026-06-29T14:15",
    "temperature_f": 91.2,
    "apparent_temperature_f": 94.0,
    "weather_code": 0,
    "weather_description": "clear",
    "precipitation_in": 0.0,
    "rain_in": 0.0,
    "cloud_cover_percent": 5,
    "wind_speed_mph": 8.2,
    "wind_gusts_mph": 15.0
  },
  "hourly": [
    {
      "time": "2026-06-29T15:00",
      "temperature_f": 92.0,
      "apparent_temperature_f": 95.0,
      "precip_probability_percent": 0,
      "precipitation_in": 0.0,
      "rain_in": 0.0,
      "snowfall_in": 0.0,
      "weather_code": 0,
      "weather_description": "clear",
      "cloud_cover_percent": 5,
      "wind_speed_mph": 8.0,
      "wind_gusts_mph": 15.0
    }
  ],
  "daily": [
    {
      "date": "2026-06-29",
      "weather_code": 0,
      "weather_description": "clear",
      "temp_max_f": 96.0,
      "temp_min_f": 74.0,
      "precip_probability_max_percent": 5,
      "precipitation_sum_in": 0.0,
      "rain_sum_in": 0.0,
      "snowfall_sum_in": 0.0,
      "sunrise": "2026-06-29T05:58",
      "sunset": "2026-06-29T21:14",
      "wind_speed_max_mph": 12.0,
      "wind_gusts_max_mph": 22.0
    }
  ],
  "summary_hint": "Answer the user's actual forecast question concisely for IRC. Use the preset and only the relevant fields. For rain questions, focus on precipitation probability and expected accumulation."
}
```

## 5.6 Example Owl final answers

User:

```text
TerraAI: weather Detroit
```

Owl final:

```text
Detroit: 91°F and clear, feels 94°F. High near 96°F; rain chance looks very low.
```

User:

```text
TerraAI: rain tonight?
```

Owl final:

```text
Not really — rain chance stays near 0–10% tonight, with little/no expected accumulation.
```

User:

```text
TerraAI: sunset?
```

Owl final:

```text
Sunset in Detroit is 9:14 PM.
```

---

# 6. Weather History Tool

## 6.1 Tool purpose

Use `weather_history` for past weather:

- yesterday
- last week
- specific past date
- historical temperature
- historical rain/snow
- “what was the weather like on July 4, 2025?”

Do not use for:

- current/future forecast
- air quality
- API reference

## 6.2 Tool schema

```python
WEATHER_HISTORY_TOOL = {
    "type": "function",
    "function": {
        "name": "weather_history",
        "description": (
            "Use for past weather on a date or date range, including yesterday, last week, "
            "historical temperature, historical rain/snow, and weather on a past date. "
            "Do not use for current/future weather or air quality."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": ["string", "null"],
                    "description": "City/place to check. If omitted, use saved user location if available.",
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format.",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format.",
                },
                "preset": {
                    "type": "string",
                    "enum": [
                        "basic",
                        "temperature",
                        "rain",
                        "snow",
                        "wind",
                        "daily",
                        "full_debug"
                    ],
                    "default": "basic",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
}
```

## 6.3 Endpoint

```text
GET https://archive-api.open-meteo.com/v1/archive
```

Required:

```text
latitude=<float>
longitude=<float>
start_date=YYYY-MM-DD
end_date=YYYY-MM-DD
```

Use also:

```text
timezone=auto
temperature_unit=fahrenheit
wind_speed_unit=mph
precipitation_unit=inch
```

## 6.4 Historical presets

### Preset: `basic`

Use for:

```text
what was the weather yesterday?
what was weather like in Detroit last Friday?
```

Request:

```text
hourly=
temperature_2m,
relative_humidity_2m,
dew_point_2m,
apparent_temperature,
precipitation,
rain,
snowfall,
weather_code,
cloud_cover,
wind_speed_10m,
wind_direction_10m,
wind_gusts_10m

daily=
weather_code,
temperature_2m_mean,
temperature_2m_max,
temperature_2m_min,
apparent_temperature_mean,
apparent_temperature_max,
apparent_temperature_min,
precipitation_sum,
rain_sum,
snowfall_sum,
precipitation_hours,
wind_speed_10m_max,
wind_gusts_10m_max,
wind_direction_10m_dominant,
sunrise,
sunset,
daylight_duration
```

### Preset: `temperature`

Use for:

```text
how hot was it?
what was the high?
what was the low?
```

Request:

```text
hourly=
temperature_2m,
apparent_temperature,
relative_humidity_2m,
dew_point_2m

daily=
temperature_2m_mean,
temperature_2m_max,
temperature_2m_min,
apparent_temperature_mean,
apparent_temperature_max,
apparent_temperature_min
```

### Preset: `rain`

Use for:

```text
how much rain did Detroit get yesterday?
did it rain last night?
rain last week?
```

Request:

```text
hourly=
precipitation,
rain,
weather_code,
cloud_cover

daily=
precipitation_sum,
rain_sum,
precipitation_hours,
weather_code
```

### Preset: `snow`

Use for:

```text
how much did it snow?
did Chicago get snow last week?
```

Request:

```text
hourly=
snowfall,
snow_depth,
temperature_2m,
weather_code

daily=
snowfall_sum,
snowfall_water_equivalent_sum,
temperature_2m_max,
temperature_2m_min,
weather_code
```

Note: Some historical models may not include snow depth or some snow variables everywhere.

### Preset: `wind`

Use for:

```text
how windy was it yesterday?
what were the gusts?
```

Request:

```text
hourly=
wind_speed_10m,
wind_direction_10m,
wind_gusts_10m

daily=
wind_speed_10m_max,
wind_gusts_10m_max,
wind_direction_10m_dominant,
wind_speed_10m_mean,
wind_gusts_10m_mean
```

### Preset: `daily`

Use for longer ranges:

```text
weather last week
rainfall this month
```

Request daily variables only to keep payload small.

```text
daily=
weather_code,
temperature_2m_mean,
temperature_2m_max,
temperature_2m_min,
precipitation_sum,
rain_sum,
snowfall_sum,
precipitation_hours,
wind_speed_10m_max,
wind_gusts_10m_max,
sunrise,
sunset
```

### Preset: `full_debug`

Use for developer/testing only. Request a broader subset based on the Open-Meteo historical docs, but do not use for casual IRC.

## 6.5 Example historical URL

Detroit, July 4 2025:

```text
https://archive-api.open-meteo.com/v1/archive?latitude=42.3314&longitude=-83.0458&start_date=2025-07-04&end_date=2025-07-04&hourly=temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,precipitation,rain,snowfall,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m&daily=weather_code,temperature_2m_mean,temperature_2m_max,temperature_2m_min,apparent_temperature_mean,apparent_temperature_max,apparent_temperature_min,precipitation_sum,rain_sum,snowfall_sum,precipitation_hours,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,sunrise,sunset,daylight_duration&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto
```

## 6.6 What `weather_history` sends back to Owl

```json
{
  "ok": true,
  "tool": "weather_history",
  "source": "open-meteo",
  "preset": "rain",
  "location": {
    "query": "Detroit, MI",
    "name": "Detroit",
    "admin1": "Michigan",
    "country_code": "US",
    "timezone": "America/Detroit",
    "latitude": 42.3314,
    "longitude": -83.0458
  },
  "date_range": {
    "start_date": "2025-07-04",
    "end_date": "2025-07-04"
  },
  "daily": [
    {
      "date": "2025-07-04",
      "weather_description": "partly cloudy",
      "temp_max_f": 85.2,
      "temp_min_f": 68.1,
      "rain_sum_in": 0.03,
      "precipitation_sum_in": 0.03,
      "precipitation_hours": 1.0
    }
  ],
  "hourly": [
    {
      "time": "2025-07-04T15:00",
      "temperature_f": 84.0,
      "rain_in": 0.0,
      "weather_description": "partly cloudy"
    }
  ],
  "summary_hint": "Answer as past weather. Mention that historical data is modeled/reanalysis data when precision matters."
}
```

## 6.7 Historical caveat Owl should know

Add this note in the tool result when using `weather_history`:

```json
{
  "data_quality_note": "Historical Open-Meteo data is based on reanalysis/model datasets, not necessarily a direct observation from a local station."
}
```

Owl should mention this only when useful, e.g. for disputed precise rain totals.

---

# 7. Air Quality Tool

## 7.1 Tool purpose

Use `air_quality` for:

- AQI
- air quality
- smoke
- wildfire smoke
- PM2.5
- PM10
- ozone
- carbon monoxide
- nitrogen dioxide
- sulphur dioxide
- dust
- UV index
- pollen

Do not use for:

- normal temperature forecast
- past weather
- historical rainfall
- API reference

## 7.2 Tool schema

```python
AIR_QUALITY_TOOL = {
    "type": "function",
    "function": {
        "name": "air_quality",
        "description": (
            "Use for air quality, AQI, smoke, pollution, PM2.5, PM10, ozone, "
            "carbon monoxide, nitrogen dioxide, sulphur dioxide, dust, UV index, and pollen. "
            "Do not use for normal weather forecast or historical weather."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": ["string", "null"],
                    "description": "City/place to check. If omitted, use saved user location if available.",
                },
                "preset": {
                    "type": "string",
                    "enum": [
                        "current",
                        "basic",
                        "smoke",
                        "uv",
                        "pollen",
                        "pollutants",
                        "full_debug"
                    ],
                    "default": "basic",
                },
                "hours": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                    "maximum": 168,
                    "default": 12
                },
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 7,
                    "default": 5
                }
            },
            "required": [],
        },
    },
}
```

## 7.3 Endpoint

```text
GET https://air-quality-api.open-meteo.com/v1/air-quality
```

Base parameters:

```text
latitude=<float>
longitude=<float>
timezone=auto
```

Air quality supports:

```text
current=<variables>
hourly=<variables>
forecast_days=0..7
past_days=0..92
forecast_hours=<int>
past_hours=<int>
start_date=YYYY-MM-DD
end_date=YYYY-MM-DD
start_hour=YYYY-MM-DDTHH:MM
end_hour=YYYY-MM-DDTHH:MM
domains=auto|cams_europe|cams_global
```

## 7.4 Air quality presets

### Preset: `current`

Use for:

```text
how is the air right now?
AQI Detroit
is it smoky outside?
```

Request:

```text
current=
us_aqi,
us_aqi_pm2_5,
us_aqi_pm10,
us_aqi_ozone,
us_aqi_nitrogen_dioxide,
us_aqi_sulphur_dioxide,
us_aqi_carbon_monoxide,
pm2_5,
pm10,
carbon_monoxide,
nitrogen_dioxide,
sulphur_dioxide,
ozone,
dust,
uv_index
```

### Preset: `basic`

Default for:

```text
air quality Detroit
how is the air today?
```

Request:

```text
current=
us_aqi,
us_aqi_pm2_5,
pm2_5,
pm10,
ozone,
carbon_monoxide,
nitrogen_dioxide,
sulphur_dioxide,
dust,
uv_index

hourly=
us_aqi,
us_aqi_pm2_5,
pm2_5,
pm10,
ozone,
dust,
uv_index
```

Use:

```text
forecast_hours=12
forecast_days=1
```

### Preset: `smoke`

Use for:

```text
is the smoke bad?
wildfire smoke?
PM2.5?
```

Request:

```text
current=
us_aqi,
us_aqi_pm2_5,
pm2_5,
pm10,
dust

hourly=
us_aqi,
us_aqi_pm2_5,
pm2_5,
pm10,
dust
```

Use:

```text
forecast_hours=24
```

### Preset: `uv`

Use for:

```text
UV index?
will I burn?
sun exposure?
```

Request:

```text
current=
uv_index,
uv_index_clear_sky

hourly=
uv_index,
uv_index_clear_sky
```

Use:

```text
forecast_hours=24
```

### Preset: `pollen`

Use for:

```text
pollen count?
allergies bad today?
grass pollen?
ragweed?
```

Request:

```text
current=
alder_pollen,
birch_pollen,
grass_pollen,
mugwort_pollen,
olive_pollen,
ragweed_pollen

hourly=
alder_pollen,
birch_pollen,
grass_pollen,
mugwort_pollen,
olive_pollen,
ragweed_pollen
```

Important: pollen variables may be Europe-only / domain-limited. If unavailable, TerraAI should return a clean error to Owl.

### Preset: `pollutants`

Use for:

```text
ozone levels?
NO2?
PM10?
CO?
```

Request:

```text
current=
pm10,
pm2_5,
carbon_monoxide,
nitrogen_dioxide,
sulphur_dioxide,
ozone,
aerosol_optical_depth,
dust

hourly=
pm10,
pm2_5,
carbon_monoxide,
nitrogen_dioxide,
sulphur_dioxide,
ozone,
aerosol_optical_depth,
dust
```

### Preset: `full_debug`

Use for developer/testing only.

Request all common air quality variables, including:

```text
european_aqi,
us_aqi,
european_aqi_pm2_5,
european_aqi_pm10,
european_aqi_nitrogen_dioxide,
european_aqi_ozone,
european_aqi_sulphur_dioxide,
us_aqi_pm2_5,
us_aqi_pm10,
us_aqi_nitrogen_dioxide,
us_aqi_ozone,
us_aqi_sulphur_dioxide,
us_aqi_carbon_monoxide,
pm10,
pm2_5,
carbon_monoxide,
nitrogen_dioxide,
sulphur_dioxide,
ozone,
aerosol_optical_depth,
dust,
uv_index,
uv_index_clear_sky,
ammonia,
alder_pollen,
birch_pollen,
grass_pollen,
mugwort_pollen,
olive_pollen,
ragweed_pollen
```

Do not use this for normal IRC unless explicitly debugging.

## 7.5 Example air quality URL

Detroit basic:

```text
https://air-quality-api.open-meteo.com/v1/air-quality?latitude=42.3314&longitude=-83.0458&current=us_aqi,us_aqi_pm2_5,pm2_5,pm10,ozone,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,dust,uv_index&hourly=us_aqi,us_aqi_pm2_5,pm2_5,pm10,ozone,dust,uv_index&timezone=auto&forecast_hours=12&forecast_days=1
```

## 7.6 What `air_quality` sends back to Owl

```json
{
  "ok": true,
  "tool": "air_quality",
  "source": "open-meteo",
  "preset": "basic",
  "location": {
    "query": "Detroit, MI",
    "name": "Detroit",
    "admin1": "Michigan",
    "country_code": "US",
    "timezone": "America/Detroit",
    "latitude": 42.3314,
    "longitude": -83.0458
  },
  "current": {
    "time": "2026-06-29T14:00",
    "us_aqi": 42,
    "us_aqi_pm2_5": 38,
    "pm2_5_ug_m3": 8.1,
    "pm10_ug_m3": 14.0,
    "ozone_ug_m3": 61.2,
    "dust_ug_m3": 0.0,
    "uv_index": 7.1
  },
  "hourly": [
    {
      "time": "2026-06-29T15:00",
      "us_aqi": 45,
      "pm2_5_ug_m3": 8.3,
      "ozone_ug_m3": 65.0,
      "uv_index": 7.4
    }
  ],
  "summary_hint": "Answer the user's actual air quality question concisely for IRC. For AQI questions, mention AQI and the main driver if available. For smoke, focus on PM2.5/PM10. For UV, focus on peak UV and simple caution."
}
```

## 7.7 Example Owl final answers

User:

```text
TerraAI: air quality Detroit
```

Owl final:

```text
Detroit air looks okay: US AQI 42, PM2.5 about 8 µg/m³. UV is high around 7.
```

User:

```text
TerraAI: is the smoke bad?
```

Owl final:

```text
Smoke does not look bad right now: PM2.5 is around 8 µg/m³ and AQI is in the good/moderate range.
```

User:

```text
TerraAI: UV today?
```

Owl final:

```text
UV is high today, peaking around 7. Use sunscreen if you’ll be out long.
```

---

# 8. Weather Reference Tool

## 8.1 Tool purpose

Use `weather_reference` only for developer/debug questions, such as:

```text
what can the Open-Meteo forecast API return?
what variables exist for air quality?
download the weather API docs
show full reference for historical weather
```

Do not use it for normal weather answers.

## 8.2 OpenAPI specs

Open-Meteo has OpenAPI YAML files in GitHub:

```text
https://github.com/open-meteo/open-meteo/tree/main/openapi
```

Download useful specs:

```bash
mkdir -p docs/openmeteo-openapi
cd docs/openmeteo-openapi

curl -L -O https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/forecast.yml
curl -L -O https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/historical-weather.yml
curl -L -O https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/air-quality.yml
curl -L -O https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/elevation.yml
curl -L -O https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/climate.yml
curl -L -O https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/ensemble.yml
curl -L -O https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/marine.yml
curl -L -O https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/seasonal.yml
curl -L -O https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/flood.yml
```

## 8.3 Tool schema

```python
WEATHER_REFERENCE_TOOL = {
    "type": "function",
    "function": {
        "name": "weather_reference",
        "description": (
            "Use only for developer/debug questions about Open-Meteo API capabilities, "
            "available endpoints, presets, or variable names. Do not use for normal weather answers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": [
                        "forecast",
                        "historical",
                        "air_quality",
                        "all"
                    ],
                    "default": "all",
                },
                "detail": {
                    "type": "string",
                    "enum": [
                        "summary",
                        "variables",
                        "endpoints",
                        "presets",
                        "full"
                    ],
                    "default": "summary",
                },
            },
            "required": [],
        },
    },
}
```

## 8.4 Implementation

`weather_reference` should read local YAML files downloaded from Open-Meteo’s OpenAPI directory.

It should return:

```json
{
  "ok": true,
  "tool": "weather_reference",
  "source": "local-openmeteo-openapi",
  "topic": "forecast",
  "detail": "variables",
  "data": {
    "endpoint": "https://api.open-meteo.com/v1/forecast",
    "current_variables": [],
    "hourly_variables": [],
    "daily_variables": []
  },
  "summary_hint": "Summarize the relevant Open-Meteo capability for a developer. If output is long, prefer a Markdown paste."
}
```

Do not call Open-Meteo live for reference data. Use downloaded specs and keep them in the repo.

---

# 9. Weather Code Mapping

Open-Meteo returns WMO weather codes.

Create:

```text
terra_ai/tools/openmeteo/weather_codes.py
```

```python
WEATHER_CODES = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "rime fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "light freezing drizzle",
    57: "freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "showers",
    82: "violent showers",
    85: "light snow showers",
    86: "snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with heavy hail",
}

def describe_weather_code(code: int | None) -> str | None:
    if code is None:
        return None
    return WEATHER_CODES.get(int(code), f"weather code {code}")
```

Add `weather_description` to normalized current/hourly/daily rows.

---

# 10. Normalization Helpers

Create:

```text
terra_ai/tools/openmeteo/normalize.py
```

## 10.1 Convert column arrays to row objects

```python
def rows_from_columns(columns: dict, rename: dict[str, str] | None = None) -> list[dict]:
    times = columns.get("time") or []
    rename = rename or {}
    rows = []

    for idx, timestamp in enumerate(times):
        row = {"time": timestamp}
        for key, values in columns.items():
            if key == "time":
                continue
            out_key = rename.get(key, key)
            if isinstance(values, list) and idx < len(values):
                row[out_key] = values[idx]
        rows.append(row)

    return rows
```

## 10.2 Add weather descriptions

```python
def add_weather_descriptions(rows: list[dict]) -> list[dict]:
    for row in rows:
        if "weather_code" in row:
            row["weather_description"] = describe_weather_code(row["weather_code"])
    return rows
```

## 10.3 Rename fields

Use clearer names for Owl.

Examples:

```python
FORECAST_FIELD_RENAMES = {
    "temperature_2m": "temperature_f",
    "apparent_temperature": "apparent_temperature_f",
    "relative_humidity_2m": "relative_humidity_percent",
    "precipitation_probability": "precip_probability_percent",
    "precipitation": "precipitation_in",
    "rain": "rain_in",
    "showers": "showers_in",
    "snowfall": "snowfall_in",
    "cloud_cover": "cloud_cover_percent",
    "wind_speed_10m": "wind_speed_mph",
    "wind_gusts_10m": "wind_gusts_mph",
    "wind_direction_10m": "wind_direction_degrees",
    "pressure_msl": "pressure_msl_hpa",
    "surface_pressure": "surface_pressure_hpa",
}
```

Daily renames can use:

```python
DAILY_FIELD_RENAMES = {
    "time": "date",
    "temperature_2m_max": "temp_max_f",
    "temperature_2m_min": "temp_min_f",
    "temperature_2m_mean": "temp_mean_f",
    "apparent_temperature_max": "apparent_temp_max_f",
    "apparent_temperature_min": "apparent_temp_min_f",
    "apparent_temperature_mean": "apparent_temp_mean_f",
    "precipitation_probability_max": "precip_probability_max_percent",
    "precipitation_probability_mean": "precip_probability_mean_percent",
    "precipitation_sum": "precipitation_sum_in",
    "rain_sum": "rain_sum_in",
    "showers_sum": "showers_sum_in",
    "snowfall_sum": "snowfall_sum_in",
    "wind_speed_10m_max": "wind_speed_max_mph",
    "wind_gusts_10m_max": "wind_gusts_max_mph",
    "wind_direction_10m_dominant": "wind_direction_dominant_degrees",
}
```

Air quality renames:

```python
AIR_QUALITY_RENAMES = {
    "pm2_5": "pm2_5_ug_m3",
    "pm10": "pm10_ug_m3",
    "carbon_monoxide": "carbon_monoxide_ug_m3",
    "nitrogen_dioxide": "nitrogen_dioxide_ug_m3",
    "sulphur_dioxide": "sulphur_dioxide_ug_m3",
    "ozone": "ozone_ug_m3",
    "dust": "dust_ug_m3",
}
```

---

# 11. Tool Routing Instructions for Owl

Add something like this to the tool/system prompt:

```text
You have client-side tools for weather and air quality.

Use weather_forecast for current or future weather:
- current weather
- forecast
- rain tonight
- snow tomorrow
- wind
- sunrise/sunset
- hourly forecast
- daily forecast

Use weather_history for past weather:
- yesterday
- last week
- historical weather
- weather on a past date
- past rain/snow/temperature

Use air_quality for:
- AQI
- air quality
- smoke
- wildfire smoke
- PM2.5/PM10
- ozone
- pollution
- UV index
- pollen

Use weather_reference only for developer/debug questions about what Open-Meteo supports.

Always request the smallest preset that can answer the user:
- weather_forecast current: right now/current conditions
- weather_forecast basic_forecast: generic weather/forecast
- weather_forecast rain: rain/snow/storm questions
- weather_forecast hourly: hour-by-hour questions
- weather_forecast daily: week/multi-day forecast
- weather_forecast sun: sunrise/sunset/daylight
- weather_forecast wind: wind/gust questions
- weather_history basic: generic past weather
- weather_history rain: past rain/precipitation
- weather_history snow: past snowfall
- weather_history temperature: past high/low/temp
- air_quality basic: generic air quality
- air_quality smoke: smoke/PM2.5/PM10
- air_quality uv: UV index
- air_quality pollen: pollen/allergy questions

If the user omits location, the tool may use saved user location. If no saved location exists, ask for location.

When composing the final IRC answer:
- Be concise.
- Do not list every field.
- Answer the user's actual question.
- Mention the location.
- Mention times in local time.
- For historical weather, mention that it is modeled/reanalysis data only if precision matters.
- For air quality, mention AQI and likely driver when available.
```

---

# 12. Implementation Steps for Claude

## Step 1: Inspect existing TerraAI tool flow

Find existing tool-related code:

```bash
grep -R "tools" -n terra_ai
grep -R "execute_tool" -n terra_ai
grep -R "tool_call" -n terra_ai
grep -R "server_tool" -n terra_ai
```

Identify:

- where request payloads are built
- how OpenRouter tools are passed
- how server-side web search is configured
- how local tool calls are executed, if already implemented
- how messages are fed back to the LLM
- how Textual test console sends messages

## Step 2: Add tool result and registry

Create or update:

```text
terra_ai/tools/result.py
terra_ai/tools/registry.py
```

Registry API:

```python
class ToolRegistry:
    def register(self, tool):
        ...

    def schemas(self) -> list[dict]:
        ...

    async def execute(self, name: str, arguments: dict, context) -> ToolResult:
        ...
```

Tool interface:

```python
class ClientTool(Protocol):
    name: str
    schema: dict

    async def execute(self, arguments: dict, context) -> ToolResult:
        ...
```

## Step 3: Wire local tool execution into OpenRouter loop

Pseudo-flow:

```python
response = await provider.chat_completion(
    messages=messages,
    tools=tool_registry.schemas(),
)

if response.has_tool_calls:
    for call in response.tool_calls:
        result = await tool_registry.execute(call.name, call.arguments, context)
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "name": call.name,
            "content": json.dumps(result_for_model(result)),
        })

    final_response = await provider.chat_completion(
        messages=messages,
        tools=tool_registry.schemas(),
    )

    send_to_irc(final_response.text)
else:
    send_to_irc(response.text)
```

Do not assume only one tool call forever. Implement at least a simple loop with a max iteration count.

Recommended:

```python
MAX_TOOL_ROUNDS = 3
```

## Step 4: Add Open-Meteo module

Create:

```text
terra_ai/tools/openmeteo/
  __init__.py
  client.py
  geocode.py
  normalize.py
  weather_codes.py
  forecast.py
  history.py
  air_quality.py
  reference.py
  schemas.py
```

## Step 5: Implement geocoding

Implement `geocode_location`.

Use saved user location first if no `location` argument was provided.

## Step 6: Implement `weather_forecast`

Implement presets exactly as defined above.

Function shape:

```python
async def execute_weather_forecast(arguments: dict, context) -> ToolResult:
    location = await resolve_location(arguments.get("location"), context)
    preset = arguments.get("preset") or "basic_forecast"
    params = build_forecast_params(location, preset, arguments)
    raw = await client.get_json(FORECAST_URL, params)
    normalized = normalize_forecast(raw, location, preset)
    return ToolResult(
        ok=True,
        tool="weather_forecast",
        source="open-meteo",
        data=normalized,
        summary_hint=forecast_summary_hint(preset),
        debug={...},
    )
```

## Step 7: Implement `weather_history`

Same pattern, but use archive endpoint and require dates.

Add date parsing before tool call if possible.

For relative dates like “yesterday,” Owl should pass actual dates if the model can infer them. TerraAI can also defensively parse common relative dates.

## Step 8: Implement `air_quality`

Same pattern, but use air-quality endpoint and AQ presets.

## Step 9: Implement `weather_reference`

Download OpenAPI YAML specs into repo or cache directory.

Parse enough to list endpoints and variable names.

This can be basic initially: return static curated tables from this document, then later parse YAML.

## Step 10: Update test console

Add commands or test inputs in Textual console:

```text
TerraAI: weather Detroit
TerraAI: rain tonight in Detroit?
TerraAI: weather Chicago this week
TerraAI: what was the weather in Detroit yesterday?
TerraAI: how much rain did Chicago get last week?
TerraAI: air quality Detroit
TerraAI: is the smoke bad in Chicago?
TerraAI: UV in Detroit today?
TerraAI: what can the weather API return?
```

## Step 11: Add logging

Log:

```text
tool name
preset
location query
resolved location
endpoint
duration
cache hit
success/failure
error type
```

Do not log:

```text
API keys
full raw responses by default
private messages unless debug mode
```

## Step 12: Add caching

Suggested TTLs:

| Data | TTL |
|---|---|
| Geocoding | 30 days |
| Current forecast | 5–10 minutes |
| Hourly/daily forecast | 15–30 minutes |
| Air quality current/basic | 10–20 minutes |
| Historical weather | effectively permanent |
| OpenAPI reference | until manually refreshed |

---

# 13. Acceptance Tests

## 13.1 Tool routing tests

Input:

```text
weather Detroit
```

Expected tool:

```text
weather_forecast preset=basic_forecast
```

Input:

```text
rain tonight in Detroit?
```

Expected tool:

```text
weather_forecast preset=rain
```

Input:

```text
what was the weather in Detroit yesterday?
```

Expected tool:

```text
weather_history preset=basic
```

Input:

```text
how much rain did Detroit get last week?
```

Expected tool:

```text
weather_history preset=rain
```

Input:

```text
air quality Detroit
```

Expected tool:

```text
air_quality preset=basic
```

Input:

```text
is the smoke bad in Detroit?
```

Expected tool:

```text
air_quality preset=smoke
```

Input:

```text
UV today in Detroit?
```

Expected tool:

```text
air_quality preset=uv
```

Input:

```text
what variables does Open-Meteo support?
```

Expected tool:

```text
weather_reference
```

## 13.2 API tests

- Geocode Detroit, MI.
- Geocode Chicago, IL.
- Forecast Detroit current.
- Forecast Detroit rain preset.
- Forecast Chicago daily preset.
- Historical Detroit yesterday.
- Historical Detroit July 4, 2025.
- Air quality Detroit basic.
- Air quality Detroit smoke.
- Air quality Detroit UV.
- Unknown location returns clean error.
- API timeout returns clean error.
- Invalid date returns clean error.

## 13.3 Output tests

Weather final answer should be concise:

```text
Detroit: 91°F and clear, feels 94°F. High near 96°F; rain chance is low.
```

Rain final answer should answer rain directly:

```text
Not likely tonight — rain chance stays under 10%, with little/no accumulation.
```

Historical final answer should be past-tense:

```text
Detroit on Jul 4, 2025: high 85°F, low 68°F, about 0.03 in rain.
```

Air quality final answer should include AQI:

```text
Detroit air looks okay: US AQI 42, PM2.5 about 8 µg/m³.
```

## 13.4 Safety tests

- No private/internal URL fetches; not relevant here except if future tools do URL fetch.
- No secrets in logs.
- No raw tracebacks to IRC.
- No giant raw JSON in IRC.
- Tool failures should produce a short useful message.

---

# 14. Config

Add config:

```ini
[terra_ai.tools]
enabled = true

[terra_ai.tools.openmeteo]
enabled = true
timeout_s = 8
default_temperature_unit = fahrenheit
default_wind_speed_unit = mph
default_precipitation_unit = inch
cache_enabled = true

[terra_ai.tools.openmeteo.forecast]
enabled = true
default_preset = basic_forecast
default_forecast_days = 3
default_forecast_hours = 24

[terra_ai.tools.openmeteo.history]
enabled = true

[terra_ai.tools.openmeteo.air_quality]
enabled = true
default_preset = basic
default_forecast_hours = 12

[terra_ai.tools.openmeteo.reference]
enabled = true
openapi_dir = docs/openmeteo-openapi
```

---

# 15. Dependencies

Likely dependencies:

```text
httpx
pydantic or jsonschema
python-dateutil
PyYAML
```

Optional:

```text
diskcache
cachetools
```

Install on Arch/CachyOS:

```bash
sudo pacman -S python-httpx python-yaml python-dateutil
```

If packages are missing from repos:

```bash
python -m pip install --user httpx PyYAML python-dateutil
```

Use project dependency management if TerraAI already has it.

---

# 16. References

Open-Meteo docs:

```text
Forecast:
https://open-meteo.com/en/docs

Geocoding:
https://open-meteo.com/en/docs/geocoding-api

Historical Weather:
https://open-meteo.com/en/docs/historical-weather-api

Air Quality:
https://open-meteo.com/en/docs/air-quality-api

OpenAPI specs:
https://github.com/open-meteo/open-meteo/tree/main/openapi
```

Raw OpenAPI downloads:

```text
https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/forecast.yml
https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/historical-weather.yml
https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi/air-quality.yml
```

---

# 17. First Milestone

Do this first:

```text
weather_forecast with:
- geocoding
- current preset
- basic_forecast preset
- rain preset
- normalized data to Owl
- final Owl answer in IRC
- Textual test console coverage
```

Do not start with historical or air quality until forecast works end-to-end.

Minimum user-facing success:

```text
TerraAI: weather Detroit
→ Detroit: 91°F and clear, feels 94°F. High near 96°F; rain chance is low.

TerraAI: rain tonight in Detroit?
→ Not likely tonight — rain chance stays under 10%, with little/no accumulation.
```

After that:

1. Add `air_quality`.
2. Add `weather_history`.
3. Add `weather_reference`.
4. Add Markdown paste support for long debug/reference output.

---

# 18. Implementation Notes (Agent1, 2026-06-29)

The first milestone has been **implemented** in `~/agentic-repos/terra-ai-agent1/`
on branch `agent1/weather-tools`. This section records what diverged from the
original plan and what to know when continuing.

## 18.1 What was actually built

Tools implemented and wired into the LLM's `tools` parameter:

- `weather_forecast` — all 8 presets (current, basic_forecast, rain, hourly, daily, sun, wind, full_debug)
- `geocode` — standalone tool to resolve place names to coordinates

Tools defined in schemas but **not yet implemented** (stubs only):

- `weather_history`
- `air_quality`
- `weather_reference`

The tool-call loop lives in `OpenRouterProvider.chat()` (providers/openrouter.py).
It loops up to `MAX_TOOL_ROUNDS = 3` times, executing local tools via
`terra_ai/tools/executor.py` and feeding `ToolResult` JSON back to the model.

## 18.2 Differences from this document's original plan

| Original plan | What we did |
|---|---|
| §4.3 Saved user location in SQLite | **Not implemented.** No location column, no DB lookup. Model knows location from the user's message. If location is missing, the tool returns a clean error asking the model to prompt the user. |
| §4.4 Geocode cache table | **Not implemented.** Can add `openmeteo_geocode_cache` table later. |
| §12 Step 2 `result.py` + `registry.py` + `ClientTool` Protocol | **Simplified.** Used the existing flat `TOOL_FUNCTIONS` dict pattern. `result.py` exists with a `ToolResult` dataclass. No `registry.py` or Protocol. |
| §12 Step 3 tool-call loop already exists | **Built from scratch.** The loop was removed when we switched to server-side search; we restored it in `openrouter.py`. |
| §15 `pydantic`, `jsonschema`, `diskcache`, `cachetools` | **Avoided all.** Uses only stdlib + `httpx` (already a project dep). |
| Geocode as internal step only | **Standalone `geocode` tool.** Model can call it to "remember" coordinates. |

## 18.3 Geocoding API quirk

Open-Meteo's `/v1/search` returns zero results for `"Detroit, MI"` but works
for `"Detroit"`. The implementation strips `, ST` suffixes via
`_clean_location_query()` in `geocode.py`. If you see "location not found"
errors, this is the first thing to check.

## 18.4 Testing

- `tests/test_weather.py` — 19 unit-of-logic tests (real Open-Meteo HTTP) + 2
  end-to-end tests (real OpenRouter AI + real Open-Meteo). All pass.
- `tests/test_ergo.py::test_bot_uses_weather_forecast_tool` — live ergo + SOPEL
  + bot integration test. Requires ergo on localhost:6667.
- All tests use real HTTP. No mocks, including no AI mocks. Source
  `~/.terra-ai/.env` first.

## 18.5 Key files

| File | Purpose |
|---|---|
| `terra_ai/tools/openmeteo/client.py` | Shared sync HTTP client |
| `terra_ai/tools/openmeteo/result.py` | `ToolResult` dataclass |
| `terra_ai/tools/openmeteo/forecast.py` | `weather_forecast` implementation |
| `terra_ai/tools/openmeteo/geocode.py` | Geocoding + `_clean_location_query` |
| `terra_ai/tools/openmeteo/geocode_tool.py` | Standalone `geocode` tool |
| `terra_ai/tools/openmeteo/schemas.py` | All 5 tool schema dicts |
| `terra_ai/tools/schemas.py` | Top-level `AVAILABLE_TOOLS` |
| `terra_ai/tools/executor.py` | `TOOL_FUNCTIONS` dispatch |
| `terra_ai/providers/openrouter.py` | Tool-call loop (max 3 rounds) |
| `tests/test_weather.py` | All weather tests |
