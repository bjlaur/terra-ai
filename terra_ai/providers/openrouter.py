"""OpenRouter provider for TerraAI."""

import json
import logging
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from terra_ai.errors import report_recoverable_error
from terra_ai.logging_config import trace_openrouter
from terra_ai.providers.base import AIProvider, Message, ProviderCapabilities
from terra_ai.providers.pacing import RequestPacer
from terra_ai.tools.executor import execute_tool

logger = logging.getLogger("terraai")

TRACE_RESPONSE_HEADERS = (
    "Retry-After",
    "RateLimit-Limit",
    "RateLimit-Remaining",
    "RateLimit-Reset",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
    "X-Generation-Id",
)

# Cap on tool-call round-trips per chat() call. Prevents infinite loops if
# the model keeps requesting tools without converging on a final answer.
MAX_TOOL_ROUNDS = 3
MAX_TRANSIENT_RETRIES = 2
TRANSIENT_HTTP_STATUSES = frozenset({429, 503})

OPENROUTER_WEB_SEARCH_TOOL = {
    "type": "openrouter:web_search",
    "parameters": {
        "engine": "auto",
        "max_results": 5,
        "max_total_results": 15,
        "search_context_size": "medium",
    },
}


class OpenRouterError(RuntimeError):
    """Base error for contextual OpenRouter failures."""


class OpenRouterTransportError(OpenRouterError):
    """The OpenRouter HTTP request failed."""


class OpenRouterResponseError(OpenRouterError):
    """OpenRouter returned a response that cannot satisfy the chat contract."""


class OpenRouterToolRoundLimitError(OpenRouterError):
    """The model requested more local tool rounds than configured."""


def _response_message(data: object, round_idx: int) -> dict:
    """Validate and return one OpenRouter assistant message."""
    if not isinstance(data, dict):
        raise OpenRouterResponseError(
            f"OpenRouter round {round_idx} returned {type(data).__name__}, expected an object"
        )
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterResponseError(
            f"OpenRouter round {round_idx} response has no choices"
        )
    first = choices[0]
    if not isinstance(first, dict):
        raise OpenRouterResponseError(
            f"OpenRouter round {round_idx} first choice must be an object"
        )
    message = first.get("message")
    if not isinstance(message, dict):
        raise OpenRouterResponseError(
            f"OpenRouter round {round_idx} first choice has no message object"
        )
    return message


def _validated_tool_call(call: object, round_idx: int, call_idx: int) -> tuple[str, str, str | dict]:
    if not isinstance(call, dict):
        raise OpenRouterResponseError(
            f"OpenRouter round {round_idx} tool call {call_idx} must be an object"
        )
    call_id = call.get("id")
    if not isinstance(call_id, str) or not call_id:
        raise OpenRouterResponseError(
            f"OpenRouter round {round_idx} tool call {call_idx} has no string id"
        )
    function = call.get("function")
    if not isinstance(function, dict):
        raise OpenRouterResponseError(
            f"OpenRouter round {round_idx} tool call {call_idx} has no function object"
        )
    name = function.get("name")
    if not isinstance(name, str) or not name:
        raise OpenRouterResponseError(
            f"OpenRouter round {round_idx} tool call {call_idx} has no function name"
        )
    arguments = function.get("arguments", "{}")
    if not isinstance(arguments, (str, dict)):
        raise OpenRouterResponseError(
            f"OpenRouter round {round_idx} tool call {call_idx} arguments must be a JSON string or object"
        )
    return call_id, name, arguments


def _server_tool_usage(data: dict, round_idx: int) -> dict:
    """Return optional server-tool metadata without invalidating a good answer."""
    try:
        usage = data.get("usage")
        if usage is None:
            usage = {}
        if not isinstance(usage, dict):
            raise OpenRouterResponseError(
                f"OpenRouter round {round_idx} usage must be an object"
            )
        server_tool_use = usage.get("server_tool_use_details")
        if server_tool_use is None:
            server_tool_use = usage.get("server_tool_use")
        if server_tool_use is None:
            server_tool_use = {}
        if not isinstance(server_tool_use, dict):
            raise OpenRouterResponseError(
                f"OpenRouter round {round_idx} server tool usage must be an object"
            )
        return server_tool_use
    except OpenRouterResponseError as exc:
        report_recoverable_error(exc, "OpenRouter server-tool usage metadata")
        return {}

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


def _safe_response_headers(response: httpx.Response) -> dict[str, str]:
    """Return only explicitly allowlisted, non-secret response headers."""
    selected = {}
    for name in TRACE_RESPONSE_HEADERS:
        value = response.headers.get(name)
        if isinstance(value, str):
            selected[name] = value
    return selected


def _trace_safe_response_headers(response: httpx.Response) -> None:
    """Trace allowlisted response headers when the trace logger is configured."""
    selected = _safe_response_headers(response)
    if selected:
        trace_openrouter(
            "response_headers=%s",
            json.dumps(selected, ensure_ascii=False, separators=(",", ":")),
        )


def _safe_error_metadata(response: httpx.Response) -> dict[str, str | int]:
    """Return allowlisted OpenRouter error metadata without leaking payloads."""
    try:
        data = response.json()
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    error = data.get("error")
    if not isinstance(error, dict):
        return {}
    metadata = error.get("metadata")
    if not isinstance(metadata, dict):
        return {}

    selected: dict[str, str | int] = {}
    for name in ("error_type", "provider_code"):
        value = metadata.get(name)
        if isinstance(value, bool):
            continue
        if isinstance(value, (str, int)):
            selected[name] = value
    return selected


def _retry_after_delay_seconds(
    response: httpx.Response,
    *,
    now: datetime | None = None,
) -> float | None:
    """Return a valid Retry-After delay in seconds, if one was supplied."""
    value = response.headers.get("Retry-After")
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None

    try:
        delay = float(value)
    except ValueError:
        delay = None
    if delay is not None:
        if math.isfinite(delay) and delay >= 0:
            return delay
        return None

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_at.tzinfo is None:
        return None

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return max(
        0.0,
        (retry_at.astimezone(timezone.utc) - current.astimezone(timezone.utc))
        .total_seconds(),
    )


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
                 timeout: int = 30,
                 request_pacer: RequestPacer | None = None):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = int(timeout)
        self._request_pacer = request_pacer or RequestPacer()

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(local_tools=True, native_search=True)

    @property
    def configured(self) -> bool:
        return bool(self._model and self._api_key)

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
        if isinstance(max_tool_rounds, bool) or not isinstance(max_tool_rounds, int):
            raise ValueError("max_tool_rounds must be an integer")
        if max_tool_rounds < 0:
            raise ValueError("max_tool_rounds must not be negative")

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
            logger.debug("OpenRouter chat: applying reasoning=%s", reasoning)
        else:
            logger.debug("OpenRouter chat: no reasoning config for model=%s", self._model)

        # Build tools list: always include server-side web_search, plus any
        # local function tools the caller passed in.
        request_tools = [OPENROUTER_WEB_SEARCH_TOOL]
        if tools:
            request_tools.extend(tools)
        payload["tools"] = request_tools

        logger.debug("OpenRouter chat: model=%s tools=%d", self._model, len(request_tools))

        with httpx.Client(timeout=self._timeout) as client:
            tool_rounds = 0
            round_idx = 0
            while True:
                # Notify caller: waiting for AI response.
                logger.debug("OpenRouter chat: round=%d — waiting on API response", round_idx)
                if noisy_callback:
                    noisy_callback("Thinking...")

                response = None
                for retry_idx in range(MAX_TRANSIENT_RETRIES + 1):
                    waited = self._request_pacer.wait()
                    if waited:
                        logger.debug(
                            "OpenRouter request pacing: round=%d waited_ms=%d "
                            "interval_seconds=%.3f",
                            round_idx,
                            int(waited * 1000),
                            self._request_pacer.interval,
                        )

                    api_start = time.monotonic()
                    try:
                        trace_openrouter(
                            "request_json=%s",
                            json.dumps(
                                payload,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        )
                        response = client.post(url, json=payload, headers=headers)
                        _trace_safe_response_headers(response)
                        trace_openrouter("response_body=%s", response.text)
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        status = exc.response.status_code
                        if (
                            status in TRANSIENT_HTTP_STATUSES
                            and self._request_pacer.enabled
                            and retry_idx < MAX_TRANSIENT_RETRIES
                        ):
                            retry_number = retry_idx + 1
                            retry_after = _retry_after_delay_seconds(exc.response)
                            retry_delay = max(
                                self._request_pacer.interval,
                                retry_after if retry_after is not None else 0.0,
                            )
                            self._request_pacer.defer_for(retry_delay)
                            reason = exc.response.reason_phrase or "HTTP error"
                            logger.warning(
                                "OpenRouter transient failure: round=%d status=%d "
                                "retry=%d/%d delay_seconds=%.3f "
                                "retry_after_seconds=%s",
                                round_idx,
                                status,
                                retry_number,
                                MAX_TRANSIENT_RETRIES,
                                retry_delay,
                                (
                                    f"{retry_after:.3f}"
                                    if retry_after is not None
                                    else "none"
                                ),
                            )
                            if noisy_callback:
                                noisy_callback(
                                    f"OpenRouter returned {status} {reason}. "
                                    f"Retrying in {retry_delay:.1f} seconds "
                                    f"({retry_number}/{MAX_TRANSIENT_RETRIES})..."
                                )
                            continue

                        safe_headers = _safe_response_headers(exc.response)
                        safe_metadata = _safe_error_metadata(exc.response)
                        error_context = ""
                        if safe_headers:
                            error_context += (
                                "; response_headers="
                                + json.dumps(
                                    safe_headers,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                )
                            )
                        if safe_metadata:
                            error_context += (
                                "; error_metadata="
                                + json.dumps(
                                    safe_metadata,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                )
                            )
                        raise OpenRouterTransportError(
                            f"OpenRouter request failed in round {round_idx} "
                            f"after {retry_idx + 1} attempt(s): "
                            f"{exc}{error_context}"
                        ) from exc
                    except httpx.HTTPError as exc:
                        raise OpenRouterTransportError(
                            f"OpenRouter request failed in round {round_idx}: {exc}"
                        ) from exc

                    api_ms = int((time.monotonic() - api_start) * 1000)
                    break

                if response is None:
                    raise OpenRouterTransportError(
                        f"OpenRouter request failed in round {round_idx} without a response"
                    )
                try:
                    data = response.json()
                except ValueError as exc:
                    raise OpenRouterResponseError(
                        f"OpenRouter round {round_idx} returned invalid JSON: {exc}"
                    ) from exc
                logger.debug(
                    "OpenRouter chat: round=%d API call took %d ms",
                    round_idx, api_ms,
                )
                message = _response_message(data, round_idx)

                # Log server-side tool usage if available.
                # OpenRouter returns this under `server_tool_use_details` (note
                # the _details suffix) on some responses — check both names so
                # older and newer response shapes both surface the notice.
                server_tool_use = _server_tool_usage(data, round_idx)
                if server_tool_use.get("web_search_requests"):
                    logger.debug(
                        "OpenRouter web_search: requests=%d",
                        server_tool_use["web_search_requests"],
                    )
                    if noisy_callback:
                        noisy_callback("Searching web...")

                tool_calls = message.get("tool_calls")

                if not tool_calls:
                    # Final text answer — done.
                    content = message.get("content")
                    logger.debug(
                        "OpenRouter final: content_type=%s content_len=%s",
                        type(content).__name__, len(content) if content else 0,
                    )
                    if not isinstance(content, str) or not content.strip():
                        raise OpenRouterResponseError(
                            f"OpenRouter round {round_idx} returned no text or tool calls"
                        )
                    return content

                if not isinstance(tool_calls, list):
                    raise OpenRouterResponseError(
                        f"OpenRouter round {round_idx} tool_calls must be a list"
                    )
                if tool_rounds >= max_tool_rounds:
                    raise OpenRouterToolRoundLimitError(
                        f"OpenRouter requested another tool round after the configured limit of {max_tool_rounds}"
                    )

                # Has tool calls — execute them and feed results back.
                logger.debug(
                    "OpenRouter tool_calls: round=%d count=%d — executing tools",
                    round_idx, len(tool_calls),
                )
                # Append the assistant message with tool_calls as-is.
                payload_messages.append(message)

                for call_idx, call in enumerate(tool_calls):
                    call_id, name, raw_args = _validated_tool_call(
                        call, round_idx, call_idx
                    )
                    # Log the argument type/value — a None/missing arguments
                    # string is a common source of downstream .replace() errors.
                    logger.debug(
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
                tool_rounds += 1
                round_idx += 1
