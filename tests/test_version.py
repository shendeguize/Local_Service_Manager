"""Release metadata consistency checks."""

from __future__ import annotations

import importlib.metadata
import json
import tomllib
from pathlib import Path

from localsm import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_version_matches_installed_metadata():
    assert importlib.metadata.version("local-sm") == __version__


def test_hatch_version_is_the_single_project_version_source():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dynamic"] == ["version"]
    assert "version" not in project

    hatch_version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"]["version"]
    assert hatch_version == {"path": "src/localsm/__init__.py"}


def test_uv_rebuilds_when_the_version_file_changes():
    """Without this, a bump leaves stale metadata that fails the check above.

    uv decides whether the installed build is current by watching the files in
    `cache-keys`, which defaults to pyproject.toml alone — and the version is
    not in pyproject.toml.
    """
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["uv"]
    version_path = config["cache-keys"]
    assert {"file": "src/localsm/__init__.py"} in version_path
    assert {"file": "pyproject.toml"} in version_path, "setting cache-keys replaces the default"


def test_npm_wrapper_version_matches_runtime_version():
    package = json.loads((ROOT / "packages" / "npm" / "package.json").read_text(encoding="utf-8"))
    assert package["version"] == __version__
