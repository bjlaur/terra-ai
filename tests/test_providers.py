"""Tests for TerraAI providers."""

from unittest.mock import MagicMock, patch

import pytest

from terra_ai.providers.base import AIProvider, Message
from terra_ai.providers.openrouter import (
    OPENROUTER_WEB_SEARCH_TOOL,
    OpenRouterProvider,
    OpenRouterResponseError,
    OpenRouterToolRoundLimitError,
)
from terra_ai.providers.registry import ProviderRegistry


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

        provider = OpenRouterProvider(model="test-model", api_key="test-key")
        result = provider.chat([Message("user", "weather")], max_tool_rounds=1)

        assert result == "It is sunny."
        assert client.post.call_count == 2
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
