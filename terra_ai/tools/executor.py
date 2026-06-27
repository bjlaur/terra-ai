"""Tool executor — maps tool name to callable."""

import json
import logging

from terra_ai.tools.web_search import web_search

logger = logging.getLogger("terraai")

TOOL_FUNCTIONS = {
    "web_search": web_search,
}


def execute_tool(name: str, arguments: str | dict) -> str:
    """Execute a tool by name and return its result as a string.

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
