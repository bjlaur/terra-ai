"""Tests for extended providers (OpenAI, Ollama)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from terra_ai.providers.openai import OpenAIProvider
from terra_ai.providers.ollama import OllamaProvider
from terra_ai.providers.base import UnsupportedProviderOptionError
from terra_ai.providers.registry import ProviderRegistry


class TestOpenAIProvider:
    def test_name(self):
        provider = OpenAIProvider(model="gpt-4o", api_key="test-key")
        assert provider.name == "openai"

    def test_public_contract_with_key(self):
        provider = OpenAIProvider(model="gpt-4o", api_key="test-key")
        assert provider.model == "gpt-4o"
        assert provider.configured is True
        assert provider.capabilities.local_tools is False
        assert provider.capabilities.native_search is False

    def test_is_not_configured_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = OpenAIProvider(model="gpt-4o", api_key=None)
        assert provider.configured is False

    @patch("terra_ai.providers.openai.httpx.Client")
    def test_chat(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hi!"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OpenAIProvider(model="gpt-4o", api_key="test-key")
        result = provider.chat([MagicMock(to_dict=lambda: {"role": "user", "content": "hi"})])
        assert result == "Hi!"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"tools": [{"type": "function"}]},
            {"effort": "low"},
        ],
    )
    def test_rejects_unsupported_options(self, kwargs):
        provider = OpenAIProvider(model="gpt-4o", api_key="test-key")
        with pytest.raises(UnsupportedProviderOptionError):
            provider.chat([], **kwargs)


class TestOllamaProvider:
    def test_name(self):
        provider = OllamaProvider(model="llama3")
        assert provider.name == "ollama"
        assert provider.model == "llama3"
        assert provider.configured is True
        assert provider.capabilities.local_tools is False
        assert provider.capabilities.native_search is False

    @patch("terra_ai.providers.ollama.httpx.Client")
    def test_chat(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "Hello from Ollama!"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OllamaProvider(model="llama3")
        result = provider.chat([MagicMock(to_dict=lambda: {"role": "user", "content": "hi"})])
        assert result == "Hello from Ollama!"

    def test_configuration_check_does_not_probe_network(self):
        provider = OllamaProvider(model="llama3")
        assert provider.configured is True

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"tools": [{"type": "function"}]},
            {"effort": "low"},
        ],
    )
    def test_rejects_unsupported_options(self, kwargs):
        provider = OllamaProvider(model="llama3")
        with pytest.raises(UnsupportedProviderOptionError):
            provider.chat([], **kwargs)


class TestProviderRegistry:
    def test_primary_available(self):
        primary = SimpleNamespace(configured=True, name="openrouter")

        registry = ProviderRegistry(primary)
        assert registry.get() is primary

    def test_fallback_when_primary_unavailable(self):
        primary = SimpleNamespace(configured=False, name="openrouter")
        fallback = SimpleNamespace(configured=True, name="local")

        registry = ProviderRegistry(primary, [fallback])
        assert registry.get() is fallback

    def test_none_when_all_unavailable(self):
        primary = SimpleNamespace(configured=False, name="openrouter")
        fallback = SimpleNamespace(configured=False, name="local")

        registry = ProviderRegistry(primary, [fallback])
        assert registry.get() is None

    def test_no_provider(self):
        registry = ProviderRegistry()
        assert registry.get() is None
