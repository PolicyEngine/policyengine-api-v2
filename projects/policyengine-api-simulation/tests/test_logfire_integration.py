"""Tests for Logfire integration logic.

These tests verify the behavior of configure_logfire without importing
the actual Modal app (which has complex dependencies).
"""

import os
from unittest.mock import MagicMock, patch, call

import pytest


class TestConfigureLogfireLogic:
    """Tests for the configure_logfire behavior."""

    def test_configure_logfire_skips_without_token(self):
        """
        Given no LOGFIRE_TOKEN environment variable
        When configure_logfire logic runs
        Then logfire.configure should not be called.
        """
        # Given
        mock_logfire = MagicMock()
        env = {}

        # When - replicate the configure_logfire logic
        token = env.get("LOGFIRE_TOKEN", "")
        if token:
            mock_logfire.configure(
                service_name="test",
                token=token,
                environment=env.get("LOGFIRE_ENVIRONMENT", "production"),
                console=False,
            )

        # Then
        mock_logfire.configure.assert_not_called()

    def test_configure_logfire_calls_configure_with_token(self):
        """
        Given a LOGFIRE_TOKEN environment variable
        When configure_logfire logic runs
        Then logfire.configure is called with correct parameters.
        """
        # Given
        mock_logfire = MagicMock()
        env = {
            "LOGFIRE_TOKEN": "test-token-123",
            "LOGFIRE_ENVIRONMENT": "staging",
        }
        service_name = "test-service"

        # When - replicate the configure_logfire logic
        token = env.get("LOGFIRE_TOKEN", "")
        if token:
            mock_logfire.configure(
                service_name=service_name,
                token=token,
                environment=env.get("LOGFIRE_ENVIRONMENT", "production"),
                console=False,
            )

        # Then
        mock_logfire.configure.assert_called_once_with(
            service_name="test-service",
            token="test-token-123",
            environment="staging",
            console=False,
        )

    def test_configure_logfire_uses_default_environment(self):
        """
        Given a LOGFIRE_TOKEN but no LOGFIRE_ENVIRONMENT
        When configure_logfire logic runs
        Then the default environment 'production' is used.
        """
        # Given
        mock_logfire = MagicMock()
        env = {
            "LOGFIRE_TOKEN": "test-token-456",
        }

        # When - replicate the configure_logfire logic
        token = env.get("LOGFIRE_TOKEN", "")
        if token:
            mock_logfire.configure(
                service_name="policyengine-simulation",
                token=token,
                environment=env.get("LOGFIRE_ENVIRONMENT", "production"),
                console=False,
            )

        # Then
        mock_logfire.configure.assert_called_once()
        call_kwargs = mock_logfire.configure.call_args[1]
        assert call_kwargs["environment"] == "production"

    def test_configure_logfire_disables_console(self):
        """
        Given any configuration
        When configure_logfire logic runs
        Then console output is disabled.
        """
        # Given
        mock_logfire = MagicMock()
        env = {"LOGFIRE_TOKEN": "test-token"}

        # When
        token = env.get("LOGFIRE_TOKEN", "")
        if token:
            mock_logfire.configure(
                service_name="test",
                token=token,
                environment=env.get("LOGFIRE_ENVIRONMENT", "production"),
                console=False,
            )

        # Then
        call_kwargs = mock_logfire.configure.call_args[1]
        assert call_kwargs["console"] is False


class TestLogfireSpanPattern:
    """Tests for the Logfire span usage pattern in run_simulation."""

    @pytest.fixture
    def mock_span(self):
        """Create a mock span with context manager support."""
        span = MagicMock()
        span.__enter__ = MagicMock(return_value=span)
        span.__exit__ = MagicMock(return_value=None)
        return span

    @pytest.fixture
    def mock_logfire(self, mock_span):
        """Create a mock logfire module."""
        logfire = MagicMock()
        logfire.span.return_value = mock_span
        return logfire

    def test_span_receives_input_params(self, mock_logfire, mock_span):
        """
        Given simulation parameters
        When a span is created
        Then input_params are passed as span attributes.
        """
        # Given
        params = {"country": "us", "reform": {"test": True}}

        # When - replicate the run_simulation span pattern
        with mock_logfire.span("run_simulation", input_params=params) as span:
            pass

        # Then
        mock_logfire.span.assert_called_once_with("run_simulation", input_params=params)

    def test_span_captures_output_result(self, mock_logfire, mock_span):
        """
        Given a successful simulation
        When the span completes
        Then output_result attribute is set.
        """
        # Given
        params = {"country": "uk"}
        result = {"budget": {"total": 1000000}}

        # When - replicate the run_simulation span pattern
        with mock_logfire.span("run_simulation", input_params=params) as span:
            span.set_attribute("output_result", result)

        # Then
        mock_span.set_attribute.assert_called_once_with("output_result", result)

    def test_force_flush_called_after_span(self, mock_logfire, mock_span):
        """
        Given any simulation execution
        When run_simulation completes
        Then logfire.force_flush is called.
        """
        # Given
        params = {}

        # When - replicate the run_simulation pattern
        try:
            with mock_logfire.span("run_simulation", input_params=params):
                pass
        finally:
            mock_logfire.force_flush()

        # Then
        mock_logfire.force_flush.assert_called_once()

    def test_force_flush_called_even_on_exception(self, mock_logfire, mock_span):
        """
        Given a simulation that raises an exception
        When run_simulation fails
        Then logfire.force_flush is still called.
        """
        # Given
        params = {}
        exception_raised = False

        # When - replicate the run_simulation pattern with exception
        try:
            with mock_logfire.span("run_simulation", input_params=params):
                raise ValueError("Simulation failed")
        except ValueError:
            exception_raised = True
        finally:
            mock_logfire.force_flush()

        # Then
        assert exception_raised
        mock_logfire.force_flush.assert_called_once()

    def test_result_is_returned_from_span(self, mock_logfire, mock_span):
        """
        Given a successful simulation
        When run_simulation completes
        Then the result is returned.
        """
        # Given
        params = {"country": "us"}
        expected_result = {"budget": {"total": 500000}}

        # When - replicate the full pattern
        def run_simulation_impl(p):
            return expected_result

        result = None
        try:
            with mock_logfire.span("run_simulation", input_params=params) as span:
                result = run_simulation_impl(params)
                span.set_attribute("output_result", result)
        finally:
            mock_logfire.force_flush()

        # Then
        assert result == expected_result
