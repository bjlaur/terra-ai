"""Deterministic external HTTP responses for fast tests.

These responses replace only the network transport. Production OpenRouter and
Open-Meteo request construction, tool execution, and response parsing remain in
the exercised path.
"""

import json

import httpx


def _place(name, admin1, latitude, longitude):
    return {
        "name": name,
        "admin1": admin1,
        "admin2": None,
        "country": "United States",
        "country_code": "US",
        "timezone": "America/Detroit",
        "latitude": latitude,
        "longitude": longitude,
        "elevation": 180.0,
        "population": 100000,
    }


PLACES = {
    "detroit": [_place("Detroit", "Michigan", 42.3314, -83.0458)],
    "chicago": [_place("Chicago", "Illinois", 41.8500, -87.6500)],
    "north branch": [
        _place("North Branch", "Minnesota", 45.5114, -92.9802),
        _place("North Branch", "Michigan", 43.2295, -83.1966),
    ],
}


class ScriptedServices:
    """httpx MockTransport handler with request capture."""

    def __init__(self):
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host = request.url.host
        if host == "openrouter.ai":
            return self._openrouter(request)
        if host == "geocoding-api.open-meteo.com":
            query = request.url.params.get("name", "").lower()
            return httpx.Response(200, json={"results": PLACES.get(query, [])})
        if host == "api.open-meteo.com":
            return httpx.Response(200, json=self._forecast(request))
        return httpx.Response(599, json={"error": f"unexpected test URL: {request.url}"})

    def _openrouter(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        messages = payload.get("messages", [])
        last = messages[-1] if messages else {}

        user_text = " ".join(
            str(message.get("content") or "")
            for message in messages
            if message.get("role") == "user"
        ).lower()
        if "simulate provider failure" in user_text:
            return httpx.Response(503, json={"error": "scripted provider failure"})

        concise_retry = any(
            message.get("role") == "system"
            and "response was too long" in str(message.get("content") or "").lower()
            for message in messages
        )

        usage = {}
        weather_source_request = (
            "web search" in user_text
            and "local weather tool" in user_text
            and ("weather" in user_text or "forecast" in user_text)
        )
        hybrid_weather_search = weather_source_request and (
            "use both" in user_text or "overread" in user_text
        )
        explicit_weather_search = weather_source_request and not hybrid_weather_search

        if last.get("role") == "tool":
            tool_content = str(last.get("content") or "")
            if '"ok": false' in tool_content.lower():
                message = {
                    "role": "assistant",
                    "content": "The weather tool failed cleanly.",
                }
            else:
                message = {
                    "role": "assistant",
                    "content": "Detroit weather forecast: 70°F and clear.",
                }
        elif hybrid_weather_search:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "weather-hybrid-1",
                        "type": "function",
                        "function": {
                            "name": "weather_forecast",
                            "arguments": json.dumps(
                                {"location": "Detroit, MI", "preset": "basic_forecast"}
                            ),
                        },
                    }
                ],
            }
            usage = {"server_tool_use": {"web_search_requests": 1}}
        elif explicit_weather_search:
            message = {
                "role": "assistant",
                "content": "External weather sources report current conditions.",
            }
            usage = {"server_tool_use": {"web_search_requests": 1}}
        elif concise_retry:
            message = {"role": "assistant", "content": "short rewritten response"}
        elif "force an oversized response" in user_text:
            message = {"role": "assistant", "content": "x" * 451}
        else:
            tools = payload.get("tools", [])
            weather_enabled = any(
                tool.get("function", {}).get("name") == "weather_forecast"
                for tool in tools
            )
            if ("weather" in user_text or "rain" in user_text) and weather_enabled:
                location = (
                    "Xyzzyville, ZZ" if "xyzzyville" in user_text else "Detroit, MI"
                )
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "weather-1",
                            "type": "function",
                            "function": {
                                "name": "weather_forecast",
                                "arguments": json.dumps(
                                    {"location": location, "preset": "current"}
                                ),
                            },
                        }
                    ],
                }
            elif "weather" in user_text or "rain" in user_text:
                message = {
                    "role": "assistant",
                    "content": "The local weather tool is disabled.",
                }
            elif "2+2" in user_text:
                message = {"role": "assistant", "content": "4"}
            elif "current" in user_text or "latest" in user_text:
                message = {
                    "role": "assistant",
                    "content": "Current information from scripted web search.",
                }
            else:
                message = {"role": "assistant", "content": "mocked AI response"}

        return httpx.Response(
            200,
            json={"choices": [{"message": message}], "usage": usage},
        )

    @staticmethod
    def _forecast(request: httpx.Request) -> dict:
        params = request.url.params
        response: dict = {}
        for block in ("current", "hourly", "daily"):
            variables = [v for v in params.get(block, "").split(",") if v]
            if not variables:
                continue
            if block == "current":
                values = {"time": "2026-07-18T12:00"}
                values.update({name: _weather_value(name) for name in variables})
            else:
                times = (
                    ["2026-07-18", "2026-07-19"]
                    if block == "daily"
                    else ["2026-07-18T12:00", "2026-07-18T13:00"]
                )
                values = {"time": times}
                values.update(
                    {name: [_weather_value(name), _weather_value(name)] for name in variables}
                )
            response[block] = values
        return response


def _weather_value(name: str):
    if name == "weather_code":
        return 0
    if name == "is_day":
        return 1
    if "temperature" in name:
        return 70.0
    if "wind" in name:
        return 8.0
    if "humidity" in name or "cloud" in name or "probability" in name:
        return 20
    if name in {"sunrise", "sunset"}:
        return "2026-07-18T20:00"
    return 0.0
