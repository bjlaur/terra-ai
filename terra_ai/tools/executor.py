"""Tool executor — maps tool name to callable.

Note: OpenRouter server-side web_search (type: "openrouter:web_search")
is handled by OpenRouter, not routed through this executor. Only local
function tools are executed here.
"""

import json
import logging
import time

from terra_ai.tools.openmeteo.forecast import execute_weather_forecast
from terra_ai.tools.openmeteo.result import ToolResult
from terra_ai.errors import report_recoverable_error

logger = logging.getLogger("terraai")

# Local function tools. OpenRouter server tools (like web_search) are
# executed server-side and never reach this dict. weather_forecast geocodes
# internally, so there is no standalone geocode tool registered here.
TOOL_FUNCTIONS = {
    "weather_forecast": execute_weather_forecast,
}


def _failure(name: str, error: str) -> str:
    return json.dumps(
        ToolResult(
            ok=False,
            tool=name or "unknown",
            source="terra-ai",
            error=error,
        ).to_dict()
    )


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
            return _failure(name, f"Invalid JSON arguments for {name!r}.")

    if not isinstance(arguments, dict):
        return _failure(name, f"Arguments for {name!r} must be a JSON object.")

    if not isinstance(name, str) or not name.strip():
        return _failure("unknown", "Tool name must be a non-empty string.")

    handler = TOOL_FUNCTIONS.get(name)
    if not handler:
        return _failure(name, f"Unknown tool {name!r}.")

    try:
        tool_start = time.time()
        result = handler(arguments, noisy_callback=noisy_callback)
        tool_ms = int((time.time() - tool_start) * 1000)
        logger.info("Tool %r executed in %d ms", name, tool_ms)
        if not isinstance(result, ToolResult):
            raise TypeError(
                f"Tool {name!r} returned {type(result).__name__}, expected ToolResult"
            )
        return json.dumps(result.to_dict())
    except Exception as exc:
        report_recoverable_error(exc, f"tool {name!r} execution")
        return _failure(name, f"Tool execution failed: {exc}")
