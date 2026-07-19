"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ProviderCapabilities:
    """Optional active features implemented by a provider adapter."""

    local_tools: bool = False
    native_search: bool = False


class UnsupportedProviderOptionError(ValueError):
    """A caller requested an option the provider does not implement."""


class Message:
    """A chat message."""

    def __init__(self, role: str, content: str):
        self.role = role  # 'user' | 'assistant' | 'system'
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}

    def __repr__(self):
        return f"Message(role={self.role!r}, content={self.content!r})"


class AIProvider(ABC):
    """Abstract AI provider interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g. 'openrouter')."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Configured model identifier, without provider-specific inspection."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Declare optional active features implemented by this adapter."""
        ...

    @property
    @abstractmethod
    def configured(self) -> bool:
        """Whether required local configuration is present.

        This is intentionally not a remote health check. A future local or
        in-process model need not have credentials, HTTP, or a preflight API.
        """
        ...

    @abstractmethod
    def chat(self, messages: list[Message], system_prompt: str | None = None,
             effort: str = "high", tools: list[dict] | None = None,
             noisy_callback: Callable[[str], None] | None = None) -> str:
        """Send messages and get a complete response.

        Args:
            messages: List of Message objects.
            system_prompt: Optional system prompt prepended as a system message.
            effort: Effort level ('low', 'medium', 'high', 'xhigh', 'max').
            tools: Local function-tool schemas to include in the request.
            noisy_callback: Optional progress callback.

        Returns:
            The AI's response text.
        """
        ...
