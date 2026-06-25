"""Tests for TerraAI providers."""

from unittest.mock import MagicMock, patch

import pytest

from terraai.providers.base import AIProvider, Message
from terraai.providers.openrouter import OpenRouterProvider
from terraai.providers.registry import ProviderRegistry


class TestOpenRouterProvider:
    def test_name(self):
        provider = OpenRouterProvider(model="google/gemini-2.0-flash-001", api_key="test-key")
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

    @patch("terraai.providers.openrouter.httpx.Client")
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

    @patch("terraai.providers.openrouter.httpx.Client")
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
