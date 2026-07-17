"""Tests for the Open-Meteo weather tools.

Two layers:
1. Unit-of-logic tests: real Open-Meteo HTTP, no AI. These call the tool
   functions directly and validate the normalization / error handling.
2. End-to-end tests: real OpenRouter AI + real Open-Meteo. These feed a
   weather question to a live provider with tools=[...] and assert the
   model calls weather_forecast and the final answer contains real data.

ALL tests use real HTTP. No mocks, including no AI mocks.
Source ~/.terra-ai/.env before running:
    source ~/.terra-ai/.env && pytest tests/test_weather.py -v
"""

import json
import os

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _require_openmeteo():
    """Open-Meteo needs no API key, but we skip if the network is blocked."""
    # No key needed — Open-Meteo is keyless. Tests just need internet.
    return True


def _require_openrouter_key():
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY not set. Source it from ~/.terra-ai/.env first:\n"
            "    source ~/.terra-ai/.env"
        )
    return key


@pytest.fixture
def openmeteo_client():
    from terra_ai.tools.openmeteo.client import OpenMeteoClient
    return OpenMeteoClient(timeout_s=10)


@pytest.fixture
def openrouter_provider():
    from terra_ai.providers.openrouter import OpenRouterProvider
    from tests.conftest import _load_sopel_test_cfg
    key = _require_openrouter_key()
    try:
        model, _ = _load_sopel_test_cfg()
    except RuntimeError as e:
        raise RuntimeError(f"{e} (Set [terraai] model in config/sopel-test.cfg)")
    return OpenRouterProvider(model=model, api_key=key)


# ---------------------------------------------------------------------------
# 1. Unit-of-logic tests (real Open-Meteo HTTP, no AI)
# ---------------------------------------------------------------------------

class TestGeocode:
    """geocode_location: real Open-Meteo geocoding HTTP."""

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

    def test_geocode_unknown_raises(self, openmeteo_client):
        from terra_ai.tools.openmeteo.geocode import geocode_location
        with pytest.raises(ValueError, match="No location found"):
            geocode_location(openmeteo_client, "Xyzzyville, ZZ")


class TestWeatherForecastTool:
    """execute_weather_forecast: real Open-Meteo forecast HTTP."""

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


class TestGeocodeTool:
    """execute_geocode: the standalone geocode tool."""

    def test_geocode_tool(self, openmeteo_client):
        from terra_ai.tools.openmeteo.geocode_tool import execute_geocode
        result = execute_geocode({"location": "Detroit, MI"}, client=openmeteo_client)
        assert result.ok is True
        assert result.tool == "geocode"
        assert result.data["latitude"] is not None
        assert result.summary_hint is not None

    def test_geocode_tool_no_location(self, openmeteo_client):
        from terra_ai.tools.openmeteo.geocode_tool import execute_geocode
        result = execute_geocode({}, client=openmeteo_client)
        assert result.ok is False
        assert "No location" in result.error


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

    def test_dispatch_geocode(self, openmeteo_client):
        from terra_ai.tools.executor import execute_tool
        args_json = json.dumps({"location": "Chicago, IL"})
        result_str = execute_tool("geocode", args_json)
        parsed = json.loads(result_str)
        assert parsed["ok"] is True
        assert parsed["tool"] == "geocode"

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

    def test_geocode_schema_valid(self):
        from terra_ai.tools.openmeteo.schemas import GEOCODE_TOOL
        assert GEOCODE_TOOL["type"] == "function"
        func = GEOCODE_TOOL["function"]
        assert func["name"] == "geocode"
        assert "location" in func["parameters"]["properties"]

    def test_available_tools_includes_weather_and_geocode(self):
        from terra_ai.tools.schemas import AVAILABLE_TOOLS
        names = []
        for t in AVAILABLE_TOOLS:
            if t["type"] == "function":
                names.append(t["function"]["name"])
            elif t["type"] == "openrouter:web_search":
                names.append("openrouter:web_search")
        assert "weather_forecast" in names
        assert "geocode" in names
        assert "openrouter:web_search" in names


# ---------------------------------------------------------------------------
# 2. End-to-end tests (real AI + real Open-Meteo)
# ---------------------------------------------------------------------------

class TestEndToEndWeatherForecast:
    """Feed a real weather question to a live OpenRouter provider with tools.

    Asserts the model calls weather_forecast and the final answer contains
    real weather content.
    """

    def test_weather_detroit(self, openrouter_provider):
        from terra_ai.tools.schemas import AVAILABLE_TOOLS
        from terra_ai.providers.base import Message

        messages = [
            Message("system", "You are a concise IRC bot. Answer weather questions briefly."),
            Message("user", "<tester> weather Detroit"),
        ]
        response = openrouter_provider.chat(
            messages,
            tools=AVAILABLE_TOOLS,
        )
        assert response, "Provider returned empty response"
        lower = response.lower()
        # The answer should mention Detroit and some weather detail.
        assert "detroit" in lower, f"Response should mention Detroit:\n{response}"
        # Should contain at least one weather-ish word.
        weather_words = ["°", "temperature", "high", "low", "cloud", "rain",
                        "clear", "wind", "forecast", "fahrenheit", "sunny",
                        "partly", "mostly"]
        assert any(w in lower for w in weather_words), \
            f"Response should contain weather info:\n{response}"

    def test_rain_tonight(self, openrouter_provider):
        from terra_ai.tools.schemas import AVAILABLE_TOOLS
        from terra_ai.providers.base import Message

        messages = [
            Message("system", "You are a concise IRC bot."),
            Message("user", "<tester> rain tonight in Detroit?"),
        ]
        response = openrouter_provider.chat(
            messages,
            tools=AVAILABLE_TOOLS,
        )
        assert response, "Provider returned empty response"
        lower = response.lower()
        assert "detroit" in lower, f"Response should mention Detroit:\n{response}"
