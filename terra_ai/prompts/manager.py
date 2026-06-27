"""Prompt manager for TerraAI."""

import logging

from terra_ai.database import Database, PromptStore

logger = logging.getLogger("terraai")
from terra_ai.prompts.defaults import (
    DEFAULT_EFFORT,
    EFFORT_LEVELS,
    FAKE_CONVERSATION,
    SYSTEM_PROMPT_TEMPLATE,
)


class PromptManager:
    """Manages custom prompts and system prompt generation."""

    def __init__(self, db: Database, config=None):
        self.db = db
        self.store = PromptStore(db)
        self._effort = config.effort if config and hasattr(config, 'effort') else DEFAULT_EFFORT
        self._config = config

    @property
    def effort(self) -> str:
        return self._effort

    def set_effort(self, level: str) -> bool:
        """Set effort level. Returns True if valid."""
        if level in EFFORT_LEVELS:
            self._effort = level
            return True
        return False

    def get_system_prompt(self) -> str:
        """Get the system prompt with variables interpolated."""
        botnick = self._config.bot_nick if self._config and hasattr(self._config, 'bot_nick') else ""
        return SYSTEM_PROMPT_TEMPLATE.format(botnick=botnick)

    def get_context_seed(self, server: str, channel: str) -> list[dict]:
        """Get the fake conversation as context seed.

        Uses source='system' so the AI knows it's context, not user messages.
        """
        botnick = self._config.bot_nick if self._config and hasattr(self._config, 'bot_nick') else ""
        seed = []
        for msg in FAKE_CONVERSATION:
            content = msg["content"].replace("{botnick}", botnick)
            seed.append({
                "role": msg["role"],
                "content": content,
                "source": "system",
            })
        return seed

    def add_prompt(self, server: str, trigger: str, response: str,
                   created_by: str | None = None) -> bool:
        """Add a custom prompt. Returns True if added, False if duplicate."""
        try:
            self.store.add(server, trigger, response, created_by)
            return True
        except Exception as e:
            logger.error("Failed to add prompt %r on %s: %s", trigger, server, e)
            return False

    def remove_prompt(self, server: str, trigger: str) -> bool:
        """Remove a custom prompt by trigger."""
        if self.store.get(server, trigger):
            self.store.remove(server, trigger)
            return True
        return False

    def remove_prompt_by_index(self, server: str, index: int) -> bool:
        """Remove a custom prompt by its alphabetical index."""
        return self.store.remove_by_index(server, index)

    def list_prompts(self, server: str) -> list[dict]:
        """List all custom prompts for a server."""
        return self.store.list_all(server)
