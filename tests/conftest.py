"""Shared pytest configuration and explicitly owned application fixtures."""

import configparser
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from terra_ai import plugin as terra_plugin
from terra_ai.bot import TerraAI
from terra_ai.providers.openrouter import OpenRouterProvider
from terra_ai.providers.registry import ProviderRegistry
from tests.support import PluginTestClient, build_fake_bot
from tests.http_fakes import ScriptedServices


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROGRESS_PATH = None


def _write_test_progress(message):
    if _PROGRESS_PATH is None:
        return
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _PROGRESS_PATH.open("a", encoding="utf-8") as progress:
        progress.write(f"{timestamp} {message}\n")


def pytest_configure(config):
    """Initialize the optional per-test progress log used by test.sh."""
    global _PROGRESS_PATH
    progress_file = os.environ.get("TERRAI_PYTEST_PROGRESS_FILE")
    _PROGRESS_PATH = Path(progress_file) if progress_file else None
    _write_test_progress("SESSION START")


def pytest_runtest_logstart(nodeid, location):
    _write_test_progress(f"START {nodeid}")


def pytest_runtest_logreport(report):
    if report.failed:
        _write_test_progress(f"FAIL {report.nodeid} phase={report.when}")
    elif report.skipped:
        _write_test_progress(f"SKIP {report.nodeid} phase={report.when}")
    elif report.when == "call":
        _write_test_progress(f"PASS {report.nodeid}")


def pytest_sessionfinish(session, exitstatus):
    _write_test_progress(f"SESSION END exitstatus={exitstatus}")


def pytest_addoption(parser):
    parser.addoption(
        "--real",
        action="store_true",
        default=False,
        help="Use real external services for selected service E2E tests",
    )
    parser.addoption(
        "--ergo",
        action="store_true",
        default=False,
        help="Run the always-real Ergo/SOPEL system tests",
    )


def pytest_collection_modifyitems(config, items):
    """Make external-service selection explicit and independent of addopts."""
    run_real = config.getoption("--real")
    run_ergo = config.getoption("--ergo")
    skip_real = pytest.mark.skip(reason="real-service test requires --real")
    skip_ergo = pytest.mark.skip(reason="Ergo system test requires --ergo")

    for item in items:
        is_ergo = Path(str(item.fspath)).name == "test_ergo.py"
        if is_ergo:
            item.add_marker("ergo")
            item.add_marker("real")
            if not run_ergo:
                item.add_marker(skip_ergo)
            continue
        if item.get_closest_marker("real") and not run_real:
            item.add_marker(skip_real)


def _load_sopel_test_cfg():
    """Return the configured real-service model and current API key."""
    cfg_path = PROJECT_ROOT / "config" / "sopel-test.cfg"
    if not cfg_path.exists():
        raise RuntimeError(
            "config/sopel-test.cfg not found. Copy the example and set "
            "[terraai] model before running real-service tests."
        )
    parser = configparser.ConfigParser()
    parser.read(cfg_path)
    model = parser.get("terraai", "model", fallback="").strip()
    if not model:
        raise RuntimeError("[terraai] model is empty in config/sopel-test.cfg")
    return model, os.environ.get("OPENROUTER_API_KEY", "")


def _make_test_config(**overrides):
    """Build deterministic application configuration without reading secrets."""
    values = {
        "model": "test/model",
        "api_key": "test-key",
        "base_url": "https://openrouter.ai/api/v1",
        "provider_timeout": 30,
        "bot_nick": "TerraAI",
        "effort": "high",
        "sqlite_path": "data/test-terraai.db",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def deny_unselected_network(request, monkeypatch):
    """Fail immediately if an offline test attempts a network connection."""
    is_real = bool(
        request.node.get_closest_marker("real")
        or request.node.get_closest_marker("e2e")
    )
    is_ergo = Path(str(request.node.fspath)).name == "test_ergo.py"
    if (is_real and request.config.getoption("--real")) or (
        is_ergo and request.config.getoption("--ergo")
    ):
        return

    def blocked_connect(sock, address):
        raise AssertionError(
            f"offline test attempted network connection to {address!r}; "
            "mock the external transport or mark/select it as real"
        )

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked_connect)


@pytest.fixture
def terra(tmp_path, request):
    """One TerraAI instance, one database connection, and deterministic teardown."""
    use_real = bool(
        (
            request.node.get_closest_marker("real")
            or request.node.get_closest_marker("e2e")
        )
        and request.config.getoption("--real")
        and not request.node.get_closest_marker("mock")
    )
    if use_real:
        model, api_key = _load_sopel_test_cfg()
        if not api_key:
            pytest.fail("OPENROUTER_API_KEY is required with --real")
    else:
        model, api_key = "test/model", "test-key"

    config = _make_test_config(
        model=model,
        api_key=api_key,
        sqlite_path=str(tmp_path / "terraai.db"),
    )
    provider = OpenRouterProvider(
        model=config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.provider_timeout,
    )
    instance = TerraAI(config, ProviderRegistry(provider))
    previous = terra_plugin._terrai
    terra_plugin._terrai = instance
    try:
        yield instance
    finally:
        terra_plugin._terrai = previous
        instance.close()


@pytest.fixture
def plugin_bot(terra):
    """Fresh SOPEL-compatible bot backed by the owned TerraAI fixture."""
    return build_fake_bot()


@pytest.fixture
def plugin_client(plugin_bot):
    return PluginTestClient(plugin_bot)


def _install_scripted_services(monkeypatch):
    real_client = httpx.Client
    scripted = ScriptedServices()
    transport = httpx.MockTransport(scripted)

    def client_with_scripted_transport(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_with_scripted_transport)
    return scripted


@pytest.fixture
def scripted_services(monkeypatch):
    """Always use deterministic HTTP, including during a broader real run."""
    return _install_scripted_services(monkeypatch)


@pytest.fixture
def service_transport(request, monkeypatch):
    """Select real services or deterministic HTTP at the transport boundary."""
    if (
        request.config.getoption("--real")
        and not request.node.get_closest_marker("mock")
    ):
        return None
    return _install_scripted_services(monkeypatch)
