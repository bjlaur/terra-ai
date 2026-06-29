"""WMO weather code mapping for Open-Meteo.

Open-Meteo returns WMO weather interpretation codes. Map them to short
human-readable descriptions for the normalized tool output.
"""

WEATHER_CODES: dict[int, str] = {
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
    """Return a human-readable description for a WMO weather code."""
    if code is None:
        return None
    return WEATHER_CODES.get(int(code), f"weather code {code}")
