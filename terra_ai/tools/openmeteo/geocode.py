"""Geocoding for Open-Meteo tools.

No saved user location in the database — the model knows location from the
user's message. The tool's `location` param is passed straight from the model
to the geocoder. If no location is provided, the tool returns a clean error
asking the model to prompt the user.
"""

import logging

from terra_ai.tools.openmeteo.client import GEOCODING_URL, OpenMeteoClient

logger = logging.getLogger("terraai")


def _clean_location_query(name: str) -> str:
    """Strip ', ST' or ', State' suffixes from a location query.

    Open-Meteo's geocoding API returns zero results for 'Detroit, MI' but
    works fine for 'Detroit'. If the query has a comma, try the part before
    it first; if that fails, fall back to the full string.
    """
    if "," in name:
        return name.split(",")[0].strip()
    return name


def geocode_location(client: OpenMeteoClient, name: str) -> dict:
    """Resolve a place string to coordinates via Open-Meteo geocoding.

    Returns a dict with name, admin1, country_code, timezone, latitude,
    longitude, elevation, population.

    Raises ValueError if no match is found.
    """
    # Try the cleaned query (no state suffix) first, then the full string.
    query = _clean_location_query(name)
    params = {
        "name": query,
        "count": 5,
        "language": "en",
        "format": "json",
    }

    data = client.get_json(GEOCODING_URL, params)
    results = data.get("results") or []

    if not results:
        raise ValueError(f"No location found for {name!r}")

    # v1: pick the first (best) result. Later we can rank by population.
    best = results[0]
    logger.info(
        "Geocoded %r -> %s, %s (%.4f, %.4f)",
        name, best.get("name"), best.get("admin1"),
        best.get("latitude"), best.get("longitude"),
    )

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
    }
