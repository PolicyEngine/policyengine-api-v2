"""Fixtures for logfire integration tests."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_span():
    """Create a mock span with context manager support."""
    span = MagicMock()
    span.__enter__ = MagicMock(return_value=span)
    span.__exit__ = MagicMock(return_value=None)
    return span


@pytest.fixture
def mock_logfire(mock_span):
    """Create a mock logfire module."""
    logfire = MagicMock()
    logfire.span.return_value = mock_span
    return logfire
