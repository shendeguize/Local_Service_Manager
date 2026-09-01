"""Managed process logs and best-effort URL/port extraction."""

from __future__ import annotations

import re
from pathlib import Path

URL_RE = re.compile(r"https?://[^\s)>\]]+")
PORT_RE = re.compile(r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0):(\d{1,5})")


def log_path(state_dir: Path, service: str) -> Path:
    return state_dir / "logs" / f"{service}.log"


def read_log(state_dir: Path, service: str, lines: int = 40) -> str:
    path = log_path(state_dir, service)
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    # A tail of zero is empty, not everything: [-0:] is the whole list, and a
    # negative count would drop that many lines off the front instead.
    if lines <= 0:
        return ""
    return "\n".join(content.splitlines()[-lines:])


def parse_actual_url(text: str) -> str | None:
    matches = URL_RE.findall(text)
    if not matches:
        return None
    # Keep fragments, especially kimi's #token=... URL fragment.
    return matches[-1].rstrip(".,;")


def parse_actual_port(text: str) -> int | None:
    matches = [int(value) for value in PORT_RE.findall(text) if 1 <= int(value) <= 65535]
    return matches[-1] if matches else None
