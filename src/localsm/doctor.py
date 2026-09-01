"""Environment diagnostics for LocalSM."""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import (
    ConfigError,
    ensure_directories,
    is_configured,
    load_services,
    load_tunnels,
    services_file,
    state_dir,
    tunnels_file,
)
from .remote import scan_hosts


@dataclass(frozen=True)
class Check:
    section: str
    name: str
    status: str
    detail: str


def _check_command(section: str, name: str, command: str, required: bool = True) -> Check:
    path = shutil.which(command)
    if path:
        return Check(section, name, "PASS", path)
    return Check(section, name, "FAIL" if required else "WARN", "未找到")


def service_binary(start: str) -> str | None:
    """Return the executable a service starts, when it is a plain command.

    Start commands are shell strings that may embed {port} or {python}
    placeholders. Only a literal leading token can be resolved on PATH.
    """
    head = start.strip().split(maxsplit=1)
    if not head:
        return None
    command = head[0]
    if "{" in command or "/" in command or "=" in command:
        return None
    return command


def configured_service_checks() -> list[Check]:
    try:
        services, _ = load_services()
    except ConfigError:
        return []
    checks = []
    for name in sorted(services):
        command = service_binary(services[name].start)
        if command:
            checks.append(_check_command("服务 CLI", name, command, required=False))
    return checks


def local_checks() -> list[Check]:
    checks = [
        _check_command("本地工具", "uv", "uv"),
        _check_command("本地工具", "ssh", "ssh"),
        _check_command("本地工具", "osascript", "osascript"),
    ]
    ghostty = Path("/Applications/Ghostty.app")
    checks.append(Check("本地工具", "Ghostty", "PASS" if ghostty.exists() else "WARN", str(ghostty)))
    checks.extend(configured_service_checks())
    checks.append(
        Check(
            "Python 依赖",
            "Flask",
            "PASS" if importlib.util.find_spec("flask") else "FAIL",
            "可导入" if importlib.util.find_spec("flask") else "未安装",
        )
    )
    if not is_configured():
        checks.append(
            Check("配置", "services.yaml", "FAIL", f"{services_file()} 不存在，运行 `LocalSM init` 生成初始配置")
        )
    else:
        try:
            services, pool = load_services()
            load_tunnels()
            checks.append(Check("配置", "services.yaml", "PASS", f"{len(services)} 个服务，端口池 {pool[0]}-{pool[1]}"))
            checks.append(Check("配置", "tunnels.yaml", "PASS", str(tunnels_file())))
        except ConfigError as exc:
            checks.append(Check("配置", "YAML 校验", "FAIL", str(exc)))
    try:
        ensure_directories()
        probe = state_dir() / ".doctor-write-test"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
        checks.append(Check("本地状态", "state 可写", "PASS", str(state_dir())))
    except OSError as exc:
        checks.append(Check("本地状态", "state 可写", "FAIL", str(exc)))
    return checks


def tunnel_hosts() -> list[str]:
    """The ssh hosts LocalSM's own tunnels depend on."""
    try:
        tunnels = load_tunnels()
    except ConfigError:
        return []
    return sorted({tunnel["host"] for tunnel in tunnels})


def remote_checks(timeout: int = 8) -> list[Check]:
    """Check the hosts LocalSM was told about, not everything in ssh config.

    A host in ~/.ssh/config that no tunnel references is none of LocalSM's
    business: failing on it would make `doctor` report someone else's outage,
    and scanning it would open a connection to a machine the operator never
    pointed LocalSM at.
    """
    hosts = tunnel_hosts()
    if not hosts:
        return [Check("远端 SSH", "隧道 Host", "PASS", "没有配置隧道，跳过远端检查")]
    results = scan_hosts(hosts, timeout=timeout)
    unreachable = sorted(item["host"] for item in results if not item["reachable"])
    if unreachable:
        return [
            Check(
                "远端 SSH",
                "隧道 Host 连通性",
                "FAIL",
                f"{len(results) - len(unreachable)}/{len(results)} 可达，不可达：{'、'.join(unreachable)}",
            )
        ]
    return [Check("远端 SSH", "隧道 Host 连通性", "PASS", f"{len(results)}/{len(results)} 可达")]


def run_doctor(local_only: bool = False, timeout: int = 8) -> list[Check]:
    checks = local_checks()
    if not local_only:
        checks.extend(remote_checks(timeout=timeout))
    return checks


def print_report(checks: list[Check]) -> int:
    # Grouped rather than printed in arrival order: a check that lands between
    # two others of the same section would otherwise print that header twice,
    # which is what the service checks did to the local tools around them.
    sections: dict[str, list[Check]] = {}
    for check in checks:
        sections.setdefault(check.section, []).append(check)
    for section, group in sections.items():
        print(f"\n[{section}]")
        for check in group:
            print(f"{check.status:4} {check.name}: {check.detail}")
    failed = sum(check.status == "FAIL" for check in checks)
    print(f"\n结果：{len(checks) - failed} 项通过/提示，{failed} 项失败")
    return 1 if failed else 0
