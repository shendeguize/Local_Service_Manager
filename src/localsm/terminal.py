"""Launch an SSH session in a macOS terminal application."""

from __future__ import annotations

import re
import shlex
import subprocess


class TerminalError(RuntimeError):
    """Raised when a terminal application cannot be launched."""


def launch_ssh(host: str, app: str = "ghostty") -> None:
    if not host or not re.fullmatch(r"[A-Za-z0-9_.:@-]+", host):
        raise TerminalError("host must be a single non-empty value")
    if app == "ghostty":
        command = ["open", "-na", "Ghostty", "--args", "-e", "ssh", host]
        try:
            subprocess.Popen(command, start_new_session=True)
        except OSError as exc:
            raise TerminalError(f"cannot launch Ghostty: {exc}") from exc
        return
    if app == "terminal":
        command = f"ssh {shlex.quote(host)}"
        escaped = command.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "Terminal" to do script "{escaped}"'
        result = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)
        if result.returncode:
            raise TerminalError(result.stderr.strip() or "Terminal.app launch failed")
        return
    raise TerminalError("app must be ghostty or terminal")
