"""Live, secret-safe pytest progress and heartbeat output for benchmarks."""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Callable, TextIO


class ProgressReporter:
    """Turn the existing pytest progress log into concise live output."""

    def __init__(
        self,
        *,
        heartbeat_seconds: float,
        output: TextIO = sys.stdout,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be positive")
        self.heartbeat_seconds = heartbeat_seconds
        self.output = output
        self.clock = clock
        self.active_test: str | None = None
        self.started_at: float | None = None
        self.last_heartbeat: float | None = None

    def _write(self, message: str) -> None:
        print(f"[progress] {message}", file=self.output, flush=True)

    def process_line(self, line: str) -> bool:
        """Process one progress-log line; return true at session end."""
        _, separator, event = line.rstrip().partition(" ")
        if not separator:
            return False

        now = self.clock()
        if event.startswith("START "):
            self.active_test = event.removeprefix("START ")
            self.started_at = now
            self.last_heartbeat = now
            self._write(f"START {self.active_test}")
            return False

        for outcome in ("PASS", "FAIL", "SKIP"):
            prefix = f"{outcome} "
            if event.startswith(prefix):
                nodeid = event.removeprefix(prefix)
                elapsed = self._elapsed(now)
                self._write(f"{outcome} {nodeid} elapsed={elapsed:.1f}s")
                self.active_test = None
                self.started_at = None
                self.last_heartbeat = None
                return False

        if event.startswith("SESSION END "):
            self._write(event)
            return True
        return False

    def _elapsed(self, now: float) -> float:
        return max(0.0, now - self.started_at) if self.started_at is not None else 0.0

    def heartbeat(self) -> None:
        """Emit a heartbeat when the active test reaches the next interval."""
        if self.active_test is None or self.last_heartbeat is None:
            return
        now = self.clock()
        if now - self.last_heartbeat < self.heartbeat_seconds:
            return
        self._write(f"RUNNING {self.active_test} elapsed={self._elapsed(now):.1f}s")
        self.last_heartbeat = now


def follow(path: Path, heartbeat_seconds: float, poll_seconds: float = 0.25) -> None:
    reporter = ProgressReporter(heartbeat_seconds=heartbeat_seconds)
    stopping = False

    def request_stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    with path.open("r", encoding="utf-8") as progress:
        while not stopping:
            line = progress.readline()
            if line:
                if reporter.process_line(line):
                    return
                continue
            reporter.heartbeat()
            time.sleep(poll_seconds)

        for line in progress:
            reporter.process_line(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("progress_file", type=Path)
    parser.add_argument("--heartbeat-seconds", type=float, default=15.0)
    args = parser.parse_args(argv)
    if args.heartbeat_seconds <= 0:
        parser.error("--heartbeat-seconds must be positive")
    follow(args.progress_file, args.heartbeat_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
