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


@pytest.fixture(autouse=True)
def localsm_home(tmp_path, monkeypatch):
    """Point LocalSM's config and state at one isolated directory.

    Autouse, so no test can reach the developer's real configuration. The
    explicit directory overrides outrank LOCALSM_ROOT, so an ambient
    LOCALSM_ROOT in the surrounding shell cannot leak into a test run either.
    """
    monkeypatch.setenv("LOCALSM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("LOCALSM_STATE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def sample_config(localsm_home):
    """Write a minimal services.yaml for tests that need a configured install."""
    (localsm_home / "services.yaml").write_text(
        'port_pool: [18300, 18310]\nservices:\n  web:\n    start: "true"\n    preferred_port: 18300\n',
        encoding="utf-8",
    )
    return localsm_home
