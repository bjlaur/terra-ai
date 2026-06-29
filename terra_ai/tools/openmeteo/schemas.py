"""LLM-facing tool schemas for Open-Meteo tools.

Four separate function tools (not one generic weather() with a preset enum)
because it makes tool choice easier for the model. Internally they share
the openmeteo module.
"""

WEATHER_FORECAST_TOOL = {
    "type": "function",
    "function": {
        "name": "weather_forecast",
        "description": (
            "Use for current or future weather: current conditions, forecast, "
            "rain tonight, snow tomorrow, storms, wind, sunrise/sunset, "
            "hourly forecast, daily/week forecast. "
            "Do not use for past weather or air quality."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": ["string", "null"],
                    "description": (
                        "City/place to check, e.g. 'Detroit, MI' or 'Chicago, IL'. "
                        "If omitted, the tool will ask the model to request a location."
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
                        "full_debug",
                    ],
                    "description": (
                        "Choose the smallest preset that answers the user. "
                        "current=right now, basic_forecast=generic, "
                        "rain=rain/snow/storms, hourly=hour-by-hour, "
                        "daily=multi-day, sun=sunrise/sunset, wind=wind/gusts, "
                        "full_debug=developer inspection only."
                    ),
                },
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 16,
                    "description": "Forecast days to request. Max 16. Default 3.",
                },
                "hours": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                    "maximum": 168,
                    "description": "Optional number of forecast hours to request.",
                },
            },
            "required": [],
        },
    },
}

WEATHER_HISTORY_TOOL = {
    "type": "function",
    "function": {
        "name": "weather_history",
        "description": (
            "Use for past weather on a date or date range: yesterday, last week, "
            "historical temperature, historical rain/snow, weather on a past date. "
            "Do not use for current/future weather or air quality."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": ["string", "null"],
                    "description": "City/place to check.",
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
                        "full_debug",
                    ],
                    "description": (
                        "basic=generic past weather, temperature=highs/lows, "
                        "rain=past precipitation, snow=snowfall, wind=wind/gusts, "
                        "daily=longer ranges, full_debug=developer only."
                    ),
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
}

AIR_QUALITY_TOOL = {
    "type": "function",
    "function": {
        "name": "air_quality",
        "description": (
            "Use for air quality, AQI, smoke, pollution, PM2.5, PM10, ozone, "
            "carbon monoxide, nitrogen dioxide, sulphur dioxide, dust, "
            "UV index, and pollen. "
            "Do not use for normal weather forecast or historical weather."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": ["string", "null"],
                    "description": "City/place to check.",
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
                        "full_debug",
                    ],
                    "description": (
                        "current=right now AQI, basic=generic, smoke=PM2.5/PM10, "
                        "uv=UV index, pollen=allergies, pollutants=individual "
                        "pollutant levels, full_debug=developer only."
                    ),
                },
                "hours": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                    "maximum": 168,
                    "description": "Hours of forecast data. Default 12.",
                },
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 7,
                    "description": "Days of forecast data. Default 5.",
                },
            },
            "required": [],
        },
    },
}

GEOCODE_TOOL = {
    "type": "function",
    "function": {
        "name": "geocode",
        "description": (
            "Resolve a place name to coordinates. Use when the user gives a "
            "location that may need disambiguation, or when you want to cache "
            "coordinates for follow-up weather queries. Returns latitude, "
            "longitude, timezone, and admin info."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City/place to resolve, e.g. 'Detroit, MI'.",
                },
            },
            "required": ["location"],
        },
    },
}

WEATHER_REFERENCE_TOOL = {
    "type": "function",
    "function": {
        "name": "weather_reference",
        "description": (
            "Use only for developer/debug questions about Open-Meteo API "
            "capabilities: available endpoints, variable names, presets. "
            "Do not use for normal weather answers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": ["forecast", "historical", "air_quality", "all"],
                    "description": "Which API reference to summarize.",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "variables", "endpoints", "presets", "full"],
                    "description": "How much detail to return.",
                },
            },
            "required": [],
        },
    },
}

# All Open-Meteo tools. The first milestone wires in weather_forecast; the
# others are registered as they are implemented.
ALL_OPENMETEO_TOOLS = [
    WEATHER_FORECAST_TOOL,
    WEATHER_HISTORY_TOOL,
    AIR_QUALITY_TOOL,
    WEATHER_REFERENCE_TOOL,
    GEOCODE_TOOL,
]
