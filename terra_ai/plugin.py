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


def _handle_management(bot, trigger, text):
    """Handle a management command."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)

    if not terra.should_respond(server, nick, None):
        return

    response = terra.handle_management(server, channel, nick, text)
    if response:
        bot.say(response)


# ── Management commands (-command) ──────────────────────────────────────────

@sopel_plugin.command("optin")
def cmd_optin(bot, trigger):
    """Opt in to AI responses."""
    _handle_management(bot, trigger, ".optin")


@sopel_plugin.command("optout")
def cmd_optout(bot, trigger):
    """Opt out of AI responses."""
    _handle_management(bot, trigger, ".optout")


@sopel_plugin.command("ai")
def cmd_ai(bot, trigger):
    """Send a prompt to the AI without conversation history."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)

    if not terra.should_respond(server, nick, None):
        return

    args = (trigger.group(2) or "").strip()
    response = terra.handle_ai_message(server, channel, nick, args, include_history=False)
    if response:
        bot.say(response)


@sopel_plugin.command("addprompt")
def cmd_addprompt(bot, trigger):
    """Add a custom prompt."""
    _handle_management(bot, trigger, trigger.group(0))


@sopel_plugin.command("rmprompt")
def cmd_rmprompt(bot, trigger):
    """Remove a custom prompt."""
    _handle_management(bot, trigger, trigger.group(0))


@sopel_plugin.command("listprompts")
def cmd_listprompts(bot, trigger):
    """List all custom prompts."""
    _handle_management(bot, trigger, ".listprompts")


@sopel_plugin.command("compact")
def cmd_compact(bot, trigger):
    """Compact conversation history."""
    _handle_management(bot, trigger, ".compact")


@sopel_plugin.command("clear")
def cmd_clear(bot, trigger):
    """Clear conversation history."""
    _handle_management(bot, trigger, ".clear")


@sopel_plugin.command("effort")
def cmd_effort(bot, trigger):
    """Set reasoning effort level."""
    _handle_management(bot, trigger, ".effort")


@sopel_plugin.command("noisy")
def cmd_noisy(bot, trigger):
    """Toggle noisy mode."""
    _handle_management(bot, trigger, ".noisy")


@sopel_plugin.command("stats")
def cmd_stats(bot, trigger):
    """Show performance stats."""
    _handle_management(bot, trigger, ".stats")


@sopel_plugin.command("help")
def cmd_help(bot, trigger):
    """Show available commands."""
    _handle_management(bot, trigger, ".help")


# ── Freeform addressed queries: TerraAI: <message> ──────────────────────────

@sopel_plugin.rule(r"$nick (.+)")
@sopel_plugin.allow_bots
def addressed_freeform(bot, trigger):
    """Handle freeform messages addressed to the bot by nick."""
    terra = _get_terra()
    server = _server_name(bot)
    channel = _channel_name(trigger)
    nick = _nick(trigger)

    if not terra.should_respond(server, nick, None):
        return

    text = (trigger.group(1) or "").strip()
    first_word = text.split(maxsplit=1)[0].lower().rstrip(":,") if text else ""

    # Avoid double-processing known management commands
    if first_word in _KNOWN_NICK_COMMANDS:
        return

    # Check management commands first
    if terra.is_management_command(text):
        response = terra.handle_management(server, channel, nick, f".{text}")
    else:
        response = terra.handle_ai_message(server, channel, nick, text)

    if response:
        bot.say(response)
