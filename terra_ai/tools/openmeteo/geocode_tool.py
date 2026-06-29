"""Standalone geocode tool — resolve a place name to coordinates.

The model can call this to "remember" a location (via conversation context)
before calling weather_forecast / weather_history / air_quality with raw
lat/lon. Also useful for -setlocation-style flows.

No caching yet — just a clean tool wrapper around geocode_location.
"""

import logging
import time
from typing import Any

from terra_ai.tools.openmeteo.client import OpenMeteoClient
from terra_ai.tools.openmeteo.geocode import geocode_location
from terra_ai.tools.openmeteo.result import ToolResult

logger = logging.getLogger("terraai")


def execute_geocode(arguments: dict[str, Any], client: OpenMeteoClient | None = None,
                   noisy_callback=None) -> ToolResult:
    """Execute the geocode tool.

    arguments: {"location": "Detroit, MI"}
    Returns: ToolResult with resolved coordinates.
    """
    start = time.time()
    client = client or OpenMeteoClient()

    location_arg = arguments.get("location")
    if noisy_callback and location_arg:
        noisy_callback(f"Geocoding {location_arg}...")
    if not location_arg:
        return ToolResult(
            ok=False,
            tool="geocode",
            source="open-meteo",
            error="No location provided.",
            summary_hint="Ask the user what location they want to resolve.",
        )

    try:
        location = geocode_location(client, location_arg)
    except ValueError as e:
        return ToolResult(
            ok=False,
            tool="geocode",
            source="open-meteo",
            error=str(e),
            summary_hint="Tell the user that location wasn't found and ask for a different one.",
        )

    duration_ms = int((time.time() - start) * 1000)

    return ToolResult(
        ok=True,
        tool="geocode",
        source="open-meteo",
        data=location,
        summary_hint=(
            "The location is resolved. You can now call weather tools with "
            "latitude/longitude directly, or remember this location for "
            "subsequent weather queries in this conversation."
        ),
        debug={
            "duration_ms": duration_ms,
        },
    )
