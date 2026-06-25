"""Prompt manager for TerraAI."""

import re

from terra_ai.database import Database, PromptStore
from terra_ai.prompts.defaults import (
    DEFAULT_EFFORT,
    EFFORT_LEVELS,
    FAKE_CONVERSATION,
    MANAGEMENT_COMMANDS,
    SYSTEM_PROMPT_TEMPLATE,
)


class PromptManager:
    """Manages custom prompts and system prompt generation."""

    def __init__(self, db: Database, trigger_char: str = "", config=None):
        self.db = db
        self.store = PromptStore(db)
        self._trigger_char = trigger_char
        self._effort = DEFAULT_EFFORT
        self._config = config

    @property
    def trigger_char(self) -> str:
        return self._trigger_char

    @property
    def effort(self) -> str:
        return self._effort

    def set_effort(self, level: str) -> bool:
        """Set effort level. Returns True if valid."""
        if level in EFFORT_LEVELS:
            self._effort = level
            return True
        return False

    def is_management_command(self, text: str) -> bool:
        """Check if text starts with a management command trigger."""
        if not text.startswith(self._trigger_char):
            return False
        # Extract the command word after the trigger
        rest = text[len(self._trigger_char):].strip()
        command = rest.split()[0].lower() if rest else ""
        return command in MANAGEMENT_COMMANDS

    def get_system_prompt(self) -> str:
        """Get the system prompt with variables interpolated."""
        botnick = self._config.bot.get("bot_nick", "") if self._config else ""
        return SYSTEM_PROMPT_TEMPLATE.format(triggerchar=self._trigger_char, botnick=botnick)

    def get_context_seed(self, server: str, channel: str) -> list[dict]:
        """Get the fake conversation as context seed.

        Uses source='system' so the AI knows it's context, not user messages.
        """
        botnick = self._config.bot.get("bot_nick", "") if self._config else ""
        seed = []
        for msg in FAKE_CONVERSATION:
            content = msg["content"].replace("${triggerchar}", self._trigger_char)
            content = content.replace("{botnick}", botnick)
            seed.append({
                "role": msg["role"],
                "content": content,
                "source": "system",
            })
        return seed

    def match_prompt(self, server: str, text: str) -> str | None:
        """Try to match text against custom prompts.

        Returns the stored response if matched, None otherwise.
        """
        if not text.startswith(self._trigger_char):
            return None
        rest = text[len(self._trigger_char):].strip()
        trigger = rest.split()[0].lower() if rest else ""

        prompt = self.store.get(server, f"{self._trigger_char}{trigger}")
        if prompt:
            return prompt["response"]
        return None

    def add_prompt(self, server: str, trigger: str, response: str,
                   created_by: str | None = None) -> bool:
        """Add a custom prompt. Returns True if added, False if duplicate."""
        if self._trigger_char and not trigger.startswith(self._trigger_char):
            trigger = f"{self._trigger_char}{trigger}"
        try:
            self.store.add(server, trigger, response, created_by)
            return True
        except Exception:
            return False

    def remove_prompt(self, server: str, trigger: str) -> bool:
        """Remove a custom prompt by trigger."""
        if self._trigger_char and not trigger.startswith(self._trigger_char):
            trigger = f"{self._trigger_char}{trigger}"
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
