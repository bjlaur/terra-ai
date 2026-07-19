"""Core TerraAI plugin logic."""

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
from terra_ai.providers.openrouter import OpenRouterProvider
from terra_ai.providers.registry import ProviderRegistry
from terra_ai.prompts.manager import PromptManager
from terra_ai.prompts.defaults import IRC_SAFE_BYTES
from terra_ai.tools.schemas import AVAILABLE_TOOLS
logger = logging.getLogger("terraai")


class TerraAI:
    """Core TerraAI plugin logic.

    Holds all state and handles message routing.
    SOPEL @rule decorators delegate to this class.
    """

    def __init__(self, config: TerraAISection):
        if not str(config.sqlite_path or "").strip():
            raise ValueError("[terraai] sqlite_path must not be empty")
        if not str(config.base_url or "").strip():
            raise ValueError("[terraai] base_url must not be empty")
        if config.provider_timeout <= 0:
            raise ValueError("[terraai] provider_timeout must be greater than zero")
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
        self.config = config
        self.db = Database(DBConfig(path=config.sqlite_path))
        self.prompts = PromptManager(
            self.db, config=config
        )
        self.context = ContextManager(self.db, self.prompts)
        self.management = ManagementCommands(self.db, self.prompts, help_prefix="-")
        self.user = UserCommands(self.db, self.prompts)

        # Set up provider
        provider = OpenRouterProvider(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.provider_timeout,
        )
        self.registry = ProviderRegistry(provider)

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
                "AI provider not configured. "
                "Set api_key in the [terraai] section of your Sopel config "
                "or export OPENROUTER_API_KEY before starting Sopel."
            )

        start = time.time()

        logger.info("AI_PROMPT: nick=%s channel=%s text=%r", nick, channel, text)

        # Prefix the user message with <nick> exactly ONCE, here — this is
        # the single chokepoint. The prefixed form is what the AI sees and
        # what gets stored in history, so replayed history matches live.
        model_text = f"<{nick}> {text}"

        if include_history:
            messages = self.context.compose_context(server, channel, model_text, nick)
        else:
            # Context-free (.ai command): the system prompt is the whole
            # prompt — no history. Still prefix with <nick> for consistency.
            messages = self.context.prompts.get_context_seed(server, channel)
            messages.append({"role": "user", "content": model_text})

        # Convert to Message objects
        msg_objs = [Message(m["role"], m["content"]) for m in messages]

        # The full JSON wire payload (messages + tools + reasoning) is
        # dumped by the provider as DEBUG "OpenRouter REQUEST BODY" — no
        # need to duplicate the messages array here.

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
        if not isinstance(response, str) or not response.strip():
            raise ValueError(
                f"Provider {provider.name!r} returned an empty or non-text response"
            )
        logger.info(
            "AI_RESPONSE: model=%s length=%d text=%.500s",
            provider._model, len(response or ""), response or "",
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
            logger.info(
                "AI_RESPONSE too long (%d bytes > %d): concise rewrite attempt %d/%d",
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
            logger.info(
                "AI_RESPONSE too long: sending system reminder (attempt %d/%d): %r",
                concise_retries, MAX_CONCISE_RETRIES, concise_reminder,
            )
            retry_msgs.append(Message("assistant", response))
            retry_msgs.append(Message("system", concise_reminder))
            response = provider.chat(
                retry_msgs, effort=self.prompts.effort, tools=tools,
                noisy_callback=noisy_callback,
            )
            logger.info(
                "AI_RESPONSE (after concise rewrite #%d): model=%s length=%d text=%.500s",
                concise_retries, provider._model, len(response or ""), response or "",
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

        # Performance data is nonessential: a diagnostics failure must not
        # replace an otherwise successful and persisted response.
        try:
            self._record_performance(
                server, channel, nick, provider.name, provider._model,
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
