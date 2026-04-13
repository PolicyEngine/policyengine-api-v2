"""Pytest plugin registration for gateway tests."""

pytest_plugins = (
    "fixtures.gateway.shared",
    "fixtures.gateway.test_endpoints",
)
