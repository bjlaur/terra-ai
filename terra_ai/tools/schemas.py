"""Tool schemas for TerraAI.

Uses OpenRouter's built-in server-side web search tool.
OpenRouter handles the search execution server-side — the model decides
when to search and OpenRouter returns the results in the conversation.
"""

# OpenRouter server-side web search tool
# https://openrouter.ai/docs#web-search
OPENROUTER_WEB_SEARCH_TOOL = {
    "type": "openrouter:web_search",
    "parameters": {
        "engine": "auto",
        "max_results": 5,
        "max_total_results": 15,
        "search_context_size": "medium",
    },
}

from terra_ai.tools.openmeteo.schemas import (
    WEATHER_FORECAST_TOOL,
    GEOCODE_TOOL,
)

# Legacy local DuckDuckGo web_search — kept for backward compat in tests
# but NOT included in production requests.
WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current information. Use when you need "
            "up-to-date facts, weather, news, or any information beyond "
            "your training data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
            },
            "required": ["query"],
        },
    },
}

# Production uses OpenRouter server-side search + local Open-Meteo tools.
# weather_forecast is the first custom local tool; more will be added.
# geocode is a standalone tool for resolving place names to coordinates.
AVAILABLE_TOOLS = [
    OPENROUTER_WEB_SEARCH_TOOL,
    WEATHER_FORECAST_TOOL,
    GEOCODE_TOOL,
]
