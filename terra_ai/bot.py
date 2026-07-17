"""Core TerraAI plugin logic."""

import logging
import time

from terra_ai.commands.management import ManagementCommands
from terra_ai.commands.user import UserCommands
from terra_ai.config import TerraAISection
from terra_ai.context.manager import ContextManager
from terra_ai.database import Database, DBConfig
from terra_ai.providers.base import Message
from terra_ai.providers.openrouter import OpenRouterProvider
from terra_ai.providers.registry import ProviderRegistry
from terra_ai.prompts.manager import PromptManager
from terra_ai.tools.schemas import AVAILABLE_TOOLS
logger = logging.getLogger("terraai")


class TerraAI:
    """Core TerraAI plugin logic.

    Holds all state and handles message routing.
    SOPEL @rule decorators delegate to this class.
    """

    def __init__(self, config: TerraAISection):
        self.config = config
        self.db = Database(DBConfig(path=config.sqlite_path))
        self.prompts = PromptManager(
            self.db, config=config
        )
        self.context = ContextManager(self.db, self.prompts)
        self.management = ManagementCommands(self.db, self.prompts, help_prefix="-")
        self.user = UserCommands(self.db, self.prompts)

        # Set up provider
        if not config.model:
            raise ValueError(
                "No AI model configured. TerraAI is model-agnostic: set "
                "[terraai] model in your SOPEL .cfg (e.g. 'tencent/hy3:free'). "
                "Refusing to start with an empty model."
            )
        if not config.api_key:
            raise ValueError(
                "No OpenRouter API key configured. Set [terraai] api_key "
                "or the OPENROUTER_API_KEY env var."
            )
        provider = OpenRouterProvider(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.provider_timeout,
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
        if nick == self.config.bot_nick:
            return False
        return True

    def handle_ai_message(self, server: str, channel: str, nick: str,
                          text: str, include_history: bool = True,
                          noisy_callback=None) -> str:
        """Handle a message that should go to the AI.

        *noisy_callback* is an optional callable(message: str) that the
        provider calls at each step of a tool-call loop so the caller can
        show progress (e.g. "Thinking...", "Geocoding Detroit...").
        """
        provider = self.registry.get()
        if not provider:
            return (
                "Error: AI provider not configured. "
                "Set api_key in the [terraai] section of your Sopel config "
                "or export OPENROUTER_API_KEY before starting Sopel."
            )

        try:
            start = time.time()

            logger.info("AI_PROMPT: nick=%s channel=%s text=%r", nick, channel, text)

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

            # DEBUG: the full payload sent to the provider — system prompt,
            # fake-conversation seed, real history, and the user's message.
            # Only emitted with -d; the bare prompt + response are info-level.
            logger.debug(
                "AI_SENT: model=%s effort=%s\n%s",
                provider._model, self.prompts.effort,
                "\n".join(
                    f"[{m.role}] {m.content}" for m in msg_objs
                ),
            )

            # Filter out disabled tools per user.
            # Only applies to local tools (those with "function" key).
            # Server-side tools (e.g. openrouter:web_search) can't be disabled.
            disabled = {
                t["tool_name"] for t in self.user.list_tools(server, nick)
                if t["disabled"]
            }
            tools = [
                t for t in AVAILABLE_TOOLS
                if "function" not in t or t["function"]["name"] not in disabled
            ]
            tool_names = [
                t["function"]["name"] if "function" in t else t.get("type", "unknown")
                for t in tools
            ]
            logger.info("AI_REQUEST: model=%s effort=%s messages=%d tools=%s",
                        provider._model, self.prompts.effort, len(msg_objs), tool_names)
            response = provider.chat(
                msg_objs, effort=self.prompts.effort, tools=tools,
                noisy_callback=noisy_callback,
            )
            logger.info(
                "AI_RESPONSE: model=%s length=%d text=%.500s",
                provider._model, len(response or ""), response or "",
            )

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
            logger.error(
                "AI call failed: model=%s effort=%s tools=%d error=%s",
                provider._model, self.prompts.effort,
                len(tools) if 'tools' in dir() else -1, e,
                exc_info=True,
            )
            return f"Error: {e}"
