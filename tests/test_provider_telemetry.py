import json
import threading
from unittest.mock import MagicMock, patch

import httpx
import pytest

from terra_ai.errors import event_error_scope
from terra_ai.providers.base import Message
from terra_ai.providers.openrouter import (
    OpenRouterProvider,
    OpenRouterTransportError,
)
from terra_ai.providers.pacing import RequestPacer
from terra_ai.providers.telemetry import (
    CompositeProviderCallSink,
    ContextEnrichingProviderCallSink,
    InMemoryProviderCallSink,
    NoOpProviderCallSink,
    RotatingJsonlProviderCallSink,
)


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def response(status=200, *, payload=None, headers=None):
    if payload is None:
        payload = {"choices": [{"message": {"content": "answer"}}]}
    return httpx.Response(
        status,
        json=payload,
        headers=headers,
        request=httpx.Request(
            "POST", "https://openrouter.ai/api/v1/chat/completions"
        ),
    )


def provider_with_sink(sink, *, rpm=0):
    fake = FakeTime()
    pacer = RequestPacer(
        requests_per_minute=rpm,
        clock=fake.clock,
        sleep=fake.sleep,
    )
    return (
        OpenRouterProvider(
            model="test/model",
            api_key="key",
            request_pacer=pacer,
            provider_call_sink=sink,
        ),
        fake,
    )


def test_successful_attempt_records_compact_safe_fields():
    sink = InMemoryProviderCallSink()
    provider, _ = provider_with_sink(sink)
    payload = {
        "id": "generation-body-id",
        "model": "returned/model",
        "provider": "Example Provider",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": "final answer"},
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "total_tokens": 14,
            "prompt_tokens_details": {"cached_tokens": 3, "secret": "no"},
            "completion_tokens_details": {"reasoning_tokens": 2},
            "cost": 0.001,
            "cost_details": {
                "upstream_inference_cost": 0.0005,
                "unknown": "excluded",
            },
            "unknown": "excluded",
        },
    }
    client = MagicMock()
    client.post.return_value = response(
        payload=payload,
        headers={"X-Generation-Id": "gen-header", "Set-Cookie": "secret"},
    )

    with patch("terra_ai.providers.openrouter.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value = client
        result = provider.chat(
            [Message("system", "private system"), Message("user", "latest intent")],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "weather_forecast",
                        "description": "schema detail must not be copied",
                    },
                }
            ],
        )

    assert result == "final answer"
    [event] = sink.events
    assert event["success"] is True
    assert event["latest_prompt"] == "latest intent"
    assert event["message_count"] == 2
    assert event["tool_names"] == ["openrouter:web_search", "weather_forecast"]
    assert "private system" not in json.dumps(event)
    assert "schema detail" not in json.dumps(event)
    assert event["returned_model"] == "returned/model"
    assert event["returned_provider"] == "Example Provider"
    assert event["generation_id"] == "gen-header"
    assert event["finish_reason"] == "stop"
    assert event["usage"] == {
        "prompt_tokens": 10,
        "completion_tokens": 4,
        "total_tokens": 14,
        "cached_tokens": 3,
        "reasoning_tokens": 2,
    }
    assert event["cost"] == {"total": 0.001, "upstream": 0.0005}
    assert event["safe_response_headers"] == {"X-Generation-Id": "gen-header"}
    assert "Set-Cookie" not in json.dumps(event)


def test_retry_recovery_records_each_attempt_and_outcome():
    sink = InMemoryProviderCallSink()
    provider, fake = provider_with_sink(sink, rpm=20)
    client = MagicMock()
    client.post.side_effect = [
        response(
            429,
            payload={
                "error": {
                    "message": "limited",
                    "metadata": {
                        "error_type": "rate_limit_exceeded",
                        "provider_code": 42,
                        "secret": "excluded",
                    },
                }
            },
        ),
        response(),
    ]

    with patch("terra_ai.providers.openrouter.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value = client
        assert provider.chat([Message("user", "hello")]) == "answer"

    assert fake.sleeps == pytest.approx([3.0])
    assert len(sink.events) == 2
    failed, succeeded = sink.events
    assert failed["http_status"] == 429
    assert failed["will_retry"] is True
    assert failed["retry_delay_ms"] == 3000
    assert failed["error"] == {
        "type": "rate_limit_exceeded",
        "message": "limited",
        "provider_code": 42,
    }
    assert "secret" not in json.dumps(failed)
    assert succeeded["attempt"] == 2
    assert succeeded["success"] is True
    assert succeeded["pacing_wait_ms"] == 3000
    assert failed["call_id"] == succeeded["call_id"]


def test_retry_exhaustion_records_three_503_attempts():
    sink = InMemoryProviderCallSink()
    provider, _ = provider_with_sink(sink, rpm=20)
    client = MagicMock()
    client.post.side_effect = [response(503), response(503), response(503)]

    with patch("terra_ai.providers.openrouter.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value = client
        with pytest.raises(OpenRouterTransportError):
            provider.chat([Message("user", "hello")])

    assert [event["attempt"] for event in sink.events] == [1, 2, 3]
    assert [event["will_retry"] for event in sink.events] == [True, True, False]
    assert all(event["success"] is False for event in sink.events)


def test_nonretryable_and_transport_errors_are_recorded():
    status_sink = InMemoryProviderCallSink()
    status_provider, _ = provider_with_sink(status_sink, rpm=20)
    client = MagicMock()
    client.post.return_value = response(400)
    with patch("terra_ai.providers.openrouter.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value = client
        with pytest.raises(OpenRouterTransportError):
            status_provider.chat([Message("user", "bad")])
    assert status_sink.events[0]["http_status"] == 400
    assert status_sink.events[0]["will_retry"] is False

    transport_sink = InMemoryProviderCallSink()
    transport_provider, _ = provider_with_sink(transport_sink)
    client = MagicMock()
    client.post.side_effect = httpx.ConnectError("offline")
    with patch("terra_ai.providers.openrouter.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value = client
        with pytest.raises(OpenRouterTransportError):
            transport_provider.chat([Message("user", "hello")])
    assert transport_sink.events[0]["http_status"] is None
    assert transport_sink.events[0]["error"]["type"] == "ConnectError"


def test_pacing_wait_is_separate_from_provider_latency():
    sink = InMemoryProviderCallSink()
    provider, fake = provider_with_sink(sink, rpm=20)
    client = MagicMock()
    client.post.return_value = response()
    with patch("terra_ai.providers.openrouter.httpx.Client") as client_cls, patch(
        "terra_ai.providers.openrouter.time.monotonic",
        side_effect=[0.0, 0.125, 1.0, 1.25],
    ):
        client_cls.return_value.__enter__.return_value = client
        provider.chat([Message("user", "one")])
        provider.chat([Message("user", "two")])

    assert fake.sleeps == pytest.approx([3.0])
    assert [event["provider_latency_ms"] for event in sink.events] == [125, 250]
    assert [event["pacing_wait_ms"] for event in sink.events] == [0, 3000]


def test_tool_followup_uses_same_call_id_and_increments_round():
    sink = InMemoryProviderCallSink()
    provider, fake = provider_with_sink(sink, rpm=20)
    first = response(
        payload={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "tool-1",
                                "function": {
                                    "name": "weather_forecast",
                                    "arguments": "{}",
                                },
                            }
                        ],
                    }
                }
            ]
        }
    )
    client = MagicMock()
    client.post.side_effect = [first, response()]

    with patch("terra_ai.providers.openrouter.httpx.Client") as client_cls, patch(
        "terra_ai.providers.openrouter.execute_tool", return_value='{"ok":true}'
    ):
        client_cls.return_value.__enter__.return_value = client
        assert provider.chat([Message("user", "weather")]) == "answer"

    assert fake.sleeps == pytest.approx([3.0])
    assert [event["request_kind"] for event in sink.events] == [
        "initial",
        "tool_followup",
    ]
    assert [event["round"] for event in sink.events] == [0, 1]
    assert sink.events[0]["response_tool_names"] == ["weather_forecast"]
    assert sink.events[0]["call_id"] == sink.events[1]["call_id"]


def test_concise_rewrite_is_explicitly_identified():
    sink = InMemoryProviderCallSink()
    provider, _ = provider_with_sink(sink)
    client = MagicMock()
    client.post.return_value = response()
    with patch("terra_ai.providers.openrouter.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value = client
        provider.chat(
            [Message("user", "shorten")], request_kind="concise_rewrite"
        )
    assert sink.events[0]["request_kind"] == "concise_rewrite"


def test_sink_failure_does_not_change_successful_provider_response(caplog):
    class FailingSink:
        def record(self, event):
            raise OSError("disk full")

    provider, _ = provider_with_sink(FailingSink())
    client = MagicMock()
    client.post.return_value = response()
    with patch("terra_ai.providers.openrouter.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value = client
        with caplog.at_level("ERROR", logger="terraai"):
            assert provider.chat([Message("user", "hello")]) == "answer"
    assert "provider telemetry" in caplog.text
    assert "disk full" in caplog.text


def test_sink_failure_does_not_emit_a_continuing_user_error():
    class FailingSink:
        def record(self, event):
            raise OSError("disk full")

    visible_messages = []
    provider, _ = provider_with_sink(FailingSink())
    client = MagicMock()
    client.post.return_value = response()
    with patch("terra_ai.providers.openrouter.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value = client
        with event_error_scope(visible_messages.append):
            assert provider.chat([Message("user", "hello")]) == "answer"

    assert visible_messages == []


def test_sink_failure_does_not_replace_provider_error():
    class FailingSink:
        def record(self, event):
            raise OSError("telemetry unavailable")

    provider, _ = provider_with_sink(FailingSink(), rpm=20)
    client = MagicMock()
    client.post.return_value = response(400)
    with patch("terra_ai.providers.openrouter.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value = client
        with pytest.raises(OpenRouterTransportError, match="400 Bad Request"):
            provider.chat([Message("user", "bad")])


def test_context_enrichment_and_composition_do_not_mutate_source():
    normal = InMemoryProviderCallSink()
    benchmark = InMemoryProviderCallSink()
    composite = CompositeProviderCallSink(
        normal,
        ContextEnrichingProviderCallSink(
            benchmark, lambda: {"benchmark_test_id": "real::one"}
        ),
    )
    event = {"call_id": "one"}
    composite.record(event)
    assert event == {"call_id": "one"}
    assert normal.events == [{"call_id": "one"}]
    assert benchmark.events == [
        {"call_id": "one", "benchmark_test_id": "real::one"}
    ]


def test_rotating_jsonl_sink_is_valid_and_concurrent(tmp_path):
    path = tmp_path / "logs" / "provider-calls.jsonl"
    sink = RotatingJsonlProviderCallSink(
        path,
        max_bytes=180,
        backup_count=2,
        secrets=("secret-key",),
    )

    def write(index):
        sink.record({"index": index, "value": "secret-key-" + "x" * 30})

    threads = [threading.Thread(target=write, args=(index,)) for index in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    files = [candidate for candidate in path.parent.iterdir() if candidate.name.startswith(path.name)]
    assert files
    for candidate in files:
        for line in candidate.read_text().splitlines():
            assert isinstance(json.loads(line), dict)
            assert "secret-key" not in line


def test_noop_sink_accepts_events():
    NoOpProviderCallSink().record({"anything": "goes"})
