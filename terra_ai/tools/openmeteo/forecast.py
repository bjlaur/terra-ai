"""weather_forecast tool — current and future weather from Open-Meteo."""

import time
from typing import Any

from terra_ai.errors import log_expected_error
from terra_ai.tools.openmeteo.client import (
    FORECAST_URL,
    OpenMeteoClient,
    OpenMeteoError,
    OpenMeteoResponseError,
)
from terra_ai.tools.openmeteo.geocode import geocode_location
from terra_ai.tools.openmeteo.normalize import (
    FORECAST_RENAMES,
    DAILY_RENAMES,
    add_weather_descriptions,
    rows_from_columns,
)

# Re-export for use in _normalize_block (avoids re-import inside the function).
_normalize_add_descriptions = add_weather_descriptions
from terra_ai.tools.openmeteo.result import ToolResult

# Preset -> variable lists. Copied exactly from the hand-off doc so the
# Open-Meteo request matches the agreed shape.

PRESETS: dict[str, dict[str, list[str]]] = {
    "current": {
        "current": [
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "is_day", "precipitation", "rain", "showers", "snowfall",
            "weather_code", "cloud_cover", "pressure_msl", "surface_pressure",
            "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
        ],
    },
    "basic_forecast": {
        "current": [
            "temperature_2m", "apparent_temperature", "relative_humidity_2m",
            "precipitation", "rain", "weather_code", "cloud_cover",
            "wind_speed_10m", "wind_gusts_10m",
        ],
        "hourly": [
            "temperature_2m", "apparent_temperature",
            "precipitation_probability", "precipitation", "rain", "showers",
            "snowfall", "weather_code", "cloud_cover",
            "wind_speed_10m", "wind_gusts_10m",
        ],
        "daily": [
            "weather_code", "temperature_2m_max", "temperature_2m_min",
            "precipitation_probability_max", "precipitation_sum", "rain_sum",
            "showers_sum", "snowfall_sum", "sunrise", "sunset",
            "wind_speed_10m_max", "wind_gusts_10m_max",
        ],
    },
    "rain": {
        "current": [
            "temperature_2m", "weather_code", "precipitation", "rain",
            "showers", "snowfall", "cloud_cover",
        ],
        "hourly": [
            "temperature_2m", "apparent_temperature",
            "precipitation_probability", "precipitation", "rain", "showers",
            "snowfall", "weather_code", "cloud_cover",
            "wind_speed_10m", "wind_gusts_10m",
        ],
        "daily": [
            "precipitation_probability_max", "precipitation_sum", "rain_sum",
            "showers_sum", "snowfall_sum", "weather_code", "sunset",
        ],
    },
    "hourly": {
        "current": [
            "temperature_2m", "apparent_temperature", "relative_humidity_2m",
            "precipitation", "rain", "weather_code", "cloud_cover",
            "wind_speed_10m", "wind_gusts_10m",
        ],
        "hourly": [
            "temperature_2m", "apparent_temperature",
            "precipitation_probability", "precipitation", "rain", "showers",
            "snowfall", "weather_code", "cloud_cover",
            "wind_speed_10m", "wind_gusts_10m",
        ],
    },
    "daily": {
        "daily": [
            "weather_code", "temperature_2m_max", "temperature_2m_min",
            "apparent_temperature_max", "apparent_temperature_min",
            "sunrise", "sunset", "daylight_duration", "sunshine_duration",
            "uv_index_max", "uv_index_clear_sky_max",
            "rain_sum", "showers_sum", "snowfall_sum",
            "precipitation_sum", "precipitation_hours",
            "precipitation_probability_max",
            "wind_speed_10m_max", "wind_gusts_10m_max",
            "wind_direction_10m_dominant",
        ],
    },
    "sun": {
        "daily": ["sunrise", "sunset", "daylight_duration", "sunshine_duration"],
    },
    "wind": {
        "current": [
            "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
            "weather_code", "temperature_2m",
        ],
        "hourly": [
            "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
            "temperature_2m", "weather_code",
        ],
        "daily": [
            "wind_speed_10m_max", "wind_gusts_10m_max",
            "wind_direction_10m_dominant",
        ],
    },
    "full_debug": {
        "current": [
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "is_day", "precipitation", "rain", "showers", "snowfall",
            "weather_code", "cloud_cover", "pressure_msl", "surface_pressure",
            "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
        ],
        "hourly": [
            "temperature_2m", "relative_humidity_2m", "dew_point_2m",
            "apparent_temperature", "precipitation_probability",
            "precipitation", "rain", "showers", "snowfall", "snow_depth",
            "weather_code", "pressure_msl", "surface_pressure",
            "cloud_cover", "cloud_cover_low", "cloud_cover_mid",
            "cloud_cover_high", "visibility", "evapotranspiration",
            "et0_fao_evapotranspiration", "vapour_pressure_deficit",
            "wind_speed_10m", "wind_speed_80m", "wind_speed_120m",
            "wind_speed_180m", "wind_direction_10m", "wind_direction_80m",
            "wind_direction_120m", "wind_direction_180m", "wind_gusts_10m",
            "temperature_80m", "temperature_120m", "temperature_180m",
            "soil_temperature_0cm", "soil_temperature_6cm",
            "soil_temperature_18cm", "soil_temperature_54cm",
            "soil_moisture_0_to_1cm", "soil_moisture_1_to_3cm",
            "soil_moisture_3_to_9cm", "soil_moisture_9_to_27cm",
            "soil_moisture_27_to_81cm", "uv_index", "uv_index_clear_sky",
            "is_day", "sunshine_duration", "wet_bulb_temperature_2m",
            "total_column_integrated_water_vapour", "cape", "lifted_index",
            "convective_inhibition", "freezing_level_height",
            "boundary_layer_height",
        ],
        "daily": [
            "weather_code", "temperature_2m_max", "temperature_2m_min",
            "apparent_temperature_max", "apparent_temperature_min",
            "sunrise", "sunset", "daylight_duration", "sunshine_duration",
            "uv_index_max", "uv_index_clear_sky_max",
            "rain_sum", "showers_sum", "snowfall_sum",
            "precipitation_sum", "precipitation_hours",
            "precipitation_probability_max",
            "wind_speed_10m_max", "wind_gusts_10m_max",
            "wind_direction_10m_dominant", "shortwave_radiation_sum",
            "et0_fao_evapotranspiration", "temperature_2m_mean",
            "apparent_temperature_mean", "cloud_cover_mean",
            "cloud_cover_max", "cloud_cover_min",
            "dew_point_2m_mean", "dew_point_2m_max", "dew_point_2m_min",
            "precipitation_probability_mean", "precipitation_probability_min",
            "relative_humidity_2m_mean", "relative_humidity_2m_max",
            "relative_humidity_2m_min", "pressure_msl_mean",
            "pressure_msl_max", "pressure_msl_min",
            "surface_pressure_mean", "surface_pressure_max",
            "surface_pressure_min", "visibility_mean", "visibility_min",
            "visibility_max", "wind_gusts_10m_mean", "wind_speed_10m_mean",
            "wind_gusts_10m_min", "wind_speed_10m_min",
            "wet_bulb_temperature_2m_mean", "wet_bulb_temperature_2m_max",
            "wet_bulb_temperature_2m_min",
        ],
    },
}

# Default forecast_days / forecast_hours per preset.
PRESET_DEFAULTS: dict[str, dict[str, int]] = {
    "current": {},
    "basic_forecast": {"forecast_days": 3, "forecast_hours": 24},
    "rain": {"forecast_days": 2, "forecast_hours": 24},
    "hourly": {"forecast_days": 3, "forecast_hours": 48},
    "daily": {"forecast_days": 7},
    "sun": {"forecast_days": 3},
    "wind": {"forecast_days": 3, "forecast_hours": 24},
    "full_debug": {"forecast_days": 7},
}


def _validate_arguments(arguments: Any) -> str | None:
    if not isinstance(arguments, dict):
        return "Arguments must be a JSON object."

    location = arguments.get("location")
    if location is not None and (
        not isinstance(location, str) or not location.strip()
    ):
        return "Location must be a non-empty string."

    preset = arguments.get("preset", "basic_forecast")
    if not isinstance(preset, str) or preset not in PRESETS:
        return f"Unknown weather preset {preset!r}."

    for field, maximum in (("days", 16), ("hours", 168)):
        value = arguments.get(field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            return f"{field.capitalize()} must be an integer."
        if not 1 <= value <= maximum:
            return f"{field.capitalize()} must be between 1 and {maximum}."
    return None


def _summary_hint(preset: str) -> str:
    base = (
        "Answer the user's actual forecast question concisely for IRC. "
        "Use only the relevant fields. Do not list every field."
    )
    if preset == "rain":
        return base + " For rain questions, focus on precipitation probability and expected accumulation."
    if preset == "sun":
        return base + " Mention sunrise/sunset/daylight times in local time."
    if preset == "wind":
        return base + " Mention current or forecasted wind speeds and gusts."
    if preset == "full_debug":
        return "This is a debug/developer response. Return structured data; do not dump all fields to IRC."
    return base


def build_forecast_params(
    latitude: float,
    longitude: float,
    preset: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Build the query params for the Open-Meteo forecast endpoint."""
    vars_by_block = PRESETS.get(preset, PRESETS["basic_forecast"])
    defaults = PRESET_DEFAULTS.get(preset, {})

    params: dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "auto",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
    }

    for block, variables in vars_by_block.items():
        params[block] = ",".join(variables)

    # forecast_days / forecast_hours: caller override, else preset default.
    days = arguments.get("days") or defaults.get("forecast_days")
    hours = arguments.get("hours") or defaults.get("forecast_hours")
    if days is not None:
        params["forecast_days"] = int(days)
    if hours is not None:
        params["forecast_hours"] = int(hours)

    return params


def _normalize_block(raw: dict, block: str, rename: dict[str, str]) -> list[dict] | dict:
    """Normalize one block (current/hourly/daily) of the raw response.

    `current` is a single dict; `hourly`/`daily` are column-oriented and
    get reshaped into row lists.
    """
    data = raw.get(block)
    if data is None:
        return {} if block == "current" else []
    if block == "current":
        # Single time step — rename + add description.
        row = {"time": data.get("time")}
        for key, value in data.items():
            if key == "time":
                continue
            out_key = rename.get(key, key)
            row[out_key] = value
        if "weather_code" in row:
            row = _normalize_add_descriptions([row])[0]
        return row
    # hourly / daily — column-oriented.
    rows = rows_from_columns(data, rename=rename)
    return _normalize_add_descriptions(rows)


def execute_weather_forecast(arguments: dict[str, Any], client: OpenMeteoClient | None = None,
                              noisy_callback=None) -> ToolResult:
    """Execute the weather_forecast tool.

    *arguments* is the parsed JSON the model sent for the tool call.
    Returns a ToolResult ready to serialize back to the model.
    """
    start = time.time()
    client = client or OpenMeteoClient()

    validation_error = _validate_arguments(arguments)
    if validation_error:
        return ToolResult(
            ok=False,
            tool="weather_forecast",
            source="terra-ai",
            error=validation_error,
            summary_hint="Correct the tool arguments before trying again.",
        )

    location_arg = arguments.get("location")
    preset = arguments.get("preset") or "basic_forecast"

    if noisy_callback and location_arg:
        noisy_callback(f"Fetching weather for {location_arg} ({preset})...")

    if not location_arg:
        return ToolResult(
            ok=False,
            tool="weather_forecast",
            source="open-meteo",
            error="No location provided.",
            summary_hint="Ask the user what location they want weather for.",
        )

    try:
        location = geocode_location(client, location_arg)
    except ValueError as exc:
        log_expected_error(exc, "weather location lookup")
        return ToolResult(
            ok=False,
            tool="weather_forecast",
            source="open-meteo",
            error=str(exc),
            summary_hint="Tell the user that location wasn't found and ask for a different one.",
        )
    except OpenMeteoError as exc:
        log_expected_error(exc, "weather geocoding service")
        return ToolResult(
            ok=False,
            tool="weather_forecast",
            source="open-meteo",
            error=f"Weather service error: {exc}",
            summary_hint="Tell the user the weather service is temporarily unavailable.",
        )

    params = build_forecast_params(
        latitude=location["latitude"],
        longitude=location["longitude"],
        preset=preset,
        arguments=arguments,
    )

    try:
        raw = client.get_json(FORECAST_URL, params)
        if not any(block in raw for block in PRESETS[preset]):
            raise OpenMeteoResponseError(
                f"Open-Meteo forecast response contains no data for preset {preset!r}"
            )
    except OpenMeteoError as exc:
        log_expected_error(exc, "weather forecast service")
        return ToolResult(
            ok=False,
            tool="weather_forecast",
            source="open-meteo",
            error=f"Weather service error: {exc}",
            summary_hint="Tell the user the weather service is temporarily unavailable.",
        )

    duration_ms = int((time.time() - start) * 1000)

    # Normalize each present block.
    current = _normalize_block(raw, "current", FORECAST_RENAMES)
    hourly = _normalize_block(raw, "hourly", FORECAST_RENAMES)
    daily = _normalize_block(raw, "daily", DAILY_RENAMES)

    data = {
        "preset": preset,
        "location": {
            "query": location_arg,
            "name": location.get("name"),
            "admin1": location.get("admin1"),
            "country_code": location.get("country_code"),
            "timezone": location.get("timezone"),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
        },
        "units": {
            "temperature": "°F",
            "wind_speed": "mph",
            "precipitation": "inch",
        },
    }
    if current:
        data["current"] = current
    if hourly:
        data["hourly"] = hourly
    if daily:
        data["daily"] = daily

    return ToolResult(
        ok=True,
        tool="weather_forecast",
        source="open-meteo",
        data=data,
        summary_hint=_summary_hint(preset),
        debug={
            "provider_url": FORECAST_URL,
            "preset": preset,
            "duration_ms": duration_ms,
        },
    )
