from pathlib import Path

import pytest

from tests.model_selection import load_configured_model, resolve_test_model


def _write_config(project_dir: Path, model: str) -> None:
    config_dir = project_dir / "config"
    config_dir.mkdir()
    (config_dir / "sopel-test.cfg").write_text(
        f"[terraai]\nmodel = {model}\n", encoding="utf-8"
    )


def test_cli_model_has_highest_precedence(tmp_path):
    _write_config(tmp_path, "config/model")
    assert resolve_test_model(
        tmp_path,
        cli_model=" cli/model ",
        environ={"TERRAI_TEST_MODEL": "env/model"},
    ) == "cli/model"


def test_environment_model_precedes_config(tmp_path):
    _write_config(tmp_path, "config/model")
    assert resolve_test_model(
        tmp_path, environ={"TERRAI_TEST_MODEL": " env/model "}
    ) == "env/model"


def test_config_model_is_fallback(tmp_path):
    _write_config(tmp_path, "config/model")
    assert resolve_test_model(tmp_path, environ={}) == "config/model"


def test_empty_overrides_fall_back_to_config(tmp_path):
    _write_config(tmp_path, "config/model")
    assert resolve_test_model(
        tmp_path,
        cli_model="  ",
        environ={"TERRAI_TEST_MODEL": "  "},
    ) == "config/model"


def test_missing_config_is_reported(tmp_path):
    with pytest.raises(RuntimeError, match="sopel-test.cfg not found"):
        load_configured_model(tmp_path)


def test_empty_config_model_is_reported(tmp_path):
    _write_config(tmp_path, "")
    with pytest.raises(RuntimeError, match="model is empty"):
        load_configured_model(tmp_path)
