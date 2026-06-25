"""Google Gemini provider for TerraAI."""

import os

import httpx

from terra_ai.providers.base import AIProvider, Message


class GeminiProvider(AIProvider):
    """Google Gemini AI provider.

    Uses the Google AI Studio API (generativelanguage.googleapis.com).
    Get an API key at https://aistudio.google.com/appkey
    """

    def __init__(self, model: str = "gemini-2.0-flash", api_key: str | None = None,
                 timeout: int = 30):
        self._model = model
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "gemini"

    def chat(self, messages: list[Message], system_prompt: str | None = None,
             effort: str = "high") -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"

        # Convert OpenAI-format messages to Gemini format
        contents = []
        for msg in messages:
            if msg.role == "system":
                # Gemini uses systemInstruction, handled below
                continue
            role = "user" if msg.role == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.content}],
            })

        payload = {"contents": contents}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        return data["candidates"][0]["content"]["parts"][0]["text"]

    def is_available(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0
