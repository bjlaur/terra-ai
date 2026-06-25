"""Configuration loader for TerraAI."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ProviderConfig:
    name: str = "openrouter"
    model: str = "google/gemini-2.0-flash-001"
    api_key: str | None = None
    base_url: str | None = None
    timeout: int = 30


@dataclass
class TerraConfig:
    bot: dict = field(default_factory=dict)
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    sqlite_path: str = "data/terraai.db"
    admin_nicks: list[str] = field(default_factory=list)
    rate_limit_enabled: bool = False
    rate_limit_messages: int = 5
    rate_limit_window_seconds: int = 60

    def __post_init__(self):
        if isinstance(self.provider, dict):
            self.provider = ProviderConfig(**self.provider)
        if isinstance(self.bot, dict):
            self.bot.setdefault("trigger_phrase", "TerraAI:")
            self.bot.setdefault("bot_nick", "TerraAI")
            self.bot.setdefault("max_context_messages", 50)
            self.bot.setdefault("irc_char_limit", 400)

    def resolve_env(self):
        """Resolve ${ENV_VAR} references in provider.api_key."""
        if self.provider.api_key and self.provider.api_key.startswith("${") and self.provider.api_key.endswith("}"):
            env_var = self.provider.api_key[2:-1]
            self.provider.api_key = os.environ.get(env_var)
        return self


def load_config(path: str | Path) -> TerraConfig:
    """Load and validate configuration from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    config = TerraConfig(**raw or {})
    config.resolve_env()
    return config
