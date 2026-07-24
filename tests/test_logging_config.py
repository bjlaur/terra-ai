"""Logging routing, privacy, and lifecycle tests."""

import io
import json
import logging
import re
from unittest.mock import MagicMock, patch

import pytest

from terra_ai import plugin as terra_plugin
from terra_ai.errors import event_error_scope
from terra_ai.logging_config import (
    configure_logging,
    shutdown_logging,
    trace_openrouter,
)
from terra_ai.providers.base import Message
from terra_ai.providers.openrouter import OpenRouterProvider
from tests.support import dispatch_line


@pytest.fixture(autouse=True)
def clean_terraai_handlers():
    shutdown_logging()
    yield
    shutdown_logging()


def _configure(tmp_path, stream, *, secret="super-secret-key", **overrides):
    console = logging.StreamHandler(stream)
    options = {
        "log_dir": tmp_path / "logs",
        "secrets": (secret,),
        "log_max_bytes": 4096,
        "log_backup_count": 2,
        "trace_max_bytes": 4096,
        "trace_backup_count": 2,
        "sopel_console": console,
    }
    options.update(overrides)
    return configure_logging(**options)


def test_levels_correlation_redaction_and_separate_files(tmp_path):
    console = io.StringIO()
    operational_path, trace_path = _configure(tmp_path, console)
    logger = logging.getLogger("terraai.component")

    with event_error_scope(lambda message: None) as correlation_id:
        logger.debug("debug detail api_key=super-secret-key")
        logger.info("prompt line one\nline two")
        trace_openrouter(
            {
                "event_type": "request",
                "call_id": "call-1",
                "round": 0,
                "attempt": 1,
                "request": {
                    "authorization": "Bearer super-secret-key",
                    "prompt": "private",
                },
            }
        )
        try:
            raise RuntimeError("Bearer super-secret-key")
        except RuntimeError:
            logger.exception("provider failed with super-secret-key")

    shutdown_logging()
    operational = operational_path.read_text()
    trace = trace_path.read_text()
    stderr = console.getvalue()

    assert correlation_id in operational
    assert correlation_id in trace
    assert correlation_id in stderr
    assert "debug detail" in operational
    assert "prompt line one" in operational
    assert "provider failed" in operational
    assert "Traceback" in operational
    assert '"event_type":"request"' not in operational
    assert "debug detail" not in stderr
    assert '"event_type":"request"' not in stderr
    assert "prompt line one" in stderr
    assert "provider failed" in stderr
    [trace_event] = [json.loads(line) for line in trace.splitlines() if line.strip()]
    assert trace_event["event_type"] == "request"
    assert trace_event["correlation_id"] == correlation_id
    assert trace_event["request"]["prompt"] == "private"
    assert "debug detail" not in trace
    assert "prompt line one" not in trace
    for output in (operational, trace, stderr):
        assert "super-secret-key" not in output
    assert "[REDACTED]" in operational
    assert "[REDACTED]" in trace
def test_setup_is_reload_safe_and_rotation_works(tmp_path):
    console = io.StringIO()
    operational_path, _ = _configure(
        tmp_path,
        console,
        log_max_bytes=128,
        log_backup_count=1,
    )
    _configure(
        tmp_path,
        console,
        log_max_bytes=128,
        log_backup_count=1,
    )
    owned = [
        handler
        for handler in logging.getLogger("terraai").handlers
        if getattr(handler, "_terraai_owned_handler", False)
    ]
    assert len(owned) == 3

    logging.getLogger("terraai").info("rotation seed")
    logging.getLogger("terraai").info("rotation payload %s", "x" * 300)
    shutdown_logging()

    rotated = operational_path.with_name("terra-ai.log.1")
    assert rotated.exists()
    assert console.getvalue().count("rotation payload") == 1


def test_standalone_error_gets_a_locatable_correlation_id(tmp_path):
    console = io.StringIO()
    operational_path, _ = _configure(tmp_path, console)

    logging.getLogger("terraai").error("standalone failure")
    shutdown_logging()

    line = operational_path.read_text()
    assert re.search(
        r"ERROR \[[0-9a-f]{8}\] terraai test_logging_config\.py:\d+: "
        r"standalone failure",
        line,
    )


def test_plugin_prompt_and_final_response_share_event_correlation(
    tmp_path, terra, plugin_bot
):
    operational_path, _ = _configure(tmp_path, io.StringIO())
    terra.registry.get().chat = MagicMock(return_value="answer line one\nline two")

    result = dispatch_line(
        plugin_bot,
        "tester",
        "TerraAI: quoted \"prompt\"",
        is_pm=False,
    )
    shutdown_logging()

    assert result["say"] == ["answer line one\nline two"]
    info_lines = [
        line
        for line in operational_path.read_text().splitlines()
        if "AI prompt sent:" in line or "AI response:" in line
    ]
    assert len(info_lines) == 2
    correlations = [
        re.search(r"\[([0-9a-f]{8})\]", line).group(1)
        for line in info_lines
    ]
    assert correlations[0] == correlations[1]
    assert r'quoted \"prompt\"' in info_lines[0]
    assert r"answer line one\nline two" in info_lines[1]


@patch("terra_ai.providers.openrouter.httpx.Client")
def test_openrouter_request_and_response_are_trace_only(
    mock_client_class, tmp_path
):
    operational_path, trace_path = _configure(
        tmp_path,
        io.StringIO(),
        secret="provider-secret",
    )
    response_data = {"choices": [{"message": {"content": "wire answer"}}]}
    response = __import__("httpx").Response(
        200,
        json=response_data,
        headers={"X-Generation-Id": "gen-wire"},
        request=__import__("httpx").Request(
            "POST", "https://openrouter.ai/api/v1/chat/completions"
        ),
    )
    client = MagicMock()
    client.post.return_value = response
    mock_client_class.return_value.__enter__.return_value = client

    provider = OpenRouterProvider(
        model="test-model",
        api_key="provider-secret",
    )
    assert provider.chat([Message("user", "wire-private-prompt")]) == "wire answer"
    shutdown_logging()

    operational = operational_path.read_text()
    trace_events = [
        json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()
    ]
    assert "wire-private-prompt" not in operational
    assert [event["event_type"] for event in trace_events] == ["request", "response"]
    assert trace_events[0]["request"]["messages"][-1]["content"] == "wire-private-prompt"
    assert "wire answer" in trace_events[1]["response_body"]
    assert trace_events[1]["safe_response_headers"] == {
        "X-Generation-Id": "gen-wire"
    }
    assert "provider-secret" not in operational
    assert "provider-secret" not in trace_path.read_text()


@patch("terra_ai.providers.openrouter.httpx.Client")
def test_trace_jsonl_keeps_multiline_bodies_on_one_line(
    mock_client_class, tmp_path
):
    _, trace_path = _configure(tmp_path, io.StringIO())
    response_data = {
        "choices": [{"message": {"content": "line one\nline two"}}]
    }
    response = __import__("httpx").Response(
        200,
        json=response_data,
        request=__import__("httpx").Request(
            "POST", "https://openrouter.ai/api/v1/chat/completions"
        ),
    )
    client = MagicMock()
    client.post.return_value = response
    mock_client_class.return_value.__enter__.return_value = client

    provider = OpenRouterProvider(model="test-model", api_key="key")
    assert provider.chat([Message("user", "hello")]) == "line one\nline two"
    shutdown_logging()

    lines = trace_path.read_text().splitlines()
    assert len(lines) == 2
    events = [json.loads(line) for line in lines]
    assert events[1]["event_type"] == "response"
    decoded_body = json.loads(events[1]["response_body"])
    assert decoded_body["choices"][0]["message"]["content"] == "line one\nline two"


@patch("terra_ai.providers.openrouter.httpx.Client")
def test_transport_error_trace_is_structured_jsonl(mock_client_class, tmp_path):
    _, trace_path = _configure(tmp_path, io.StringIO())
    client = MagicMock()
    client.post.side_effect = __import__("httpx").ConnectError("offline")
    mock_client_class.return_value.__enter__.return_value = client

    provider = OpenRouterProvider(model="test-model", api_key="key")
    with pytest.raises(Exception, match="offline"):
        provider.chat([Message("user", "hello")])
    shutdown_logging()

    events = [
        json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()
    ]
    assert [event["event_type"] for event in events] == [
        "request",
        "transport_error",
    ]
    assert events[1]["error"]["type"] == "ConnectError"


@patch("terra_ai.providers.openrouter.httpx.Client")
def test_unserializable_trace_event_does_not_change_provider_response(
    mock_client_class, monkeypatch
):
    client = MagicMock()
    client.post.return_value = __import__("httpx").Response(
        200,
        json={"choices": [{"message": {"content": "answer"}}]},
        request=__import__("httpx").Request(
            "POST", "https://openrouter.ai/api/v1/chat/completions"
        ),
    )
    mock_client_class.return_value.__enter__.return_value = client
    monkeypatch.setattr(
        "terra_ai.providers.openrouter.OPENROUTER_WEB_SEARCH_TOOL",
        {"type": "openrouter:web_search", "bad_trace_value": object()},
    )

    provider = OpenRouterProvider(model="test-model", api_key="key")
    assert provider.chat([Message("user", "hello")]) == "answer"


def test_shutdown_failure_is_traced_before_handlers_close(tmp_path):
    operational_path, _ = _configure(tmp_path, io.StringIO())
    terra_plugin._terrai = MagicMock()
    terra_plugin._terrai.close.side_effect = RuntimeError("close failed")

    with pytest.raises(RuntimeError, match="close failed"):
        terra_plugin.shutdown()

    operational = operational_path.read_text()
    assert "TerraAI shutdown failed" in operational
    assert "Traceback" in operational
    assert "RuntimeError: close failed" in operational
    assert "TerraAI plugin unloaded" in operational
    assert terra_plugin._terrai is None


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("log_max_bytes", 0),
        ("log_backup_count", -1),
        ("trace_max_bytes", True),
        ("trace_backup_count", 0),
    ],
)
def test_invalid_rotation_configuration_is_rejected(tmp_path, option, value):
    with pytest.raises(ValueError, match=option):
        _configure(tmp_path, io.StringIO(), **{option: value})


def test_empty_log_directory_is_rejected_before_side_effects():
    with pytest.raises(ValueError, match="log_dir"):
        configure_logging(log_dir="")
