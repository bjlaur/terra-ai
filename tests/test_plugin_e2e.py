"""Plugin-routed scenarios shared by fast and real-service modes.

The test bodies are identical in both modes. ``service_transport`` chooses
deterministic HTTP responses by default or actual services with ``--real``.
"""

import pytest
from unittest.mock import patch

from terra_ai.prompts.defaults import IRC_SAFE_BYTES


pytestmark = pytest.mark.e2e


def _assert_ai_reply(result, *, scripted_text=None):
    assert len(result["say"]) == 1
    assert result["say"][0].strip()
    if scripted_text is not None:
        assert scripted_text.lower() in result["say"][0].lower()


def test_addressed_channel_prompt(terra, plugin_client, service_transport):
    with patch.object(
        terra, "handle_ai_message", wraps=terra.handle_ai_message
    ) as handle_ai_message:
        result = plugin_client.send_message("TerraAI: hello")

    handle_ai_message.assert_called_once()
    _assert_ai_reply(
        result,
        scripted_text="mocked AI response" if service_transport else None,
    )


def test_unknown_prefixed_prompt(terra, plugin_client, service_transport):
    with patch.object(
        terra, "handle_ai_message", wraps=terra.handle_ai_message
    ) as handle_ai_message:
        result = plugin_client.send_message("-what is 2+2?")

    handle_ai_message.assert_called_once()
    assert handle_ai_message.call_args.args[3] == "-what is 2+2?"
    _assert_ai_reply(result, scripted_text="4")


def test_bare_private_message(terra, plugin_client, service_transport):
    with patch.object(
        terra, "handle_ai_message", wraps=terra.handle_ai_message
    ) as handle_ai_message:
        result = plugin_client.send_pm("tester", "hello from a PM")

    handle_ai_message.assert_called_once()
    _assert_ai_reply(
        result,
        scripted_text="mocked AI response" if service_transport else None,
    )


def test_current_information_prompt(plugin_client, service_transport):
    result = plugin_client.send_message("TerraAI: find current information about SQLite")

    _assert_ai_reply(
        result,
        scripted_text="current information" if service_transport else None,
    )


def test_weather_tool_round_trip(plugin_client, service_transport):
    plugin_client.send_message("-noisy")
    plugin_client.bot.notices.clear()

    result = plugin_client.send_message("TerraAI: weather Detroit")

    _assert_ai_reply(result, scripted_text="Detroit" if service_transport else None)
    notices = " ".join(message for _, message in plugin_client.bot.notices)
    assert "Thinking" in notices
    assert any(word in notices.lower() for word in ("weather", "forecast", "fetching"))


def test_explicit_weather_web_search_override(plugin_client, service_transport):
    plugin_client.send_message("-noisy")
    plugin_client.bot.notices.clear()

    result = plugin_client.send_message(
        "TerraAI: Use web search instead of the local weather tool to find "
        "the current weather in Traverse City, Michigan."
    )

    _assert_ai_reply(
        result,
        scripted_text="external weather sources" if service_transport else None,
    )
    notices = " ".join(message for _, message in plugin_client.bot.notices)
    assert "Searching web..." in notices
    assert "Fetching weather" not in notices
    if service_transport:
        assert not any(
            request.url.host.endswith("open-meteo.com")
            for request in service_transport.requests
        )


def test_explicit_weather_hybrid_overread(plugin_client, service_transport):
    plugin_client.send_message("-noisy")
    plugin_client.bot.notices.clear()

    result = plugin_client.send_message(
        "TerraAI: Use both the local weather tool and web search as an overread "
        "for the weather in Detroit, Michigan, then combine what they say."
    )

    _assert_ai_reply(result, scripted_text="Detroit" if service_transport else None)
    notices = " ".join(message for _, message in plugin_client.bot.notices)
    assert "Searching web..." in notices
    assert "Fetching weather" in notices
    if service_transport:
        assert any(
            request.url.host.endswith("open-meteo.com")
            for request in service_transport.requests
        )


def test_ordinary_channel_traffic_never_reaches_provider(
    terra, plugin_client, service_transport
):
    provider = terra.registry.get()
    with patch.object(provider, "chat", wraps=provider.chat) as chat:
        result = plugin_client.send_message("ordinary synthetic channel text")

    assert result == {"say": [], "notice": []}
    chat.assert_not_called()
    if service_transport:
        assert service_transport.requests == []


@pytest.mark.parametrize(
    ("text", "is_pm"),
    [
        ("TerraAI: synthetic private prompt", False),
        ("-explain synthetic private prompt", False),
        ("synthetic private PM", True),
        ("-setlocation Detroit, MI", False),
    ],
)
def test_opted_out_user_never_reaches_provider(
    terra, plugin_client, service_transport, text, is_pm
):
    plugin_client.send_message("-optout")
    provider = terra.registry.get()
    with patch.object(provider, "chat", wraps=provider.chat) as chat:
        if is_pm:
            result = plugin_client.send_pm("tester", text)
        else:
            result = plugin_client.send_message(text)

    assert result == {"say": [], "notice": []}
    chat.assert_not_called()
    if service_transport:
        assert service_transport.requests == []


def test_self_message_never_reaches_provider(terra, plugin_client, service_transport):
    provider = terra.registry.get()
    with patch.object(provider, "chat", wraps=provider.chat) as chat:
        result = plugin_client.send_as("TerraAI", "TerraAI: synthetic loop")

    assert result == {"say": [], "notice": []}
    chat.assert_not_called()
    if service_transport:
        assert service_transport.requests == []


def test_registered_command_does_not_fall_through_to_ai(
    terra, plugin_client, service_transport
):
    provider = terra.registry.get()
    with patch.object(provider, "chat", wraps=provider.chat) as chat:
        result = plugin_client.send_message("-optin")

    assert len(result["say"]) == 1
    assert "opted in" in result["say"][0].lower()
    chat.assert_not_called()
    if service_transport:
        assert service_transport.requests == []


def test_tool_management_round_trip(plugin_client, service_transport):
    disabled = plugin_client.send_as("admin", "-disable-tool weather_forecast")
    listed_disabled = plugin_client.send_as("admin", "-list-tools")
    enabled = plugin_client.send_as("admin", "-enable-tool weather_forecast")
    listed_enabled = plugin_client.send_as("admin", "-list-tools")

    assert "disabled" in disabled["say"][0].lower()
    assert "weather_forecast: disabled" in listed_disabled["say"][0].lower()
    assert "enabled" in enabled["say"][0].lower()
    assert "weather_forecast: enabled" in listed_enabled["say"][0].lower()
    if service_transport:
        assert service_transport.requests == []


def test_history_is_composed_into_the_next_provider_call(
    terra, plugin_client, service_transport, monkeypatch
):
    provider = terra.registry.get()
    original_chat = provider.chat
    observed_messages = []

    def observe_chat(messages, *args, **kwargs):
        observed_messages.append(list(messages))
        return original_chat(messages, *args, **kwargs)

    monkeypatch.setattr(provider, "chat", observe_chat)
    first = plugin_client.send_message("TerraAI: remember token cobalt-7")
    second = plugin_client.send_message("TerraAI: what token did I mention?")

    _assert_ai_reply(first)
    _assert_ai_reply(second)
    last_contents = [message.content for message in observed_messages[-1]]
    assert "<tester> remember token cobalt-7" in last_contents


def test_context_free_ai_excludes_history_and_does_not_persist(
    terra, plugin_client, service_transport, monkeypatch
):
    first = plugin_client.send_message("TerraAI: remember token amber-9")
    _assert_ai_reply(first)
    history_before = terra.context.history.recent("test-network", "#terra-ai")

    provider = terra.registry.get()
    original_chat = provider.chat
    observed_messages = []

    def observe_chat(messages, *args, **kwargs):
        observed_messages.append(list(messages))
        return original_chat(messages, *args, **kwargs)

    monkeypatch.setattr(provider, "chat", observe_chat)
    result = plugin_client.send_message("-ai answer without conversation history")

    _assert_ai_reply(result)
    contents = [message.content for message in observed_messages[-1]]
    assert "<tester> remember token amber-9" not in contents
    assert "<tester> answer without conversation history" in contents
    history_after = terra.context.history.recent("test-network", "#terra-ai")
    assert history_after == history_before


def test_admin_prompt_uses_provider_and_history_without_nick_prefix(
    terra, plugin_client, service_transport, monkeypatch
):
    provider = terra.registry.get()
    original_chat = provider.chat
    observed_messages = []

    def observe_chat(messages, *args, **kwargs):
        observed_messages.append(list(messages))
        return original_chat(messages, *args, **kwargs)

    monkeypatch.setattr(provider, "chat", observe_chat)
    prompt = "Keep answers concise for this conversation"
    result = plugin_client.send_as("admin", f"-admin {prompt}")

    _assert_ai_reply(result)
    contents = [message.content for message in observed_messages[0]]
    assert prompt in contents
    assert f"<admin> {prompt}" not in contents
    history = terra.context.history.recent("test-network", "#terra-ai")
    assert history[-2]["role"] == "user"
    assert history[-2]["content"] == prompt


def test_disabled_weather_tool_is_absent_from_provider_request(
    terra, plugin_client, service_transport, monkeypatch
):
    disabled = plugin_client.send_as("admin", "-disable-tool weather_forecast")
    assert "disabled" in disabled["say"][0].lower()

    provider = terra.registry.get()
    original_chat = provider.chat
    observed_tools = []

    def observe_chat(messages, *args, **kwargs):
        observed_tools.append(list(kwargs.get("tools") or []))
        return original_chat(messages, *args, **kwargs)

    monkeypatch.setattr(provider, "chat", observe_chat)
    result = plugin_client.send_message("TerraAI: weather Detroit")

    _assert_ai_reply(result)
    tool_names = {
        tool.get("function", {}).get("name") for tool in observed_tools[-1]
    }
    assert "weather_forecast" not in tool_names
    if service_transport:
        assert not any(
            request.url.host.endswith("open-meteo.com")
            for request in service_transport.requests
        )


@pytest.mark.mock
def test_provider_http_failure_reaches_irc_once(plugin_client, service_transport):
    result = plugin_client.send_message("TerraAI: simulate provider failure")

    assert len(result["say"]) == 1
    assert result["say"][0].startswith("Error [")
    assert len(service_transport.requests) == 1


@pytest.mark.mock
def test_weather_tool_failure_completes_the_real_tool_loop(
    plugin_client, service_transport
):
    result = plugin_client.send_message("TerraAI: weather Xyzzyville")

    _assert_ai_reply(result, scripted_text="failed cleanly")
    hosts = [request.url.host for request in service_transport.requests]
    assert hosts.count("openrouter.ai") == 2
    assert "geocoding-api.open-meteo.com" in hosts
    assert "api.open-meteo.com" not in hosts


@pytest.mark.mock
def test_unexpected_tool_failure_reports_then_model_recovers(
    plugin_client, service_transport
):
    def broken_weather(arguments, noisy_callback=None):
        raise RuntimeError("unexpected weather defect")

    with patch.dict(
        "terra_ai.tools.executor.TOOL_FUNCTIONS",
        {"weather_forecast": broken_weather},
    ):
        result = plugin_client.send_message("TerraAI: weather Detroit")

    assert len(result["say"]) == 2
    assert result["say"][0].startswith("Error [")
    assert "RuntimeError: unexpected weather defect" in result["say"][0]
    assert result["say"][1] == "The weather tool failed cleanly."
    assert len(service_transport.requests) == 2


@pytest.mark.mock
def test_oversized_reply_uses_real_provider_rewrite_path(
    terra, plugin_client, service_transport
):
    result = plugin_client.send_message("TerraAI: force an oversized response")

    _assert_ai_reply(result, scripted_text="short rewritten response")
    assert len(result["say"][0].encode("utf-8")) <= IRC_SAFE_BYTES
    openrouter_requests = [
        request
        for request in service_transport.requests
        if request.url.host == "openrouter.ai"
    ]
    assert len(openrouter_requests) == 2
    history = terra.context.history.recent("test-network", "#terra-ai")
    assert history[-1]["content"] == "short rewritten response"
