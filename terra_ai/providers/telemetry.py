"""Structured, failure-isolated provider call telemetry sinks."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from terra_ai.errors import log_expected_error

_REDACTED = "[REDACTED]"


class ProviderCallSink(Protocol):
    """Destination for one normalized provider-attempt event."""

    def record(self, event: Mapping[str, object]) -> None:
        """Persist one event without mutating it."""
        ...


class NoOpProviderCallSink:
    """Disabled telemetry sink."""

    def record(self, event: Mapping[str, object]) -> None:
        return None


class InMemoryProviderCallSink:
    """Thread-safe deterministic sink used by tests and local callers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.events: list[dict[str, object]] = []

    def record(self, event: Mapping[str, object]) -> None:
        copied = _json_round_trip(event)
        with self._lock:
            self.events.append(copied)


class CompositeProviderCallSink:
    """Fan one event out to independent sinks."""

    def __init__(self, *sinks: ProviderCallSink) -> None:
        self._sinks = tuple(sinks)

    def record(self, event: Mapping[str, object]) -> None:
        for sink in self._sinks:
            try:
                sink.record(event)
            except Exception as exc:  # diagnostics must never break providers
                _report_telemetry_failure(exc, "provider telemetry sink")


class ContextEnrichingProviderCallSink:
    """Write an enriched copy while leaving the canonical event unchanged."""

    def __init__(
        self,
        sink: ProviderCallSink,
        context_provider: Callable[[], Mapping[str, object]],
    ) -> None:
        self._sink = sink
        self._context_provider = context_provider

    def record(self, event: Mapping[str, object]) -> None:
        enriched = dict(event)
        context = self._context_provider()
        if context:
            enriched.update(context)
        self._sink.record(enriched)


class JsonlProviderCallSink:
    """Private, append-only, thread-safe JSONL sink."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        secrets: tuple[str, ...] | list[str] = (),
    ) -> None:
        self.path = Path(path)
        self._secrets = tuple(str(secret) for secret in secrets if secret)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def record(self, event: Mapping[str, object]) -> None:
        line = _serialize_event(event, self._secrets)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as output:
                output.write(line)
                output.write("\n")


class RotatingJsonlProviderCallSink:
    """Private, rotating, thread-safe JSONL sink."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        max_bytes: int = 25 * 1024 * 1024,
        backup_count: int = 2,
        secrets: tuple[str, ...] | list[str] = (),
    ) -> None:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        if (
            isinstance(backup_count, bool)
            or not isinstance(backup_count, int)
            or backup_count < 1
        ):
            raise ValueError("backup_count must be a positive integer")
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._secrets = tuple(str(secret) for secret in secrets if secret)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def record(self, event: Mapping[str, object]) -> None:
        line = _serialize_event(event, self._secrets)
        encoded_size = len((line + "\n").encode("utf-8"))
        with self._lock:
            self._rotate_if_needed(encoded_size)
            with self.path.open("a", encoding="utf-8") as output:
                output.write(line)
                output.write("\n")

    def _rotate_if_needed(self, incoming_size: int) -> None:
        current_size = self.path.stat().st_size if self.path.exists() else 0
        if current_size == 0 or current_size + incoming_size <= self.max_bytes:
            return
        oldest = self.path.with_name(f"{self.path.name}.{self.backup_count}")
        if oldest.exists():
            oldest.unlink()
        for index in range(self.backup_count - 1, 0, -1):
            source = self.path.with_name(f"{self.path.name}.{index}")
            destination = self.path.with_name(f"{self.path.name}.{index + 1}")
            if source.exists():
                source.replace(destination)
        if self.path.exists():
            rotated = self.path.with_name(f"{self.path.name}.1")
            self.path.replace(rotated)


def record_provider_event(
    sink: ProviderCallSink,
    event: Mapping[str, object],
) -> None:
    """Record nonessential telemetry without changing provider behavior."""
    try:
        sink.record(event)
    except Exception as exc:
        _report_telemetry_failure(exc, "provider telemetry")


def _report_telemetry_failure(exc: BaseException, operation: str) -> None:
    """Log telemetry failure without sending a continuing error to the user."""
    try:
        log_expected_error(exc, operation)
    except Exception:
        # Diagnostics are strictly best-effort. This also protects providers
        # from unusual logging-handler or formatter failures.
        return


def _serialize_event(
    event: Mapping[str, object],
    secrets: tuple[str, ...],
) -> str:
    line = json.dumps(
        event,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    for secret in secrets:
        line = line.replace(secret, _REDACTED)
    return line


def _json_round_trip(event: Mapping[str, object]) -> dict[str, object]:
    """Make a deep JSON-compatible copy and reject non-finite values."""
    value = json.loads(json.dumps(event, ensure_ascii=False, allow_nan=False))
    if not isinstance(value, dict):
        raise TypeError("provider telemetry event must be a JSON object")
    return value
