"""Provider registry for TerraAI."""

import logging

from terra_ai.providers.base import AIProvider

logger = logging.getLogger("terraai")


class ProviderRegistry:
    """Holds the active provider and dormant fallback configuration."""

    def __init__(self, primary: AIProvider | None = None,
                 fallbacks: list[AIProvider] | None = None):
        self._primary = primary
        self._fallbacks = fallbacks or []

    def set_provider(self, provider: AIProvider):
        """Set the primary provider."""
        self._primary = provider

    def set_fallbacks(self, fallbacks: list[AIProvider]):
        """Set fallback providers."""
        self._fallbacks = fallbacks

    def get(self) -> AIProvider | None:
        """Get the first configured provider (primary, then dormant fallbacks)."""
        if self._primary and self._primary.configured:
            return self._primary

        for fallback in self._fallbacks:
            if fallback.configured:
                logger.warning(
                    "Primary provider %s is not configured; using fallback %s",
                    self._primary.name if self._primary else "None",
                    fallback.name,
                )
                return fallback

        return None

    @property
    def primary_name(self) -> str:
        return self._primary.name if self._primary else "none"
