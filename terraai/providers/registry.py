"""Provider registry for TerraAI."""

from terraai.providers.base import AIProvider


class ProviderRegistry:
    """Manages the active AI provider."""

    def __init__(self, provider: AIProvider | None = None):
        self._provider = provider

    def set_provider(self, provider: AIProvider):
        """Set the active provider."""
        self._provider = provider

    def get(self) -> AIProvider | None:
        """Get the active provider, or None if not configured."""
        return self._provider
