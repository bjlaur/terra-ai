"""Offline tests for generated SOPEL test configuration."""

from tests.sopel_harness import write_sopel_test_config


def test_generated_config_contains_provider_pacing_values(tmp_path):
    config = write_sopel_test_config(
        tmp_path,
        project_dir=tmp_path,
        model="test/model",
        api_key="test-key",
        sqlite_path=tmp_path / "terra.db",
        provider_timeout=30,
        provider_requests_per_minute=20,
        provider_min_interval=3.5,
        log_dir=tmp_path / "logs",
    )

    content = config.read_text()
    assert "provider_requests_per_minute = 20" in content
    assert "provider_min_interval = 3.5" in content
