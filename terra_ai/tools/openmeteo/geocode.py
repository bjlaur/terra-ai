"""Geocoding for Open-Meteo tools.

No saved user location in the database — the model knows location from the
user's message. The tool's `location` param is passed straight from the model
to the geocoder. If no location is provided, the tool returns a clean error
asking the model to prompt the user.
"""

import logging

from terra_ai.tools.openmeteo.client import (
    GEOCODING_URL,
    OpenMeteoClient,
    OpenMeteoResponseError,
)

logger = logging.getLogger("terraai")

# US state abbreviations -> full names, for matching the parsed qualifier.
_US_STATE_ABBR = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}
# Canadian province abbreviations -> full names.
_CA_PROVINCE_ABBR = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
    "NB": "New Brunswick", "NL": "Newfoundland and Labrador", "NS": "Nova Scotia",
    "NT": "Northwest Territories", "NU": "Nunavut", "ON": "Ontario",
    "PE": "Prince Edward Island", "QC": "Quebec", "SK": "Saskatchewan",
    "YT": "Yukon",
}


def _parse_admin1(name: str) -> str | None:
    """Extract a normalized administrative region (state/province) from a
    location string like 'North Branch, MI' or 'London, Ontario, Canada'.

    Returns the full canonical name (e.g. 'Michigan', 'Ontario') or None if
    no recognizable qualifier is present.
    """
    if "," not in name:
        return None
    qualifiers = [q.strip() for q in name.split(",")[1:]]
    if not qualifiers:
        return None
    qual = qualifiers[0]
    # Two-letter abbreviation?
    if len(qual) == 2 and qual.isalpha():
        up = qual.upper()
        if up in _US_STATE_ABBR:
            return _US_STATE_ABBR[up]
        if up in _CA_PROVINCE_ABBR:
            return _CA_PROVINCE_ABBR[up]
    # Full name match (case-insensitive) against known regions.
    low = qual.lower()
    for full in list(_US_STATE_ABBR.values()) + list(_CA_PROVINCE_ABBR.values()):
        if full.lower() == low:
            return full
    # Otherwise return the qualifier as-is so callers can still compare.
    return qual


def _clean_location_query(name: str) -> str:
    """Build the API query string from a place name.

    Open-Meteo's geocoding API returns zero results for ANY comma form
    ('Detroit, MI', 'North Branch, Michigan', 'London, Ontario, Canada' all
    return []). So we strip everything after the first comma for the actual
    API call and rely on the qualifier only for client-side re-ranking
    (see geocode_location). The bare name ('North Branch') works fine.
    """
    if "," in name:
        return name.split(",")[0].strip()
    return name


def _rank_results(results: list, requested_admin1: str | None) -> list:
    """Re-rank Open-Meteo results so a result whose admin1 matches the
    requested state/province is preferred. Open-Meteo ranks by population and
    relevance, which can put the wrong state first for same-named cities
    (e.g. North Branch, MN above North Branch, MI). When no qualifier was
    requested, or nothing matches, the original ranking is preserved.
    """
    if not requested_admin1 or not results:
        return results
    req = requested_admin1.lower()
    matched = [r for r in results if (r.get("admin1") or "").lower() == req]
    rest = [r for r in results if (r.get("admin1") or "").lower() != req]
    return matched + rest


def geocode_location(client: OpenMeteoClient, name: str) -> dict:
    """Resolve a place string to coordinates via Open-Meteo geocoding.

    Returns a dict with name, admin1, country_code, timezone, latitude,
    longitude, elevation, population.

    The model is instructed to pass qualifiers as full names (e.g.
    'North Branch, Michigan'), but Open-Meteo rejects comma forms, so we query
    the bare name and re-rank by the parsed state to disambiguate same-named
    cities across states.

    Raises ValueError if no match is found.
    """
    requested_admin1 = _parse_admin1(name)
    query = _clean_location_query(name)
    params = {
        "name": query,
        "count": 10,
        "language": "en",
        "format": "json",
    }

    data = client.get_json(GEOCODING_URL, params)
    results = data.get("results") or []

    if not isinstance(results, list):
        raise OpenMeteoResponseError(
            "Open-Meteo geocoding response field 'results' must be a list"
        )
    if any(not isinstance(result, dict) for result in results):
        raise OpenMeteoResponseError(
            "Open-Meteo geocoding results must contain only objects"
        )

    if not results:
        raise ValueError(f"No location found for {name!r}")

    ranked = _rank_results(results, requested_admin1)
    best = ranked[0]
    for coordinate in ("latitude", "longitude"):
        if isinstance(best.get(coordinate), bool) or not isinstance(
            best.get(coordinate), (int, float)
        ):
            raise OpenMeteoResponseError(
                f"Open-Meteo geocoding result has no numeric {coordinate}"
            )
    if requested_admin1 and best.get("admin1", "").lower() != requested_admin1.lower():
        logger.warning(
            "Geocode: requested %s but no result matched; fell back to %s, %s",
            requested_admin1, best.get("name"), best.get("admin1"),
        )
    logger.debug(
        "Geocoded %r (requested admin1=%r) -> %s, %s (%.4f, %.4f)",
        name, requested_admin1, best.get("name"), best.get("admin1"),
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
