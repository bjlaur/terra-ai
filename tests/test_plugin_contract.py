"""Plugin-level characterization tests for TerraAI's routing contract.

These tests enter through :func:`terra_ai.plugin.dispatch_line` and SOPEL's
rule manager. External provider behavior is replaced at the boundary; routing,
guards, identity handling, history, and plugin error handling remain real.
"""

import logging
import re
from unittest.mock import MagicMock, patch

import pytest

from terra_ai import plugin as terra_plugin
from terra_ai.prompts.defaults import IRC_SAFE_BYTES
from test_tool.console import _build_fake_bot


@pytest.fixture
def plugin_bot(terra):
    """A SOPEL-compatible bot with the production plugin rules registered."""
    return _build_fake_bot()


def dispatch(plugin_bot, text, *, nick="tester", is_pm=False):
    """Send one IRC message through the production plugin dispatcher."""
    return terra_plugin.dispatch_line(
        plugin_bot,
        nick,
        text,
        is_pm=is_pm,
    )


@pytest.mark.mock
def test_ordinary_channel_traffic_is_completely_ignored(
    terra, plugin_bot, caplog
):
    """Unaddressed channel text must not cross any downstream boundary."""
    private_text = "ordinary private channel text 7c3c8f"
    provider = terra.registry.get()

    terra.handle_ai_message = MagicMock(name="handle_ai_message")
    provider.chat = MagicMock(name="provider_chat")
    terra.context.compose_context = MagicMock(name="compose_context")
    terra.context.save_exchange = MagicMock(name="save_exchange")
    terra.prompts.get_context_seed = MagicMock(name="get_context_seed")

    with patch("terra_ai.tools.executor.execute_tool") as execute_tool:
        with caplog.at_level(logging.DEBUG, logger="terraai"):
            result = dispatch(plugin_bot, private_text)

    assert result == {"say": [], "notice": []}
    terra.handle_ai_message.assert_not_called()
    provider.chat.assert_not_called()
    terra.context.compose_context.assert_not_called()
    terra.context.save_exchange.assert_not_called()
    terra.prompts.get_context_seed.assert_not_called()
    execute_tool.assert_not_called()
    assert private_text not in caplog.text


@pytest.mark.mock
def test_addressed_channel_prompt_routes_exactly_once(terra, plugin_bot):
    terra.handle_ai_message = MagicMock(return_value="addressed response")

    result = dispatch(plugin_bot, "TerraAI: hello there")

    assert result["say"] == ["addressed response"]
    terra.handle_ai_message.assert_called_once()
    args, kwargs = terra.handle_ai_message.call_args
    assert args == ("test-network", "#terra-ai", "tester", "hello there")
    assert callable(kwargs["noisy_callback"])


@pytest.mark.mock
def test_unknown_prefixed_channel_prompt_routes_exactly_once(terra, plugin_bot):
    terra.handle_ai_message = MagicMock(return_value="prefixed response")

    result = dispatch(plugin_bot, "-explain sqlite")

    assert result["say"] == ["prefixed response"]
    terra.handle_ai_message.assert_called_once()
    args, kwargs = terra.handle_ai_message.call_args
    assert args == ("test-network", "#terra-ai", "tester", "explain sqlite")
    assert callable(kwargs["noisy_callback"])


@pytest.mark.mock
@pytest.mark.parametrize(
    ("text", "expected_text"),
    [
        ("hello from PM", "hello from PM"),
        ("-explain sqlite", "explain sqlite"),
    ],
)
def test_pm_prompts_route_exactly_once(terra, plugin_bot, text, expected_text):
    terra.handle_ai_message = MagicMock(return_value="PM response")

    result = dispatch(plugin_bot, text, is_pm=True)

    assert result["say"] == ["PM response"]
    terra.handle_ai_message.assert_called_once()
    args, kwargs = terra.handle_ai_message.call_args
    assert args == ("test-network", "tester", "tester", expected_text)
    assert callable(kwargs["noisy_callback"])


@pytest.mark.mock
def test_registered_management_command_does_not_also_route_to_ai(
    terra, plugin_bot
):
    terra.handle_ai_message = MagicMock(return_value="unexpected AI response")

    result = dispatch(plugin_bot, "-optin")

    assert len(result["say"]) == 1
    assert "opted in" in result["say"][0]
    terra.handle_ai_message.assert_not_called()


@pytest.mark.mock
@pytest.mark.parametrize(
    ("text", "is_pm"),
    [
        ("TerraAI: hello", False),
        ("-explain sqlite", False),
        ("hello in PM", True),
        ("-setlocation Detroit, MI", False),
    ],
)
def test_opted_out_user_cannot_reach_ai(terra, plugin_bot, text, is_pm):
    terra.user.handle_optout("test-network", "tester")
    terra.handle_ai_message = MagicMock(return_value="unexpected AI response")

    result = dispatch(plugin_bot, text, is_pm=is_pm)

    assert result == {"say": [], "notice": []}
    terra.handle_ai_message.assert_not_called()


@pytest.mark.mock
def test_self_message_cannot_reach_ai(terra, plugin_bot):
    terra.handle_ai_message = MagicMock(return_value="unexpected AI response")

    result = dispatch(plugin_bot, "TerraAI: hello", nick="TerraAI")

    assert result == {"say": [], "notice": []}
    terra.handle_ai_message.assert_not_called()


@pytest.mark.mock
def test_plugin_path_adds_identity_once_and_persists_model_visible_history(
    terra, plugin_bot
):
    provider = terra.registry.get()
    provider.chat = MagicMock(return_value="hello back")

    result = dispatch(plugin_bot, "TerraAI: hello")

    assert result["say"] == ["hello back"]
    provider.chat.assert_called_once()
    messages = provider.chat.call_args.args[0]
    user_messages = [m.content for m in messages if m.role == "user"]
    assert user_messages[-1] == "<tester> hello"
    assert "<tester> <tester>" not in user_messages[-1]

    history = terra.context.history.recent("test-network", "#terra-ai")
    assert [(row["role"], row["content"]) for row in history] == [
        ("user", "<tester> hello"),
        ("assistant", "hello back"),
    ]


@pytest.mark.mock
def test_context_free_ai_command_does_not_read_or_write_history(
    terra, plugin_bot
):
    terra.context.save_exchange(
        "test-network", "#terra-ai", "tester", "old prompt", "old response"
    )
    provider = terra.registry.get()
    provider.chat = MagicMock(return_value="fresh response")

    result = dispatch(plugin_bot, "-ai fresh prompt")

    assert result["say"] == ["fresh response"]
    messages = provider.chat.call_args.args[0]
    assert [m.content for m in messages if m.role == "user"] == [
        "<tester> fresh prompt"
    ]
    history = terra.context.history.recent("test-network", "#terra-ai")
    assert [(row["role"], row["content"]) for row in history] == [
        ("user", "old prompt"),
        ("assistant", "old response"),
    ]


@pytest.mark.mock
def test_unhandled_plugin_error_is_logged_and_reported_once(
    terra, plugin_bot, caplog
):
    terra.handle_ai_message = MagicMock(side_effect=RuntimeError("boom"))

    with caplog.at_level(logging.ERROR, logger="terraai"):
        result = dispatch(plugin_bot, "TerraAI: hello")

    assert result["say"] == ["Error: boom"]
    assert caplog.text.count("RuntimeError: boom") == 1
    assert "Traceback" in caplog.text


@pytest.mark.mock
@pytest.mark.xfail(
    strict=True,
    reason="Phase 2 pending contract: correlated IRC errors with source locations",
)
def test_phase2_error_reply_and_log_share_correlation_and_source(
    terra, plugin_bot, caplog
):
    """Pending Phase 2 contract for correlated, locatable IRC errors."""
    terra.handle_ai_message = MagicMock(side_effect=RuntimeError("boom"))

    with caplog.at_level(logging.ERROR, logger="terraai"):
        result = dispatch(plugin_bot, "TerraAI: hello")

    match = re.fullmatch(
        r"Error \[(?P<correlation>[0-9a-f]{8}) "
        r"(?P<source>[^\]]+\.py:\d+)\]: RuntimeError: boom",
        result["say"][0],
    )
    assert match is not None
    assert match.group("correlation") in caplog.text


@pytest.mark.mock
def test_oversize_response_is_rewritten_before_plugin_reply(terra, plugin_bot):
    provider = terra.registry.get()
    provider.chat = MagicMock(
        side_effect=["x" * (IRC_SAFE_BYTES + 1), "short response"]
    )

    result = dispatch(plugin_bot, "TerraAI: be concise")

    assert result["say"] == ["short response"]
    assert provider.chat.call_count == 2
    assert len(result["say"][0].encode("utf-8")) <= IRC_SAFE_BYTES
    history = terra.context.history.recent("test-network", "#terra-ai")
    assert history[-1]["content"] == "short response"
