"""Tests for extended providers (OpenAI, Ollama) and web search."""

import os
from unittest.mock import MagicMock, patch

import pytest

from terraai.providers.openai import OpenAIProvider
from terraai.providers.ollama import OllamaProvider
from terraai.providers.registry import ProviderRegistry
from terraai.tools.web_search import web_search


class TestOpenAIProvider:
    def test_name(self):
        provider = OpenAIProvider(model="gpt-4o", api_key="test-key")
        assert provider.name == "openai"

    def test_is_available_with_key(self):
        provider = OpenAIProvider(model="gpt-4o", api_key="test-key")
        assert provider.is_available() is True

    def test_is_available_without_key(self):
        provider = OpenAIProvider(model="gpt-4o", api_key=None)
        assert provider.is_available() is False

    @patch("terraai.providers.openai.httpx.Client")
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


class TestOllamaProvider:
    def test_name(self):
        provider = OllamaProvider(model="llama3", api_key=None)
        assert provider.name == "ollama"

    @patch("terraai.providers.ollama.httpx.Client")
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

    @patch("terraai.providers.ollama.httpx.Client")
    def test_is_available_reachable(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OllamaProvider(model="llama3")
        assert provider.is_available() is True


class TestProviderRegistry:
    def test_primary_available(self):
        primary = MagicMock()
        primary.is_available.return_value = True
        primary.name = "openrouter"

        registry = ProviderRegistry(primary)
        assert registry.get() is primary

    def test_fallback_when_primary_unavailable(self):
        primary = MagicMock()
        primary.is_available.return_value = False
        primary.name = "openrouter"

        fallback = MagicMock()
        fallback.is_available.return_value = True
        fallback.name = "gemini"

        registry = ProviderRegistry(primary, [fallback])
        assert registry.get() is fallback

    def test_none_when_all_unavailable(self):
        primary = MagicMock()
        primary.is_available.return_value = False

        fallback = MagicMock()
        fallback.is_available.return_value = False

        registry = ProviderRegistry(primary, [fallback])
        assert registry.get() is None

    def test_no_provider(self):
        registry = ProviderRegistry()
        assert registry.get() is None


class TestWebSearch:
    @patch("terraai.tools.web_search.httpx.Client")
    def test_search_with_abstract(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.text = '{"AbstractText": "Python is a programming language."}'
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = web_search("what is python")
        assert "Python" in result

    @patch("terraai.tools.web_search.httpx.Client")
    def test_search_failure(self, mock_client_cls):
        mock_client_cls.side_effect = Exception("Connection error")
        result = web_search("test")
        assert "Search failed" in result
