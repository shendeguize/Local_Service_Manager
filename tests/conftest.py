"""Shared pytest configuration and test-contract markers."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from localsm import launchd


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
    # Also redirect launchd agents, so no test can write to or read from the
    # developer's real ~/Library/LaunchAgents.
    monkeypatch.setenv("LOCALSM_AGENTS_DIR", str(tmp_path / "LaunchAgents"))
    return tmp_path


class FakeResult:
    """The subset of CompletedProcess that launchd.py reads."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeLaunchctl:
    """Record launchctl invocations and reply with canned results per verb."""

    def __init__(self):
        self.commands = []
        self.results = {}

    def __call__(self, command, **kwargs):
        self.commands.append(tuple(command))
        return self.results.get(command[1], self.default(command[1]))

    @staticmethod
    def default(verb: str) -> FakeResult:
        # `list` against an agent the real launchd never loaded exits non-zero,
        # which is what an unmocked run on macOS produced. The load, unload, and
        # kickstart verbs succeed, which is what it produced for those.
        if verb == "list":
            return FakeResult(returncode=113, stderr="Could not find service")
        return FakeResult()

    def __getitem__(self, index):
        return self.commands[index]


def stub_subprocess(run):
    """A subprocess stand-in carrying only what launchd.py reaches for.

    Replacing the name in launchd's namespace rather than patching
    `subprocess.run` itself keeps the real function intact for every other
    module: services.py runs `ps` through it while these tests are active.
    """
    return SimpleNamespace(
        run=run,
        TimeoutExpired=subprocess.TimeoutExpired,
    )


@pytest.fixture(autouse=True)
def fake_launchctl(monkeypatch):
    """Stand in for launchctl in every test.

    Autouse, because `enable` and `disable` otherwise bootstrap real agents into
    the developer's own launchd, and there is no launchctl at all on Linux.
    Tests that care about a specific reply set `results[verb]`. The name is
    deliberately not `launchctl`, which a test module could shadow with a
    narrower fixture and silently lose this protection.
    """
    recorder = FakeLaunchctl()
    monkeypatch.setattr(launchd, "subprocess", stub_subprocess(recorder))
    return recorder


@pytest.fixture
def sample_config(localsm_home):
    """Write a minimal services.yaml for tests that need a configured install."""
    (localsm_home / "services.yaml").write_text(
        'port_pool: [18300, 18310]\nservices:\n  web:\n    start: "true"\n    preferred_port: 18300\n',
        encoding="utf-8",
    )
    return localsm_home
