"""Unit tests for the OpenRouter server-side web-search schema.

Plugin-routed fast/real search coverage lives in ``test_plugin_e2e.py``.
"""

import json
from terra_ai.tools.schemas import AVAILABLE_TOOLS, OPENROUTER_WEB_SEARCH_TOOL


class TestToolSchema:
    """Test the tool schema structure (no network needed)."""

    def test_schema_type(self):
        """OpenRouter web search uses server_tool type."""
        assert OPENROUTER_WEB_SEARCH_TOOL["type"] == "openrouter:web_search"

    def test_schema_has_parameters(self):
        """OpenRouter web search has expected parameters."""
        params = OPENROUTER_WEB_SEARCH_TOOL["parameters"]
        assert "engine" in params
        assert "max_results" in params
        assert "max_total_results" in params
        assert "search_context_size" in params

    def test_available_tools_contains_web_search(self):
        """AVAILABLE_TOOLS includes the OpenRouter web search tool."""
        assert len(AVAILABLE_TOOLS) >= 1
        assert any(t.get("type") == "openrouter:web_search" for t in AVAILABLE_TOOLS)

    def test_schema_is_valid_json(self):
        """Tool schemas serialize to valid JSON."""
        for tool in AVAILABLE_TOOLS:
            serialized = json.dumps(tool)
            parsed = json.loads(serialized)
            assert parsed == tool
