import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.benchmarking import (
    BenchmarkCase,
    add_infrastructure_failure,
    combine_model_output,
    combine_output,
    current_benchmark_context,
    read_records,
    render_markdown,
    summarize_provider_attempts,
    summarize_tests,
    write_record,
)


def _record(**overrides):
    record = {
        "test_id": "real::tests/test_plugin_e2e.py::test_arithmetic",
        "model": "vendor/model:free",
        "suite": "real",
        "scenario": "arithmetic",
        "test": "tests/test_plugin_e2e.py::test_arithmetic",
        "messages": [{"turn": 1, "nick": "tester", "text": "What is 17 times 6?"}],
        "responses": [{"turn": 1, "text": "102", "raw": "102"}],
        "elapsed_seconds": 1.25,
        "status": "passed",
        "passed": True,
        "failure_reason": None,
        "timestamp": "2026-07-21T20:00:00+00:00",
    }
    record.update(overrides)
    return record


def _attempt(**overrides):
    event = {
        "schema_version": 1,
        "timestamp": "2026-07-24T15:03:57.622Z",
        "call_id": "call-1",
        "correlation_id": "corr-1",
        "provider": "openrouter",
        "requested_model": "vendor/model:free",
        "returned_model": "vendor/model:free",
        "returned_provider": "Example",
        "request_kind": "initial",
        "round": 0,
        "attempt": 1,
        "latest_prompt": "What is 17 times 6?",
        "message_count": 1,
        "tool_names": ["openrouter:web_search"],
        "success": True,
        "http_status": 200,
        "provider_latency_ms": 100,
        "pacing_wait_ms": 0,
        "response_text": "102",
        "response_tool_names": [],
        "generation_id": "gen-1",
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        "cost": {"total": 0.001},
        "finish_reason": "stop",
        "error": None,
        "safe_response_headers": {"X-Generation-Id": "gen-1"},
        "will_retry": False,
        "retry_delay_ms": 0,
        "benchmark_test_id": "real::tests/test_plugin_e2e.py::test_arithmetic",
        "benchmark_turn": 1,
        "benchmark_scenario": "arithmetic",
        "benchmark_suite": "real",
        "benchmark_model": "vendor/model:free",
    }
    event.update(overrides)
    return event


def test_case_tracks_turns_and_exposes_current_context(monkeypatch):
    ticks = iter([10.0, 12.5])
    monkeypatch.setattr("tests.benchmarking.time.monotonic", lambda: next(ticks))
    item = SimpleNamespace(nodeid="tests/test_plugin_e2e.py::test_history")

    with BenchmarkCase(
        item, scenario="conversation_memory", suite="real", model="test/model"
    ) as case:
        case.add_message("tester", "Remember Miso")
        assert current_benchmark_context()["benchmark_turn"] == 1
        case.add_response("Okay")
        case.add_message("tester", "What is the name?")
        assert current_benchmark_context()["benchmark_turn"] == 2
        case.add_response("Miso")

    assert current_benchmark_context() == {}
    assert item._terra_benchmark_record["messages"] == [
        {"turn": 1, "nick": "tester", "text": "Remember Miso"},
        {"turn": 2, "nick": "tester", "text": "What is the name?"},
    ]
    assert item._terra_benchmark_record["responses"] == [
        {"turn": 1, "text": "Okay", "raw": "Okay"},
        {"turn": 2, "text": "Miso", "raw": "Miso"},
    ]
    assert case.final_response == "Miso"
    assert item._terra_benchmark_record["elapsed_seconds"] == 2.5


def test_jsonl_round_trip(tmp_path):
    path = tmp_path / "real-tests.jsonl"
    write_record(path, _record())
    write_record(path, _record(scenario="fact", elapsed_seconds=2.0))
    assert [record["scenario"] for record in read_records([path])] == [
        "arithmetic",
        "fact",
    ]


def test_test_summary_has_min_mean_median_p95_and_max():
    records = [
        _record(elapsed_seconds=1.0),
        _record(
            test_id="real::fact",
            scenario="fact",
            elapsed_seconds=3.0,
            status="failed",
            passed=False,
        ),
    ]
    [summary] = summarize_tests(records)
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["latency_seconds"] == {
        "count": 2,
        "minimum": 1.0,
        "mean": 2.0,
        "median": 2.0,
        "p95": 3.0,
        "maximum": 3.0,
    }


def test_provider_summary_calculates_latency_recovery_and_failures():
    attempts = [
        _attempt(
            success=False,
            http_status=429,
            provider_latency_ms=25,
            will_retry=True,
            retry_delay_ms=3000,
            error={"type": "rate_limit_exceeded", "message": "limited", "provider_code": None},
        ),
        _attempt(attempt=2, provider_latency_ms=100, pacing_wait_ms=3000),
        _attempt(call_id="call-2", provider_latency_ms=300, pacing_wait_ms=1000),
    ]
    summary = summarize_provider_attempts(attempts)
    assert summary["total_attempts"] == 3
    assert summary["successful_attempts"] == 2
    assert summary["failed_attempts"] == 1
    assert summary["failures_by_http_status"] == {"429": 1}
    assert summary["failures_by_error_type"] == {"rate_limit_exceeded": 1}
    assert summary["retries_scheduled"] == 1
    assert summary["logical_rounds_recovered_by_retry"] == 1
    assert summary["logical_rounds_retries_exhausted"] == 0
    assert summary["total_pacing_wait_ms"] == 4000.0
    assert summary["successful_provider_latency_ms"] == {
        "count": 2,
        "minimum": 100.0,
        "mean": 200.0,
        "median": 200.0,
        "p95": 300.0,
        "maximum": 300.0,
    }


def test_provider_summary_handles_empty_and_single_sample():
    empty = summarize_provider_attempts([])
    assert empty["successful_provider_latency_ms"]["mean"] is None
    single = summarize_provider_attempts([_attempt(provider_latency_ms=123)])
    stats = single["successful_provider_latency_ms"]
    assert stats == {
        "count": 1,
        "minimum": 123.0,
        "mean": 123.0,
        "median": 123.0,
        "p95": 123.0,
        "maximum": 123.0,
    }


def test_model_result_joins_real_tests_and_provider_calls(tmp_path):
    model_dir = tmp_path / "vendor_model_free"
    write_record(model_dir / "real-tests.jsonl", _record())
    write_record(
        model_dir / "ergo-tests.jsonl",
        _record(
            test_id="ergo::identity",
            suite="ergo",
            scenario="identity",
        ),
    )
    write_record(model_dir / "real-provider-calls.jsonl", _attempt())

    payload = combine_model_output(
        model_dir,
        model="vendor/model:free",
        rpm=20,
        min_interval=1,
    )

    assert (model_dir / "benchmark-results.json").exists()
    assert payload["run"]["pacing"]["effective_interval_seconds"] == 3.0
    assert len(payload["benchmarks"]) == 1
    assert len(payload["benchmarks"][0]["provider_attempts"]) == 1
    assert payload["benchmarks"][0]["provider_summary"]["total_attempts"] == 1
    assert len(payload["ergo"]) == 1
    assert payload["unassociated_provider_attempts"] == []


def test_provider_call_summary_includes_unassociated_attempts(tmp_path):
    model_dir = tmp_path / "vendor_model_free"
    write_record(model_dir / "real-tests.jsonl", _record())
    write_record(model_dir / "real-provider-calls.jsonl", _attempt())
    write_record(
        model_dir / "real-provider-calls.jsonl",
        _attempt(
            call_id="orphan-call",
            benchmark_test_id=None,
            benchmark_turn=None,
            provider_latency_ms=300,
        ),
    )

    payload = combine_model_output(model_dir, model="vendor/model:free")

    assert len(payload["unassociated_provider_attempts"]) == 1
    [summary] = payload["provider_call_summary"]
    assert summary["total_attempts"] == 2
    assert summary["successful_provider_latency_ms"]["mean"] == 200.0


def test_root_result_stitches_per_model_results_and_recomputes(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_record(first / "real-tests.jsonl", _record())
    write_record(first / "ergo-tests.jsonl", _record(test_id="ergo::one", suite="ergo"))
    write_record(first / "real-provider-calls.jsonl", _attempt())
    combine_model_output(first, model="vendor/model:free", rpm=20)

    second_record = _record(
        test_id="real::second",
        model="other/model",
        scenario="second",
        elapsed_seconds=3.0,
    )
    second_attempt = _attempt(
        benchmark_test_id="real::second",
        benchmark_model="other/model",
        requested_model="other/model",
        returned_model="other/model",
        provider_latency_ms=500,
    )
    write_record(second / "real-tests.jsonl", second_record)
    write_record(second / "ergo-tests.jsonl", _record(test_id="ergo::two", suite="ergo", model="other/model"))
    write_record(second / "real-provider-calls.jsonl", second_attempt)
    combine_model_output(second, model="other/model", rpm=20)

    payload = combine_output(tmp_path)

    assert payload["run"]["models"] == ["vendor/model:free", "other/model"] or payload["run"]["models"] == ["other/model", "vendor/model:free"]
    assert len(payload["benchmarks"]) == 2
    assert len(payload["ergo"]) == 2
    assert len(payload["provider_call_summary"]) == 2
    assert (tmp_path / "benchmark-results.json").exists()
    assert (tmp_path / "benchmark-results.md").exists()



def test_provider_summary_groups_missing_error_metadata_as_unknown():
    summary = summarize_provider_attempts(
        [_attempt(success=False, http_status=500, error=None)]
    )
    assert summary["failures_by_error_type"] == {"unknown": 1}


def test_root_result_rejects_mismatched_per_model_pacing(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_record(first / "real-tests.jsonl", _record())
    write_record(first / "real-provider-calls.jsonl", _attempt())
    combine_model_output(first, model="vendor/model:free", rpm=20)

    write_record(
        second / "real-tests.jsonl",
        _record(test_id="real::second", model="other/model"),
    )
    write_record(
        second / "real-provider-calls.jsonl",
        _attempt(
            benchmark_test_id="real::second",
            benchmark_model="other/model",
            requested_model="other/model",
        ),
    )
    combine_model_output(second, model="other/model", rpm=10)

    with pytest.raises(ValueError, match="pacing settings do not match"):
        combine_output(tmp_path)

def test_markdown_contains_real_ergo_and_provider_sections():
    payload = {
        "summary": {
            "benchmarks": summarize_tests([_record()]),
            "ergo": summarize_tests([_record(test_id="ergo::one", suite="ergo")]),
        },
        "benchmarks": [{**_record(), "provider_attempts": [_attempt()], "provider_summary": summarize_provider_attempts([_attempt()])}],
        "ergo": [_record(test_id="ergo::one", suite="ergo")],
        "provider_call_summary": [{"model": "vendor/model:free", **summarize_provider_attempts([_attempt()])}],
    }
    markdown = render_markdown(payload)
    assert "Real benchmark comparison" in markdown
    assert "## Ergo" in markdown
    assert "Provider-attempt performance" in markdown
    assert "P95 uses nearest rank" in markdown
    assert "102" in markdown


def test_infrastructure_failure_uses_test_record_shape(tmp_path):
    path = tmp_path / "real-tests.jsonl"
    add_infrastructure_failure(
        path,
        model="vendor/model:free",
        suite="real",
        reason="pytest exited 3",
    )
    [record] = read_records([path])
    assert record["test_id"] == "real::infrastructure"
    assert record["status"] == "failed"
    assert record["passed"] is False
    assert record["failure_reason"] == "pytest exited 3"


def test_direct_real_pacer_and_provider_sink_are_session_scoped():
    from tests import conftest

    assert conftest.real_request_pacer._fixture_function_marker.scope == "session"
    assert conftest.real_provider_call_sink._fixture_function_marker.scope == "session"
