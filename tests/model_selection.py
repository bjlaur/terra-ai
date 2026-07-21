"""Shared test-model selection for real, Ergo, and manual workflows."""

from __future__ import annotations

import configparser
import os
from collections.abc import Mapping
from pathlib import Path


MODEL_ENV_VAR = "TERRAI_TEST_MODEL"


def load_configured_model(project_dir: Path) -> str:
    """Read the fallback model from config/sopel-test.cfg."""
    config_path = Path(project_dir) / "config" / "sopel-test.cfg"
    if not config_path.exists():
        raise RuntimeError(
            "config/sopel-test.cfg not found; copy the example and set "
            "[terraai] model"
        )

    parser = configparser.ConfigParser()
    parser.read(config_path)
    model = parser.get("terraai", "model", fallback="").strip()
    if not model:
        raise RuntimeError("[terraai] model is empty in config/sopel-test.cfg")
    return model


def resolve_test_model(
    project_dir: Path,
    *,
    cli_model: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Resolve CLI > TERRAI_TEST_MODEL > config/sopel-test.cfg."""
    if cli_model and cli_model.strip():
        return cli_model.strip()

    environment = os.environ if environ is None else environ
    env_model = environment.get(MODEL_ENV_VAR, "").strip()
    if env_model:
        return env_model

    return load_configured_model(project_dir)
