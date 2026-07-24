"""OpenAI provider for TerraAI."""

import os

import httpx

from terra_ai.providers.base import (
    AIProvider,
    Message,
    ProviderCapabilities,
    UnsupportedProviderOptionError,
)


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider.

    Uses OpenAI's /v1/chat/completions endpoint.
    Get an API key at https://platform.openai.com/api-keys
    """

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None,
                 base_url: str = "https://api.openai.com/v1",
                 timeout: int = 30):
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._base_url = base_url
        self._timeout = int(timeout)

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    @property
    def configured(self) -> bool:
        return bool(self._model and self._api_key)

    def chat(self, messages: list[Message], system_prompt: str | None = None,
             effort: str = "high", tools: list[dict] | None = None,
             noisy_callback=None, request_kind: str = "initial") -> str:
        if tools:
            raise UnsupportedProviderOptionError(
                "OpenAIProvider does not implement local tool calling"
            )
        if effort != "high":
            raise UnsupportedProviderOptionError(
                "OpenAIProvider does not implement reasoning effort"
            )
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        payload_messages.extend(m.to_dict() for m in messages)

        payload = {
            "model": self._model,
            "messages": payload_messages,
        }

        if noisy_callback:
            noisy_callback("Thinking...")
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]
