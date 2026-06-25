"""SOPEL plugin entry point for TerraAI."""

import logging
import time

from terraai.commands.admin import AdminCommands
from terraai.commands.user import UserCommands
from terraai.config import TerraConfig
from terraai.context.manager import ContextManager
from terraai.database import Database, DBConfig
from terraai.providers.base import Message
from terraai.providers.openrouter import OpenRouterProvider
from terraai.providers.registry import ProviderRegistry
from terraai.prompts.manager import PromptManager

logger = logging.getLogger("terraai")


class TerraAI:
    """Core TerraAI plugin logic.

    Holds all state and handles message routing.
    SOPEL @rule decorators delegate to this class.
    """

    def __init__(self, config: TerraConfig):
        self.config = config
        self.db = Database(DBConfig(path=config.sqlite_path))
        self.prompts = PromptManager(self.db, trigger_char=".")
        self.context = ContextManager(self.db, self.prompts)
        self.admin = AdminCommands(self.db, self.prompts)
        self.user = UserCommands(self.db, self.prompts)

        # Set up provider
        provider = OpenRouterProvider(
            model=config.provider.model,
            api_key=config.provider.api_key,
            base_url=config.provider.base_url or "https://openrouter.ai/api/v1",
            timeout=config.provider.timeout,
        )
        self.registry = ProviderRegistry(provider)
        self._effort = config.bot.get("effort", "high")

    def is_admin(self, nick: str) -> bool:
        """Check if a nick is in the admin list."""
        return nick in self.config.admin_nicks

    def is_opted_in(self, server: str, nick: str) -> bool:
        """Check if user is opted in. Defaults to True if user not in DB."""
        row = self.db.conn.execute(
            "SELECT opted_in FROM users WHERE server = ? AND nick = ?",
            (server, nick)
        ).fetchone()
        if row is None:
            return True  # Default: opted in
        return bool(row["opted_in"])

    def should_respond(self, server: str, nick: str, text: str) -> bool:
        """Check if the bot should respond to this message."""
        if not self.is_opted_in(server, nick):
            return False
        # Don't respond to our own messages
        if nick == self.config.bot.get("bot_nick", "TerraAI"):
            return False
        return True

    def is_management_command(self, text: str) -> bool:
        """Check if text is a management command."""
        return self.prompts.is_management_command(text)

    def handle_management(self, server: str, channel: str, nick: str,
                          text: str) -> str | None:
        """Handle management commands. Returns response or None."""
        # Extract command
        parts = text.strip().split(None, 1)
        if not parts:
            return None

        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Admin commands
        if command == ".listprompts":
            return self.admin.handle_listprompts(server, nick)
        elif command == ".rmprompt":
            return self.admin.handle_rmprompt(server, nick, args)
        elif command == ".addprompt":
            return self.admin.handle_addprompt(server, nick, args)
        elif command == ".compact":
            return self.admin.handle_compact(server, channel, nick)
        elif command == ".clear":
            return self.admin.handle_clear(server, channel)
        elif command == ".stats":
            return self.admin.handle_stats(server, channel)
        elif command == ".help":
            return self.admin.handle_help()

        # User commands
        elif command == ".optin":
            return self.user.handle_optin(server, nick)
        elif command == ".optout":
            return self.user.handle_optout(server, nick)
        elif command == ".noisy":
            return self.user.handle_noisy(server, nick)
        elif command == ".setlocation":
            return self.user.handle_setlocation(server, channel, nick, args)
        elif command == ".ai":
            # .ai is special — it goes to AI without history
            return None  # Let the AI handler deal with it
        elif command == ".effort":
            return self.user.handle_effort(args)

        return None

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

            response = provider.chat(msg_objs, effort=self._effort)

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

    def handle_setlocation(self, server: str, channel: str, nick: str,
                           location: str) -> None:
        """Save location as system message in history."""
        self.context.save_system_message(
            server, channel, nick, f"{nick}'s location is {location}"
        )
