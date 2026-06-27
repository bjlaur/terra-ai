"""Tool executor — maps tool name to callable.

Note: OpenRouter server-side web_search (type: "openrouter:web_search")
is handled by OpenRouter, not routed through this executor. Only local
function tools are executed here.
"""

import json
import logging

logger = logging.getLogger("terraai")

# Only local function tools go here.
# OpenRouter server tools (like web_search) are executed server-side.
TOOL_FUNCTIONS = {}


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
        return handler(**arguments)
    except Exception as e:
        logger.error("Tool %r execution failed: %s", name, e)
        return f"Error: {e}"
