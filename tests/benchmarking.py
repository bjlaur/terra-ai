"""Small pytest-side recorder and report generator for TerraAI dogfood runs."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OUTPUT_ENV_VAR = "TERRAI_BENCHMARK_OUTPUT"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BenchmarkCase:
    """Collect one scenario using the same shape for one or many turns."""

    def __init__(self, item, *, scenario: str, suite: str, model: str):
        self.item = item
        self.record: dict[str, Any] = {
            "model": model,
            "suite": suite,
            "scenario": scenario,
            "test": item.nodeid,
            "messages": [],
            "responses": [],
            "elapsed_seconds": None,
            "passed": None,
            "failure_reason": None,
            "timestamp": utc_now(),
        }
        self._started: float | None = None

    def __enter__(self) -> "BenchmarkCase":
        self._started = time.monotonic()
        return self

    def add_message(self, nick: str, text: str) -> None:
        self.record["messages"].append({"nick": nick, "text": text})

    def add_response(self, text: str, *, raw: str | None = None) -> None:
        response_text = str(text)
        self.record["responses"].append(
            {"text": response_text, "raw": response_text if raw is None else str(raw)}
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
        return False


def write_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        json.dump(record, output, ensure_ascii=False, sort_keys=True)
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
                    records.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise ValueError(f"invalid JSONL in {path}:{line_number}: {error}") from error
    return records


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["model"], record["suite"])].append(record)

    summary = []
    for (model, suite), group in sorted(grouped.items()):
        durations = [
            float(record["elapsed_seconds"])
            for record in group
            if record.get("elapsed_seconds") is not None
        ]
        passed = sum(record.get("passed") is True for record in group)
        failed = len(group) - passed
        summary.append(
            {
                "model": model,
                "suite": suite,
                "passed": passed,
                "failed": failed,
                "total_seconds": round(sum(durations), 6),
                "mean_seconds": round(statistics.mean(durations), 6) if durations else None,
                "median_seconds": round(statistics.median(durations), 6) if durations else None,
            }
        )
    return summary


def _format_seconds(value: float | None) -> str:
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


def render_markdown(records: list[dict[str, Any]]) -> str:
    summary = summarize(records)
    lines = [
        "# TerraAI End-to-End Model Benchmark",
        "",
        "These measurements are user-visible TerraAI end-to-end latency, not provider token throughput.",
        "",
        "## Comparison",
        "",
        "| Model | Suite | Passed | Failed | Total (s) | Mean (s) | Median (s) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            "| {model} | {suite} | {passed} | {failed} | {total} | {mean} | {median} |".format(
                model=row["model"],
                suite=row["suite"],
                passed=row["passed"],
                failed=row["failed"],
                total=_format_seconds(row["total_seconds"]),
                mean=_format_seconds(row["mean_seconds"]),
                median=_format_seconds(row["median_seconds"]),
            )
        )

    for record in records:
        status = "PASS" if record.get("passed") else "FAIL"
        lines.extend(
            [
                "",
                f"## {record['model']} — {record['suite']} — {record['scenario']}",
                "",
                f"- Status: **{status}**",
                f"- Elapsed: **{_format_seconds(record.get('elapsed_seconds'))} seconds**",
                f"- Test: `{record.get('test', '')}`",
                f"- Timestamp: `{record.get('timestamp', '')}`",
                "",
                "### Messages",
                "",
            ]
        )
        for message in record.get("messages", []):
            lines.append(f"- **{message.get('nick', '')}:** {message.get('text', '')}")

        lines.extend(["", "### Responses", ""])
        responses = record.get("responses", [])
        if responses:
            for index, response in enumerate(responses, 1):
                lines.extend([f"**Response {index}**", ""])
                lines.extend(_fenced_text(response.get("text", "")))
                lines.append("")
        else:
            lines.append("_No response captured._")
            lines.append("")

        if record.get("failure_reason"):
            lines.extend(["### Failure", ""])
            lines.extend(_fenced_text(str(record["failure_reason"])))

    return "\n".join(lines).rstrip() + "\n"


def combine_output(output_dir: Path) -> list[dict[str, Any]]:
    response_paths = sorted(output_dir.glob("*/*-responses.jsonl"))
    records = read_records(response_paths)
    combined_jsonl = output_dir / "benchmark-results.jsonl"
    combined_jsonl.write_text("", encoding="utf-8")
    for record in records:
        write_record(combined_jsonl, record)

    payload = {
        "generated_at": utc_now(),
        "summary": summarize(records),
        "records": records,
    }
    (output_dir / "benchmark-results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "benchmark-results.md").write_text(
        render_markdown(records), encoding="utf-8"
    )
    return records


def add_infrastructure_failure(
    path: Path, *, model: str, suite: str, reason: str
) -> None:
    record = {
        "model": model,
        "suite": suite,
        "scenario": "infrastructure",
        "test": "",
        "messages": [],
        "responses": [],
        "elapsed_seconds": None,
        "passed": False,
        "failure_reason": reason,
        "timestamp": utc_now(),
    }
    write_record(path, record)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    combine_parser = subparsers.add_parser("combine")
    combine_parser.add_argument("output_dir", type=Path)

    failure_parser = subparsers.add_parser("add-failure")
    failure_parser.add_argument("output", type=Path)
    failure_parser.add_argument("--model", required=True)
    failure_parser.add_argument("--suite", required=True)
    failure_parser.add_argument("--reason", required=True)

    args = parser.parse_args(argv)
    if args.command == "combine":
        combine_output(args.output_dir)
    else:
        add_infrastructure_failure(
            args.output, model=args.model, suite=args.suite, reason=args.reason
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
