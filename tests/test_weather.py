"""Deterministic component tests for Open-Meteo weather behavior.

HTTP is replaced at the transport boundary, while production geocoding,
forecast request construction, normalization, and tool execution remain real.
Plugin-routed fast/real weather coverage lives in ``test_plugin_e2e.py``.
"""

import json
import pytest


pytestmark = pytest.mark.usefixtures("scripted_services")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def openmeteo_client():
    from terra_ai.tools.openmeteo.client import OpenMeteoClient
    return OpenMeteoClient(timeout_s=10)


# ---------------------------------------------------------------------------
# Component tests (scripted Open-Meteo HTTP, no AI)
# ---------------------------------------------------------------------------

class TestGeocode:
    """Geocoding request, selection, and normalization behavior."""

    def test_geocode_detroit(self, openmeteo_client):
        from terra_ai.tools.openmeteo.geocode import geocode_location
        result = geocode_location(openmeteo_client, "Detroit, MI")
        assert result["name"] == "Detroit"
        assert result["country_code"] == "US"
        assert abs(result["latitude"] - 42.33) < 0.1
        assert abs(result["longitude"] - (-83.05)) < 0.1

    def test_geocode_chicago(self, openmeteo_client):
        from terra_ai.tools.openmeteo.geocode import geocode_location
        result = geocode_location(openmeteo_client, "Chicago, IL")
        assert result["name"] == "Chicago"
        assert result["country_code"] == "US"
        assert abs(result["latitude"] - 41.88) < 0.1

    def test_geocode_north_branch_mi(self, openmeteo_client):
        """North Branch, MI must resolve to MICHIGAN, not Minnesota.

        Open-Meteo ranks North Branch, MN above North Branch, MI by default,
        and _clean_location_query strips the ', MI' state hint before the
        query, so the geocoder never sees that Michigan was requested. This
        test captures that bug: the requested state should disambiguate.
        """
        from terra_ai.tools.openmeteo.geocode import geocode_location
        result = geocode_location(openmeteo_client, "North Branch, MI")
        # Michigan, not Minnesota.
        assert result["admin1"] == "Michigan", \
            f"Expected Michigan, got {result['admin1']!r} ({result['name']})"
        assert result["country_code"] == "US"
        # North Branch, MI is near (43.23, -83.20).
        assert abs(result["latitude"] - 43.23) < 0.1
        assert abs(result["longitude"] - (-83.20)) < 0.1

    def test_geocode_unknown_raises(self, openmeteo_client):
        from terra_ai.tools.openmeteo.geocode import geocode_location
        with pytest.raises(ValueError, match="No location found"):
            geocode_location(openmeteo_client, "Xyzzyville, ZZ")


class TestWeatherForecastTool:
    """Forecast request, normalization, and error behavior."""

    def test_basic_forecast_detroit(self, openmeteo_client):
        from terra_ai.tools.openmeteo.forecast import execute_weather_forecast
        result = execute_weather_forecast(
            {"location": "Detroit, MI", "preset": "basic_forecast"},
            client=openmeteo_client,
        )
        assert result.ok is True
        assert result.tool == "weather_forecast"
        assert result.source == "open-meteo"
        data = result.data
        assert data is not None
        assert data["location"]["name"] == "Detroit"
        assert "current" in data
        assert "hourly" in data
        assert "daily" in data
        assert data["units"]["temperature"] == "°F"

    def test_current_preset(self, openmeteo_client):
        from terra_ai.tools.openmeteo.forecast import execute_weather_forecast
        result = execute_weather_forecast(
            {"location": "Chicago, IL", "preset": "current"},
            client=openmeteo_client,
        )
        assert result.ok is True
        data = result.data
        assert "current" in data
        # current preset should not include hourly/daily
        assert "hourly" not in data
        assert "daily" not in data
        assert "temperature_f" in data["current"]
        assert "weather_description" in data["current"]

    def test_rain_preset(self, openmeteo_client):
        from terra_ai.tools.openmeteo.forecast import execute_weather_forecast
        result = execute_weather_forecast(
            {"location": "Detroit, MI", "preset": "rain"},
            client=openmeteo_client,
        )
        assert result.ok is True
        data = result.data
        # Rain preset should include precip_probability in hourly
        assert len(data["hourly"]) > 0
        assert "precip_probability_percent" in data["hourly"][0]

    def test_no_location_returns_error(self, openmeteo_client):
        from terra_ai.tools.openmeteo.forecast import execute_weather_forecast
        result = execute_weather_forecast({}, client=openmeteo_client)
        assert result.ok is False
        assert "No location" in result.error
        assert result.summary_hint is not None

    def test_unknown_location_returns_error(self, openmeteo_client):
        from terra_ai.tools.openmeteo.forecast import execute_weather_forecast
        result = execute_weather_forecast(
            {"location": "Xyzzyville, ZZ", "preset": "basic_forecast"},
            client=openmeteo_client,
        )
        assert result.ok is False
        assert "not found" in result.error.lower() or "No location" in result.error

    def test_default_preset_is_basic_forecast(self, openmeteo_client):
        from terra_ai.tools.openmeteo.forecast import execute_weather_forecast
        result = execute_weather_forecast(
            {"location": "Detroit, MI"},
            client=openmeteo_client,
        )
        assert result.ok is True
        assert result.data["preset"] == "basic_forecast"

    def test_full_debug_preset(self, openmeteo_client):
        from terra_ai.tools.openmeteo.forecast import execute_weather_forecast
        result = execute_weather_forecast(
            {"location": "Detroit, MI", "preset": "full_debug"},
            client=openmeteo_client,
        )
        assert result.ok is True
        data = result.data
        # full_debug should return a large variable set
        assert "hourly" in data
        assert len(data["hourly"]) > 0
        # Should include niche variables like cape, soil_temperature, etc.
        hour = data["hourly"][0]
        assert "cape" in hour or "soil_temperature_0cm" in hour


class TestExecutor:
    """execute_tool: the name -> callable dispatcher."""

    def test_dispatch_weather_forecast(self, openmeteo_client):
        from terra_ai.tools.executor import execute_tool
        # Pass a JSON string (as the model returns in tool_calls.arguments).
        args_json = json.dumps({"location": "Detroit, MI", "preset": "current"})
        result_str = execute_tool("weather_forecast", args_json)
        # Should return a JSON-serialized ToolResult
        parsed = json.loads(result_str)
        assert parsed["ok"] is True
        assert parsed["tool"] == "weather_forecast"

    def test_dispatch_unknown_tool(self):
        from terra_ai.tools.executor import execute_tool
        result_str = execute_tool("nonexistent_tool", '{"query": "x"}')
        assert "unknown tool" in result_str.lower()

    def test_dispatch_invalid_json(self):
        from terra_ai.tools.executor import execute_tool
        result_str = execute_tool("weather_forecast", "not valid json")
        assert "invalid json" in result_str.lower()


class TestSchemas:
    """Tool schema structure validation."""

    def test_weather_forecast_schema_valid(self):
        from terra_ai.tools.openmeteo.schemas import WEATHER_FORECAST_TOOL
        assert WEATHER_FORECAST_TOOL["type"] == "function"
        func = WEATHER_FORECAST_TOOL["function"]
        assert func["name"] == "weather_forecast"
        assert "parameters" in func
        assert "preset" in func["parameters"]["properties"]

    def test_available_tools_includes_weather(self):
        from terra_ai.tools.schemas import AVAILABLE_TOOLS
        names = []
        for t in AVAILABLE_TOOLS:
            if t["type"] == "function":
                names.append(t["function"]["name"])
            elif t["type"] == "openrouter:web_search":
                names.append("openrouter:web_search")
        assert "weather_forecast" in names
        assert "openrouter:web_search" in names
        # geocode is NOT a standalone tool — weather_forecast geocodes internally.
        assert "geocode" not in names
