"""OpenRouter provider for TerraAI."""

import json
import logging
import math
import time
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from terra_ai.errors import current_correlation_id, report_recoverable_error
from terra_ai.logging_config import trace_openrouter
from terra_ai.providers.base import AIProvider, Message, ProviderCapabilities
from terra_ai.providers.pacing import RequestPacer
from terra_ai.providers.telemetry import (
    NoOpProviderCallSink,
    ProviderCallSink,
    record_provider_event,
)
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



def _http_status(response: httpx.Response | object) -> int | None:
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _header_string(response: httpx.Response | object, name: str) -> str | None:
    headers = getattr(response, "headers", None)
    value = headers.get(name) if hasattr(headers, "get") else None
    return value if isinstance(value, str) else None


def _raw_response_text(response: httpx.Response | object) -> str:
    value = getattr(response, "text", "")
    return value if isinstance(value, str) else str(value)

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


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _latest_user_prompt(messages: list[dict]) -> str | None:
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"]
    return None


def _request_tool_names(tools: list[dict]) -> list[str]:
    names: list[str] = []
    for tool in tools:
        function = tool.get("function") if isinstance(tool, dict) else None
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            names.append(function["name"])
        elif isinstance(tool, dict) and isinstance(tool.get("type"), str):
            names.append(tool["type"])
    return names


def _safe_error(response: httpx.Response) -> dict[str, object]:
    metadata = _safe_error_metadata(response)
    message: str | None = None
    try:
        data = response.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            message = error["message"]
    return {
        "type": metadata.get("error_type"),
        "message": message or response.reason_phrase or "Provider returned error",
        "provider_code": metadata.get("provider_code"),
    }


def _safe_usage_and_cost(data: dict) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    raw = data.get("usage")
    if not isinstance(raw, dict):
        return None, None

    usage: dict[str, object] = {}
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = raw.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            usage[name] = value

    prompt_details = raw.get("prompt_tokens_details")
    if isinstance(prompt_details, dict):
        cached = prompt_details.get("cached_tokens")
        if isinstance(cached, int) and not isinstance(cached, bool):
            usage["cached_tokens"] = cached

    completion_details = raw.get("completion_tokens_details")
    if isinstance(completion_details, dict):
        reasoning = completion_details.get("reasoning_tokens")
        if isinstance(reasoning, int) and not isinstance(reasoning, bool):
            usage["reasoning_tokens"] = reasoning

    cost: dict[str, object] = {}
    total_cost = raw.get("cost")
    if isinstance(total_cost, (int, float)) and not isinstance(total_cost, bool):
        if math.isfinite(float(total_cost)):
            cost["total"] = total_cost
    details = raw.get("cost_details")
    if isinstance(details, dict):
        upstream = details.get("upstream_inference_cost")
        if isinstance(upstream, (int, float)) and not isinstance(upstream, bool):
            if math.isfinite(float(upstream)):
                cost["upstream"] = upstream

    return usage or None, cost or None


def _validated_response_details(
    data: dict,
    round_idx: int,
) -> tuple[dict, str | None, list[str], str | None]:
    message = _response_message(data, round_idx)
    tool_calls = message.get("tool_calls")
    tool_names: list[str] = []
    if tool_calls is not None:
        if not isinstance(tool_calls, list):
            raise OpenRouterResponseError(
                f"OpenRouter round {round_idx} tool_calls must be a list"
            )
        for call_idx, call in enumerate(tool_calls):
            _, name, _ = _validated_tool_call(call, round_idx, call_idx)
            tool_names.append(name)

    content = message.get("content")
    response_text = content if isinstance(content, str) else None
    if not tool_names and (not isinstance(content, str) or not content.strip()):
        raise OpenRouterResponseError(
            f"OpenRouter round {round_idx} returned no text or tool calls"
        )

    choices = data.get("choices")
    finish_reason = None
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        value = choices[0].get("finish_reason")
        if isinstance(value, str):
            finish_reason = value
    return message, response_text, tool_names, finish_reason


class OpenRouterProvider(AIProvider):
    """OpenRouter AI provider with local tools, pacing, retries, and telemetry."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 30,
        request_pacer: RequestPacer | None = None,
        provider_call_sink: ProviderCallSink | None = None,
    ):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = int(timeout)
        self._request_pacer = request_pacer or RequestPacer()
        self._provider_call_sink = provider_call_sink or NoOpProviderCallSink()

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

    def chat(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        effort: str = "high",
        tools: list[dict] | None = None,
        max_tool_rounds: int = MAX_TOOL_ROUNDS,
        noisy_callback=None,
        request_kind: str = "initial",
    ) -> str:
        """Send messages and return a complete response."""
        if isinstance(max_tool_rounds, bool) or not isinstance(max_tool_rounds, int):
            raise ValueError("max_tool_rounds must be an integer")
        if max_tool_rounds < 0:
            raise ValueError("max_tool_rounds must not be negative")
        if request_kind not in {"initial", "concise_rewrite"}:
            raise ValueError("request_kind must be 'initial' or 'concise_rewrite'")

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://terra-ai.local",
            "X-OpenRouter-Title": "TerraAI",
        }

        payload_messages: list[dict] = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        payload_messages.extend(m.to_dict() for m in messages)
        payload: dict[str, object] = {
            "model": self._model,
            "messages": payload_messages,
        }

        reasoning = _reasoning_for_model(self._model, effort)
        if reasoning:
            payload["reasoning"] = reasoning
            logger.debug("OpenRouter chat: applying reasoning=%s", reasoning)
        else:
            logger.debug("OpenRouter chat: no reasoning config for model=%s", self._model)

        request_tools = [OPENROUTER_WEB_SEARCH_TOOL]
        if tools:
            request_tools.extend(tools)
        payload["tools"] = request_tools
        request_tool_names = _request_tool_names(request_tools)
        logger.debug("OpenRouter chat: model=%s tools=%d", self._model, len(request_tools))

        logical_call_id = str(uuid.uuid4())
        correlation_id = current_correlation_id()

        def attempt_event(
            *,
            round_idx: int,
            retry_idx: int,
            attempt_kind: str,
            provider_latency_ms: int,
            pacing_wait_ms: int,
            success: bool,
            http_status: int | None,
            safe_response_headers: dict[str, str] | None = None,
            response_text: str | None = None,
            response_tool_names: list[str] | None = None,
            returned_model: str | None = None,
            returned_provider: str | None = None,
            generation_id: str | None = None,
            usage: dict[str, object] | None = None,
            cost: dict[str, object] | None = None,
            finish_reason: str | None = None,
            error: dict[str, object] | None = None,
            will_retry: bool = False,
            retry_delay_ms: int = 0,
        ) -> dict[str, object]:
            return {
                "schema_version": 1,
                "timestamp": _utc_timestamp(),
                "call_id": logical_call_id,
                "correlation_id": correlation_id,
                "provider": "openrouter",
                "requested_model": self._model,
                "returned_model": returned_model,
                "returned_provider": returned_provider,
                "request_kind": attempt_kind,
                "round": round_idx,
                "attempt": retry_idx + 1,
                "latest_prompt": _latest_user_prompt(payload_messages),
                "message_count": len(payload_messages),
                "tool_names": request_tool_names,
                "success": success,
                "http_status": http_status,
                "provider_latency_ms": provider_latency_ms,
                "pacing_wait_ms": pacing_wait_ms,
                "response_text": response_text,
                "response_tool_names": response_tool_names or [],
                "generation_id": generation_id,
                "usage": usage,
                "cost": cost,
                "finish_reason": finish_reason,
                "error": error,
                "safe_response_headers": safe_response_headers or {},
                "will_retry": will_retry,
                "retry_delay_ms": retry_delay_ms,
            }

        with httpx.Client(timeout=self._timeout) as client:
            tool_rounds = 0
            round_idx = 0
            retry_wait_pending = False
            while True:
                logger.debug(
                    "OpenRouter chat: round=%d — waiting on API response", round_idx
                )
                if noisy_callback:
                    noisy_callback("Thinking...")

                response = None
                data = None
                message = None
                response_text = None
                response_tool_names: list[str] = []
                for retry_idx in range(MAX_TRANSIENT_RETRIES + 1):
                    waited = self._request_pacer.wait()
                    pacing_wait_ms = int(waited * 1000)
                    if waited:
                        logger.debug(
                            "OpenRouter request pacing: round=%d waited_ms=%d "
                            "interval_seconds=%.3f",
                            round_idx,
                            pacing_wait_ms,
                            self._request_pacer.interval,
                        )
                        if noisy_callback and not retry_wait_pending:
                            noisy_callback(
                                f"OpenRouter pacing: waiting {waited:.1f} seconds "
                                "before sending request..."
                            )
                    retry_wait_pending = False

                    attempt_kind = request_kind if round_idx == 0 else "tool_followup"
                    trace_base = {
                        "correlation_id": correlation_id,
                        "call_id": logical_call_id,
                        "round": round_idx,
                        "attempt": retry_idx + 1,
                    }
                    trace_openrouter(
                        {
                            **trace_base,
                            "event_type": "request",
                            "request": payload,
                        }
                    )
                    api_start = time.monotonic()
                    try:
                        response = client.post(url, json=payload, headers=headers)
                        provider_latency_ms = int((time.monotonic() - api_start) * 1000)
                        safe_headers = _safe_response_headers(response)
                        trace_openrouter(
                            {
                                **trace_base,
                                "event_type": "response",
                                "http_status": _http_status(response),
                                "safe_response_headers": safe_headers,
                                "response_body": _raw_response_text(response),
                            }
                        )
                        response.raise_for_status()
                        try:
                            data = response.json()
                        except ValueError as exc:
                            raise OpenRouterResponseError(
                                f"OpenRouter round {round_idx} returned invalid JSON: {exc}"
                            ) from exc
                        if not isinstance(data, dict):
                            raise OpenRouterResponseError(
                                f"OpenRouter round {round_idx} returned "
                                f"{type(data).__name__}, expected an object"
                            )
                        (
                            message,
                            response_text,
                            response_tool_names,
                            finish_reason,
                        ) = _validated_response_details(data, round_idx)
                    except httpx.HTTPStatusError as exc:
                        status = exc.response.status_code
                        safe_headers = _safe_response_headers(exc.response)
                        can_retry = (
                            status in TRANSIENT_HTTP_STATUSES
                            and self._request_pacer.enabled
                            and retry_idx < MAX_TRANSIENT_RETRIES
                        )
                        retry_delay = 0.0
                        if can_retry:
                            retry_after = _retry_after_delay_seconds(exc.response)
                            retry_delay = max(
                                self._request_pacer.interval,
                                retry_after if retry_after is not None else 0.0,
                            )
                        record_provider_event(
                            self._provider_call_sink,
                            attempt_event(
                                round_idx=round_idx,
                                retry_idx=retry_idx,
                                attempt_kind=attempt_kind,
                                provider_latency_ms=provider_latency_ms,
                                pacing_wait_ms=pacing_wait_ms,
                                success=False,
                                http_status=status,
                                safe_response_headers=safe_headers,
                                error=_safe_error(exc.response),
                                will_retry=can_retry,
                                retry_delay_ms=int(retry_delay * 1000),
                            ),
                        )
                        if can_retry:
                            retry_number = retry_idx + 1
                            retry_after = _retry_after_delay_seconds(exc.response)
                            self._request_pacer.defer_for(retry_delay)
                            retry_wait_pending = True
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

                        safe_metadata = _safe_error_metadata(exc.response)
                        error_context = ""
                        if safe_headers:
                            error_context += "; response_headers=" + json.dumps(
                                safe_headers,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        if safe_metadata:
                            error_context += "; error_metadata=" + json.dumps(
                                safe_metadata,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        raise OpenRouterTransportError(
                            f"OpenRouter request failed in round {round_idx} "
                            f"after {retry_idx + 1} attempt(s): "
                            f"{exc}{error_context}"
                        ) from exc
                    except httpx.HTTPError as exc:
                        provider_latency_ms = int((time.monotonic() - api_start) * 1000)
                        trace_openrouter(
                            {
                                **trace_base,
                                "event_type": "transport_error",
                                "error": {
                                    "type": type(exc).__name__,
                                    "message": str(exc),
                                },
                            }
                        )
                        record_provider_event(
                            self._provider_call_sink,
                            attempt_event(
                                round_idx=round_idx,
                                retry_idx=retry_idx,
                                attempt_kind=attempt_kind,
                                provider_latency_ms=provider_latency_ms,
                                pacing_wait_ms=pacing_wait_ms,
                                success=False,
                                http_status=None,
                                error={
                                    "type": type(exc).__name__,
                                    "message": str(exc),
                                    "provider_code": None,
                                },
                            ),
                        )
                        raise OpenRouterTransportError(
                            f"OpenRouter request failed in round {round_idx}: {exc}"
                        ) from exc
                    except OpenRouterResponseError as exc:
                        record_provider_event(
                            self._provider_call_sink,
                            attempt_event(
                                round_idx=round_idx,
                                retry_idx=retry_idx,
                                attempt_kind=attempt_kind,
                                provider_latency_ms=provider_latency_ms,
                                pacing_wait_ms=pacing_wait_ms,
                                success=False,
                                http_status=(
                                    _http_status(response) if response is not None else None
                                ),
                                safe_response_headers=(
                                    _safe_response_headers(response) if response else {}
                                ),
                                error={
                                    "type": type(exc).__name__,
                                    "message": str(exc),
                                    "provider_code": None,
                                },
                            ),
                        )
                        raise

                    usage, cost = _safe_usage_and_cost(data)
                    returned_model = data.get("model")
                    returned_provider = data.get("provider")
                    record_provider_event(
                        self._provider_call_sink,
                        attempt_event(
                            round_idx=round_idx,
                            retry_idx=retry_idx,
                            attempt_kind=attempt_kind,
                            provider_latency_ms=provider_latency_ms,
                            pacing_wait_ms=pacing_wait_ms,
                            success=True,
                            http_status=_http_status(response),
                            safe_response_headers=safe_headers,
                            response_text=response_text,
                            response_tool_names=response_tool_names,
                            returned_model=(
                                returned_model if isinstance(returned_model, str) else None
                            ),
                            returned_provider=(
                                returned_provider
                                if isinstance(returned_provider, str)
                                else None
                            ),
                            generation_id=_header_string(response, "X-Generation-Id"),
                            usage=usage,
                            cost=cost,
                            finish_reason=finish_reason,
                        ),
                    )
                    logger.debug(
                        "OpenRouter chat: round=%d API call took %d ms",
                        round_idx,
                        provider_latency_ms,
                    )
                    break

                if response is None or data is None or message is None:
                    raise OpenRouterTransportError(
                        f"OpenRouter request failed in round {round_idx} without a response"
                    )

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
                    logger.debug(
                        "OpenRouter final: content_type=%s content_len=%s",
                        type(response_text).__name__,
                        len(response_text) if response_text else 0,
                    )
                    return response_text

                if tool_rounds >= max_tool_rounds:
                    raise OpenRouterToolRoundLimitError(
                        "OpenRouter requested another tool round after the configured "
                        f"limit of {max_tool_rounds}"
                    )

                logger.debug(
                    "OpenRouter tool_calls: round=%d count=%d — executing tools",
                    round_idx,
                    len(tool_calls),
                )
                payload_messages.append(message)
                for call_idx, call in enumerate(tool_calls):
                    tool_call_id, name, raw_args = _validated_tool_call(
                        call, round_idx, call_idx
                    )
                    logger.debug(
                        "Tool call: id=%s name=%s args_type=%s args=%r",
                        tool_call_id,
                        name,
                        type(raw_args).__name__,
                        raw_args,
                    )
                    result_str = execute_tool(
                        name, raw_args, noisy_callback=noisy_callback
                    )
                    payload_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": name,
                            "content": result_str,
                        }
                    )
                tool_rounds += 1
                round_idx += 1
