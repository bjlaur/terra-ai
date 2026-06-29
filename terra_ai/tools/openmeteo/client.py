"""Shared HTTP client for Open-Meteo APIs.

Uses a synchronous httpx.Client to match the rest of TerraAI's provider
layer (which is also sync). Open-Meteo requires no API key.
"""

import logging
import time

import httpx

logger = logging.getLogger("terraai")

# Default base URLs for the Open-Meteo services we use.
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


class OpenMeteoClient:
    """Sync HTTP client for Open-Meteo APIs.

    No API key is required. We request US units (F/mph/inch) by default;
    callers set the unit params explicitly in their requests.
    """

    def __init__(self, timeout_s: float = 8.0):
        self.timeout_s = timeout_s

    def get_json(self, url: str, params: dict) -> dict:
        """GET a JSON response, raising on HTTP errors.

        Returns the parsed JSON dict.
        """
        start = time.time()
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            duration_ms = int((time.time() - start) * 1000)
            logger.error(
                "OpenMeteo HTTP error: url=%s duration_ms=%d error=%s",
                url, duration_ms, e,
            )
            raise

        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            "OpenMeteo request: url=%s duration_ms=%d",
            url, duration_ms,
        )
        return data
