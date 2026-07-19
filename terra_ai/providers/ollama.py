"""Ollama provider for TerraAI."""

import httpx

from terra_ai.providers.base import (
    AIProvider,
    Message,
    ProviderCapabilities,
    UnsupportedProviderOptionError,
)


class OllamaProvider(AIProvider):
    """Ollama local LLM provider.

    Uses Ollama's /api/chat endpoint.
    Requires Ollama to be running locally (http://localhost:11434).
    Install from https://ollama.com
    """

    def __init__(self, model: str = "llama3",
                 base_url: str = "http://localhost:11434",
                 timeout: int = 120):
        self._model = model
        self._base_url = base_url
        self._timeout = int(timeout)

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    @property
    def configured(self) -> bool:
        return bool(self._model and self._base_url)

    def chat(self, messages: list[Message], system_prompt: str | None = None,
             effort: str = "high", tools: list[dict] | None = None,
             noisy_callback=None) -> str:
        if tools:
            raise UnsupportedProviderOptionError(
                "OllamaProvider does not implement local tool calling"
            )
        if effort != "high":
            raise UnsupportedProviderOptionError(
                "OllamaProvider does not implement reasoning effort"
            )
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

        if noisy_callback:
            noisy_callback("Thinking...")
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        return data["message"]["content"]
