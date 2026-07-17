"""OpenRouter provider for TerraAI."""

import json
import logging
import os

import httpx

from terra_ai.providers.base import AIProvider, Message
from terra_ai.tools.executor import execute_tool

logger = logging.getLogger("terraai")

# Cap on tool-call round-trips per chat() call. Prevents infinite loops if
# the model keeps requesting tools without converging on a final answer.
MAX_TOOL_ROUNDS = 3

# Models that do NOT support reasoning controls via chat-completions.
# Sending reasoning fields to these models causes 422 errors or silent ignore.
# TerraAI is model-agnostic: add a model here only when you have verified it
# rejects reasoning controls (unknown models fall through to None below).
_NO_REASONING_MODELS = {
    "google/gemini-2.0-flash-001",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
}

# Gemini 2.5+: effort → thinking budget (max_tokens).
_GEMINI_25_BUDGETS = {
    "low": 1024,
    "medium": 4096,
    "high": 8192,
    "xhigh": 16384,
    "max": 24576,
}


def _reasoning_for_model(model: str, effort: str) -> dict | None:
    """Build the reasoning config for an OpenRouter chat-completions request.

    Returns None if the model does not support reasoning controls.
    Gating by model prevents 422 errors from unsupported providers.
    """
    effort = effort.lower()

    if model in _NO_REASONING_MODELS:
        return None

    if model.startswith("google/gemini-2.5"):
        budgets = _GEMINI_25_BUDGETS
        return {"max_tokens": budgets.get(effort, 4096), "exclude": True}

    if model.startswith("anthropic/"):
        return {"enabled": True, "effort": effort, "exclude": True}

    if model.startswith("openai/o") or model.startswith("openai/gpt-5"):
        return {"effort": effort, "exclude": True}

    return None


class OpenRouterProvider(AIProvider):
    """OpenRouter AI provider.

    Uses OpenAI-compatible /v1/chat/completions endpoint.
    Get an API key at https://openrouter.ai/keys

    Web search uses OpenRouter's built-in server-side web search tool
    (type: "openrouter:web_search"). OpenRouter handles execution — no
    local tool-call loop is needed for search.
    """

    def __init__(self, model: str, api_key: str | None = None,
                 base_url: str = "https://openrouter.ai/api/v1",
                 timeout: int = 30):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = int(timeout)

    @property
    def name(self) -> str:
        return "openrouter"

    def chat(self, messages: list[Message], system_prompt: str | None = None,
             effort: str = "high", tools: list[dict] | None = None,
             max_tool_rounds: int = MAX_TOOL_ROUNDS,
             noisy_callback=None) -> str:
        """Send messages and get a complete response.

        If the model returns tool_calls, execute them locally and feed the
        results back, looping until the model gives a final text response
        or max_tool_rounds is reached.

        Args:
            messages: List of Message objects.
            system_prompt: Optional system prompt prepended as a system message.
            effort: Effort level ('low', 'medium', 'high', 'xhigh', 'max').
            tools: Local function-tool schemas to include alongside the
                server-side web_search tool.
            max_tool_rounds: Max tool-call round-trips before giving up.
            noisy_callback: Optional callable(message: str) called at each
                step so the caller can show progress (e.g. "Thinking...",
                "Geocoding Detroit...").

        Returns:
            The AI's response text.
        """
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            # OpenRouter app attribution
            "HTTP-Referer": "https://terra-ai.local",
            "X-OpenRouter-Title": "TerraAI",
        }

        payload_messages: list[dict] = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        payload_messages.extend(m.to_dict() for m in messages)

        payload = {
            "model": self._model,
            "messages": payload_messages,
        }

        # Add reasoning config if applicable
        reasoning = _reasoning_for_model(self._model, effort)
        if reasoning:
            payload["reasoning"] = reasoning
            logger.info("OpenRouter chat: applying reasoning=%s", reasoning)
        else:
            logger.info("OpenRouter chat: no reasoning config for model=%s", self._model)

        # Build tools list: always include server-side web_search, plus any
        # local function tools the caller passed in.
        request_tools = [
            {
                "type": "openrouter:web_search",
                "parameters": {
                    "engine": "auto",
                    "max_results": 5,
                    "max_total_results": 15,
                    "search_context_size": "medium",
                },
            }
        ]
        if tools:
            request_tools.extend(tools)
        payload["tools"] = request_tools

        logger.info("OpenRouter chat: model=%s tools=%d", self._model, len(request_tools))

        with httpx.Client(timeout=self._timeout) as client:
            for round_idx in range(max_tool_rounds + 1):
                # Notify caller: waiting for AI response.
                logger.info("OpenRouter chat: round=%d — waiting on API response", round_idx)
                if noisy_callback:
                    noisy_callback("Thinking...")

                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                # Log server-side tool usage if available.
                # OpenRouter returns this under `server_tool_use_details` (note
                # the _details suffix) on some responses — check both names so
                # older and newer response shapes both surface the notice.
                usage = data.get("usage") or {}
                server_tool_use = (
                    usage.get("server_tool_use_details")
                    or usage.get("server_tool_use")
                    or {}
                )
                if server_tool_use.get("web_search_requests"):
                    logger.info(
                        "OpenRouter web_search: requests=%d",
                        server_tool_use["web_search_requests"],
                    )
                    if noisy_callback:
                        noisy_callback("Searching web...")

                message = data["choices"][0]["message"]
                tool_calls = message.get("tool_calls")

                if not tool_calls:
                    # Final text answer — done.
                    content = message.get("content")
                    logger.info(
                        "OpenRouter final: content_type=%s content_len=%s",
                        type(content).__name__, len(content) if content else 0,
                    )
                    return content or ""

                # Has tool calls — execute them and feed results back.
                logger.info(
                    "OpenRouter tool_calls: round=%d count=%d — executing tools",
                    round_idx, len(tool_calls),
                )
                # Append the assistant message with tool_calls as-is.
                payload_messages.append(message)

                for call in tool_calls:
                    call_id = call.get("id", "")
                    function = call.get("function") or {}
                    name = function.get("name", "")
                    raw_args = function.get("arguments", "{}")
                    # Log the argument type/value — a None/missing arguments
                    # string is a common source of downstream .replace() errors.
                    logger.info(
                        "Tool call: id=%s name=%s args_type=%s args=%r",
                        call_id, name, type(raw_args).__name__, raw_args,
                    )

                    # Forward noisy_callback so the tool can report what it does.
                    result_str = execute_tool(name, raw_args,
                                              noisy_callback=noisy_callback)

                    payload_messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": result_str,
                    })

            # Fell off the loop — last attempt, return whatever we have.
            logger.warning("OpenRouter: hit max_tool_rounds=%d", max_tool_rounds)
            return message.get("content") or ""

    def is_available(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0
