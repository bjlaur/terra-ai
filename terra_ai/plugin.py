"""SOPEL plugin interface for TerraAI."""

import functools
import logging
import re

from sopel import plugin as sopel_plugin
from sopel import bot as sopel_bot
from sopel.trigger import Trigger

from terra_ai.bot import TerraAI

logger = logging.getLogger("terraai")


def _irc_error_handler(func):
    """Decorator: catch exceptions, log them, and send 'Error:' to IRC.

    Ensures the bot NEVER stays silent on a crash — users always see
    an error message, and operators always see the traceback in logs.
    """
    @functools.wraps(func)
    def wrapper(bot, trigger, *args, **kwargs):
        try:
            return func(bot, trigger, *args, **kwargs)
        except Exception as e:
            logger.error("Handler %s crashed: %s", func.__name__, e, exc_info=True)
            bot.say(f"Error: {e}")
    return wrapper

# Global instance — set during setup
_terrai: TerraAI | None = None

_KNOWN_NICK_COMMANDS = {
    "ai", "optin", "optout", "noisy", "setlocation",
    "addprompt", "rmprompt", "listprompts",
    "compact", "clear", "effort", "stats", "help",
}


def setup(bot):
    """Called by Sopel when the plugin is loaded."""
    global _terrai

    # SOPEL already parsed the [terraai] section into bot.config.terraai
    # (a TerraAISection instance). Use it directly — no separate YAML needed.
    config = bot.config.terraai
    logger.info("TerraAI setup starting; model=%r", config.model)
    _terrai = TerraAI(config)
    logger.info("TerraAI setup complete")


def shutdown(bot=None):
    """Called by Sopel when the plugin is unloaded."""
    global _terrai
    _terrai = None
    logger.info("TerraAI plugin unloaded")


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
    args = (trigger.group(2) or "").strip()
    # Store locally as custom prompt — no prefix, SOPEL already stripped it
    terra.prompts.add_prompt(server, "setlocation", args, nick)
    # Forward to AI for the response (hybrid behavior)
    text = f"{nick} setlocation {args}"
    response = terra.handle_ai_message(server, channel, nick, text)
    if response:
        bot.say(response)


# ── Unknown -command fallback: route to AI ─────────────────────────────────


def _prefix_fallback_loader(settings):
    """Build a regex from Sopel's configured command prefix.

    settings.core.prefix is already a regex, e.g. '-'.
    Wrap it in a non-capturing group and use named captures for the command
    and rest of line.
    """
    prefix = settings.core.prefix
    pattern = rf'^(?:{prefix})(?P<command>\S+)(?:\s+(?P<args>.*))?$'
    logger.info("TerraAI prefix fallback regex: %s", pattern)
    return [re.compile(pattern)]


def _is_registered_sopel_command(bot, command: str) -> bool:
    """Return True if Sopel already has a command by this name or alias."""
    command = (command or '').strip().lower()
    if not command:
        return False

    # `bot` in plugin handlers is usually a SopelWrapper, but it proxies the
    # underlying Sopel object. `bot.rules` should work in normal Sopel usage.
    return bot.rules.has_command(command, follow_alias=True)


@sopel_plugin.rule_lazy(_prefix_fallback_loader)
@sopel_plugin.priority('low')
@sopel_plugin.thread(False)
def unknown_prefixed_command_to_ai(bot, trigger):
    """Route unknown `-whatever` messages to AI.

    Examples:
      -what is 2+2       -> AI sees "what is 2+2"
      -explain sqlite    -> AI sees "explain sqlite"

    Known Sopel commands are skipped:
      -help              -> normal @plugin.command('help') handler
      -ai hello          -> normal @plugin.command('ai') handler
      -optin             -> normal @plugin.command('optin') handler
    """
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

    text = f'{command} {args}'.strip()
    logger.info("TerraAI prefix fallback handling unknown command as AI: %r", text)

    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)

    if not terra.should_respond(server, nick):
        return

    # Notify noisy users that the AI is thinking
    if terra.user.is_noisy(server, nick):
        bot.notice("Thinking...", nick)

    response = terra.handle_ai_message(server, channel, nick, text)
    if response:
        bot.say(response)


# ── Freeform addressed queries: TerraAI: <message> ──────────────────────────

@sopel_plugin.rule(r"$nick (.+)")
@sopel_plugin.allow_bots
@_irc_error_handler
def addressed_freeform(bot, trigger):
    """Handle freeform messages addressed to the bot by nick."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)
    logger.info("addressed_freeform server=%r nick=%r text=%r", server, nick, trigger.group(1))

    if not terra.should_respond(server, nick):
        logger.info("addressed_freeform: should_respond=False")
        return

    text = (trigger.group(1) or "").strip()
    first_word = text.split(maxsplit=1)[0].lower().rstrip(":,") if text else ""

    # Avoid double-processing known management commands
    if first_word in _KNOWN_NICK_COMMANDS:
        logger.info("addressed_freeform: first_word=%r in KNOWN_NICK_COMMANDS", first_word)
        return

    # Notify noisy users that the AI is thinking
    if terra.user.is_noisy(server, nick):
        bot.notice("Thinking...", nick)

    logger.info("addressed_freeform: calling handle_ai_message text=%r", text)
    response = terra.handle_ai_message(server, channel, nick, text)
    logger.info("addressed_freeform: response=%r", response)
    if response:
        bot.say(response)


# ── PM catch-all: bare text in private messages ─────────────────────────────


@sopel_plugin.rule(r"(.+)")
@sopel_plugin.priority('low')
@_irc_error_handler
def pm_catch_all(bot, trigger):
    """Route bare PM text (no prefix, no nick addressing) to the AI.

    Channel messages without a prefix or nick addressing are ignored — this
    rule only fires for PMs. We detect PMs by checking that ``trigger.sender``
    is not a channel name (channels start with ``#``).
    """
    sender = trigger.sender or ""
    if sender.startswith("#"):
        return  # Channel message — ignore (handled by other rules if addressed)

    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)

    if not terra.should_respond(server, nick):
        return

    text = (trigger.group(1) or "").strip()
    if not text:
        return

    logger.info("pm_catch_all: forwarding PM from %r: %r", nick, text)

    if terra.user.is_noisy(server, nick):
        bot.notice("Thinking...", nick)

    response = terra.handle_ai_message(server, nick, nick, text)
    if response:
        bot.say(response)


# ── Test-console routing entry point ─────────────────────────────────────────
#
# The test console (test_tool/console.py) routes through SOPEL's real rule
# dispatcher via ``dispatch_line``.  The legacy manual-routing shims
# (``handle_channel_message``, ``handle_pm_message``, ``_cmd_word``,
# ``_notify_thinking``) have been removed — SOPEL's decorators now handle
# all routing.


def dispatch_line(bot, nick, line, is_pm=False):
    """Route a user line through SOPEL's rule dispatcher (test-console entry point).

    *bot* must have ``settings`` (with ``core.nick`` / ``core.prefix``) and
    ``rules`` (a populated :class:`sopel.plugins.rules.Manager``).  *line* is
    the plain text the user typed — this function wraps it in a minimal IRC
    ``PRIVMSG`` before feeding it to :class:`~sopel.trigger.PreTrigger`.

    Returns ``{"say": [...], "notice": [...]}`` with everything the handlers
    produced via ``bot.say()`` / ``bot.notice()``.
    """
    from sopel.trigger import PreTrigger, Trigger
    from sopel.bot import SopelWrapper

    target = nick if is_pm else "#terra-ai"
    # Build a minimal IRC PRIVMSG line that PreTrigger can parse.
    # Format: :nick!user@host PRIVMSG <target> :<text>
    irc_line = f":{nick}!user@host PRIVMSG {target} :{line}"
    pretrigger = PreTrigger(bot.settings.core.nick, irc_line)

    bot.messages.clear()
    bot.notices.clear()

    for rule, match in bot.rules.get_triggered_rules(bot, pretrigger):
        trigger = Trigger(bot.settings, pretrigger, match, account=None)
        wrapper = SopelWrapper(bot, trigger)
        rule.execute(wrapper, trigger)

    return {"say": list(bot.messages), "notice": list(bot.notices)}
