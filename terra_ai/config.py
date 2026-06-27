"""Configuration for TerraAI plugin.

Uses SOPEL's native StaticSection config system.
All settings live in the [terraai] section of the SOPEL .cfg file.

Command prefix routing is handled by SOPEL's ``settings.core.prefix`` and
``$nick`` rules — there is no ``trigger_char`` or ``trigger_phrase`` in the
TerraAI config section.
"""

from sopel.config import types


class TerraAISection(types.StaticSection):
    """SOPEL config section for the TerraAI plugin.

    Defined in the [terraai] section of the SOPEL config file (.cfg).
    All fields have sensible defaults — the plugin works with zero
    configuration beyond enabling it.

    Note: ``trigger_char`` and ``trigger_phrase`` have been removed.
    SOPEL's ``settings.core.prefix`` handles command prefix routing,
    and ``$nick`` rules handle addressed freeform queries.
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

    bot_nick = types.ValidatedAttribute(
        'bot_nick', default='',
    )
    """Bot nick for prompt interpolation. Empty = use SOPEL's nick."""

    effort = types.ValidatedAttribute(
        'effort', default='high',
    )
    """Default reasoning effort level (low/medium/high/xhigh/max)."""

    # ── Storage ────────────────────────────────────────────────────────

    sqlite_path = types.ValidatedAttribute(
        'sqlite_path', default='data/terraai.db',
    )
    """Path to the SQLite database file."""
