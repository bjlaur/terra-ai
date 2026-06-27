"""OpenRouter provider for TerraAI."""

import logging
import os

import httpx

from terra_ai.providers.base import AIProvider, Message

logger = logging.getLogger("terraai")

# Models that do NOT support reasoning controls via chat-completions.
# Sending reasoning fields to these models causes 422 errors or silent ignore.
# Note: owl-alpha is experimental — Claude Code path may translate effort
# through Anthropic compat layer even if chat-completions metadata doesn't
# advertise it. User may remove owl-alpha from this set to experiment.
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
    """

    def __init__(self, model: str = "openrouter/owl-alpha", api_key: str | None = None,
                 base_url: str = "https://openrouter.ai/api/v1",
                 timeout: int = 30):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "openrouter"

    def chat(self, messages: list[Message], system_prompt: str | None = None,
             effort: str = "high", tools: list[dict] | None = None,
             max_tool_rounds: int = 5) -> str:
        """Send messages and get a complete response.

        Args:
            messages: List of Message objects.
            system_prompt: Optional system prompt prepended as a system message.
            effort: Effort level ('low', 'medium', 'high', 'xhigh', 'max').
            tools: Optional list of OpenAI-compatible tool schemas.
            max_tool_rounds: Max tool-call ↔ execute rounds before forcing a text reply.

        Returns:
            The AI's response text.
        """
        from terra_ai.tools.executor import execute_tool

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        payload_messages.extend(m.to_dict() for m in messages)

        for _ in range(max_tool_rounds + 1):
            payload = {
                "model": self._model,
                "messages": payload_messages,
            }

            reasoning = _reasoning_for_model(self._model, effort)
            if reasoning:
                payload["reasoning"] = reasoning

            if tools:
                payload["tools"] = tools

            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            choice = data["choices"][0]["message"]

            # If the model wants to call tools, execute them and continue.
            tool_calls = choice.get("tool_calls")
            if tool_calls:
                # Append the assistant's tool_calls message to the conversation.
                payload_messages.append(choice)

                # Execute each tool call and append results.
                for tc in tool_calls:
                    fn = tc["function"]
                    logger.info(
                        "Tool call: %s(%s)", fn["name"], fn.get("arguments", "")
                    )
                    result = execute_tool(fn["name"], fn.get("arguments", "{}"))
                    payload_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })
                # Loop — call the API again with the tool results appended.
                continue

            # No tool calls — return the text content.
            return choice.get("content") or ""

        # Safety: if we exhausted rounds, return whatever the last response was.
        logger.warning("Exceeded max_tool_rounds (%d)", max_tool_rounds)
        return choice.get("content") or "Error: too many tool rounds"

    def is_available(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0
