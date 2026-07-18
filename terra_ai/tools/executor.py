"""Tool executor — maps tool name to callable.

Note: OpenRouter server-side web_search (type: "openrouter:web_search")
is handled by OpenRouter, not routed through this executor. Only local
function tools are executed here.
"""

import json
import logging
import time

from terra_ai.tools.openmeteo.forecast import execute_weather_forecast

logger = logging.getLogger("terraai")

# Local function tools. OpenRouter server tools (like web_search) are
# executed server-side and never reach this dict. weather_forecast geocodes
# internally, so there is no standalone geocode tool registered here.
TOOL_FUNCTIONS = {
    "weather_forecast": execute_weather_forecast,
}


def execute_tool(name: str, arguments: str | dict, noisy_callback=None) -> str:
    """Execute a local tool by name and return its result as a string.

    *arguments* can be a dict (already parsed) or a JSON string
    (as returned by the OpenAI tool_calls response).
    *noisy_callback* is an optional callable(message: str) the tool can use
    to report what it's doing (for noisy mode).
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
        tool_start = time.time()
        result = handler(arguments, noisy_callback=noisy_callback)
        tool_ms = int((time.time() - tool_start) * 1000)
        logger.info("Tool %r executed in %d ms", name, tool_ms)
        # ToolResult -> JSON string for the model.
        if hasattr(result, "to_dict"):
            return json.dumps(result.to_dict())
        return str(result)
    except Exception as e:
        logger.error("Tool %r execution failed: %s", name, e)
        return f"Error: {e}"
