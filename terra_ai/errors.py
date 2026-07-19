"""Event-scoped error reporting shared by TerraAI's plugin boundaries."""

from __future__ import annotations

import logging
import os
import traceback
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator

from terra_ai.prompts.defaults import IRC_SAFE_BYTES
from terra_ai.irc import limit_utf8


logger = logging.getLogger("terraai")

_correlation_id: ContextVar[str | None] = ContextVar(
    "terraai_correlation_id", default=None
)
_continuing_error_output: ContextVar[Callable[[str], None] | None] = ContextVar(
    "terraai_continuing_error_output", default=None
)


def current_correlation_id() -> str | None:
    """Return the active inbound-event correlation ID, if there is one."""
    return _correlation_id.get()


def new_correlation_id() -> str:
    """Return a new standalone correlation ID."""
    return uuid.uuid4().hex[:8]


def _get_or_create_correlation_id() -> str:
    correlation_id = current_correlation_id()
    if correlation_id is None:
        correlation_id = new_correlation_id()
    return correlation_id


@contextmanager
def event_error_scope(
    continuing_error_output: Callable[[str], None],
    event: object | None = None,
) -> Iterator[str]:
    """Establish error context for one plugin handler invocation."""
    correlation_id = None
    if event is not None:
        correlation_id = getattr(event, "_terraai_correlation_id", None)
    correlation_id = correlation_id or _get_or_create_correlation_id()
    if event is not None and not hasattr(event, "_terraai_correlation_id"):
        setattr(event, "_terraai_correlation_id", correlation_id)
    correlation_token = _correlation_id.set(correlation_id)
    output_token = _continuing_error_output.set(continuing_error_output)
    try:
        yield correlation_id
    finally:
        _continuing_error_output.reset(output_token)
        _correlation_id.reset(correlation_token)


def _exception_source(exc: BaseException) -> str:
    frames = traceback.extract_tb(exc.__traceback__)
    if not frames:
        return "unknown:0"
    origin = frames[-1]
    return f"{os.path.basename(origin.filename)}:{origin.lineno}"


def format_irc_error(exc: BaseException) -> str:
    """Build a compact, locatable IRC error message for *exc*."""
    correlation_id = _get_or_create_correlation_id()
    source = _exception_source(exc)
    detail = str(exc) or "(no details)"
    return limit_utf8(
        f"Error [{correlation_id} {source}]: {type(exc).__name__}: {detail}",
        IRC_SAFE_BYTES,
    )


def _log_exception(exc: BaseException, message: str, *args: object) -> None:
    correlation_id = _get_or_create_correlation_id()
    source = _exception_source(exc)
    logger.error(
        "[%s %s] " + message,
        correlation_id,
        source,
        *args,
        exc_info=(type(exc), exc, exc.__traceback__),
    )


def report_terminal_error(bot, exc: BaseException, handler_name: str) -> None:
    """Log and emit the one terminal IRC error for an inbound event."""
    _log_exception(exc, "Handler %s crashed: %s", handler_name, exc)
    bot.say(format_irc_error(exc))


def report_recoverable_error(exc: BaseException, operation: str) -> None:
    """Report an unexpected recovered error, then allow valid work to continue.

    This is intentionally distinct from :func:`report_terminal_error`. It is
    the single future policy/configuration point for visible continuing errors.
    """
    _log_exception(exc, "Recovered unexpected failure in %s: %s", operation, exc)
    output = _continuing_error_output.get()
    if output is not None:
        output(format_irc_error(exc))


def log_expected_error(exc: BaseException, operation: str) -> None:
    """Log a handled expected exception without emitting an IRC error."""
    _log_exception(exc, "Handled expected failure in %s: %s", operation, exc)
