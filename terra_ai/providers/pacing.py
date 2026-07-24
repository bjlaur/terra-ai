"""Thread-safe request-start pacing for provider transports."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable


def _validated_nonnegative_number(value: float, name: str) -> float:
    """Return *value* as a finite nonnegative float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite nonnegative number")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return parsed


class RequestPacer:
    """Serialize provider request starts at a configured interval.

    The first request is admitted immediately. Later callers share one lock and
    wait until both the normal request interval and any explicit cooldown have
    expired. The lock is released before the HTTP request itself begins.
    """

    def __init__(
        self,
        requests_per_minute: float = 0,
        min_interval: float = 0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._requests_per_minute = _validated_nonnegative_number(
            requests_per_minute, "requests_per_minute"
        )
        self._min_interval = _validated_nonnegative_number(
            min_interval, "min_interval"
        )
        rpm_interval = (
            60.0 / self._requests_per_minute
            if self._requests_per_minute
            else 0.0
        )

        self._interval = max(rpm_interval, self._min_interval)
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last_started: float | None = None
        self._blocked_until = 0.0

    @property
    def requests_per_minute(self) -> float:
        """Configured requests-per-minute constraint."""
        return self._requests_per_minute

    @property
    def min_interval(self) -> float:
        """Configured minimum request-start interval, in seconds."""
        return self._min_interval

    @property
    def interval(self) -> float:
        """Effective interval between request starts, in seconds."""
        return self._interval

    @property
    def enabled(self) -> bool:
        """Whether request-start pacing imposes a positive interval."""
        return self._interval > 0

    def wait(self) -> float:
        """Wait until a request may start and return the duration waited."""
        with self._lock:
            now = self._clock()
            normal_deadline = (
                self._last_started + self._interval
                if self._last_started is not None
                else now
            )
            deadline = max(normal_deadline, self._blocked_until)
            delay = max(0.0, deadline - now)
            if delay:
                self._sleep(delay)
            started = max(self._clock(), deadline)
            self._last_started = started
            return delay

    def defer_for(self, seconds: float) -> None:
        """Block all callers for at least *seconds* from the current time."""
        delay = _validated_nonnegative_number(seconds, "seconds")
        with self._lock:
            self._blocked_until = max(
                self._blocked_until,
                self._clock() + delay,
            )
