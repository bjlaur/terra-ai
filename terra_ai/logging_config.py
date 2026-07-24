"""Owned, correlated logging for the TerraAI plugin."""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable

from terra_ai.errors import current_correlation_id, log_expected_error, new_correlation_id


TRACE = 5
TRACE_LOGGER_NAME = "terraai.openrouter.trace"
_OWNED_HANDLER = "_terraai_owned_handler"
_REDACTED = "[REDACTED]"

logging.addLevelName(TRACE, "TRACE")


class CorrelationFilter(logging.Filter):
    """Attach the active event correlation ID to a log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "correlation_id"):
            correlation_id = current_correlation_id()
            if correlation_id is None and record.levelno >= logging.ERROR:
                correlation_id = new_correlation_id()
            record.correlation_id = correlation_id or "--------"
        return True


class RedactingFormatter(logging.Formatter):
    """Remove configured API keys from the final rendered record."""

    def __init__(self, *args, secrets: Iterable[str] = (), **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._secrets = tuple(str(secret) for secret in secrets if secret)

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        for secret in self._secrets:
            rendered = rendered.replace(secret, _REDACTED)
        return rendered


class TraceOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.name == TRACE_LOGGER_NAME and record.levelno == TRACE


def _owned(handler: logging.Handler) -> logging.Handler:
    setattr(handler, _OWNED_HANDLER, True)
    return handler


def shutdown_logging() -> None:
    """Remove and close only handlers owned by TerraAI."""
    logger = logging.getLogger("terraai")
    for handler in list(logger.handlers):
        if getattr(handler, _OWNED_HANDLER, False):
            logger.removeHandler(handler)
            handler.close()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


def configure_logging(
    *,
    log_dir: str | os.PathLike[str],
    secrets: Iterable[str] = (),
    log_max_bytes: int = 10 * 1024 * 1024,
    log_backup_count: int = 5,
    trace_max_bytes: int = 25 * 1024 * 1024,
    trace_backup_count: int = 2,
    sopel_console: logging.Handler | None = None,
) -> tuple[Path, Path]:
    """Install reload-safe operational, trace, and stderr handlers."""
    if not str(log_dir).strip():
        raise ValueError("log_dir must not be empty")
    for name, value in (
        ("log_max_bytes", log_max_bytes),
        ("log_backup_count", log_backup_count),
        ("trace_max_bytes", trace_max_bytes),
        ("trace_backup_count", trace_backup_count),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    shutdown_logging()

    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    operational_path = directory / "terra-ai.log"
    trace_path = directory / "openrouter-trace.jsonl"

    context_filter = CorrelationFilter()
    formatter = RedactingFormatter(
        "%(asctime)s %(levelname)s [%(correlation_id)s] "
        "%(name)s %(filename)s:%(lineno)d: %(message)s",
        secrets=secrets,
    )

    operational = _owned(
        RotatingFileHandler(
            operational_path,
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
            encoding="utf-8",
        )
    )
    operational.setLevel(logging.DEBUG)
    operational.addFilter(context_filter)
    operational.setFormatter(formatter)

    trace = _owned(
        RotatingFileHandler(
            trace_path,
            maxBytes=trace_max_bytes,
            backupCount=trace_backup_count,
            encoding="utf-8",
        )
    )
    trace.setLevel(TRACE)
    trace.addFilter(TraceOnlyFilter())
    trace.addFilter(context_filter)
    trace.setFormatter(RedactingFormatter("%(message)s", secrets=secrets))

    stream = getattr(sopel_console, "stream", None) or sys.stderr
    console = _owned(logging.StreamHandler(stream))
    console.setLevel(logging.INFO)
    console.addFilter(context_filter)
    console.setFormatter(formatter)

    logger = logging.getLogger("terraai")
    logger.disabled = False
    logger.setLevel(TRACE)
    logger.propagate = False
    logger.addHandler(operational)
    logger.addHandler(trace)
    logger.addHandler(console)

    trace_logger = logging.getLogger(TRACE_LOGGER_NAME)
    trace_logger.disabled = False
    return operational_path, trace_path


def trace_openrouter(event: Mapping[str, object]) -> None:
    """Best-effort write of one structured OpenRouter wire event."""
    try:
        payload = dict(event)
        payload.setdefault(
            "timestamp",
            datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
        )
        payload.setdefault("correlation_id", current_correlation_id())
        rendered = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
        logging.getLogger(TRACE_LOGGER_NAME).log(TRACE, rendered)
    except Exception as exc:
        try:
            log_expected_error(exc, "OpenRouter trace telemetry")
        except Exception:
            return
