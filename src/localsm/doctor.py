"""Environment diagnostics for LocalSM."""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import STATE_DIR, TUNNELS_FILE, ConfigError, ensure_directories, load_services, load_tunnels
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


def local_checks() -> list[Check]:
    checks = [
        _check_command("本地工具", "uv", "uv"),
        _check_command("本地工具", "ssh", "ssh"),
        _check_command("本地工具", "osascript", "osascript"),
        _check_command("服务 CLI", "enva", "enva", required=False),
        _check_command("服务 CLI", "dshc", "dshc", required=False),
        _check_command("服务 CLI", "aqp", "aqp", required=False),
        _check_command("服务 CLI", "kimi", "kimi", required=False),
        _check_command("服务 CLI", "dsh", "dsh", required=False),
    ]
    ghostty = Path("/Applications/Ghostty.app")
    checks.append(Check("本地工具", "Ghostty", "PASS" if ghostty.exists() else "WARN", str(ghostty)))
    checks.append(
        Check(
            "Python 依赖",
            "Flask",
            "PASS" if importlib.util.find_spec("flask") else "FAIL",
            "可导入" if importlib.util.find_spec("flask") else "未安装",
        )
    )
    try:
        services, pool = load_services()
        load_tunnels()
        checks.append(Check("配置", "services.yaml", "PASS", f"{len(services)} 个服务，端口池 {pool[0]}-{pool[1]}"))
        checks.append(Check("配置", "tunnels.yaml", "PASS", str(TUNNELS_FILE)))
    except ConfigError as exc:
        checks.append(Check("配置", "YAML 校验", "FAIL", str(exc)))
    try:
        ensure_directories()
        probe = STATE_DIR / ".doctor-write-test"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
        checks.append(Check("本地状态", "state 可写", "PASS", str(STATE_DIR)))
    except OSError as exc:
        checks.append(Check("本地状态", "state 可写", "FAIL", str(exc)))
    return checks


def remote_checks(timeout: int = 8) -> list[Check]:
    results = scan_hosts(timeout=timeout)
    if not results:
        return [Check("远端 SSH", "Host 扫描", "WARN", "ssh config 中没有可扫描的 Host")]
    reachable = sum(1 for item in results if item["reachable"])
    unreachable = len(results) - reachable
    status = "PASS" if unreachable == 0 else "FAIL"
    return [Check("远端 SSH", "Host 连通性", status, f"{reachable}/{len(results)} 可达")]


def run_doctor(local_only: bool = False, timeout: int = 8) -> list[Check]:
    checks = local_checks()
    if not local_only:
        checks.extend(remote_checks(timeout=timeout))
    return checks


def print_report(checks: list[Check]) -> int:
    current_section = None
    for check in checks:
        if check.section != current_section:
            current_section = check.section
            print(f"\n[{current_section}]")
        print(f"{check.status:4} {check.name}: {check.detail}")
    failed = sum(check.status == "FAIL" for check in checks)
    print(f"\n结果：{len(checks) - failed} 项通过/提示，{failed} 项失败")
    return 1 if failed else 0
