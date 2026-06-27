"""OpenAI-compatible tool schemas for TerraAI."""

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

AVAILABLE_TOOLS = [WEB_SEARCH_TOOL]
