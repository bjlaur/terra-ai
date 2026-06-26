"""Shared test fixtures.

Mock vs Real provider:

- By default, all routing tests use a mocked OpenRouterProvider.chat()
  that returns instantly — no real API calls, ~0.01s per test.

- To run against the real API, pass --real on the command line.
  Only tests marked @pytest.mark.real will hit the real provider.
  Requires OPENROUTER_API_KEY to be set.
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
        trigger_phrase="TerraAI:",
        bot_nick="",
        trigger_char=".",
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
    """TerraAI instance with mock provider by default.

    When --real is passed AND the test is marked @pytest.mark.real,
    the real OpenRouter provider is used (requires OPENROUTER_API_KEY).
    Otherwise, provider.chat() is patched to return a mock response.
    """
    use_real = (
        request.config.getoption("--real")
        and bool(os.environ.get("OPENROUTER_API_KEY"))
        and request.node.get_closest_marker("real") is not None
    )

    config = _make_test_config(sqlite_path=db.config.path)
    t = TerraAI(config)

    if use_real:
        # Real API — set effort to low for speed
        t.prompts.set_effort("low")
    else:
        # Mock — patch provider.chat() to return instantly
        original_chat = OpenRouterProvider.chat

        def mock_chat(self, messages, system_prompt=None, effort="high"):
            return "mocked AI response"

        OpenRouterProvider.chat = mock_chat
        request.addfinalizer(lambda: setattr(OpenRouterProvider, "chat", original_chat))

    # So plugin handlers (_get_terra()) work in tests
    terra_plugin._terrai = t
    request.addfinalizer(lambda: setattr(terra_plugin, "_terrai", None))

    return t
