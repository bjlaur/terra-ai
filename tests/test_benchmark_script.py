"""Offline contract tests for the benchmark driver CLI."""

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark-models"


def run_script(*args):
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_help_documents_pacing_flags():
    result = run_script("--help")
    assert result.returncode == 0
    assert "--rpm RPM" in result.stdout
    assert "--min-interval SECONDS" in result.stdout


def test_invalid_rpm_stops_before_creating_output(tmp_path):
    output = tmp_path / "benchmark-output"
    result = run_script("--rpm", "nan", "--output-dir", str(output))
    assert result.returncode == 2
    assert "--rpm must be a finite nonnegative number" in result.stderr
    assert not output.exists()


def test_invalid_minimum_interval_stops_before_creating_output(tmp_path):
    output = tmp_path / "benchmark-output"
    result = run_script("--min-interval", "-1", "--output-dir", str(output))
    assert result.returncode == 2
    assert "--min-interval must be a finite nonnegative number" in result.stderr
    assert not output.exists()


def test_pacing_and_artifact_paths_reach_the_expected_suites(tmp_path):
    project = tmp_path / "project"
    scripts = project / "scripts"
    tests_dir = project / "tests"
    bin_dir = project / "bin"
    scripts.mkdir(parents=True)
    tests_dir.mkdir()
    bin_dir.mkdir()

    copied_script = scripts / "benchmark-models"
    copied_script.write_text(SCRIPT.read_text())
    copied_script.chmod(0o755)

    (tests_dir / "__init__.py").write_text("")
    (tests_dir / "benchmarking.py").write_text(
        '''import json
import pathlib
import sys

command = sys.argv[1]
if command == "combine-model":
    model_dir = pathlib.Path(sys.argv[2])
    model = sys.argv[sys.argv.index("--model") + 1]
    payload = {
        "schema_version": 2,
        "run": {"models": [model], "pacing": {"requests_per_minute": 20.0, "minimum_interval_seconds": 1.0}},
        "benchmarks": [],
        "ergo": [],
        "unassociated_provider_attempts": [],
    }
    (model_dir / "benchmark-results.json").write_text(json.dumps(payload))
elif command == "combine":
    output = pathlib.Path(sys.argv[2])
    (output / "benchmark-results.json").write_text("{}")
    (output / "benchmark-results.md").write_text("ok\\n")
elif command == "add-failure":
    path = pathlib.Path(sys.argv[2])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"status":"failed"}\\n')
'''
    )

    invocation_log = project / "invocations.log"
    sleep_log = project / "sleeps.log"
    test_runner = project / "test.sh"
    test_runner.write_text(
        '''#!/usr/bin/env bash
set -eu
printf '%s|%s|%s|%s|%s|%s|%s\n' \
  "$1" "$TERRAI_TEST_MODEL" "$TERRAI_TEST_PROVIDER_RPM" \
  "$TERRAI_TEST_PROVIDER_MIN_INTERVAL" "$TERRAI_TEST_LIVE_PROGRESS" \
  "$TERRAI_BENCHMARK_OUTPUT" "${TERRAI_BENCHMARK_PROVIDER_OUTPUT:-}" \
  >> "$INVOCATION_LOG"
mkdir -p "$(dirname "$TERRAI_BENCHMARK_OUTPUT")"
printf '{"status":"passed"}\n' > "$TERRAI_BENCHMARK_OUTPUT"
if [[ -n "${TERRAI_BENCHMARK_PROVIDER_OUTPUT:-}" ]]; then
  printf '{"success":true}\n' > "$TERRAI_BENCHMARK_PROVIDER_OUTPUT"
fi
'''
    )
    test_runner.chmod(0o755)

    fake_sleep = bin_dir / "sleep"
    fake_sleep.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$1\" >> \"$SLEEP_LOG\"\n"
    )
    fake_sleep.chmod(0o755)

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "INVOCATION_LOG": str(invocation_log),
        "SLEEP_LOG": str(sleep_log),
    }
    result = subprocess.run(
        [
            str(copied_script),
            "--model",
            "test/model",
            "--rpm",
            "20",
            "--min-interval",
            "1",
            "--verbose",
            "--output-dir",
            "benchmark-results/test-run",
        ],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    lines = invocation_log.read_text().splitlines()
    assert len(lines) == 2
    real = lines[0].split("|")
    ergo = lines[1].split("|")
    assert real[:5] == ["real", "test/model", "20", "1", "1"]
    assert real[5].endswith("/test_model/real-tests.jsonl")
    assert real[6].endswith("/test_model/real-provider-calls.jsonl")
    assert ergo[:5] == ["ergo", "test/model", "20", "1", "1"]
    assert ergo[5].endswith("/test_model/ergo-tests.jsonl")
    assert ergo[6] == ""
    assert sleep_log.read_text().splitlines() == ["3.0"]
    model_dir = project / "benchmark-results" / "test-run" / "test_model"
    assert (model_dir / "model.txt").read_text().strip() == "test/model"
    assert (model_dir / "benchmark-results.json").exists()
    assert (project / "benchmark-results" / "test-run" / "benchmark-results.json").exists()
