from io import StringIO

import pytest

from tests.progress_reporter import ProgressReporter


class FakeClock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now


def test_reports_test_names_outcomes_and_elapsed_time():
    output = StringIO()
    clock = FakeClock()
    reporter = ProgressReporter(
        heartbeat_seconds=15, output=output, clock=clock
    )

    reporter.process_line("2026-07-22T00:00:00+00:00 START tests/test_example.py::test_one\n")
    clock.now = 12.5
    reporter.process_line("2026-07-22T00:00:02+00:00 PASS tests/test_example.py::test_one\n")

    assert output.getvalue().splitlines() == [
        "[progress] START tests/test_example.py::test_one",
        "[progress] PASS tests/test_example.py::test_one elapsed=2.5s",
    ]


def test_heartbeat_reports_active_test_at_each_interval():
    output = StringIO()
    clock = FakeClock()
    reporter = ProgressReporter(
        heartbeat_seconds=15, output=output, clock=clock
    )
    reporter.process_line("timestamp START tests/test_example.py::test_slow\n")

    clock.now = 24.9
    reporter.heartbeat()
    clock.now = 25.0
    reporter.heartbeat()
    clock.now = 40.0
    reporter.heartbeat()

    assert output.getvalue().splitlines() == [
        "[progress] START tests/test_example.py::test_slow",
        "[progress] RUNNING tests/test_example.py::test_slow elapsed=15.0s",
        "[progress] RUNNING tests/test_example.py::test_slow elapsed=30.0s",
    ]


def test_rejects_nonpositive_heartbeat_interval():
    with pytest.raises(ValueError, match="must be positive"):
        ProgressReporter(heartbeat_seconds=0)
