#!/usr/bin/env python3
"""Reject runtime state and generated files from the tracked repository."""

from __future__ import annotations

import subprocess
import sys

ALLOWED_STATE_FILES = {"state/.gitkeep", "state/logs/.gitkeep"}
FORBIDDEN_PREFIXES = (
    ".venv/",
    ".pytest_cache/",
    "htmlcov/",
    "dist/",
    "__pycache__/",
)
FORBIDDEN_FILES = {".coverage"}


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True, text=False)
    return [path for path in result.stdout.decode().split("\0") if path]


def forbidden(path: str) -> bool:
    if path in ALLOWED_STATE_FILES:
        return False
    if path.startswith("state/"):
        return True
    if path in FORBIDDEN_FILES or path.endswith((".pyc", ".pyo")):
        return True
    return path.startswith(FORBIDDEN_PREFIXES)


def main() -> int:
    violations = [path for path in tracked_files() if forbidden(path)]
    if violations:
        print("Generated or runtime files are tracked:", file=sys.stderr)
        print("\n".join(f"  {path}" for path in violations), file=sys.stderr)
        return 1
    print("Repository hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
