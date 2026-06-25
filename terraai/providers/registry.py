"""Provider registry for TerraAI."""

import logging

from terraai.providers.base import AIProvider

logger = logging.getLogger("terraai")


class ProviderRegistry:
    """Manages the active AI provider with optional fallback chain."""

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
        """Get the first available provider (primary, then fallbacks)."""
        if self._primary and self._primary.is_available():
            return self._primary

        for fallback in self._fallbacks:
            if fallback.is_available():
                logger.warning(
                    f"Primary provider {self._primary.name if self._primary else 'None'} "
                    f"unavailable, using fallback {fallback.name}"
                )
                return fallback

        return None

    @property
    def primary_name(self) -> str:
        return self._primary.name if self._primary else "none"
