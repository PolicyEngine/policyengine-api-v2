"""Tests for gateway error-redaction helpers."""

from __future__ import annotations

import re

from src.modal.gateway import errors as errors_module


CORRELATION_RE = re.compile(r"correlation_id=([0-9a-f]{32})")


def test_log_and_redact_exception_emits_correlation_id(monkeypatch):
    class _FakeLogfire:
        def __init__(self):
            self.calls = []

        def exception(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    fake = _FakeLogfire()
    monkeypatch.setattr(errors_module, "_logfire", fake)
    monkeypatch.setattr(errors_module, "_logfire_is_configured", lambda: True)

    exc = RuntimeError(
        "Signed GCS URL https://storage.googleapis.com/foo?token=SECRET "
        "failed to resolve"
    )
    message = errors_module.log_and_redact_exception(
        exc, scope="test_scope", context={"job_id": "abc"}
    )

    match = CORRELATION_RE.search(message)
    assert match is not None, message

    assert "SECRET" not in message
    assert "token=" not in message
    assert message.startswith("Simulation failed")

    assert len(fake.calls) == 1
    # Correlation id must appear in the server-side structured log.
    _, kwargs = fake.calls[0]
    assert kwargs["correlation_id"] == match.group(1)
    assert kwargs["scope"] == "test_scope"
    assert kwargs["job_id"] == "abc"


def test_log_and_redact_exception_falls_back_to_stdlib_logger(monkeypatch, caplog):
    monkeypatch.setattr(errors_module, "_logfire", None)
    exc = ValueError("secret-parameter-name")
    with caplog.at_level("ERROR", logger="src.modal.gateway.errors"):
        message = errors_module.log_and_redact_exception(exc, scope="fallback")

    assert "secret-parameter-name" not in message
    assert message.startswith("Simulation failed")
    assert any("fallback" in record.message for record in caplog.records)
