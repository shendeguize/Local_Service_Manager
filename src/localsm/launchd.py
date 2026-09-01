"""Opt-in launchd agents for services that should survive logout and reboot.

LocalSM's default model is a detached process tracked by a pidfile. A service
that is `enable`d instead gets a user LaunchAgent, so launchd owns its
lifecycle: it starts at login and is restarted when it dies. Because launchd
starts the service with no LocalSM process in attendance, the port cannot be
negotiated at start time and is frozen into the plist by `enable`.
"""

from __future__ import annotations

import os
import plistlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import agents_dir

LABEL_PREFIX = "com.localsm."
PORT_VARIABLE = "LOCALSM_PORT"
# launchd's floor for respawning a job; stated explicitly so the plist is
# self-documenting rather than relying on the platform default.
THROTTLE_SECONDS = 10
_PID_PATTERN = re.compile(r'"PID"\s*=\s*(\d+);')
_EXIT_PATTERN = re.compile(r'"LastExitStatus"\s*=\s*(-?\d+);')


class LaunchdError(RuntimeError):
    """Raised when a launchd agent cannot be written, loaded, or unloaded."""


@dataclass(frozen=True)
class AgentState:
    label: str
    enabled: bool
    loaded: bool
    pid: int | None = None
    last_exit_status: int | None = None


def label_for(name: str) -> str:
    return f"{LABEL_PREFIX}{name}"


def plist_path(name: str) -> Path:
    return agents_dir() / f"{label_for(name)}.plist"


def domain_target() -> str:
    return f"gui/{os.getuid()}"


def service_target(name: str) -> str:
    return f"{domain_target()}/{label_for(name)}"


def is_enabled(name: str) -> bool:
    return plist_path(name).exists()


def enabled_services() -> list[str]:
    directory = agents_dir()
    if not directory.is_dir():
        return []
    prefix_length = len(LABEL_PREFIX)
    return sorted(path.stem[prefix_length:] for path in directory.glob(f"{LABEL_PREFIX}*.plist"))


def _launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=False, timeout=15)
    except FileNotFoundError as exc:  # pragma: no cover - launchctl is macOS-only
        raise LaunchdError("launchctl not found; launchd agents need macOS") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LaunchdError(f"launchctl {' '.join(args)} failed: {exc}") from exc


def state(name: str) -> AgentState:
    label = label_for(name)
    if not is_enabled(name):
        # Without a plist LocalSM does not manage this service, so skip the
        # launchctl call entirely: status() runs for every service on every
        # dashboard refresh.
        return AgentState(label, enabled=False, loaded=False)
    result = _launchctl("list", label)
    if result.returncode:
        return AgentState(label, enabled=True, loaded=False)
    pid = _PID_PATTERN.search(result.stdout)
    exit_status = _EXIT_PATTERN.search(result.stdout)
    return AgentState(
        label,
        enabled=True,
        loaded=True,
        pid=int(pid.group(1)) if pid else None,
        last_exit_status=int(exit_status.group(1)) if exit_status else None,
    )


def frozen_port(name: str) -> int | None:
    """Read back the port `enable` wrote into the plist."""
    try:
        with plist_path(name).open("rb") as handle:
            document = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return None
    value = (document.get("EnvironmentVariables") or {}).get(PORT_VARIABLE)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def write_plist(
    name: str,
    command: str,
    *,
    shell: str,
    log_file: Path,
    port: int | None = None,
    working_dir: str | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    environment = dict(env or {})
    if port is not None:
        environment[PORT_VARIABLE] = str(port)
    document: dict[str, object] = {
        "Label": label_for(name),
        # A login shell keeps the service's PATH the same as the one the start
        # command was written against in an interactive terminal.
        "ProgramArguments": [shell, "-lc", command],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": THROTTLE_SECONDS,
        # Same log file the detached path appends to, so `LocalSM logs` works
        # identically whichever supervisor is in charge.
        "StandardOutPath": str(log_file),
        "StandardErrorPath": str(log_file),
    }
    if working_dir:
        document["WorkingDirectory"] = working_dir
    if environment:
        document["EnvironmentVariables"] = environment
    path = plist_path(name)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            plistlib.dump(document, handle)
    except OSError as exc:
        raise LaunchdError(f"cannot write {path}: {exc}") from exc
    return path


def remove_plist(name: str) -> bool:
    path = plist_path(name)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise LaunchdError(f"cannot remove {path}: {exc}") from exc
    return True


def bootstrap(name: str) -> None:
    result = _launchctl("bootstrap", domain_target(), str(plist_path(name)))
    if result.returncode:
        message = (result.stderr or result.stdout).strip()
        # 37 / EALREADY: the agent is already loaded, which is the goal state.
        if "already" in message.lower() or result.returncode == 37:
            return
        raise LaunchdError(f"cannot load {label_for(name)}: {message or result.returncode}")


def bootout(name: str) -> None:
    result = _launchctl("bootout", service_target(name))
    if result.returncode:
        message = (result.stderr or result.stdout).strip()
        # 3 / ESRCH: no such job, so it is already unloaded.
        if "no such process" in message.lower() or "could not find" in message.lower() or result.returncode == 3:
            return
        raise LaunchdError(f"cannot unload {label_for(name)}: {message or result.returncode}")


def kickstart(name: str, restart: bool = False) -> None:
    args = ["kickstart"]
    if restart:
        args.append("-k")
    args.append(service_target(name))
    result = _launchctl(*args)
    if result.returncode:
        message = (result.stderr or result.stdout).strip()
        raise LaunchdError(f"cannot start {label_for(name)}: {message or result.returncode}")
