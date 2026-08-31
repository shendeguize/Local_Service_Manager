"""Shared pytest configuration and test-contract markers."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register the test layers used by local and CI test runs."""
    markers = {
        "unit": "isolated test of a single LocalSM component",
        "integration": "test spanning multiple LocalSM components",
        "e2e": "end-to-end test against a running LocalSM application",
        "requires_ssh": "test requiring a configured and reachable SSH host",
    }
    for name, description in markers.items():
        config.addinivalue_line("markers", f"{name}: {description}")
