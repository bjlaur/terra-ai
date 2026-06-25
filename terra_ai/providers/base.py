"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod
from typing import Generator


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

    @abstractmethod
    def chat(self, messages: list[Message], system_prompt: str | None = None,
             effort: str = "high") -> str:
        """Send messages and get a complete response.

        Args:
            messages: List of Message objects.
            system_prompt: Optional system prompt prepended as a system message.
            effort: Effort level ('low', 'medium', 'high', 'xhigh', 'max').

        Returns:
            The AI's response text.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and reachable."""
        ...
