"""Configuration and state paths for LocalSM."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PORT_POOL = (8000, 8999)


class ConfigError(ValueError):
    """Raised when LocalSM configuration is invalid."""


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else None


def project_root() -> Path | None:
    """Return the LOCALSM_ROOT override, which holds both config/ and state/."""
    return _env_path("LOCALSM_ROOT")


def config_dir() -> Path:
    override = _env_path("LOCALSM_CONFIG_DIR")
    if override is not None:
        return override
    root = project_root()
    if root is not None:
        return root / "config"
    return (_env_path("XDG_CONFIG_HOME") or Path.home() / ".config") / "localsm"


def state_dir() -> Path:
    override = _env_path("LOCALSM_STATE_DIR")
    if override is not None:
        return override
    root = project_root()
    if root is not None:
        return root / "state"
    return (_env_path("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "localsm"


def agents_dir() -> Path:
    """Directory holding LocalSM's launchd agents."""
    override = _env_path("LOCALSM_AGENTS_DIR")
    if override is not None:
        return override
    root = project_root()
    if root is not None:
        return root / "LaunchAgents"
    return Path.home() / "Library" / "LaunchAgents"


def services_file() -> Path:
    return config_dir() / "services.yaml"


def tunnels_file() -> Path:
    return config_dir() / "tunnels.yaml"


def is_configured() -> bool:
    return services_file().exists()


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    start: str
    preferred_port: int | None = None
    port_range: tuple[int, int] | None = None
    set_port: tuple[str, ...] = ()
    stop: tuple[str, ...] = ()
    status_cmd: str | None = None
    url_from_log: bool = False
    working_dir: str | None = None
    env: dict[str, str] | None = None


def ensure_directories() -> None:
    root = state_dir()
    root.mkdir(parents=True, exist_ok=True)
    (root / "pids").mkdir(exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)


def _as_commands(value: Any, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value):
        return tuple(value)
    raise ConfigError(f"{label} must be a command string or list of strings")


def _port(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ConfigError(f"{label} must be an integer between 1 and 65535")
    return value


def _load_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping")
    return data


def load_services(path: Path | None = None) -> tuple[dict[str, ServiceConfig], tuple[int, int]]:
    path = path or services_file()
    data = _load_yaml(path, {"services": {}, "port_pool": list(DEFAULT_PORT_POOL)})
    raw_services = data.get("services", {})
    if not isinstance(raw_services, dict):
        raise ConfigError("services must be a mapping")
    pool = data.get("port_pool", list(DEFAULT_PORT_POOL))
    if (
        not isinstance(pool, list)
        or len(pool) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in pool)
        or not 1 <= pool[0] <= pool[1] <= 65535
    ):
        raise ConfigError("port_pool must be [first_port, last_port]")

    services: dict[str, ServiceConfig] = {}
    for name, raw in raw_services.items():
        if not isinstance(name, str) or not isinstance(raw, dict):
            raise ConfigError("each service must have a name and mapping")
        start = raw.get("start")
        if not isinstance(start, str) or not start.strip():
            raise ConfigError(f"services.{name}.start is required")
        port_range = raw.get("port_range")
        parsed_range = None
        if port_range is not None:
            if (
                not isinstance(port_range, list)
                or len(port_range) != 2
                or any(isinstance(item, bool) or not isinstance(item, int) for item in port_range)
                or not 1 <= port_range[0] <= port_range[1] <= 65535
            ):
                raise ConfigError(f"services.{name}.port_range is invalid")
            parsed_range = (port_range[0], port_range[1])
        env = raw.get("env")
        if env is not None and (
            not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items())
        ):
            raise ConfigError(f"services.{name}.env must be a string mapping")
        services[name] = ServiceConfig(
            name=name,
            start=start,
            preferred_port=_port(raw.get("preferred_port"), f"services.{name}.preferred_port"),
            port_range=parsed_range,
            set_port=_as_commands(raw.get("set_port"), f"services.{name}.set_port"),
            stop=_as_commands(raw.get("stop"), f"services.{name}.stop"),
            status_cmd=raw.get("status_cmd"),
            url_from_log=bool(raw.get("url_from_log", False)),
            working_dir=raw.get("working_dir"),
            env=env,
        )
    return services, (pool[0], pool[1])


def load_tunnels(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or tunnels_file()
    data = _load_yaml(path, {"tunnels": []})
    tunnels = data.get("tunnels", [])
    if not isinstance(tunnels, list):
        raise ConfigError("tunnels must be a list")
    for tunnel in tunnels:
        if not isinstance(tunnel, dict):
            raise ConfigError("each tunnel must be a mapping")
        for key in ("name", "host", "local_port", "remote_port"):
            if key not in tunnel:
                raise ConfigError(f"tunnel missing {key}")
    return tunnels


def save_tunnels(tunnels: list[dict[str, Any]], path: Path | None = None) -> None:
    path = path or tunnels_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(yaml.safe_dump({"tunnels": tunnels}, sort_keys=False), encoding="utf-8")
    temporary.replace(path)
