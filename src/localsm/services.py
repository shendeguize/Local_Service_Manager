"""Detached local service lifecycle management."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import ServiceConfig, ensure_directories, load_services, state_dir
from .logs import log_path, parse_actual_port, parse_actual_url, read_log
from .ports import PortError, allocate_port


class ServiceError(RuntimeError):
    """Raised for service lifecycle failures."""


@dataclass
class ServiceStatus:
    name: str
    state: str
    pid: int | None = None
    port: int | None = None
    url: str | None = None
    log: str = ""
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ServiceManager:
    def __init__(self, services: dict[str, ServiceConfig] | None = None, port_pool: tuple[int, int] = (8000, 8999)):
        ensure_directories()
        if services is None:
            services, port_pool = load_services()
        self.services = services
        self.port_pool = port_pool

    def _config(self, name: str) -> ServiceConfig:
        try:
            return self.services[name]
        except KeyError as exc:
            available = ", ".join(sorted(self.services))
            raise ServiceError(f"unknown service {name!r}; available: {available}") from exc

    def _pid_path(self, name: str) -> Path:
        return state_dir() / "pids" / f"{name}.pid"

    def _read_pid(self, name: str) -> int | None:
        try:
            pid = int(self._pid_path(name).read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            return None
        return pid if pid > 0 else None

    def _pid_alive(self, pid: int | None) -> bool:
        if pid is None:
            return False
        try:
            state = subprocess.run(
                ["ps", "-p", str(pid), "-o", "state="],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            if not state or state.startswith("Z"):
                return False
        except OSError:
            pass
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return False
        except OSError:
            return False
        return True

    def _working_dir(self, config: ServiceConfig) -> str | None:
        if config.working_dir:
            return str(Path(config.working_dir).expanduser())
        return None

    def _render(self, command: str, port: int | None, current_port: int | None = None) -> str:
        values = {
            "port": port or "",
            "current_port": current_port or "",
            "python": os.environ.get("PYTHON", os.sys.executable),
        }
        try:
            return command.format(**values)
        except KeyError as exc:
            raise ServiceError(f"unsupported command template variable: {exc.args[0]}") from exc

    def status(self, name: str) -> ServiceStatus:
        config = self._config(name)
        pid = self._read_pid(name)
        text = read_log(state_dir(), name)
        port = parse_actual_port(text)
        url = parse_actual_url(text) if config.url_from_log else None
        if self._pid_alive(pid):
            return ServiceStatus(name, "running", pid, port, url, text)
        if pid is not None:
            self._pid_path(name).unlink(missing_ok=True)
        if config.status_cmd:
            external = self._external_status(config)
            if external is not None:
                return external
        return ServiceStatus(name, "stopped", None, port, url, text)

    def _external_status(self, config: ServiceConfig) -> ServiceStatus | None:
        try:
            result = subprocess.run(
                config.status_cmd or "",
                shell=True,
                executable=os.environ.get("SHELL", "/bin/zsh"),
                cwd=self._working_dir(config),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        output = (result.stdout + result.stderr).strip()
        if result.returncode or not output:
            return None
        lowered = output.lower()
        if any(marker in lowered for marker in ("未运行", "stopped", "not running", "not found")):
            return None
        if not any(marker in lowered for marker in ("运行中", "running", "已运行")):
            return None
        pid_match = re.search(r"\bpid\s+(\d+)", output, re.IGNORECASE)
        port_match = re.search(r"(?:端口|port)\s+(\d+)", output, re.IGNORECASE)
        port = int(port_match.group(1)) if port_match else None
        return ServiceStatus(config.name, "running", int(pid_match.group(1)) if pid_match else None, port, None, output)

    def all_status(self) -> list[ServiceStatus]:
        return [self.status(name) for name in sorted(self.services)]

    def up(self, name: str, requested_port: int | None = None, auto_port: bool = False) -> ServiceStatus:
        config = self._config(name)
        current = self.status(name)
        if current.state == "running":
            return current
        try:
            port = allocate_port(
                name,
                config.preferred_port,
                config.port_range or self.port_pool,
                requested=requested_port,
                auto=auto_port,
            )
        except PortError as exc:
            raise ServiceError(str(exc)) from exc
        command = self._render(config.start, port)
        path = log_path(state_dir(), name)
        path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = path.open("a", encoding="utf-8")
        env = os.environ.copy()
        if config.env:
            env.update(config.env)
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                executable=os.environ.get("SHELL", "/bin/zsh"),
                cwd=self._working_dir(config),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            log_handle.close()
            raise ServiceError(f"cannot start {name}: {exc}") from exc
        finally:
            if not log_handle.closed:
                log_handle.close()
        self._pid_path(name).write_text(f"{process.pid}\n", encoding="ascii")
        time.sleep(0.15)
        result = self.status(name)
        # The child is intentionally detached; Popen must not try to reap it
        # when its short-lived Python wrapper object is garbage-collected.
        process.returncode = 0
        if result.state != "running":
            detail = result.log.splitlines()[-1] if result.log else "process exited immediately"
            raise ServiceError(f"{name} failed to start: {detail}")
        if result.port is None:
            result.port = port
        return result

    def down(self, name: str) -> ServiceStatus:
        config = self._config(name)
        pid = self._read_pid(name)
        if self._pid_alive(pid):
            try:
                os.killpg(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            deadline = time.monotonic() + 5
            while self._pid_alive(pid) and time.monotonic() < deadline:
                time.sleep(0.1)
            if self._pid_alive(pid):
                try:
                    os.killpg(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        for command in config.stop:
            self._run_command(self._render(command, None), config)
        self._pid_path(name).unlink(missing_ok=True)
        return self.status(name)

    def restart(self, name: str, requested_port: int | None = None, auto_port: bool = False) -> ServiceStatus:
        self.down(name)
        return self.up(name, requested_port=requested_port, auto_port=auto_port)

    def set_port(self, name: str, port: int) -> ServiceStatus | None:
        config = self._config(name)
        if not 1 <= port <= 65535:
            raise ServiceError("port must be between 1 and 65535")
        if config.set_port:
            current_port = self.status(name).port or config.preferred_port
            for command in config.set_port:
                self._run_command(self._render(command, port, current_port), config)
            from .ports import save_port

            save_port(name, port)
            return self.status(name)
        return self.restart(name, requested_port=port)

    def execute(self, name: str, command: list[str]) -> int:
        config = self._config(name)
        if not command:
            raise ServiceError("exec requires a command")
        result = subprocess.run(command, cwd=self._working_dir(config), check=False)
        return result.returncode

    def logs(self, name: str, lines: int = 40) -> str:
        self._config(name)
        return read_log(state_dir(), name, lines)

    def _run_command(self, command: str, config: ServiceConfig) -> None:
        result = subprocess.run(
            command,
            shell=True,
            executable=os.environ.get("SHELL", "/bin/zsh"),
            cwd=self._working_dir(config),
            check=False,
        )
        if result.returncode:
            raise ServiceError(f"command failed ({result.returncode}): {command}")
