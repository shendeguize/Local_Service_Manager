"""SSH config parsing and concurrent remote listener scans."""

from __future__ import annotations

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import STATE_DIR, TUNNELS_FILE, ensure_directories, load_tunnels

REMOTE_PORT_COMMAND = (
    "if command -v ss >/dev/null 2>&1; then "
    "ss -ltnH; "
    "elif command -v lsof >/dev/null 2>&1; then "
    "lsof -nP -iTCP -sTCP:LISTEN; "
    "elif command -v netstat >/dev/null 2>&1; then "
    "netstat -lnt; "
    "elif command -v python3 >/dev/null 2>&1; then "
    "python3 -c 'import pathlib; "
    'files=(pathlib.Path("/proc/net/tcp"), pathlib.Path("/proc/net/tcp6")); '
    'print("\\n".join(str(int(line.split()[1].rsplit(":",1)[1],16)) '
    "for f in files if f.exists() for line in f.read_text().splitlines()[1:] "
    'if len(line.split()) > 3 and line.split()[3] == "0A"))\'; '
    "else echo 'LocalSM: neither ss, lsof, netstat, nor python3 is installed' >&2; exit 127; fi"
)


@dataclass
class SSHHost:
    alias: str
    hostname: str | None = None
    port: int = 22
    user: str | None = None
    proxy_jump: str | None = None


@dataclass
class RemoteScan:
    host: str
    reachable: bool
    ports: list[int]
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_ssh_config(path: Path | None = None) -> list[SSHHost]:
    path = path or Path.home() / ".ssh" / "config"
    if not path.exists():
        return []
    hosts: list[SSHHost] = []
    current: list[SSHHost] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        key, value = parts[0].lower(), parts[1].strip()
        if key == "host":
            current = []
            for alias in value.split():
                if alias == "*" or any(char in alias for char in "?*!"):
                    continue
                current.append(SSHHost(alias=alias))
                hosts.append(current[-1])
        elif current:
            if key == "hostname":
                for host in current:
                    host.hostname = value
            elif key == "port" and value.isdigit():
                for host in current:
                    host.port = int(value)
            elif key == "user":
                for host in current:
                    host.user = value
            elif key == "proxyjump":
                for host in current:
                    host.proxy_jump = value
    return hosts


def _parse_ss(output: str) -> list[int]:
    ports: set[int] = set()
    for line in output.splitlines():
        # ss -ltnH: LISTEN 0 128 127.0.0.1:8080 0.0.0.0:*
        match = re.search(r":(\d+)(?:\s|$)", line)
        if match and 1 <= int(match.group(1)) <= 65535:
            ports.add(int(match.group(1)))
    return sorted(ports)


def _scan_one(host: SSHHost, timeout: int = 8) -> RemoteScan:
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={timeout}",
        "-o",
        "StrictHostKeyChecking=accept-new",
        host.alias,
        REMOTE_PORT_COMMAND,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 3, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return RemoteScan(host.alias, False, [], str(exc))
    if result.returncode:
        message = (result.stderr or result.stdout or f"ssh exited {result.returncode}").strip()
        network_failure = any(
            marker in message.lower()
            for marker in ("connection timed out", "connection refused", "could not resolve", "permission denied")
        )
        return RemoteScan(host.alias, not network_failure, [], message[-500:])
    return RemoteScan(host.alias, True, _parse_ss(result.stdout))


def tunnel_coverage(host: str, port: int) -> list[str]:
    return [
        str(item.get("name"))
        for item in load_tunnels(TUNNELS_FILE)
        if item.get("host") == host and int(item.get("remote_port", -1)) == port
    ]


def scan_hosts(hosts: list[str] | None = None, timeout: int = 8) -> list[dict[str, object]]:
    configured = {item.alias: item for item in parse_ssh_config()}
    selected = [configured[name] for name in hosts if name in configured] if hosts else list(configured.values())
    unknown = [name for name in (hosts or []) if name not in configured]
    results: list[RemoteScan] = [RemoteScan(name, False, [], "host not found in ssh config") for name in unknown]
    with ThreadPoolExecutor(max_workers=min(12, max(1, len(selected)))) as executor:
        futures = {executor.submit(_scan_one, host, timeout): host.alias for host in selected}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda result: result.host)
    output = []
    for result in results:
        item = result.as_dict()
        item["tunnels"] = {str(port): tunnel_coverage(result.host, port) for port in result.ports}
        output.append(item)
    ensure_directories()
    (STATE_DIR / "remote_scan.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return output
