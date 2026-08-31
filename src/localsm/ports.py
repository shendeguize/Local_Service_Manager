"""Local port probing and sticky allocation."""

from __future__ import annotations

import json
import socket
from pathlib import Path

from .config import STATE_DIR, ensure_directories


class PortError(RuntimeError):
    """Raised when a requested port cannot be allocated."""


def port_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _state_path() -> Path:
    ensure_directories()
    return STATE_DIR / "ports.json"


def load_ports() -> dict[str, int]:
    try:
        data = json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): int(v) for k, v in data.items() if isinstance(v, int) and 1 <= v <= 65535}


def save_port(service: str, port: int) -> None:
    ports = load_ports()
    ports[service] = port
    path = _state_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(ports, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def allocate_port(
    service: str,
    preferred: int | None,
    port_range: tuple[int, int] | None,
    *,
    requested: int | None = None,
    auto: bool = False,
    exclude: set[int] | None = None,
) -> int:
    if requested is not None:
        if not 1 <= requested <= 65535:
            raise PortError("port must be between 1 and 65535")
        if not port_available(requested) and requested not in (exclude or set()):
            raise PortError(f"port {requested} is already in use")
        save_port(service, requested)
        return requested

    sticky = load_ports().get(service)
    candidates: list[int] = []
    if sticky is not None:
        candidates.append(sticky)
    if preferred is not None and preferred not in candidates:
        candidates.append(preferred)
    if auto or preferred is None:
        first, last = port_range or (8000, 8999)
        candidates.extend(port for port in range(first, last + 1) if port not in candidates)
    for port in candidates:
        if port_available(port):
            save_port(service, port)
            return port
    raise PortError(f"no free port found for {service}")
