"""SOPEL plugin entry point for TerraAI."""

import logging
import time

from terra_ai.commands.management import ManagementCommands
from terra_ai.commands.user import UserCommands
from terra_ai.config import TerraConfig
from terra_ai.context.manager import ContextManager
from terra_ai.database import Database, DBConfig
from terra_ai.providers.base import Message
from terra_ai.providers.openrouter import OpenRouterProvider
from terra_ai.providers.registry import ProviderRegistry
from terra_ai.prompts.manager import PromptManager

logger = logging.getLogger("terraai")


class TerraAI:
    """Core TerraAI plugin logic.

    Holds all state and handles message routing.
    SOPEL @rule decorators delegate to this class.
    """

    def __init__(self, config: TerraConfig):
        self.config = config
        self.db = Database(DBConfig(path=config.sqlite_path))
        trigger_char = config.bot.get("trigger_char", ".") if config else "."
        self.prompts = PromptManager(self.db, trigger_char=trigger_char, config=config)
        self.context = ContextManager(self.db, self.prompts)
        self.management = ManagementCommands(self.db, self.prompts)
        self.user = UserCommands(self.db, self.prompts)

        # Set up provider
        provider = OpenRouterProvider(
            model=config.provider.model,
            api_key=config.provider.api_key,
            base_url=config.provider.base_url or "https://openrouter.ai/api/v1",
            timeout=config.provider.timeout,
        )
        self.registry = ProviderRegistry(provider)

    def is_opted_in(self, server: str, nick: str) -> bool:
        """Check if user is opted in. Defaults to True if user not in DB."""
        row = self.db.conn.execute(
            "SELECT opted_in FROM users WHERE server = ? AND nick = ?",
            (server, nick)
        ).fetchone()
        if row is None:
            return True  # Default: opted in
        return bool(row["opted_in"])

    def should_respond(self, server: str, nick: str) -> bool:
        """Check if the bot should respond to this message."""
        if not self.is_opted_in(server, nick):
            return False
        # Don't respond to our own messages
        if nick == self.config.bot.get("bot_nick", ""):
            return False
        return True

    def handle_ai_message(self, server: str, channel: str, nick: str,
                          text: str, include_history: bool = True) -> str:
        """Handle a message that should go to the AI."""
        provider = self.registry.get()
        if not provider:
            return "AI provider not configured."

        try:
            start = time.time()

            if include_history:
                messages = self.context.compose_context(server, channel, text, nick)
            else:
                # Context-free (.ai command)
                messages = [
                    {"role": "system", "content": self.prompts.get_system_prompt()},
                    {"role": "user", "content": text},
                ]

            # Convert to Message objects
            msg_objs = [Message(m["role"], m["content"]) for m in messages]

            logger.info("handle_ai_message: calling provider.chat model=%s effort=%s", provider._model, self.prompts.effort)
            response = provider.chat(msg_objs, effort=self.prompts.effort)
            logger.info("handle_ai_message: provider.chat returned %r", response[:80] if response else None)

            elapsed_ms = int((time.time() - start) * 1000)

            # Save to history
            if include_history:
                self.context.save_exchange(server, channel, nick, text, response)

            # Log performance
            self.db.conn.execute(
                """INSERT INTO performance_stats
                   (server, channel, nick, session_id, provider, model,
                    processing_time_ms, response_chars)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (server, channel, nick, "active", provider.name, provider._model,
                 elapsed_ms, len(response))
            )
            self.db.conn.commit()

            return response

        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return f"Error: {e}"
