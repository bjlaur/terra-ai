"""Shared test fixtures.

Mock vs Real provider:

- By default, all routing tests use a mocked OpenRouterProvider.chat()
  that returns instantly — no real API calls, ~0.01s per test.

- To run against the real API, pass --real on the command line.
  Only tests marked @pytest.mark.real will hit the real provider.
  Requires OPENROUTER_API_KEY to be set.

- Tests marked @pytest.mark.mock always use the mock provider,
  even when --real is passed.

- Tests with no marker default to mock behavior.

Run mock tests (default):  pytest
Run real API tests:         pytest --real -m real
Run everything:              pytest --real
"""

import os
import tempfile
from types import SimpleNamespace

import pytest

from terra_ai.bot import TerraAI
from terra_ai.database import DBConfig, Database
from terra_ai.providers.openrouter import OpenRouterProvider
from terra_ai import plugin as terra_plugin


def pytest_addoption(parser):
    parser.addoption(
        "--real", action="store_true", default=False,
        help="Run tests that hit the real OpenRouter API",
    )


def _make_test_config(**overrides):
    """Create a lightweight config with TerraAISection defaults.

    Tests don't have a running SOPEL bot, so we use a SimpleNamespace
    with the same attributes as TerraAISection.
    """
    defaults = dict(
        model="openrouter/owl-alpha",
        api_key=os.environ.get("OPENROUTER_API_KEY", "test-key"),
        base_url="https://openrouter.ai/api/v1",
        provider_timeout=30,
        bot_nick="",
        effort="high",
        sqlite_path="data/terraai.db",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def db():
    """Temp SQLite database — cleaned up after test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    config = DBConfig(path=path, wal=False)
    database = Database(config)
    yield database
    os.unlink(path)


@pytest.fixture
def terra(db, request):
    """TerraAI instance — mock or real depending on markers.

    Rules:
    - @pytest.mark.mock → mock provider (always, even with --real)
    - @pytest.mark.real + --real + key → real provider
    - @pytest.mark.real without --real or key → skip
    - No marker → mock provider (default)
    """
    has_key = bool(os.environ.get("OPENROUTER_API_KEY"))
    marker_real = request.node.get_closest_marker("real")
    marker_mock = request.node.get_closest_marker("mock")

    if marker_real is not None:
        if not request.config.getoption("--real"):
            pytest.skip("@pytest.mark.real requires --real flag")
        if not has_key:
            pytest.skip("@pytest.mark.real requires OPENROUTER_API_KEY")
        use_real = True
    elif marker_mock is not None:
        use_real = False
    else:
        # No marker → default mock
        use_real = False

    config = _make_test_config(sqlite_path=db.config.path)
    t = TerraAI(config)

    if not use_real:
        # Mock — patch provider.chat() to return instantly
        original_chat = OpenRouterProvider.chat

        def mock_chat(self, messages, system_prompt=None, effort="high",
                      tools=None, max_tool_rounds=5):
            return "mocked AI response"

        OpenRouterProvider.chat = mock_chat
        request.addfinalizer(lambda: setattr(OpenRouterProvider, "chat", original_chat))
    else:
        # Real API — set effort to low for speed
        t.prompts.set_effort("low")

    # So plugin handlers (_get_terra()) work in tests
    terra_plugin._terrai = t
    request.addfinalizer(lambda: setattr(terra_plugin, "_terrai", None))

    return t
