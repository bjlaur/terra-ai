"""Shared configuration for automated and manual SOPEL/Ergo testing."""

import configparser
from pathlib import Path


ERGO_HOST = "127.0.0.1"
ERGO_PORT = 6667
TEST_CHANNEL = "#terra-ai-agent1"
BOT_NICK = "TerraAI"
COMMAND_PREFIX = "-"
PLUGIN_LIST = (
    "admin",
    "adminchannel",
    "ping",
    "reload",
    "safety",
    "coretasks",
    "terra_ai",
)


def load_test_model(project_dir: Path) -> str:
    config_path = project_dir / "config" / "sopel-test.cfg"
    if not config_path.exists():
        raise RuntimeError(
            "config/sopel-test.cfg not found; copy the example and set the model"
        )
    parser = configparser.ConfigParser()
    parser.read(config_path)
    model = parser.get("terraai", "model", fallback="").strip()
    if not model:
        raise RuntimeError("[terraai] model is empty in config/sopel-test.cfg")
    return model


def write_sopel_test_config(
    directory: Path,
    *,
    project_dir: Path,
    model: str,
    api_key: str,
    sqlite_path: Path,
    provider_timeout: int,
) -> Path:
    """Write the private config shared by Ergo tests and manual mode."""
    plugins = "\n    ".join(PLUGIN_LIST)
    content = f"""[core]
nick = {BOT_NICK}
host = {ERGO_HOST}
port = {ERGO_PORT}
use_ssl = false
owner = agent1
channels = {TEST_CHANNEL}
prefix = {COMMAND_PREFIX}
help_prefix = {COMMAND_PREFIX}
logging_level = DEBUG
extra = {project_dir}
enable =
    {plugins}

[terraai]
model = {model}
api_key = {api_key}
base_url = https://openrouter.ai/api/v1
provider_timeout = {provider_timeout}
bot_nick = {BOT_NICK}
effort = high
sqlite_path = {sqlite_path}
"""
    config_file = directory / "sopel.cfg"
    config_file.write_text(content)
    config_file.chmod(0o600)
    return config_file
