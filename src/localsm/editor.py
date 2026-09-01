"""Open LocalSM's configuration in the user's editor."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

FALLBACK_EDITOR = "vi"


class EditorError(RuntimeError):
    """Raised when the configured editor cannot be run or exits non-zero."""


def resolve_editor() -> list[str]:
    """Return the editor command, honouring the usual environment variables.

    LOCALSM_EDITOR wins so the dashboard's editor can differ from the one git
    uses. Values may carry arguments, as in `code --wait`.
    """
    for name in ("LOCALSM_EDITOR", "VISUAL", "EDITOR"):
        value = os.environ.get(name, "").strip()
        if value:
            return shlex.split(value)
    return [FALLBACK_EDITOR]


def open_in_editor(path: Path) -> None:
    command = [*resolve_editor(), str(path)]
    try:
        result = subprocess.run(command, check=False)
    except OSError as exc:
        raise EditorError(f"cannot run {command[0]!r}: {exc}") from exc
    if result.returncode:
        raise EditorError(f"{command[0]} exited with code {result.returncode}; {path} was left as it was")
