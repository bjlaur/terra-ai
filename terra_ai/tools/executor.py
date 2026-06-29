"""Tool executor — maps tool name to callable.

Note: OpenRouter server-side web_search (type: "openrouter:web_search")
is handled by OpenRouter, not routed through this executor. Only local
function tools are executed here.
"""

import json
import logging

from terra_ai.tools.openmeteo.forecast import execute_weather_forecast
from terra_ai.tools.openmeteo.geocode_tool import execute_geocode

logger = logging.getLogger("terraai")

# Local function tools. OpenRouter server tools (like web_search) are
# executed server-side and never reach this dict.
TOOL_FUNCTIONS = {
    "weather_forecast": execute_weather_forecast,
    "geocode": execute_geocode,
}


def execute_tool(name: str, arguments: str | dict) -> str:
    """Execute a local tool by name and return its result as a string.

    *arguments* can be a dict (already parsed) or a JSON string
    (as returned by the OpenAI tool_calls response).
    """
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return f"Error: invalid JSON arguments for '{name}'"

    handler = TOOL_FUNCTIONS.get(name)
    if not handler:
        return f"Error: unknown tool '{name}'"

    try:
        result = handler(arguments)
        # ToolResult -> JSON string for the model.
        if hasattr(result, "to_dict"):
            return json.dumps(result.to_dict())
        return str(result)
    except Exception as e:
        logger.error("Tool %r execution failed: %s", name, e)
        return f"Error: {e}"
