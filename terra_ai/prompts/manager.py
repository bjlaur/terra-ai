"""Prompt manager for TerraAI."""

import sqlite3

from terra_ai.database import Database, PromptStore
from terra_ai.errors import log_expected_error
from terra_ai.providers.base import ProviderCapabilities
from terra_ai.prompts.defaults import (
    DEFAULT_EFFORT,
    EFFORT_LEVELS,
    SYSTEM_PROMPTS,
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

    def get_context_seed(
        self,
        server: str,
        channel: str,
        capabilities: ProviderCapabilities | None = None,
    ) -> list[dict]:
        """Get the prompt as a list of system messages (one per rule).

        Optional feature instructions are included only when the active
        provider declares that capability.
        """
        capabilities = capabilities or ProviderCapabilities()
        templates = [
            template
            for template, required_capability in SYSTEM_PROMPTS
            if required_capability is None
            or getattr(capabilities, required_capability)
        ]
        botnick = self._config.bot_nick if self._config and hasattr(self._config, 'bot_nick') else ""
        return [
            {"role": "system", "content": tmpl.format(botnick=botnick)}
            for tmpl in templates
        ]

    def add_prompt(self, server: str, trigger: str, response: str,
                   created_by: str | None = None) -> bool:
        """Add a custom prompt. Returns True if added, False if duplicate."""
        try:
            self.store.add(server, trigger, response, created_by)
            return True
        except sqlite3.IntegrityError as exc:
            log_expected_error(exc, "duplicate prompt insertion")
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
