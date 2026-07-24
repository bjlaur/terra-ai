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
        'model', default=None,
    )
    """AI model to use via OpenRouter. REQUIRED — no default.

    TerraAI is model-agnostic: the operator MUST set ``model`` in the
    [terraai] section (e.g. ``tencent/hy3:free``). An empty model fails
    loudly at startup rather than silently sending an invalid request.
    """

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

    provider_requests_per_minute = types.ValidatedAttribute(
        'provider_requests_per_minute', parse=float, default=0.0,
    )
    """Maximum evenly spaced provider request starts per minute; 0 disables."""

    provider_min_interval = types.ValidatedAttribute(
        'provider_min_interval', parse=float, default=0.0,
    )
    """Minimum seconds between provider request starts; 0 disables."""

    provider_call_log_enabled = types.BooleanAttribute(
        'provider_call_log_enabled', default=True,
    )
    """Write compact structured provider-attempt telemetry."""

    provider_call_log_max_bytes = types.ValidatedAttribute(
        'provider_call_log_max_bytes', parse=int, default=25 * 1024 * 1024,
    )
    provider_call_log_backup_count = types.ValidatedAttribute(
        'provider_call_log_backup_count', parse=int, default=2,
    )

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

    # ── Logging ────────────────────────────────────────────────────────

    log_dir = types.FilenameAttribute(
        'log_dir', directory=True, default='data/logs',
    )
    """Directory for TerraAI's operational and OpenRouter trace logs."""

    log_max_bytes = types.ValidatedAttribute(
        'log_max_bytes', parse=int, default=10 * 1024 * 1024,
    )
    log_backup_count = types.ValidatedAttribute(
        'log_backup_count', parse=int, default=5,
    )
    trace_log_max_bytes = types.ValidatedAttribute(
        'trace_log_max_bytes', parse=int, default=25 * 1024 * 1024,
    )
    trace_log_backup_count = types.ValidatedAttribute(
        'trace_log_backup_count', parse=int, default=2,
    )
