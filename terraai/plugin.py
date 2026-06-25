"""SOPEL plugin interface for TerraAI.

This is the entry point that SOPEL loads.
"""

import logging

import sopel
from sopel import bot as sopel_bot
from sopel.trigger import Trigger

from terraai.bot import TerraAI
from terraai.config import load_config

logger = logging.getLogger("terraai")

# Global instance — set during setup
_terrai: TerraAI | None = None


def setup(bot: sopel_bot.Sopel):
    """Called by SOPEL when the plugin is loaded."""
    global _terrai

    # Get config path from SOPEL [terraai] section, or fall back
    config_path = (
        getattr(getattr(bot.config, "terraai", None), "config_path", None)
        or "config/terraai.yaml"
    )
    config = load_config(config_path)
    _terrai = TerraAI(config)
    logger.info("TerraAI plugin loaded from %s", config_path)


def shutdown():
    """Called by SOPEL when the plugin is unloaded."""
    global _terrai
    _terrai = None
    logger.info("TerraAI plugin unloaded")


def _get_terra() -> TerraAI:
    """Get the global TerraAI instance."""
    if _terrai is None:
        raise RuntimeError("TerraAI not initialized")
    return _terrai


def _server_name(trigger: Trigger) -> str:
    """Get the server name from a SOPEL trigger."""
    return trigger.sender.nick if hasattr(trigger, 'sender') and hasattr(trigger.sender, 'nick') else "unknown"


def _channel_name(trigger: Trigger) -> str:
    """Get the channel name from a SOPEL trigger."""
    return trigger.sender if hasattr(trigger, 'sender') else "#unknown"


def _nick(trigger: Trigger) -> str:
    """Get the nick from a SOPEL trigger."""
    return trigger.nick if hasattr(trigger, 'nick') else "unknown"


@sopel.module.rule("^TerraAI[:,] (.*)")
def handle_trigger(bot, trigger):
    """Handle 'TerraAI: message' trigger."""
    terra = _get_terra()
    server = _server_name(trigger)
    channel = _channel_name(trigger)
    nick = _nick(trigger)
    text = trigger.group(1)

    if not terra.should_respond(server, nick, text):
        return

    # Check management commands first
    if terra.is_management_command(text):
        response = terra.handle_management(server, channel, nick, f".{text}")
    else:
        response = terra.handle_ai_message(server, channel, nick, text)

    if response:
        bot.say(response)


@sopel.module.rule(r"^\.(\w+)(?: (.+))?$")
def handle_shorthand(bot, trigger):
    """Handle '.command' shorthand."""
    terra = _get_terra()
    server = _server_name(trigger)
    channel = _channel_name(trigger)
    nick = _nick(trigger)

    if not terra.should_respond(server, nick, None):
        return

    text = trigger.group(0)
    command = trigger.group(1)
    args = trigger.group(2) or ""

    # Check management commands first
    if terra.is_management_command(text):
        response = terra.handle_management(server, channel, nick, text)
        if response:
            bot.say(response)
        return

    # Custom prompt check
    prompt_response = terra.prompts.match_prompt(server, text)
    if prompt_response:
        bot.say(prompt_response)
        return

    # .ai command — context-free
    if command == "ai":
        ai_text = args
        response = terra.handle_ai_message(server, channel, nick, ai_text, include_history=False)
        bot.say(response)
        return

    # Anything else — route to AI
    full_text = f"{command}" + (f" {args}" if args else "")
    response = terra.handle_ai_message(server, channel, nick, full_text)
    if response:
        bot.say(response)
