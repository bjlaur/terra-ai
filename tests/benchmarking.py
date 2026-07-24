"""Pytest-side benchmark recorder and canonical report assembler."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OUTPUT_ENV_VAR = "TERRAI_BENCHMARK_OUTPUT"
PROVIDER_OUTPUT_ENV_VAR = "TERRAI_BENCHMARK_PROVIDER_OUTPUT"
_CURRENT_BENCHMARK_CONTEXT: ContextVar[dict[str, object]] = ContextVar(
    "terraai_benchmark_context", default={}
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def current_benchmark_context() -> dict[str, object]:
    """Return a copy of the active direct benchmark test context."""
    return dict(_CURRENT_BENCHMARK_CONTEXT.get())


class BenchmarkCase:
    """Collect one scenario using the same shape for one or many turns."""

    def __init__(self, item, *, scenario: str, suite: str, model: str):
        self.item = item
        self.test_id = f"{suite}::{item.nodeid}"
        self.record: dict[str, Any] = {
            "test_id": self.test_id,
            "model": model,
            "suite": suite,
            "scenario": scenario,
            "test": item.nodeid,
            "messages": [],
            "responses": [],
            "elapsed_seconds": None,
            "status": None,
            "passed": None,
            "failure_reason": None,
            "timestamp": utc_now(),
        }
        self._started: float | None = None
        self._context_token = None
        self._turn = 0

    def __enter__(self) -> "BenchmarkCase":
        self._started = time.monotonic()
        self._context_token = _CURRENT_BENCHMARK_CONTEXT.set({})
        return self

    def add_message(self, nick: str, text: str) -> None:
        self._turn += 1
        self.record["messages"].append(
            {"turn": self._turn, "nick": nick, "text": text}
        )
        _CURRENT_BENCHMARK_CONTEXT.set(
            {
                "benchmark_test_id": self.test_id,
                "benchmark_turn": self._turn,
                "benchmark_scenario": self.record["scenario"],
                "benchmark_suite": self.record["suite"],
                "benchmark_model": self.record["model"],
            }
        )

    def add_response(self, text: str, *, raw: str | None = None) -> None:
        response_text = str(text)
        self.record["responses"].append(
            {
                "turn": self._turn or 1,
                "text": response_text,
                "raw": response_text if raw is None else str(raw),
            }
        )

    def add_responses(self, responses) -> None:
        for response in responses:
            self.add_response(str(response))

    @property
    def final_response(self) -> str:
        responses = self.record["responses"]
        return responses[-1]["text"] if responses else ""

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if self._started is None:
            raise RuntimeError("benchmark case was not started")
        self.record["elapsed_seconds"] = round(time.monotonic() - self._started, 6)
        if exc is not None:
            self.record["failure_reason"] = f"{type(exc).__name__}: {exc}"
        self.item._terra_benchmark_record = self.record
        if self._context_token is not None:
            _CURRENT_BENCHMARK_CONTEXT.reset(self._context_token)
        return False


def write_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        json.dump(record, output, ensure_ascii=False, sort_keys=True, allow_nan=False)
        output.write("\n")


def read_records(paths) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"invalid JSONL in {path}:{line_number}: {error}"
                    ) from error
                if not isinstance(value, dict):
                    raise ValueError(f"expected JSON object in {path}:{line_number}")
                records.append(value)
    return records


def _nearest_rank_p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = math.ceil(0.95 * len(ordered))
    return ordered[rank - 1]


def _statistics(values: list[float], *, digits: int = 6) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "minimum": None,
            "mean": None,
            "median": None,
            "p95": None,
            "maximum": None,
        }
    return {
        "count": len(values),
        "minimum": round(min(values), digits),
        "mean": round(statistics.mean(values), digits),
        "median": round(statistics.median(values), digits),
        "p95": round(_nearest_rank_p95(values), digits),
        "maximum": round(max(values), digits),
    }


def summarize_tests(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("model", ""))].append(record)
    rows = []
    for model, group in sorted(grouped.items()):
        durations = [
            float(record["elapsed_seconds"])
            for record in group
            if record.get("elapsed_seconds") is not None
        ]
        statuses = Counter(str(record.get("status") or "failed") for record in group)
        rows.append(
            {
                "model": model,
                "passed": statuses["passed"],
                "failed": statuses["failed"],
                "xfailed": statuses["xfailed"],
                "xpassed": statuses["xpassed"],
                "total_seconds": round(sum(durations), 6),
                "latency_seconds": _statistics(durations),
            }
        )
    return rows


def summarize_provider_attempts(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    successful_latencies = [
        float(event["provider_latency_ms"])
        for event in attempts
        if event.get("success") is True and event.get("provider_latency_ms") is not None
    ]
    failed = [event for event in attempts if event.get("success") is not True]
    status_failures = Counter(
        str(event.get("http_status")) if event.get("http_status") is not None else "none"
        for event in failed
    )
    error_failures = Counter(
        str(
            event["error"].get("type") or "unknown"
            if isinstance(event.get("error"), dict)
            else "unknown"
        )
        for event in failed
    )

    rounds: dict[tuple[object, object], list[dict[str, Any]]] = defaultdict(list)
    for event in attempts:
        rounds[(event.get("call_id"), event.get("round"))].append(event)
    recovered = 0
    exhausted = 0
    for group in rounds.values():
        ordered = sorted(group, key=lambda event: int(event.get("attempt") or 0))
        had_retryable_failure = any(event.get("will_retry") is True for event in ordered)
        if not had_retryable_failure:
            continue
        if ordered[-1].get("success") is True:
            recovered += 1
        else:
            exhausted += 1

    pacing_waits = [float(event.get("pacing_wait_ms") or 0) for event in attempts]
    return {
        "total_attempts": len(attempts),
        "successful_attempts": len(attempts) - len(failed),
        "failed_attempts": len(failed),
        "failures_by_http_status": dict(sorted(status_failures.items())),
        "failures_by_error_type": dict(sorted(error_failures.items())),
        "retries_scheduled": sum(event.get("will_retry") is True for event in attempts),
        "logical_rounds_recovered_by_retry": recovered,
        "logical_rounds_retries_exhausted": exhausted,
        "total_pacing_wait_ms": round(sum(pacing_waits), 3),
        "mean_pacing_wait_ms": (
            round(statistics.mean(pacing_waits), 3) if pacing_waits else None
        ),
        "successful_provider_latency_ms": _statistics(successful_latencies, digits=3),
    }


def _attach_provider_attempts(
    benchmarks: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_test: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unassociated: list[dict[str, Any]] = []
    known = {str(record.get("test_id")) for record in benchmarks}
    for event in attempts:
        test_id = event.get("benchmark_test_id")
        if isinstance(test_id, str) and test_id in known:
            by_test[test_id].append(event)
        else:
            unassociated.append(event)

    for record in benchmarks:
        events = sorted(
            by_test.get(str(record.get("test_id")), []),
            key=lambda event: (
                int(event.get("benchmark_turn") or 0),
                str(event.get("timestamp") or ""),
                str(event.get("call_id") or ""),
                int(event.get("round") or 0),
                int(event.get("attempt") or 0),
            ),
        )
        record["provider_attempts"] = events
        record["provider_summary"] = summarize_provider_attempts(events)
    return benchmarks, unassociated


def build_payload(
    *,
    models: list[str],
    benchmarks: list[dict[str, Any]],
    ergo: list[dict[str, Any]],
    unassociated_provider_attempts: list[dict[str, Any]],
    rpm: float,
    min_interval: float,
) -> dict[str, Any]:
    associated_attempts = [
        event
        for record in benchmarks
        for event in record.get("provider_attempts", [])
    ]
    all_attempts = associated_attempts + unassociated_provider_attempts
    provider_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in all_attempts:
        provider_groups[str(event.get("benchmark_model") or event.get("requested_model") or "")].append(event)
    provider_summary = [
        {"model": model, **summarize_provider_attempts(events)}
        for model, events in sorted(provider_groups.items())
    ]
    effective_interval = max(60.0 / rpm if rpm else 0.0, min_interval)
    return {
        "schema_version": 2,
        "generated_at": utc_now(),
        "run": {
            "models": models,
            "pacing": {
                "requests_per_minute": rpm,
                "minimum_interval_seconds": min_interval,
                "effective_interval_seconds": effective_interval,
            },
        },
        "benchmarks": benchmarks,
        "ergo": ergo,
        "summary": {
            "benchmarks": summarize_tests(benchmarks),
            "ergo": summarize_tests(ergo),
        },
        "provider_call_summary": provider_summary,
        "unassociated_provider_attempts": unassociated_provider_attempts,
    }


def combine_model_output(
    model_dir: Path,
    *,
    model: str,
    rpm: float = 0.0,
    min_interval: float = 0.0,
) -> dict[str, Any]:
    benchmarks = read_records([model_dir / "real-tests.jsonl"])
    ergo = read_records([model_dir / "ergo-tests.jsonl"])
    attempts = read_records([model_dir / "real-provider-calls.jsonl"])
    benchmarks, unassociated = _attach_provider_attempts(benchmarks, attempts)
    payload = build_payload(
        models=[model],
        benchmarks=benchmarks,
        ergo=ergo,
        unassociated_provider_attempts=unassociated,
        rpm=rpm,
        min_interval=min_interval,
    )
    (model_dir / "benchmark-results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def combine_output(output_dir: Path) -> dict[str, Any]:
    model_payloads = []
    for path in sorted(output_dir.glob("*/benchmark-results.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 2:
            raise ValueError(f"unsupported benchmark schema in {path}")
        model_payloads.append(payload)
    if not model_payloads:
        raise ValueError("no per-model benchmark-results.json files found")

    models: list[str] = []
    benchmarks: list[dict[str, Any]] = []
    ergo: list[dict[str, Any]] = []
    unassociated: list[dict[str, Any]] = []
    for payload in model_payloads:
        models.extend(payload["run"]["models"])
        benchmarks.extend(payload.get("benchmarks", []))
        ergo.extend(payload.get("ergo", []))
        unassociated.extend(payload.get("unassociated_provider_attempts", []))
    pacing = model_payloads[0]["run"]["pacing"]
    for model_payload in model_payloads[1:]:
        if model_payload["run"]["pacing"] != pacing:
            raise ValueError("per-model benchmark pacing settings do not match")
    payload = build_payload(
        models=models,
        benchmarks=benchmarks,
        ergo=ergo,
        unassociated_provider_attempts=unassociated,
        rpm=float(pacing["requests_per_minute"]),
        min_interval=float(pacing["minimum_interval_seconds"]),
    )
    (output_dir / "benchmark-results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "benchmark-results.md").write_text(
        render_markdown(payload), encoding="utf-8"
    )
    return payload


def _format_number(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _fenced_text(text: str) -> list[str]:
    longest_run = 0
    current_run = 0
    for character in text:
        if character == "`":
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 0
    fence = "`" * max(3, longest_run + 1)
    return [f"{fence}text", text, fence]


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# TerraAI Model Benchmark",
        "",
        "`--real` results are the performance benchmark. Ergo results are integration checks.",
        "",
        "## Real benchmark comparison",
        "",
        "| Model | Passed | Failed | Min (s) | Mean (s) | Median (s) | P95 (s) | Max (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["summary"]["benchmarks"]:
        stats = row["latency_seconds"]
        lines.append(
            f"| {row['model']} | {row['passed']} | {row['failed']} | "
            f"{_format_number(stats['minimum'])} | {_format_number(stats['mean'])} | "
            f"{_format_number(stats['median'])} | {_format_number(stats['p95'])} | "
            f"{_format_number(stats['maximum'])} |"
        )

    lines.extend(["", "## Ergo", ""])
    for row in payload["summary"]["ergo"]:
        lines.append(
            f"- **{row['model']}**: {row['passed']} passed, {row['failed']} failed, "
            f"{row['xfailed']} xfailed, {row['xpassed']} xpassed"
        )

    for record in payload["benchmarks"]:
        lines.extend(_render_test(record, heading="Benchmark"))
    for record in payload["ergo"]:
        lines.extend(_render_test(record, heading="Ergo"))

    lines.extend(
        [
            "",
            "## Provider-attempt performance",
            "",
            "P95 uses nearest rank, so small samples may report the maximum.",
            "Provider latency excludes pacing waits, retry delays, tools, and local processing.",
            "",
            "| Model | Attempts | Success | Failed | Min (ms) | Mean (ms) | Median (ms) | P95 (ms) | Max (ms) | Retries | Recovered | Exhausted | Pacing (ms) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["provider_call_summary"]:
        stats = row["successful_provider_latency_ms"]
        lines.append(
            f"| {row['model']} | {row['total_attempts']} | {row['successful_attempts']} | "
            f"{row['failed_attempts']} | {_format_number(stats['minimum'])} | "
            f"{_format_number(stats['mean'])} | {_format_number(stats['median'])} | "
            f"{_format_number(stats['p95'])} | {_format_number(stats['maximum'])} | "
            f"{row['retries_scheduled']} | {row['logical_rounds_recovered_by_retry']} | "
            f"{row['logical_rounds_retries_exhausted']} | {row['total_pacing_wait_ms']:.3f} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_test(record: dict[str, Any], *, heading: str) -> list[str]:
    status = str(record.get("status") or "failed").upper()
    lines = [
        "",
        f"## {heading}: {record.get('model', '')} — {record.get('scenario', '')}",
        "",
        f"- Status: **{status}**",
        f"- Elapsed: **{_format_number(record.get('elapsed_seconds'))} seconds**",
        f"- Test: `{record.get('test', '')}`",
        "",
        "### Messages",
        "",
    ]
    for message in record.get("messages", []):
        lines.append(f"- **{message.get('nick', '')}:** {message.get('text', '')}")
    lines.extend(["", "### Responses", ""])
    responses = record.get("responses", [])
    if responses:
        for index, response in enumerate(responses, 1):
            lines.extend([f"**Response {index}**", ""])
            lines.extend(_fenced_text(str(response.get("text", ""))))
            lines.append("")
    else:
        lines.extend(["_No response captured._", ""])
    if record.get("failure_reason"):
        lines.extend(["### Failure", ""])
        lines.extend(_fenced_text(str(record["failure_reason"])))
    return lines


def add_infrastructure_failure(
    path: Path, *, model: str, suite: str, reason: str
) -> None:
    write_record(
        path,
        {
            "test_id": f"{suite}::infrastructure",
            "model": model,
            "suite": suite,
            "scenario": "infrastructure",
            "test": "",
            "messages": [],
            "responses": [],
            "elapsed_seconds": None,
            "status": "failed",
            "passed": False,
            "failure_reason": reason,
            "timestamp": utc_now(),
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    model_parser = subparsers.add_parser("combine-model")
    model_parser.add_argument("model_dir", type=Path)
    model_parser.add_argument("--model", required=True)
    model_parser.add_argument("--rpm", type=float, default=0.0)
    model_parser.add_argument("--min-interval", type=float, default=0.0)

    combine_parser = subparsers.add_parser("combine")
    combine_parser.add_argument("output_dir", type=Path)

    failure_parser = subparsers.add_parser("add-failure")
    failure_parser.add_argument("output", type=Path)
    failure_parser.add_argument("--model", required=True)
    failure_parser.add_argument("--suite", required=True)
    failure_parser.add_argument("--reason", required=True)

    args = parser.parse_args(argv)
    if args.command == "combine-model":
        combine_model_output(
            args.model_dir,
            model=args.model,
            rpm=args.rpm,
            min_interval=args.min_interval,
        )
    elif args.command == "combine":
        combine_output(args.output_dir)
    else:
        add_infrastructure_failure(
            args.output, model=args.model, suite=args.suite, reason=args.reason
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
