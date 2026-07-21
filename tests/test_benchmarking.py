import json
from pathlib import Path
from types import SimpleNamespace

from tests.benchmarking import (
    BenchmarkCase,
    add_infrastructure_failure,
    combine_output,
    read_records,
    render_markdown,
    summarize,
    write_record,
)


def _record(**overrides):
    record = {
        "model": "vendor/model:free",
        "suite": "real",
        "scenario": "arithmetic",
        "test": "tests/test_plugin_e2e.py::test_unknown_prefixed_arithmetic_prompt",
        "messages": [{"nick": "tester", "text": "What is 17 times 6?"}],
        "responses": [{"text": "102", "raw": "102"}],
        "elapsed_seconds": 1.25,
        "passed": True,
        "failure_reason": None,
        "timestamp": "2026-07-21T20:00:00+00:00",
    }
    record.update(overrides)
    return record


def test_case_uses_same_shape_for_multiple_turns(monkeypatch):
    ticks = iter([10.0, 12.5])
    monkeypatch.setattr("tests.benchmarking.time.monotonic", lambda: next(ticks))
    item = SimpleNamespace(
        nodeid="tests/test_plugin_e2e.py::test_history_is_composed_into_the_next_provider_call"
    )

    with BenchmarkCase(
        item, scenario="conversation_memory", suite="real", model="test/model"
    ) as case:
        case.add_message("tester", "Remember Miso")
        case.add_response("Okay")
        case.add_message("tester", "What is the name?")
        case.add_response("Miso")

    assert item._terra_benchmark_record["messages"] == [
        {"nick": "tester", "text": "Remember Miso"},
        {"nick": "tester", "text": "What is the name?"},
    ]
    assert item._terra_benchmark_record["responses"] == [
        {"text": "Okay", "raw": "Okay"},
        {"text": "Miso", "raw": "Miso"},
    ]
    assert case.final_response == "Miso"
    assert item._terra_benchmark_record["elapsed_seconds"] == 2.5


def test_jsonl_round_trip(tmp_path):
    path = tmp_path / "responses.jsonl"
    write_record(path, _record())
    write_record(path, _record(scenario="fact", elapsed_seconds=2.0))
    assert [record["scenario"] for record in read_records([path])] == [
        "arithmetic",
        "fact",
    ]


def test_summary_groups_model_and_suite():
    records = [
        _record(elapsed_seconds=1.0),
        _record(scenario="fact", elapsed_seconds=3.0, passed=False),
    ]
    assert summarize(records) == [
        {
            "model": "vendor/model:free",
            "suite": "real",
            "passed": 1,
            "failed": 1,
            "total_seconds": 4.0,
            "mean_seconds": 2.0,
            "median_seconds": 2.0,
        }
    ]


def test_markdown_preserves_exact_response_and_failure():
    response = "Exact response with punctuation: yes!"
    markdown = render_markdown(
        [_record(responses=[{"text": response, "raw": response}], passed=False,
                 failure_reason="expected Lansing")]
    )
    assert response in markdown
    assert "expected Lansing" in markdown
    assert "end-to-end latency" in markdown


def test_markdown_preserves_response_code_fences():
    response = "Here is code:\n```python\nprint('hello')\n```"
    markdown = render_markdown(
        [_record(responses=[{"text": response, "raw": response}])]
    )
    assert response in markdown
    assert "````text\n" in markdown


def test_combine_writes_all_formats(tmp_path):
    model_dir = tmp_path / "vendor_model_free"
    write_record(model_dir / "real-responses.jsonl", _record())
    write_record(
        model_dir / "ergo-responses.jsonl",
        _record(suite="ergo", scenario="identity"),
    )

    records = combine_output(tmp_path)

    assert len(records) == 2
    assert len(read_records([tmp_path / "benchmark-results.jsonl"])) == 2
    payload = json.loads((tmp_path / "benchmark-results.json").read_text())
    assert len(payload["records"]) == 2
    assert "Exact" not in (tmp_path / "benchmark-results.md").read_text()


def test_infrastructure_failure_uses_normal_record_shape(tmp_path):
    path = tmp_path / "real-responses.jsonl"
    add_infrastructure_failure(
        path,
        model="vendor/model:free",
        suite="real",
        reason="pytest exited 3",
    )
    [record] = read_records([path])
    assert record["messages"] == []
    assert record["responses"] == []
    assert record["passed"] is False
    assert record["failure_reason"] == "pytest exited 3"
