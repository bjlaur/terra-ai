"""Shared configuration for automated and manual SOPEL/Ergo testing."""

import configparser
import os
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
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
    "coretasks",
    "terra_ai",
)


@lru_cache
def get_test_run_directory(mode: str = "ergo") -> Path:
    """Return the sortable, private artifact directory for this test run."""
    configured = os.environ.get("TERRAI_TEST_RUN_DIR")
    if configured:
        directory = Path(configured)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        directory = (
            Path(tempfile.gettempdir())
            / "terraai-tests"
            / f"{stamp}-{mode}-{os.getpid()}"
        )
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    return directory


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
    log_dir: Path | None = None,
) -> Path:
    """Write the private config shared by Ergo tests and manual mode."""
    log_dir = log_dir or get_test_run_directory()
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
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
logdir = {log_dir}
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
log_dir = {log_dir / 'terra-ai'}
"""
    config_file = directory / "sopel.cfg"
    config_file.write_text(content)
    config_file.chmod(0o600)
    return config_file
