"""Tests for TerraAI providers."""

import os
from unittest.mock import MagicMock, patch

import pytest

from terra_ai.providers.base import AIProvider, Message
from terra_ai.providers.openrouter import OpenRouterProvider
from terra_ai.providers.registry import ProviderRegistry

# Skip real API tests unless OPENROUTER_API_KEY is set
HAS_API_KEY = bool(os.environ.get("OPENROUTER_API_KEY"))


class TestOpenRouterProvider:
    def test_name(self):
        provider = OpenRouterProvider(model="openrouter/owl-alpha", api_key="test-key")
        assert provider.name == "openrouter"

    def test_is_available_with_key(self):
        provider = OpenRouterProvider(model="test", api_key="test-key")
        assert provider.is_available() is True

    def test_is_available_without_key(self):
        provider = OpenRouterProvider(model="test", api_key=None)
        assert provider.is_available() is False

    def test_is_available_empty_key(self):
        provider = OpenRouterProvider(model="test", api_key="")
        assert provider.is_available() is False

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
        result = provider.chat(messages, system_prompt="You are a bot")

        assert result == "Hello!"
        mock_client.post.assert_called_once()

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
            model="openrouter/owl-alpha",
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
            model="openrouter/owl-alpha",
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


@pytest.mark.real
@pytest.mark.skipif(not HAS_API_KEY, reason="OPENROUTER_API_KEY not set")
class TestOpenRouterProviderRealAPI:
    """Integration tests that hit the real OpenRouter API.

    Only run when OPENROUTER_API_KEY environment variable is set.
    """

    def test_real_chat(self):
        """Test a real API call to OpenRouter."""
        provider = OpenRouterProvider(
            model="openrouter/owl-alpha",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        messages = [Message("user", "Say hello in one word.")]
        result = provider.chat(messages)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_real_chat_with_system_prompt(self):
        """Test a real API call with system prompt."""
        provider = OpenRouterProvider(
            model="openrouter/owl-alpha",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        messages = [Message("user", "What is 2+2? Answer with just the number.")]
        result = provider.chat(messages, system_prompt="You are a helpful math assistant.")
        assert isinstance(result, str)
        assert "4" in result
