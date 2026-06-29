"""Normalization helpers for Open-Meteo responses.

Open-Meteo returns column-oriented data (one array per variable). The model
reasons more reliably with row-oriented data (one dict per time step), so
these helpers reshape and rename the raw response before it goes back.
"""

from terra_ai.tools.openmeteo.weather_codes import describe_weather_code

# Rename Open-Meteo's verbose variable names into clearer, unit-suffixed
# names for the model. The API already returns F/mph/inch because we request
# those units, so the rename just makes the unit obvious.
FORECAST_RENAMES: dict[str, str] = {
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

DAILY_RENAMES: dict[str, str] = {
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

AIR_QUALITY_RENAMES: dict[str, str] = {
    "pm2_5": "pm2_5_ug_m3",
    "pm10": "pm10_ug_m3",
    "carbon_monoxide": "carbon_monoxide_ug_m3",
    "nitrogen_dioxide": "nitrogen_dioxide_ug_m3",
    "sulphur_dioxide": "sulphur_dioxide_ug_m3",
    "ozone": "ozone_ug_m3",
    "dust": "dust_ug_m3",
}


def rows_from_columns(columns: dict, rename: dict[str, str] | None = None) -> list[dict]:
    """Convert a column-oriented payload to a list of row dicts.

    Input shape:  {"time": [...], "temperature_2m": [...], ...}
    Output shape: [{"time": ..., "temperature_f": ...}, ...]
    """
    rename = rename or {}
    times = columns.get("time") or []
    rows: list[dict] = []

    for idx, timestamp in enumerate(times):
        row: dict = {"time": timestamp}
        for key, values in columns.items():
            if key == "time":
                continue
            out_key = rename.get(key, key)
            if isinstance(values, list) and idx < len(values):
                row[out_key] = values[idx]
        rows.append(row)

    return rows


def add_weather_descriptions(rows: list[dict]) -> list[dict]:
    """Add a human-readable weather_description to each row that has a code."""
    for row in rows:
        if "weather_code" in row:
            row["weather_description"] = describe_weather_code(row["weather_code"])
    return rows
