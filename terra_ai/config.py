"""Configuration for TerraAI plugin.

Uses SOPEL's native StaticSection config system.
All settings live in the [terraai] section of the SOPEL .cfg file.
"""

from sopel.config import types
from sopel.config import Config as SopelConfig


def load_config(path):
    """Load a SOPEL config file and return the terraai section.

    Falls back to a default TerraAISection if the file is missing or
    doesn't define a [terraai] section.
    """
    try:
        sopel_config = SopelConfig(path)
        sopel_config.define_section("terraai", TerraAISection)
        return sopel_config.terraai
    except Exception:
        section = TerraAISection.__new__(TerraAISection)
        section.model = "openrouter/owl-alpha"
        section.api_key = ""
        section.base_url = "https://openrouter.ai/api/v1"
        section.provider_timeout = 30
        section.trigger_phrase = "TerraAI:"
        section.bot_nick = ""
        section.trigger_char = "."
        section.effort = "high"
        section.sqlite_path = "data/terraai.db"
        return section


class TerraAISection(types.StaticSection):
    """SOPEL config section for the TerraAI plugin.

    Defined in the [terraai] section of the SOPEL config file (.cfg).
    All fields have sensible defaults — the plugin works with zero
    configuration beyond enabling it.
    """

    # ── Provider settings ──────────────────────────────────────────────

    model = types.ValidatedAttribute(
        'model', default='openrouter/owl-alpha',
    )
    """AI model to use via OpenRouter."""

    api_key = types.SecretAttribute(
        'api_key', default='',
    )
    """OpenRouter API key. Can also be set via OPENROUTER_API_KEY env var."""

    base_url = types.ValidatedAttribute(
        'base_url', default='https://openrouter.ai/api/v1',
    )
    """OpenRouter API base URL."""

    provider_timeout = types.ValidatedAttribute(
        'provider_timeout', parse=int, default=30,
    )
    """HTTP timeout for provider API calls (seconds)."""

    # ── Bot behavior ───────────────────────────────────────────────────

    trigger_phrase = types.ValidatedAttribute(
        'trigger_phrase', default='TerraAI:',
    )
    """Trigger phrase for addressed queries (e.g. 'TerraAI: hello')."""

    bot_nick = types.ValidatedAttribute(
        'bot_nick', default='',
    )
    """Bot nick for prompt interpolation. Empty = use SOPEL's nick."""

    trigger_char = types.ValidatedAttribute(
        'trigger_char', default='.',
    )
    """Command prefix character (e.g. '.' for .optin, '-' for -optin)."""

    effort = types.ValidatedAttribute(
        'effort', default='high',
    )
    """Default reasoning effort level (low/medium/high/xhigh/max)."""

    # ── Storage ────────────────────────────────────────────────────────

    sqlite_path = types.ValidatedAttribute(
        'sqlite_path', default='data/terraai.db',
    )
    """Path to the SQLite database file."""
