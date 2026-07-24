"""Shared pytest configuration and explicitly owned application fixtures."""

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
from terra_ai.providers.pacing import RequestPacer
from terra_ai.providers.registry import ProviderRegistry
from tests.support import PluginTestClient, build_fake_bot
from tests.http_fakes import ScriptedServices
from tests.benchmarking import BenchmarkCase, OUTPUT_ENV_VAR, write_record
from tests.model_selection import resolve_test_model


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


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach pytest's final outcome to any captured benchmark scenario."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return

    record = getattr(item, "_terra_benchmark_record", None)
    if record is None:
        return

    record["passed"] = report.passed
    if not report.passed:
        record["failure_reason"] = str(report.longrepr)

    output_path = os.environ.get(OUTPUT_ENV_VAR)
    if output_path:
        write_record(Path(output_path), record)


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
    parser.addoption(
        "--model",
        default=None,
        metavar="MODEL",
        help="Override the real-service test model",
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


def _load_sopel_test_cfg(pytest_config=None):
    """Return the resolved real-service model and current API key."""
    cli_model = pytest_config.getoption("--model") if pytest_config else None
    model = resolve_test_model(PROJECT_ROOT, cli_model=cli_model)
    return model, os.environ.get("OPENROUTER_API_KEY", "")


def _make_test_config(**overrides):
    """Build deterministic application configuration without reading secrets."""
    values = {
        "model": "test/model",
        "api_key": "test-key",
        "base_url": "https://openrouter.ai/api/v1",
        "provider_timeout": 30,
        "provider_requests_per_minute": 0.0,
        "provider_min_interval": 0.0,
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


def _test_pacing_values() -> tuple[float, float]:
    """Return live-test pacing values from the test-only environment."""
    return (
        float(os.environ.get("TERRAI_TEST_PROVIDER_RPM", "0")),
        float(os.environ.get("TERRAI_TEST_PROVIDER_MIN_INTERVAL", "0")),
    )


@pytest.fixture(scope="session")
def real_request_pacer():
    """One request pacer shared by every direct real-test provider."""
    requests_per_minute, min_interval = _test_pacing_values()
    return RequestPacer(
        requests_per_minute=requests_per_minute,
        min_interval=min_interval,
    )


@pytest.fixture
def terra(tmp_path, request, real_request_pacer):
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
        model, api_key = _load_sopel_test_cfg(request.config)
        if not api_key:
            pytest.fail("OPENROUTER_API_KEY is required with --real")
        provider_timeout = int(os.environ.get("TERRAI_TEST_TIMEOUT", "30"))
    else:
        model, api_key = "test/model", "test-key"
        provider_timeout = 30

    config = _make_test_config(
        model=model,
        api_key=api_key,
        provider_timeout=provider_timeout,
        provider_requests_per_minute=(
            real_request_pacer.requests_per_minute if use_real else 0.0
        ),
        provider_min_interval=(
            real_request_pacer.min_interval if use_real else 0.0
        ),
        sqlite_path=str(tmp_path / "terraai.db"),
    )
    provider = OpenRouterProvider(
        model=config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.provider_timeout,
        request_pacer=real_request_pacer if use_real else None,
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
def benchmark_case(request):
    """Create one timed benchmark record for the current pytest item."""
    is_ergo = request.config.getoption("--ergo")
    is_real = request.config.getoption("--real")
    suite = "ergo" if is_ergo else "real"
    model = (
        resolve_test_model(
            PROJECT_ROOT,
            cli_model=request.config.getoption("--model"),
        )
        if is_real or is_ergo
        else "test/model"
    )
    created = False

    def create(scenario: str) -> BenchmarkCase:
        nonlocal created
        if created:
            raise RuntimeError("only one benchmark case is allowed per test")
        created = True
        return BenchmarkCase(
            request.node,
            scenario=scenario,
            suite=suite,
            model=model,
        )

    return create


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
