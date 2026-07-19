"""Core TerraAI plugin logic."""

import json
import logging
import time

from terra_ai.commands.management import ManagementCommands
from terra_ai.commands.user import UserCommands
from terra_ai.config import TerraAISection
from terra_ai.context.manager import ContextManager
from terra_ai.database import Database, DBConfig, UserStore
from terra_ai.errors import report_recoverable_error
from terra_ai.irc import limit_utf8
from terra_ai.providers.base import Message
from terra_ai.providers.registry import ProviderRegistry
from terra_ai.prompts.manager import PromptManager
from terra_ai.prompts.defaults import IRC_SAFE_BYTES
from terra_ai.tools.policy import ToolPolicy
from terra_ai.tools.schemas import LOCAL_TOOLS
logger = logging.getLogger("terraai")


class TerraAI:
    """Core TerraAI plugin logic.

    Holds all state and handles message routing.
    SOPEL @rule decorators delegate to this class.
    """

    def __init__(self, config: TerraAISection, registry: ProviderRegistry):
        if not str(config.sqlite_path or "").strip():
            raise ValueError("[terraai] sqlite_path must not be empty")
        self.config = config
        self.db = Database(DBConfig(path=config.sqlite_path))
        self.prompts = PromptManager(
            self.db, config=config
        )
        self.context = ContextManager(self.db, self.prompts)
        self.management = ManagementCommands(self.db, self.prompts, help_prefix="-")
        self.user = UserCommands(self.db, self.prompts)
        self.tool_policy = ToolPolicy(self.db)
        self.registry = registry

    def is_opted_in(self, server: str, nick: str) -> bool:
        """Check if user is opted in. Defaults to True if user not in DB."""
        return bool(UserStore(self.db).is_opted_in(server, nick))

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
            raise RuntimeError(
                "No configured AI provider is active."
            )

        start = time.time()

        # Prefix the user message with <nick> exactly ONCE, here — this is
        # the single chokepoint. The prefixed form is what the AI sees and
        # what gets stored in history, so replayed history matches live.
        model_text = f"<{nick}> {text}"

        if include_history:
            messages = self.context.compose_context(
                server,
                channel,
                model_text,
                nick,
                capabilities=provider.capabilities,
            )
        else:
            # Context-free (.ai command): the system prompt is the whole
            # prompt — no history. Still prefix with <nick> for consistency.
            messages = self.context.prompts.get_context_seed(
                server,
                channel,
                capabilities=provider.capabilities,
            )
            messages.append({"role": "user", "content": model_text})

        # Convert to Message objects
        msg_objs = [Message(m["role"], m["content"]) for m in messages]

        # The provider owns exact wire logging and native feature schemas.

        disabled = self.tool_policy.disabled_names(server)
        tools = None
        if provider.capabilities.local_tools:
            tools = [
                tool for tool in LOCAL_TOOLS
                if tool["function"]["name"] not in disabled
            ]
        tool_names = [
            t["function"]["name"] if "function" in t else t.get("type", "unknown")
            for t in tools or []
        ]
        logger.info(
            "AI prompt sent: model=%s nick=%s channel=%s prompt=%s",
            provider.model,
            nick,
            channel,
            json.dumps(model_text, ensure_ascii=False),
        )
        logger.debug(
            "AI request: model=%s effort=%s messages=%d tools=%s",
            provider.model,
            self.prompts.effort,
            len(msg_objs),
            tool_names,
        )
        response = provider.chat(
            msg_objs, effort=self.prompts.effort, tools=tools,
            noisy_callback=noisy_callback,
        )
        if not isinstance(response, str) or not response.strip():
            raise ValueError(
                f"Provider {provider.name!r} returned an empty or non-text response"
            )
        logger.debug(
            "AI provider response: model=%s length=%d text=%s",
            provider.model,
            len(response or ""),
            json.dumps(response or "", ensure_ascii=False),
        )

        # ── Auto-concise loop ───────────────────────────────────────────
        # IRC lines are capped (512 bytes including the protocol prefix),
        # so a long reply would be truncated or dropped by the server.
        # If the model's reply is too long, feed it back with a system
        # reminder naming the hard limit and demand a rewrite. Loop up to
        # MAX_CONCISE_RETRIES times, re-checking the byte count each pass,
        # so we never ship an over-long reply (the model sometimes ignores
        # a single soft nudge and grows longer). The final reply — once it
        # fits, or after we give up — is what we keep and save.
        MAX_CONCISE_RETRIES = 2
        concise_retries = 0
        retry_msgs = list(msg_objs)
        while (response
               and len(response.encode("utf-8")) > IRC_SAFE_BYTES
               and concise_retries < MAX_CONCISE_RETRIES):
            concise_retries += 1
            logger.debug(
                "AI response too long (%d bytes > %d): concise rewrite attempt %d/%d",
                len(response.encode("utf-8")), IRC_SAFE_BYTES,
                concise_retries, MAX_CONCISE_RETRIES,
            )
            if noisy_callback:
                noisy_callback(
                    "Reply was too long for IRC — rewriting to be more concise..."
                )
            concise_reminder = (
                f"Your response was too long. You MUST follow the rules and "
                f"reply with at most {IRC_SAFE_BYTES} UTF-8 bytes."
            )
            logger.debug(
                "AI response too long: sending system reminder (attempt %d/%d): %r",
                concise_retries, MAX_CONCISE_RETRIES, concise_reminder,
            )
            retry_msgs.append(Message("assistant", response))
            retry_msgs.append(Message("system", concise_reminder))
            response = provider.chat(
                retry_msgs, effort=self.prompts.effort, tools=tools,
                noisy_callback=noisy_callback,
            )
            logger.debug(
                "AI response after concise rewrite #%d: model=%s length=%d text=%s",
                concise_retries,
                provider.model,
                len(response or ""),
                json.dumps(response or "", ensure_ascii=False),
            )
            if not isinstance(response, str) or not response.strip():
                raise ValueError(
                    f"Provider {provider.name!r} returned an empty or non-text concise rewrite"
                )

        if len(response.encode("utf-8")) > IRC_SAFE_BYTES:
            logger.warning(
                "AI_RESPONSE remained over limit after %d concise rewrites; "
                "applying deterministic UTF-8 truncation",
                concise_retries,
            )
            response = limit_utf8(response, IRC_SAFE_BYTES)

        elapsed_ms = int((time.time() - start) * 1000)

        # Save to history (model_text is already <nick>-prefixed)
        if include_history:
            self.context.save_exchange(server, channel, nick, model_text, response)

        logger.info(
            "AI response: model=%s response=%s",
            provider.model,
            json.dumps(response, ensure_ascii=False),
        )

        # Performance data is nonessential: a diagnostics failure must not
        # replace an otherwise successful and persisted response.
        try:
            self._record_performance(
                server, channel, nick, provider.name, provider.model,
                elapsed_ms, len(response),
            )
        except Exception as exc:
            report_recoverable_error(exc, "performance statistics persistence")

        return response

    def _record_performance(
        self,
        server: str,
        channel: str,
        nick: str,
        provider_name: str,
        model: str,
        elapsed_ms: int,
        response_chars: int,
    ) -> None:
        """Persist nonessential performance diagnostics."""
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO performance_stats
                   (server, channel, nick, session_id, provider, model,
                    processing_time_ms, response_chars)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    server, channel, nick, "active", provider_name, model,
                    elapsed_ms, response_chars,
                ),
            )

    def close(self) -> None:
        """Release resources owned by this TerraAI instance."""
        self.db.close()
