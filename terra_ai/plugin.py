"""SOPEL plugin interface for TerraAI."""

import functools
import logging
import re

from sopel import plugin as sopel_plugin
from sopel import bot as sopel_bot
from sopel.trigger import Trigger

from terra_ai.bot import TerraAI
from terra_ai.config import TerraAISection
from terra_ai.errors import event_error_scope, report_terminal_error
from terra_ai.logging_config import configure_logging, shutdown_logging

logger = logging.getLogger("terraai")


def _irc_error_handler(func):
    """Decorator: catch exceptions, log them, and send 'Error:' to IRC.

    Ensures the bot NEVER stays silent on a crash — users always see
    an error message, and operators always see the traceback in logs.
    """
    @functools.wraps(func)
    def wrapper(bot, trigger, *args, **kwargs):
        event = getattr(trigger, "_pretrigger", trigger)
        with event_error_scope(bot.say, event=event):
            try:
                return func(bot, trigger, *args, **kwargs)
            except Exception as exc:
                report_terminal_error(bot, exc, func.__name__)
    return wrapper

# Global instance — set during setup
_terrai: TerraAI | None = None

_KNOWN_NICK_COMMANDS = {
    "ai", "optin", "optout", "noisy", "setlocation",
    "addprompt", "rmprompt", "listprompts",
    "compact", "clear", "effort", "stats", "help",
}


def configure(config):
    """Register TerraAI's typed SOPEL configuration section."""
    config.define_section("terraai", TerraAISection, validate=False)


def setup(bot):
    """Called by Sopel when the plugin is loaded."""
    global _terrai

    bot.config.define_section("terraai", TerraAISection, validate=True)
    config = bot.config.terraai
    _configure_logging(bot, config)
    if not config.bot_nick:
        config.bot_nick = bot.settings.core.nick
    logger.info("TerraAI setup starting; model=%r", config.model)
    try:
        _terrai = TerraAI(config)
    except Exception:
        logger.exception("TerraAI setup failed")
        shutdown_logging()
        raise
    logger.info("TerraAI setup complete")


def _configure_logging(bot, config):
    """Install TerraAI handlers while sharing SOPEL's stderr stream."""
    root = logging.getLogger()
    sopel_console = None
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            sopel_console = handler
            break
    configure_logging(
        log_dir=config.log_dir,
        secrets=(config.api_key,),
        log_max_bytes=config.log_max_bytes,
        log_backup_count=config.log_backup_count,
        trace_max_bytes=config.trace_log_max_bytes,
        trace_backup_count=config.trace_log_backup_count,
        sopel_console=sopel_console,
    )


def shutdown(bot=None):
    """Called by Sopel when the plugin is unloaded."""
    global _terrai
    terra, _terrai = _terrai, None
    try:
        if terra is not None:
            terra.close()
    except Exception:
        logger.exception("TerraAI shutdown failed")
        raise
    finally:
        logger.info("TerraAI plugin unloaded")
        shutdown_logging()


def _get_terra() -> TerraAI:
    if _terrai is None:
        raise RuntimeError("TerraAI not initialized")
    return _terrai


def _server_name(bot) -> str:
    return bot.isupport.get("NETWORK", "unknown")


def _channel_name(trigger: Trigger) -> str:
    return trigger.sender if hasattr(trigger, "sender") else "#unknown"


def _nick(trigger: Trigger) -> str:
    return trigger.nick if hasattr(trigger, "nick") else "unknown"


def _guard(server, nick) -> bool:
    """Shared guard: opt-in check + should_respond."""
    terra = _get_terra()
    if not terra.should_respond(server, nick):
        return False
    return True


# ── Management commands (-command) ──────────────────────────────────────────

@sopel_plugin.command("optin")
@_irc_error_handler
def cmd_optin(bot, trigger):
    """Opt in to AI responses."""
    # Don't guard — users should always be able to opt back in
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    bot.say(terra.user.handle_optin(server, nick))


@sopel_plugin.command("optout")
@_irc_error_handler
def cmd_optout(bot, trigger):
    """Opt out of AI responses."""
    # Don't guard — users should always be able to opt out
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    args = (trigger.group(2) or "").strip()
    if args and not trigger.admin:
        bot.say("Only admins can opt out other users.")
        return
    bot.say(terra.user.handle_optout(server, nick, args))


@sopel_plugin.command("ai")
@_irc_error_handler
def cmd_ai(bot, trigger):
    """Send a prompt to the AI without conversation history."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)
    if not _guard(server, nick):
        return

    args = (trigger.group(2) or "").strip()
    response = terra.handle_ai_message(server, channel, nick, args, include_history=False)
    if response:
        bot.say(response)


@sopel_plugin.command("addprompt")
@_irc_error_handler
def cmd_addprompt(bot, trigger):
    """Add a custom prompt."""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    args = (trigger.group(2) or "").strip()
    bot.say(terra.management.handle_addprompt(server, nick, args))


@sopel_plugin.command("rmprompt")
@_irc_error_handler
def cmd_rmprompt(bot, trigger):
    """Remove a custom prompt."""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    args = (trigger.group(2) or "").strip()
    bot.say(terra.management.handle_rmprompt(server, nick, args))


@sopel_plugin.command("listprompts")
@_irc_error_handler
def cmd_listprompts(bot, trigger):
    """List all custom prompts."""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    bot.say(terra.management.handle_listprompts(server, nick))


@sopel_plugin.command("compact")
@sopel_plugin.require_admin("Permission denied. .compact is admin-only.")
@_irc_error_handler
def cmd_compact(bot, trigger):
    """Compact conversation history. Admin only."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    bot.say(terra.management.handle_compact(server, channel, trigger.nick))


@sopel_plugin.command("clear")
@_irc_error_handler
def cmd_clear(bot, trigger):
    """Clear conversation history."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    bot.say(terra.management.handle_clear(server, channel))


@sopel_plugin.command("effort")
@_irc_error_handler
def cmd_effort(bot, trigger):
    """Set reasoning effort level."""
    terra = _get_terra()
    args = (trigger.group(2) or "").strip()
    bot.say(terra.user.handle_effort(args))


@sopel_plugin.command("noisy")
@_irc_error_handler
def cmd_noisy(bot, trigger):
    """Toggle noisy mode."""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    bot.say(terra.user.handle_noisy(server, nick))


@sopel_plugin.command("stats")
@_irc_error_handler
def cmd_stats(bot, trigger):
    """Show performance stats."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    bot.say(terra.management.handle_stats(server, channel))


@sopel_plugin.command("help")
@_irc_error_handler
def cmd_help(bot, trigger):
    """Show available commands."""
    terra = _get_terra()
    bot.say(terra.management.handle_help())


@sopel_plugin.command("setlocation")
@_irc_error_handler
def cmd_setlocation(bot, trigger):
    """Set your location (stored locally, then forwarded to AI)."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)
    if not _guard(server, nick):
        return

    args = (trigger.group(2) or "").strip()
    # Store locally as custom prompt — no prefix, SOPEL already stripped it
    terra.prompts.add_prompt(server, "setlocation", args, nick)
    # Forward to AI for the response (hybrid behavior). The <nick> prefix is
    # added by the single chokepoint in handle_ai_message, so pass bare text.
    text = f"setlocation {args}"
    response = terra.handle_ai_message(server, channel, nick, text)
    if response:
        bot.say(response)


@sopel_plugin.command("disable-tool")
@_irc_error_handler
def cmd_disable_tool(bot, trigger):
    """Disable a tool. Usage: -disable-tool <tool_name>"""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    args = (trigger.group(2) or "").strip()
    if not args:
        bot.say("Usage: -disable-tool <tool_name>")
        return
    valid = terra.user.valid_tool_names()
    if args not in valid:
        bot.say(f"Unknown tool '{args}'. Valid: {', '.join(sorted(valid))}")
        return
    terra.user.disable_tool(server, nick, args)
    bot.say(f"Tool '{args}' disabled.")


@sopel_plugin.command("enable-tool")
@_irc_error_handler
def cmd_enable_tool(bot, trigger):
    """Enable a tool. Usage: -enable-tool <tool_name>"""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    args = (trigger.group(2) or "").strip()
    if not args:
        bot.say("Usage: -enable-tool <tool_name>")
        return
    valid = terra.user.valid_tool_names()
    if args not in valid:
        bot.say(f"Unknown tool '{args}'. Valid: {', '.join(sorted(valid))}")
        return
    terra.user.enable_tool(server, nick, args)
    bot.say(f"Tool '{args}' enabled.")


@sopel_plugin.command("list-tools")
@_irc_error_handler
def cmd_listtools(bot, trigger):
    """List tools and their enabled/disabled status. Usage: -list-tools"""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    rows = terra.user.list_tools(server, nick)
    if not rows:
        bot.say("No tool overrides set. All tools enabled.")
        return
    parts = [
        f"{r['tool_name']}: {'disabled' if r['disabled'] else 'enabled'}"
        for r in rows
    ]
    bot.say("Tools: " + "; ".join(parts))


# ── Unknown -command fallback: route to AI ─────────────────────────────────


def _prefix_fallback_loader(settings):
    """Build a regex from Sopel's configured command prefix.

    settings.core.prefix is already a regex, e.g. '-'.
    Wrap it in a non-capturing group and use named captures for the command
    and rest of line.
    """
    prefix = settings.core.prefix
    pattern = rf'^(?:{prefix})(?P<command>\S+)(?:\s+(?P<args>.*))?$'
    logger.debug("TerraAI prefix fallback regex: %s", pattern)
    return [re.compile(pattern)]


def _is_registered_sopel_command(bot, command: str) -> bool:
    """Return True if Sopel already has a command by this name or alias."""
    command = (command or '').strip().lower()
    if not command:
        return False

    # `bot` in plugin handlers is usually a SopelWrapper, but it proxies the
    # underlying Sopel object. `bot.rules` should work in normal Sopel usage.
    return bot.rules.has_command(command, follow_alias=True)


def _match_prefixed_command(bot, text: str):
    """Match Sopel's configured prefix against raw message text."""
    prefix = bot.settings.core.prefix
    pattern = rf'^(?:{prefix})(?P<command>\S+)(?:\s+(?P<args>.*))?$'
    return re.match(pattern, text)


@sopel_plugin.rule_lazy(_prefix_fallback_loader)
@sopel_plugin.priority('low')
@sopel_plugin.thread(False)
@_irc_error_handler
def unknown_prefixed_command_to_ai(bot, trigger):
    """Route unknown `-whatever` messages to AI.

    Examples:
      -what is 2+2       -> AI sees "what is 2+2"
      -explain sqlite    -> AI sees "explain sqlite"

    Known Sopel commands are skipped:
      -help              -> normal @plugin.command('help') handler
      -ai hello          -> normal @plugin.command('ai') handler
      -optin             -> normal @plugin.command('optin') handler

    PMs are skipped — `pm_catch_all` handles all PM text to avoid duplicates.
    """
    sender = trigger.sender or ""
    if not sender.startswith("#"):
        return  # PM — let pm_catch_all handle it

    command = (trigger.group('command') or '').strip()
    args = (trigger.group('args') or '').strip()

    if not command:
        return

    command_lc = command.lower()

    # This replaces `_KNOWN_COMMANDS`.
    if _is_registered_sopel_command(bot, command_lc):
        logger.debug(
            "TerraAI prefix fallback skipping registered command: %s",
            command_lc,
        )
        return

    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)

    if not terra.should_respond(server, nick):
        return

    text = f'{command} {args}'.strip()
    logger.debug("TerraAI prefix fallback handling unknown command as AI: %r", text)

    # Build a noisy callback so the user can see tool-call progress.
    # Falls back to a no-op if noisy is disabled.
    def _noisy_notify(msg):
        if terra.user.is_noisy(server, nick):
            bot.notice(msg, nick)

    response = terra.handle_ai_message(server, channel, nick, text,
                                       noisy_callback=_noisy_notify)
    if response:
        bot.say(response)


# ── Freeform addressed queries: TerraAI: <message> ──────────────────────────

@sopel_plugin.rule(r"$nick (.+)")
@sopel_plugin.allow_bots
@_irc_error_handler
def addressed_freeform(bot, trigger):
    """Handle freeform messages addressed to the bot by nick."""
    # PMs are owned by pm_text_to_ai. In PMs, users do not need to address the bot.
    if trigger.is_privmsg:
        return

    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)
    if not terra.should_respond(server, nick):
        logger.debug(
            "addressed_freeform ignored: should_respond=False server=%r nick=%r",
            server,
            nick,
        )
        return

    text = (trigger.group(1) or "").strip()
    logger.debug(
        "addressed_freeform server=%r nick=%r text=%r", server, nick, text
    )
    first_word = text.split(maxsplit=1)[0].lower().rstrip(":,") if text else ""

    # Avoid double-processing known management commands
    if first_word in _KNOWN_NICK_COMMANDS:
        logger.debug("addressed_freeform: first_word=%r in KNOWN_NICK_COMMANDS", first_word)
        return

    # Build a noisy callback so the user can see tool-call progress.
    def _noisy_notify(msg):
        if terra.user.is_noisy(server, nick):
            bot.notice(msg, nick)

    logger.debug("addressed_freeform: calling handle_ai_message text=%r", text)
    response = terra.handle_ai_message(server, channel, nick, text,
                                       noisy_callback=_noisy_notify)
    logger.debug("addressed_freeform: response=%r", response)
    if response:
        bot.say(response)


# ── PM fallback: bare PMs and unknown prefixed PM commands ──────────────────


@sopel_plugin.rule(r"(.+)")
@sopel_plugin.priority('low')
@sopel_plugin.thread(False)
@_irc_error_handler
def pm_text_to_ai(bot, trigger):
    """Handle PM text that was not handled by a registered Sopel command.

    Owns:
      hello                  -> AI sees "hello"
      -weather Detroit       -> AI sees "weather Detroit"
      TerraAI: hello         -> AI sees "TerraAI: hello" (AI figures it out)

    Does NOT own:
      -help                  -> @sopel_plugin.command('help')
      -optin                 -> @sopel_plugin.command('optin')
      -ai hello              -> @sopel_plugin.command('ai')
      any other registered Sopel command
    """
    if not trigger.is_privmsg:
        return

    raw = (trigger.group(1) or "").strip()
    if not raw:
        return

    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)

    # For PM history, use a per-user conversation key.
    channel = nick

    m = _match_prefixed_command(bot, raw)
    if m:
        command = (m.group("command") or "").strip()
        args = (m.group("args") or "").strip()

        if not command:
            return

        command_lc = command.lower()

        # Known commands are owned by @sopel_plugin.command().
        # This prevents duplicate replies for -help, -optin, -ai, etc.
        if _is_registered_sopel_command(bot, command_lc):
            logger.debug(
                "TerraAI PM fallback skipping registered command: %s",
                command_lc,
            )
            return

        # Unknown prefixed PM: "-weather Detroit" -> "weather Detroit"
        text = f"{command} {args}".strip()
    else:
        # Bare PM: send as-is. AI can figure out addressing.
        text = raw

    if not text:
        return

    if not terra.should_respond(server, nick):
        return

    def _noisy_notify(msg):
        if terra.user.is_noisy(server, nick):
            bot.notice(msg, nick)

    logger.debug("TerraAI PM fallback handling text as AI: %r", text)
    response = terra.handle_ai_message(server, channel, nick, text,
                                       noisy_callback=_noisy_notify)
    if response:
        bot.say(response)


# ── In-process test routing entry point ──────────────────────────────────────
#
# Plugin tests route through SOPEL's real rule dispatcher via ``dispatch_line``.
# The legacy manual-routing shims
# (``handle_channel_message``, ``handle_pm_message``, ``_cmd_word``,
# ``_notify_thinking``) have been removed — SOPEL's decorators now handle
# all routing.


def dispatch_line(bot, nick, line, is_pm=False):
    """Route a user line through SOPEL's rule dispatcher for tests.

    *bot* must have ``settings`` (with ``core.nick`` / ``core.prefix``) and
    ``rules`` (a populated :class:`sopel.plugins.rules.Manager``).  *line* is
    the plain text the user typed — this function wraps it in a minimal IRC
    ``PRIVMSG`` before feeding it to :class:`~sopel.trigger.PreTrigger`.

    Returns ``{"say": [...], "notice": [...]}`` with everything the handlers
    produced via ``bot.say()`` / ``bot.notice()``.
    """
    from sopel.trigger import PreTrigger, Trigger
    from sopel.bot import SopelWrapper

    target = bot.settings.core.nick if is_pm else "#terra-ai"
    # Build a minimal IRC PRIVMSG line that PreTrigger can parse.
    # Format: :nick!user@host PRIVMSG <target> :<text>
    irc_line = f":{nick}!user@host PRIVMSG {target} :{line}"
    pretrigger = PreTrigger(bot.settings.core.nick, irc_line)

    bot.messages.clear()
    bot.notices.clear()

    # If the bot has a live_notice callback (set by the console TUI),
    # wire it so that bot.notice() also triggers an immediate UI update.
    live_notice = getattr(bot, "live_notice", None)

    for rule, match in bot.rules.get_triggered_rules(bot, pretrigger):
        trigger = Trigger(bot.settings, pretrigger, match, account=None)
        wrapper = SopelWrapper(bot, trigger)
        rule.execute(wrapper, trigger)

    result = {"say": list(bot.messages), "notice": list(bot.notices)}

    # Deliver any buffered notices immediately after dispatch completes — but
    # only if they weren't already streamed live during dispatch. When the
    # TUI's FakeBot.notice() is relaying notices in real time (live_notice +
    # the _notice_streamed_live flag), re-forwarding here would double-serve
    # every notice. In the live IRC bot there is no flag, so notices still
    # flush through sobot path.
    if live_notice and not getattr(bot, "_notice_streamed_live", False):
        for dest, msg in bot.notices:
            live_notice(msg)

    return result
