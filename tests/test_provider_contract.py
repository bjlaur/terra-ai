"""Provider-neutral core contract tests."""

from types import SimpleNamespace

import pytest

from terra_ai.bot import TerraAI
from terra_ai.providers.base import AIProvider, Message, ProviderCapabilities
from terra_ai.providers.registry import ProviderRegistry


class InProcessProvider(AIProvider):
    """Network-free provider fake with no OpenRouter implementation details."""

    def __init__(self, capabilities: ProviderCapabilities):
        self._capabilities = capabilities
        self.calls = []

    @property
    def name(self) -> str:
        return "in-process"

    @property
    def model(self) -> str:
        return "memory-model"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    @property
    def configured(self) -> bool:
        return True

    def chat(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        effort: str = "high",
        tools: list[dict] | None = None,
        noisy_callback=None,
    ) -> str:
        self.calls.append(
            {
                "messages": list(messages),
                "system_prompt": system_prompt,
                "effort": effort,
                "tools": tools,
                "noisy_callback": noisy_callback,
            }
        )
        return "in-process answer"


def _core(tmp_path, capabilities):
    config = SimpleNamespace(
        sqlite_path=str(tmp_path / "terraai.db"),
        bot_nick="TerraAI",
        effort="high",
    )
    provider = InProcessProvider(capabilities)
    return TerraAI(config, ProviderRegistry(provider)), provider


@pytest.mark.parametrize(
    ("capabilities", "has_weather_prompt", "has_search_prompt", "has_tools"),
    [
        (ProviderCapabilities(), False, False, False),
        (ProviderCapabilities(local_tools=True), True, False, True),
        (ProviderCapabilities(native_search=True), False, True, False),
        (ProviderCapabilities(local_tools=True, native_search=True), True, True, True),
    ],
)
def test_core_uses_only_public_provider_contract(
    tmp_path,
    capabilities,
    has_weather_prompt,
    has_search_prompt,
    has_tools,
):
    terra, provider = _core(tmp_path, capabilities)
    try:
        result = terra.handle_ai_message(
            "test-network",
            "#terra-ai",
            "tester",
            "hello",
            include_history=False,
        )
        assert result == "in-process answer"
        call = provider.calls[0]
        prompt = " ".join(message.content for message in call["messages"])
        assert ("weather_forecast" in prompt) is has_weather_prompt
        assert ("provider-side web search" in prompt) is has_search_prompt
        has_weather_search_override = has_weather_prompt and has_search_prompt
        assert (
            "asks you to use web search instead" in prompt
        ) is has_weather_search_override
        assert ("asks for a web-search overread" in prompt) is has_weather_search_override
        if has_tools:
            assert [
                tool["function"]["name"] for tool in call["tools"]
            ] == ["weather_forecast"]
        else:
            assert call["tools"] is None

        telemetry = terra.db.fetchone(
            "SELECT provider, model FROM performance_stats ORDER BY id DESC LIMIT 1"
        )
        assert (telemetry["provider"], telemetry["model"]) == (
            "in-process",
            "memory-model",
        )
        assert not hasattr(provider, "_model")
    finally:
        terra.close()
