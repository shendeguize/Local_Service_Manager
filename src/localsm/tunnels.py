"""Explicit SSH local tunnel lifecycle."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from .config import ensure_directories, load_tunnels, save_tunnels, state_dir
from .ports import port_available


class TunnelError(RuntimeError):
    """Raised when a tunnel cannot be created or maintained."""


def _last_log_line(path: Path, offset: int = 0) -> str:
    """The last non-empty line written to a tunnel log after `offset`."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            lines = [line.strip() for line in handle if line.strip()]
    except OSError:
        return ""
    return lines[-1] if lines else ""


class TunnelManager:
    def __init__(self) -> None:
        ensure_directories()

    def _pid_path(self, name: str) -> Path:
        return state_dir() / "pids" / f"tunnel-{name}.pid"

    def _pid(self, name: str) -> int | None:
        try:
            return int(self._pid_path(name).read_text(encoding="ascii"))
        except (OSError, ValueError):
            return None

    @staticmethod
    def _alive(pid: int | None) -> bool:
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def list(self) -> list[dict[str, Any]]:
        result = []
        for tunnel in load_tunnels():
            item = dict(tunnel)
            item["state"] = "running" if self._alive(self._pid(str(item["name"]))) else "stopped"
            item["pid"] = self._pid(str(item["name"]))
            result.append(item)
        return result

    def add(
        self,
        name: str,
        host: str,
        local_port: int,
        remote_port: int,
        remote_host: str = "127.0.0.1",
    ) -> dict[str, Any]:
        if not all(1 <= port <= 65535 for port in (local_port, remote_port)):
            raise TunnelError("local and remote ports must be between 1 and 65535")
        if not port_available(local_port):
            raise TunnelError(f"local port {local_port} is already in use")
        tunnels = load_tunnels()
        if any(item.get("name") == name for item in tunnels):
            raise TunnelError(f"tunnel {name!r} already exists")
        command = [
            "ssh",
            "-N",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            "-L",
            f"{local_port}:{remote_host}:{remote_port}",
            host,
        ]
        log_path = state_dir() / "logs" / f"tunnel-{name}.log"
        # Only what this attempt writes is worth quoting back on failure.
        already_logged = log_path.stat().st_size if log_path.exists() else 0
        log = log_path.open("a", encoding="utf-8")
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            log.close()
            raise TunnelError(f"cannot start tunnel: {exc}") from exc
        finally:
            if not log.closed:
                log.close()
        time.sleep(0.2)
        if process.poll() is not None:
            # ssh explained itself into the log; an exit code alone would make
            # the reader go find that file to learn it was a typo in the host.
            reason = _last_log_line(log_path, already_logged)
            detail = f": {reason}" if reason else ""
            raise TunnelError(f"ssh tunnel exited with code {process.returncode}{detail}")
        # The tunnel is deliberately detached; do not let Popen's finalizer
        # warn while the SSH process continues under its pidfile.
        process.returncode = 0
        item = {
            "name": name,
            "host": host,
            "local_port": local_port,
            "remote_host": remote_host,
            "remote_port": remote_port,
        }
        tunnels.append(item)
        save_tunnels(tunnels)
        self._pid_path(name).write_text(f"{process.pid}\n", encoding="ascii")
        return {**item, "pid": process.pid, "state": "running"}

    def remove(self, name: str) -> None:
        tunnels = load_tunnels()
        matching = [item for item in tunnels if item.get("name") == name]
        if not matching:
            raise TunnelError(f"tunnel {name!r} not found")
        pid = self._pid(name)
        if self._alive(pid):
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        self._pid_path(name).unlink(missing_ok=True)
        save_tunnels([item for item in tunnels if item.get("name") != name])

    def ensure(self, name: str | None = None) -> list[dict[str, Any]]:
        definitions = load_tunnels()
        selected = [item for item in definitions if name is None or item.get("name") == name]
        if name and not selected:
            raise TunnelError(f"tunnel {name!r} not found")
        results = []
        for item in selected:
            tunnel_name = str(item["name"])
            if not self._alive(self._pid(tunnel_name)):
                self._pid_path(tunnel_name).unlink(missing_ok=True)
                # Reuse the persisted definition while replacing only its
                # dead process.  add() intentionally rejects duplicate names,
                # so temporarily remove this stale definition and restore it
                # if process creation fails.
                save_tunnels([candidate for candidate in definitions if candidate.get("name") != tunnel_name])
                try:
                    results.append(
                        self.add(
                            tunnel_name,
                            str(item["host"]),
                            int(item["local_port"]),
                            int(item["remote_port"]),
                            str(item.get("remote_host", "127.0.0.1")),
                        )
                    )
                except Exception:
                    save_tunnels(definitions)
                    raise
            else:
                results.append({**item, "pid": self._pid(tunnel_name), "state": "running"})
        return results
