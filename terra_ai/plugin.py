"""SOPEL plugin interface for TerraAI."""

import logging

from sopel import plugin as sopel_plugin
from sopel import bot as sopel_bot
from sopel.trigger import Trigger

from terra_ai.bot import TerraAI
from terra_ai.config import load_config

logger = logging.getLogger("terraai")

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

    config_path = (
        getattr(getattr(bot.config, "terraai", None), "config_path", None)
        or "config/terraai.yaml"
    )
    logger.info("TerraAI setup starting; config_path=%r", config_path)
    config = load_config(config_path)
    _terrai = TerraAI(config)
    logger.info("TerraAI setup complete")


def shutdown():
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
def cmd_optin(bot, trigger):
    """Opt in to AI responses."""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    if not _guard(server, nick):
        return
    bot.say(terra.user.handle_optin(server, nick))


@sopel_plugin.command("optout")
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
def cmd_addprompt(bot, trigger):
    """Add a custom prompt."""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    if not _guard(server, nick):
        return
    args = (trigger.group(2) or "").strip()
    bot.say(terra.management.handle_addprompt(server, nick, args))


@sopel_plugin.command("rmprompt")
def cmd_rmprompt(bot, trigger):
    """Remove a custom prompt."""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    if not _guard(server, nick):
        return
    args = (trigger.group(2) or "").strip()
    bot.say(terra.management.handle_rmprompt(server, nick, args))


@sopel_plugin.command("listprompts")
def cmd_listprompts(bot, trigger):
    """List all custom prompts."""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    if not _guard(server, nick):
        return
    bot.say(terra.management.handle_listprompts(server, nick))


@sopel_plugin.command("compact")
@sopel_plugin.require_admin("Permission denied. .compact is admin-only.")
def cmd_compact(bot, trigger):
    """Compact conversation history. Admin only."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    if not _guard(server, trigger.nick):
        return
    bot.say(terra.management.handle_compact(server, channel, trigger.nick))


@sopel_plugin.command("clear")
def cmd_clear(bot, trigger):
    """Clear conversation history."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)
    if not _guard(server, nick):
        return
    bot.say(terra.management.handle_clear(server, channel))


@sopel_plugin.command("effort")
def cmd_effort(bot, trigger):
    """Set reasoning effort level."""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    if not _guard(server, nick):
        return
    args = (trigger.group(2) or "").strip()
    bot.say(terra.user.handle_effort(args))


@sopel_plugin.command("noisy")
def cmd_noisy(bot, trigger):
    """Toggle noisy mode."""
    terra = _get_terra()
    server = _server_name(bot)
    nick = _nick(trigger)
    if not _guard(server, nick):
        return
    bot.say(terra.user.handle_noisy(server, nick))


@sopel_plugin.command("stats")
def cmd_stats(bot, trigger):
    """Show performance stats."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)
    if not _guard(server, nick):
        return
    bot.say(terra.management.handle_stats(server, channel))


@sopel_plugin.command("help")
def cmd_help(bot, trigger):
    """Show available commands."""
    terra = _get_terra()
    nick = _nick(trigger)
    if not _guard(_server_name(bot), nick):
        return
    bot.say(terra.management.handle_help())


@sopel_plugin.command("setlocation")
def cmd_setlocation(bot, trigger):
    """Set your location (stored locally, then forwarded to AI)."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)
    if not _guard(server, nick):
        return
    args = (trigger.group(2) or "").strip()
    # Store locally as custom prompt
    terra.prompts.add_prompt(server, ".setlocation", args, nick)
    # Forward to AI for the response (hybrid behavior)
    text = f"{nick} .setlocation {args}"
    response = terra.handle_ai_message(server, channel, nick, text)
    if response:
        bot.say(response)


# ── Freeform addressed queries: TerraAI: <message> ──────────────────────────

@sopel_plugin.rule(r"$nick (.+)")
@sopel_plugin.allow_bots
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

    logger.info("addressed_freeform: calling handle_ai_message text=%r", text)
    response = terra.handle_ai_message(server, channel, nick, text)
    logger.info("addressed_freeform: response=%r", response)
    if response:
        bot.say(response)
