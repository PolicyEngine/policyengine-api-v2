"""Helpers for safe gateway error reporting.

We intentionally do **not** leak ``str(exc)`` to API callers. Worker-side
exceptions routinely embed container paths, HF URLs with pre-signed tokens,
and internal parameter names that we do not want to surface to the public
internet. Instead, we record the full exception server-side via
:func:`logfire.exception` (or the configured structured logger) and return
the caller a stable generic message plus a correlation id they can cite to
support.

Two helpers live here:

- :func:`log_and_redact_exception` for request-handler code paths that want
  to surface an HTTP error body.
- :func:`make_correlation_id` for anywhere we need a free-standing id that
  can be stitched back to a logged span.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


try:
    import logfire as _logfire  # type: ignore
except Exception:  # pragma: no cover - logfire optional locally
    _logfire = None


def _logfire_is_configured() -> bool:
    if _logfire is None:
        return False
    # logfire exposes a module-global "configured" flag only in newer
    # versions; fall back to the private ``DEFAULT_LOGFIRE_INSTANCE``.
    try:
        instance = getattr(_logfire, "DEFAULT_LOGFIRE_INSTANCE", None)
        if instance is None:
            return False
        return bool(getattr(instance.config, "send_to_logfire", False))
    except Exception:
        return False


GENERIC_JOB_FAILURE_MESSAGE = "Simulation failed"


def make_correlation_id() -> str:
    return uuid.uuid4().hex


def log_and_redact_exception(
    exc: BaseException,
    *,
    scope: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Record ``exc`` with full context server-side and return a redacted
    caller-safe message paired with a correlation id.

    The public return string has the shape ``"Simulation failed
    (correlation_id=<hex>)"`` so clients can paste it into support tickets
    without needing to parse JSON. The same correlation id is attached to
    the server-side log line so operators can jump between the two.
    """

    correlation_id = make_correlation_id()
    payload = {
        "correlation_id": correlation_id,
        "scope": scope,
    }
    if context:
        payload.update(context)

    if _logfire_is_configured():
        try:
            _logfire.exception(  # type: ignore[union-attr]
                "Gateway {scope} failed",
                scope=scope,
                correlation_id=correlation_id,
                **(context or {}),
            )
        except Exception:  # pragma: no cover - defensive, never raise from logger
            logger.exception(
                "Gateway %s failed (correlation_id=%s)",
                scope,
                correlation_id,
                extra=payload,
            )
    else:
        logger.exception(
            "Gateway %s failed (correlation_id=%s)",
            scope,
            correlation_id,
            extra=payload,
        )

    return f"{GENERIC_JOB_FAILURE_MESSAGE} (correlation_id={correlation_id})"
