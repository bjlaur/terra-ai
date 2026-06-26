"""Ollama provider for TerraAI."""

import logging
import os

import httpx

from terra_ai.providers.base import AIProvider, Message

logger = logging.getLogger("terraai")


class OllamaProvider(AIProvider):
    """Ollama local LLM provider.

    Uses Ollama's /api/chat endpoint.
    Requires Ollama to be running locally (http://localhost:11434).
    Install from https://ollama.com
    """

    def __init__(self, model: str = "llama3", api_key: str | None = None,
                 base_url: str = "http://localhost:11434",
                 timeout: int = 120):
        self._model = model
        self._api_key = api_key  # Ollama doesn't use API keys, but kept for interface consistency
        self._base_url = base_url
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "ollama"

    def chat(self, messages: list[Message], system_prompt: str | None = None,
             effort: str = "high") -> str:
        url = f"{self._base_url}/api/chat"

        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        payload_messages.extend(m.to_dict() for m in messages)

        payload = {
            "model": self._model,
            "messages": payload_messages,
            "stream": False,
        }

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        return data["message"]["content"]

    def is_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error("Ollama availability check failed: %s", e)
            return False
