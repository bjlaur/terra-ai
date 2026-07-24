"""Tests for TerraAI providers."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

from terra_ai.providers.base import AIProvider, Message
from terra_ai.providers.openrouter import (
    OPENROUTER_WEB_SEARCH_TOOL,
    OpenRouterProvider,
    OpenRouterResponseError,
    OpenRouterTransportError,
    OpenRouterToolRoundLimitError,
    _retry_after_delay_seconds,
)
from terra_ai.providers.pacing import RequestPacer
from terra_ai.providers.registry import ProviderRegistry


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def paced_provider(*, rpm=20):
    fake = FakeTime()
    pacer = RequestPacer(
        requests_per_minute=rpm,
        clock=fake.clock,
        sleep=fake.sleep,
    )
    return OpenRouterProvider(
        model="test-model",
        api_key="test-key",
        request_pacer=pacer,
    ), fake


def http_response(status, *, payload=None, headers=None):
    return httpx.Response(
        status,
        headers=headers,
        json=payload or {"error": {"message": "temporary failure"}},
        request=httpx.Request(
            "POST", "https://openrouter.ai/api/v1/chat/completions"
        ),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0", 0.0),
        ("12.5", 12.5),
        ("-1", None),
        ("nan", None),
        ("inf", None),
        ("not-a-delay", None),
        ("", None),
    ],
)
def test_retry_after_numeric_and_invalid_values(value, expected):
    response = http_response(429, headers={"Retry-After": value})

    assert _retry_after_delay_seconds(response) == expected


def test_retry_after_http_date_is_converted_to_delay():
    response = http_response(
        503,
        headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"},
    )

    assert _retry_after_delay_seconds(
        response,
        now=datetime(2015, 10, 21, 7, 27, 45, tzinfo=timezone.utc),
    ) == pytest.approx(15.0)


def test_retry_after_past_http_date_becomes_zero_delay():
    response = http_response(
        429,
        headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"},
    )

    assert _retry_after_delay_seconds(
        response,
        now=datetime(2015, 10, 21, 7, 29, 0, tzinfo=timezone.utc),
    ) == 0.0


class TestOpenRouterProvider:
    def test_name(self):
        provider = OpenRouterProvider(model="openrouter/test-model", api_key="test-key")
        assert provider.name == "openrouter"
        assert provider.model == "openrouter/test-model"
        assert provider.capabilities.local_tools is True
        assert provider.capabilities.native_search is True

    def test_is_configured_with_key(self):
        provider = OpenRouterProvider(model="test", api_key="test-key")
        assert provider.configured is True

    def test_is_not_configured_without_key(self):
        provider = OpenRouterProvider(model="test", api_key=None)
        assert provider.configured is False

    def test_is_not_configured_with_empty_key(self):
        provider = OpenRouterProvider(model="test", api_key="")
        assert provider.configured is False

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_chat(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OpenRouterProvider(model="test-model", api_key="test-key")
        messages = [Message("user", "hi")]
        local_tool = {
            "type": "function",
            "function": {"name": "weather_forecast"},
        }
        result = provider.chat(
            messages,
            system_prompt="You are a bot",
            tools=[local_tool],
        )

        assert result == "Hello!"
        mock_client.post.assert_called_once()
        request_tools = mock_client.post.call_args.kwargs["json"]["tools"]
        assert request_tools.count(OPENROUTER_WEB_SEARCH_TOOL) == 1
        assert request_tools.count(local_tool) == 1

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_chat_without_system_prompt(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hey!"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OpenRouterProvider(model="test-model", api_key="test-key")
        result = provider.chat([Message("user", "hi")])

        assert result == "Hey!"

    @patch("terra_ai.providers.openrouter.execute_tool", return_value='{"ok": true}')
    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_tool_result_is_consumed_by_followup_request(
        self, mock_client_cls, mock_execute_tool
    ):
        first = MagicMock()
        first.raise_for_status = MagicMock()
        first.json.return_value = {
            "choices": [{"message": {"content": None, "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "weather_forecast", "arguments": "{}"},
            }]}}]
        }
        second = MagicMock()
        second.raise_for_status = MagicMock()
        second.json.return_value = {
            "choices": [{"message": {"content": "It is sunny."}}]
        }
        client = MagicMock()
        client.post.side_effect = [first, second]
        mock_client_cls.return_value.__enter__.return_value = client

        provider, fake = paced_provider(rpm=20)
        result = provider.chat([Message("user", "weather")], max_tool_rounds=1)

        assert result == "It is sunny."
        assert client.post.call_count == 2
        assert fake.sleeps == pytest.approx([3.0])
        followup = client.post.call_args_list[1].kwargs["json"]["messages"]
        assert followup[-1] == {
            "role": "tool",
            "tool_call_id": "call-1",
            "name": "weather_forecast",
            "content": '{"ok": true}',
        }
        mock_execute_tool.assert_called_once_with(
            "weather_forecast", "{}", noisy_callback=None
        )

    @patch("terra_ai.providers.openrouter.execute_tool")
    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_tool_call_is_rejected_before_execution_at_limit(
        self, mock_client_cls, mock_execute_tool
    ):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "choices": [{"message": {"content": None, "tool_calls": [{
                "id": "call-1",
                "function": {"name": "weather_forecast", "arguments": "{}"},
            }]}}]
        }
        client = MagicMock()
        client.post.return_value = response
        mock_client_cls.return_value.__enter__.return_value = client
        provider = OpenRouterProvider(model="test-model", api_key="test-key")

        with pytest.raises(OpenRouterToolRoundLimitError, match="limit of 0"):
            provider.chat([Message("user", "weather")], max_tool_rounds=0)

        mock_execute_tool.assert_not_called()
        client.post.assert_called_once()

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_malformed_response_has_contextual_error(self, mock_client_cls):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"choices": []}
        client = MagicMock()
        client.post.return_value = response
        mock_client_cls.return_value.__enter__.return_value = client
        provider = OpenRouterProvider(model="test-model", api_key="test-key")

        with pytest.raises(OpenRouterResponseError, match="round 0.*no choices"):
            provider.chat([Message("user", "hello")])

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_empty_final_response_is_rejected(self, mock_client_cls):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"choices": [{"message": {"content": ""}}]}
        client = MagicMock()
        client.post.return_value = response
        mock_client_cls.return_value.__enter__.return_value = client
        provider = OpenRouterProvider(model="test-model", api_key="test-key")

        with pytest.raises(OpenRouterResponseError, match="no text or tool calls"):
            provider.chat([Message("user", "hello")])

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_malformed_optional_usage_does_not_replace_answer(
        self, mock_client_cls, caplog
    ):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "choices": [{"message": {"content": "valid answer"}}],
            "usage": [],
        }
        client = MagicMock()
        client.post.return_value = response
        mock_client_cls.return_value.__enter__.return_value = client
        provider = OpenRouterProvider(model="test-model", api_key="test-key")

        with caplog.at_level("ERROR", logger="terraai"):
            result = provider.chat([Message("user", "hello")])

        assert result == "valid answer"
        assert "usage must be an object" in caplog.text
        assert "Traceback" in caplog.text

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_429_retries_twice_at_effective_interval_and_notifies_noisy_mode(
        self, mock_client_cls
    ):
        success = http_response(
            200, payload={"choices": [{"message": {"content": "done"}}]}
        )
        client = MagicMock()
        client.post.side_effect = [
            http_response(429),
            http_response(429),
            success,
        ]
        mock_client_cls.return_value.__enter__.return_value = client
        provider, fake = paced_provider(rpm=20)
        notices = MagicMock()

        result = provider.chat(
            [Message("user", "hello")], noisy_callback=notices
        )

        assert result == "done"
        assert client.post.call_count == 3
        assert fake.sleeps == pytest.approx([3.0, 3.0])
        assert notices.call_args_list == [
            call("Thinking..."),
            call(
                "OpenRouter returned 429 Too Many Requests. "
                "Retrying in 3.0 seconds (1/2)..."
            ),
            call(
                "OpenRouter returned 429 Too Many Requests. "
                "Retrying in 3.0 seconds (2/2)..."
            ),
        ]

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_retry_after_delay_overrides_shorter_pacing_interval(
        self, mock_client_cls
    ):
        success = http_response(
            200, payload={"choices": [{"message": {"content": "done"}}]}
        )
        client = MagicMock()
        client.post.side_effect = [
            http_response(429, headers={"Retry-After": "10"}),
            success,
        ]
        mock_client_cls.return_value.__enter__.return_value = client
        provider, fake = paced_provider(rpm=20)
        notices = MagicMock()

        result = provider.chat(
            [Message("user", "hello")], noisy_callback=notices
        )

        assert result == "done"
        assert fake.sleeps == pytest.approx([10.0])
        assert notices.call_args_list[-1] == call(
            "OpenRouter returned 429 Too Many Requests. "
            "Retrying in 10.0 seconds (1/2)..."
        )

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_503_retries_twice_then_returns_final_error(self, mock_client_cls):
        client = MagicMock()
        client.post.side_effect = [
            http_response(503),
            http_response(503),
            http_response(503),
        ]
        mock_client_cls.return_value.__enter__.return_value = client
        provider, fake = paced_provider(rpm=20)

        with pytest.raises(
            OpenRouterTransportError, match=r"after 3 attempt\(s\).*503"
        ):
            provider.chat([Message("user", "hello")])

        assert client.post.call_count == 3
        assert fake.sleeps == pytest.approx([3.0, 3.0])

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_transient_status_is_not_retried_when_pacing_is_disabled(
        self, mock_client_cls
    ):
        client = MagicMock()
        client.post.return_value = http_response(429)
        mock_client_cls.return_value.__enter__.return_value = client
        provider = OpenRouterProvider(model="test-model", api_key="test-key")

        with pytest.raises(
            OpenRouterTransportError, match=r"after 1 attempt\(s\).*429"
        ):
            provider.chat([Message("user", "hello")])

        client.post.assert_called_once()

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_nontransient_status_is_not_retried(self, mock_client_cls):
        client = MagicMock()
        client.post.return_value = http_response(400)
        mock_client_cls.return_value.__enter__.return_value = client
        provider, fake = paced_provider(rpm=20)

        with pytest.raises(OpenRouterTransportError, match="400 Bad Request"):
            provider.chat([Message("user", "hello")])

        client.post.assert_called_once()
        assert fake.sleeps == []

    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_separate_chat_calls_share_provider_pacing_state(
        self, mock_client_cls
    ):
        response = http_response(
            200, payload={"choices": [{"message": {"content": "done"}}]}
        )
        client = MagicMock()
        client.post.return_value = response
        mock_client_cls.return_value.__enter__.return_value = client
        provider, fake = paced_provider(rpm=20)

        assert provider.chat([Message("user", "one")]) == "done"
        assert provider.chat([Message("user", "two")]) == "done"

        assert client.post.call_count == 2
        assert fake.sleeps == pytest.approx([3.0])

    @patch("terra_ai.providers.openrouter.trace_openrouter")
    @patch("terra_ai.providers.openrouter.httpx.Client")
    def test_traces_only_allowlisted_response_headers(
        self, mock_client_cls, mock_trace
    ):
        response = httpx.Response(
            429,
            headers={
                "Retry-After": "60",
                "RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1750000000",
                "X-Generation-Id": "gen-test",
                "Set-Cookie": "secret-cookie",
                "Authorization": "Bearer secret",
            },
            json={
                "error": {
                    "code": 429,
                    "message": "rate limited",
                    "metadata": {
                        "error_type": "provider_overloaded",
                        "provider_code": 42901,
                        "secret": "must-not-leak",
                    },
                }
            },
            request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        )
        client = MagicMock()
        client.post.return_value = response
        mock_client_cls.return_value.__enter__.return_value = client
        provider = OpenRouterProvider(model="test-model", api_key="test-key")

        with patch("terra_ai.providers.openrouter.MAX_TRANSIENT_RETRIES", 0):
            with pytest.raises(
                OpenRouterTransportError, match="429 Too Many Requests"
            ) as error:
                provider.chat([Message("user", "hello")])

        error_text = str(error.value)
        assert (
            'response_headers={"Retry-After":"60","RateLimit-Remaining":"0",'
            '"X-RateLimit-Reset":"1750000000",'
            '"X-Generation-Id":"gen-test"}'
        ) in error_text
        assert (
            'error_metadata={"error_type":"provider_overloaded",'
            '"provider_code":42901}'
        ) in error_text
        assert "must-not-leak" not in error_text
        assert "secret-cookie" not in error_text
        assert "Bearer secret" not in error_text

        header_payloads = [
            call.args[1]
            for call in mock_trace.call_args_list
            if call.args and call.args[0] == "response_headers=%s"
        ]
        assert header_payloads == [
            (
                '{"Retry-After":"60","RateLimit-Remaining":"0",'
                '"X-RateLimit-Reset":"1750000000",'
                '"X-Generation-Id":"gen-test"}'
            )
        ]
        assert "secret-cookie" not in header_payloads[0]
        assert "Bearer secret" not in header_payloads[0]


class TestProviderRegistry:
    def test_get_returns_none_when_empty(self):
        registry = ProviderRegistry()
        assert registry.get() is None

    def test_set_and_get(self):
        registry = ProviderRegistry()
        provider = OpenRouterProvider(model="test", api_key="key")
        registry.set_provider(provider)
        assert registry.get() is provider


class TestMessage:
    def test_to_dict(self):
        msg = Message("user", "hello")
        assert msg.to_dict() == {"role": "user", "content": "hello"}

    def test_repr(self):
        msg = Message("assistant", "hi")
        assert "assistant" in repr(msg)


@pytest.mark.mock
class TestOpenRouterProviderMockAPI:
    """Mock tests for OpenRouterProvider."""

    def test_mock_chat(self):
        """Test that provider.chat() works with mocked httpx."""
        from unittest.mock import patch, MagicMock

        provider = OpenRouterProvider(
            model="openrouter/test-model",
            api_key="test-key",
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "mocked response"}}]
        }

        with patch("httpx.Client.post", return_value=mock_response):
            messages = [Message("user", "hello")]
            result = provider.chat(messages)
            assert result == "mocked response"

    def test_mock_chat_with_system_prompt(self):
        """Test that provider.chat() passes system prompt with mocked httpx."""
        from unittest.mock import patch, MagicMock

        provider = OpenRouterProvider(
            model="openrouter/test-model",
            api_key="test-key",
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "mocked with system"}}]
        }

        with patch("httpx.Client.post", return_value=mock_response) as mock_post:
            messages = [Message("user", "hello")]
            result = provider.chat(messages, system_prompt="Be helpful.")
            assert result == "mocked with system"
            # Verify system prompt was sent
            call_kwargs = mock_post.call_args[1]
            body = call_kwargs.get("json", {})
            assert any(m.get("role") == "system" for m in body.get("messages", []))
