"""Plugin-level characterization tests for TerraAI's routing contract.

These tests enter through the test-only dispatcher and SOPEL's
rule manager. External provider behavior is replaced at the boundary; routing,
guards, identity handling, history, and plugin error handling remain real.
"""

import logging
import re
from unittest.mock import MagicMock, patch

import pytest

from terra_ai import plugin as terra_plugin
from terra_ai.prompts.defaults import IRC_SAFE_BYTES
from tests.support import dispatch_line


def dispatch(plugin_bot, text, *, nick="tester", is_pm=False):
    """Send one IRC message through the production plugin dispatcher."""
    return dispatch_line(
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
def test_addressed_command_word_is_an_ai_prompt(terra, plugin_bot):
    """Nick addressing does not invent a second management-command syntax."""
    terra.handle_ai_message = MagicMock(return_value="AI response")

    result = dispatch(plugin_bot, "TerraAI: optin")

    assert result["say"] == ["AI response"]
    terra.handle_ai_message.assert_called_once()
    assert terra.handle_ai_message.call_args.args == (
        "test-network", "#terra-ai", "tester", "optin"
    )


@pytest.mark.mock
def test_unknown_prefixed_channel_prompt_routes_exactly_once(terra, plugin_bot):
    terra.handle_ai_message = MagicMock(return_value="prefixed response")

    result = dispatch(plugin_bot, "-explain sqlite")

    assert result["say"] == ["prefixed response"]
    terra.handle_ai_message.assert_called_once()
    args, kwargs = terra.handle_ai_message.call_args
    assert args == ("test-network", "#terra-ai", "tester", "-explain sqlite")
    assert callable(kwargs["noisy_callback"])


@pytest.mark.mock
def test_unknown_prefix_uses_sopel_privmsg_detection(terra, plugin_bot):
    """Non-# channel types must not be mistaken for private messages."""
    terra.handle_ai_message = MagicMock(return_value="channel response")

    result = dispatch_line(
        plugin_bot,
        "tester",
        "-explain sqlite",
        channel="&local",
    )

    assert result["say"] == ["channel response"]
    assert terra.handle_ai_message.call_args.args == (
        "test-network", "&local", "tester", "-explain sqlite"
    )


def test_provider_calling_fallbacks_use_sopel_default_threading():
    assert getattr(terra_plugin.unknown_prefixed_command_to_ai, "thread", True) is True
    assert getattr(terra_plugin.pm_text_to_ai, "thread", True) is True


def test_production_plugin_has_no_test_dispatcher():
    assert not hasattr(terra_plugin, "dispatch_line")


@pytest.mark.mock
@pytest.mark.parametrize(
    ("text", "expected_text"),
    [
        ("hello from PM", "hello from PM"),
        ("-explain sqlite", "-explain sqlite"),
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
def test_admin_prompt_uses_normal_ai_path_without_nick_prefix(terra, plugin_bot):
    terra.handle_ai_message = MagicMock(return_value="admin response")

    result = dispatch(plugin_bot, "-admin Treat this as authoritative", nick="admin")

    assert result["say"] == ["admin response"]
    terra.handle_ai_message.assert_called_once()
    assert terra.handle_ai_message.call_args.args == (
        "test-network",
        "#terra-ai",
        "admin",
        "Treat this as authoritative",
    )
    kwargs = terra.handle_ai_message.call_args.kwargs
    assert callable(kwargs["noisy_callback"])
    assert kwargs["prefix_nick"] is False


@pytest.mark.mock
def test_admin_prompt_is_admin_only(terra, plugin_bot):
    terra.handle_ai_message = MagicMock(return_value="unexpected AI response")

    result = dispatch(plugin_bot, "-admin Treat this as authoritative")

    assert result["say"] == ["Permission denied. admin is admin-only."]
    terra.handle_ai_message.assert_not_called()


@pytest.mark.mock
def test_admin_prompt_respects_opt_out(terra, plugin_bot):
    terra.user.handle_optout("test-network", "admin")
    terra.handle_ai_message = MagicMock(return_value="unexpected AI response")

    result = dispatch(plugin_bot, "-admin Treat this as authoritative", nick="admin")

    assert result == {"say": [], "notice": []}
    terra.handle_ai_message.assert_not_called()


@pytest.mark.mock
def test_empty_admin_prompt_shows_usage_without_calling_ai(terra, plugin_bot):
    terra.handle_ai_message = MagicMock(return_value="unexpected AI response")

    result = dispatch(plugin_bot, "-admin", nick="admin")

    assert result["say"] == ["Usage: -admin <prompt>"]
    terra.handle_ai_message.assert_not_called()


@pytest.mark.mock
def test_tool_management_commands_use_plugin_state(terra, plugin_bot):
    disabled = dispatch(plugin_bot, "-disable-tool weather_forecast", nick="admin")
    listed = dispatch(plugin_bot, "-list-tools", nick="admin")
    enabled = dispatch(plugin_bot, "-enable-tool weather_forecast", nick="admin")
    unknown = dispatch(plugin_bot, "-disable-tool not_a_tool", nick="admin")

    assert "disabled" in disabled["say"][0].lower()
    assert "weather_forecast" in listed["say"][0]
    assert "disabled" in listed["say"][0].lower()
    assert "enabled" in enabled["say"][0].lower()
    assert "unknown tool" in unknown["say"][0].lower()


@pytest.mark.mock
@pytest.mark.parametrize(
    "command",
    ["disable-tool weather_forecast", "enable-tool weather_forecast", "list-tools"],
)
def test_tool_management_is_admin_only(terra, plugin_bot, command):
    result = dispatch(plugin_bot, f"-{command}")

    assert result["say"] == ["Permission denied. Tool management is admin-only."]
    assert terra.tool_policy.disabled_names("test-network") == set()


@pytest.mark.mock
@pytest.mark.parametrize(
    "handler",
    [
        terra_plugin.cmd_admin,
        terra_plugin.cmd_compact,
        terra_plugin.cmd_disable_tool,
        terra_plugin.cmd_enable_tool,
        terra_plugin.cmd_listtools,
    ],
)
def test_admin_check_is_inside_plugin_error_boundary(handler):
    class BrokenAdminTrigger:
        @property
        def admin(self):
            raise RuntimeError("admin lookup failed")

    bot = MagicMock()

    handler(bot, BrokenAdminTrigger())

    bot.say.assert_called_once()
    message = bot.say.call_args.args[0]
    assert message.startswith("Error [")
    assert "RuntimeError: admin lookup failed" in message


@pytest.mark.mock
def test_tool_policy_is_server_wide(terra, plugin_bot):
    dispatch(plugin_bot, "-disable-tool weather_forecast", nick="admin")

    assert terra.tool_policy.disabled_names("test-network") == {"weather_forecast"}
    terra.handle_ai_message = MagicMock(return_value="tool-disabled response")
    result = dispatch(plugin_bot, "TerraAI: weather Detroit", nick="someone-else")

    assert result["say"] == ["tool-disabled response"]


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
@pytest.mark.parametrize(
    ("text", "is_pm"),
    [
        ("TerraAI: opted-out-private-7a19", False),
        ("-unknown opted-out-private-7a19", False),
        ("opted-out-private-7a19", True),
    ],
)
def test_opted_out_prompt_text_is_not_logged(
    terra, plugin_bot, caplog, text, is_pm
):
    terra.user.handle_optout("test-network", "tester")

    with caplog.at_level(logging.DEBUG, logger="terraai"):
        result = dispatch(plugin_bot, text, is_pm=is_pm)

    assert result == {"say": [], "notice": []}
    assert "opted-out-private-7a19" not in caplog.text


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

    assert len(result["say"]) == 1
    assert re.fullmatch(
        r"Error \[[0-9a-f]{8} [^\]]+\.py:\d+\]: RuntimeError: boom",
        result["say"][0],
    )
    assert caplog.text.count("RuntimeError: boom") == 1
    assert "Traceback" in caplog.text


@pytest.mark.mock
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
def test_recoverable_unexpected_error_is_reported_then_response_continues(
    terra, plugin_bot, caplog
):
    provider = terra.registry.get()
    provider.chat = MagicMock(return_value="completed answer")
    terra._record_performance = MagicMock(side_effect=RuntimeError("stats failed"))

    with caplog.at_level(logging.ERROR, logger="terraai"):
        result = dispatch(plugin_bot, "TerraAI: hello")

    assert len(result["say"]) == 2
    assert re.fullmatch(
        r"Error \[[0-9a-f]{8} [^\]]+\.py:\d+\]: RuntimeError: stats failed",
        result["say"][0],
    )
    assert result["say"][1] == "completed answer"
    assert caplog.text.count("RuntimeError: stats failed") == 1
    assert "Traceback" in caplog.text
    correlation = re.search(r"Error \[([0-9a-f]{8}) ", result["say"][0]).group(1)
    assert correlation in caplog.text


@pytest.mark.mock
def test_irc_error_is_utf8_safe_and_within_byte_limit(terra, plugin_bot):
    terra.handle_ai_message = MagicMock(
        side_effect=RuntimeError("é" * IRC_SAFE_BYTES)
    )

    result = dispatch(plugin_bot, "TerraAI: hello")

    assert len(result["say"]) == 1
    reply = result["say"][0]
    assert len(reply.encode("utf-8")) <= IRC_SAFE_BYTES
    assert reply.endswith("…")


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
    assert [(row["role"], row["content"]) for row in history] == [
        ("user", "<tester> be concise"),
        ("assistant", "short response"),
    ]


@pytest.mark.mock
def test_oversize_response_has_deterministic_utf8_fallback(terra, plugin_bot):
    provider = terra.registry.get()
    provider.chat = MagicMock(return_value="é" * IRC_SAFE_BYTES)

    result = dispatch(plugin_bot, "TerraAI: still too long")

    assert provider.chat.call_count == 3
    assert len(result["say"][0].encode("utf-8")) <= IRC_SAFE_BYTES
    assert result["say"][0].endswith("…")
    history = terra.context.history.recent("test-network", "#terra-ai")
    assert len(history) == 2
    assert history[-1]["content"] == result["say"][0]
