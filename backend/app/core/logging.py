"""Structured JSON logging.

Every log line is a JSON object so operators can grep/parse without reading
source code. Never pass secrets (API keys, tokens) into `extra=` — see
core.errors.ErrorCategory for how failures are classified without leaking
provider internals to end users.
"""
from __future__ import annotations

import logging
import sys
import time
import uuid
from contextvars import ContextVar

import structlog

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
session_id_ctx: ContextVar[str] = ContextVar("session_id", default="-")

_REDACT_KEYS = {"api_key", "anthropic_api_key", "authorization", "password", "token", "secret"}


def _redact_processor(_, __, event_dict):
    for key in list(event_dict.keys()):
        if key.lower() in _REDACT_KEYS:
            event_dict[key] = "***redacted***"
    return event_dict


def _inject_context(_, __, event_dict):
    event_dict.setdefault("request_id", request_id_ctx.get())
    event_dict.setdefault("session_id", session_id_ctx.get())
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _inject_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


class Timer:
    """Small helper: `with Timer() as t: ...` then `t.elapsed_ms`."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self.elapsed_ms = 0.0
        return self

    def __exit__(self, *exc) -> None:
        self.elapsed_ms = round((time.perf_counter() - self._start) * 1000, 2)
