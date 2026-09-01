"""Command-line interface for LocalSM."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from typing import Any

from . import __version__
from .config import (
    ConfigError,
    config_dir,
    is_configured,
    load_services,
    load_tunnels,
    services_file,
    state_dir,
    tunnels_file,
)
from .doctor import print_report, run_doctor
from .remote import scan_hosts
from .scaffold import scaffold_config
from .services import ServiceError, ServiceManager
from .terminal import TerminalError, launch_ssh
from .tunnels import TunnelError, TunnelManager

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_UNHANDLED = 2


def _status_line(item: object) -> str:
    data = item.as_dict() if hasattr(item, "as_dict") else item
    assert isinstance(data, dict)
    details = [str(data["name"]), str(data["state"])]
    if data.get("pid"):
        details.append(f"pid={data['pid']}")
    if data.get("port"):
        details.append(f"port={data['port']}")
    if data.get("url"):
        details.append(f"url={data['url']}")
    return " ".join(details)


class Output:
    """Route each command's result to either the JSON contract or humans."""

    def __init__(self, as_json: bool = False, quiet: bool = False) -> None:
        self.as_json = as_json
        self.quiet = quiet

    def emit(self, payload: Any, lines: list[str] | None = None) -> None:
        if self.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        elif not self.quiet:
            for line in lines or []:
                print(line)

    def emit_raw(self, payload: Any, text: str) -> None:
        """Emit content that is already formatted, such as log output."""
        if self.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        elif not self.quiet:
            print(text, end="")


def _global_flags() -> argparse.ArgumentParser:
    # SUPPRESS keeps an unset flag out of the namespace, so `LocalSM --json up`
    # is not overwritten by the subparser's own default.
    flags = argparse.ArgumentParser(add_help=False)
    flags.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="emit machine-readable JSON instead of human-readable text",
    )
    flags.add_argument(
        "--quiet",
        action="store_true",
        default=argparse.SUPPRESS,
        help="suppress informational output; errors still go to stderr",
    )
    return flags


def build_parser() -> argparse.ArgumentParser:
    flags = _global_flags()
    parser = argparse.ArgumentParser(
        prog="LocalSM",
        description="Manage local services and SSH tunnels.",
        parents=[flags],
    )
    parser.add_argument("--version", action="version", version=f"LocalSM {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, **kwargs: Any) -> argparse.ArgumentParser:
        return sub.add_parser(name, parents=[flags], **kwargs)

    for action in ("up", "restart"):
        command = add(action)
        command.add_argument("service", nargs="?")
        command.add_argument("--port", type=int)
        command.add_argument("--auto-port", action="store_true")
    for action in ("down", "status"):
        command = add(action)
        command.add_argument("service", nargs="?")
    set_port = add("set-port")
    set_port.add_argument("service")
    set_port.add_argument("port", type=int)
    execute = add("exec")
    execute.add_argument("service")
    execute.add_argument("exec_command", nargs=argparse.REMAINDER)
    logs = add("logs")
    logs.add_argument("service")
    logs.add_argument("--lines", type=int, default=40)

    remote = add("remote")
    remote_sub = remote.add_subparsers(dest="remote_command", required=True)
    scan = remote_sub.add_parser("scan", parents=[flags])
    scan.add_argument("hosts", nargs="*")
    scan.add_argument("--timeout", type=int, default=8)

    tunnel = add("tunnel")
    tunnel_sub = tunnel.add_subparsers(dest="tunnel_command", required=True)
    tunnel_add = tunnel_sub.add_parser("add", parents=[flags])
    tunnel_add.add_argument("name")
    tunnel_add.add_argument("host")
    tunnel_add.add_argument("local_port", type=int)
    tunnel_add.add_argument("remote_port", type=int)
    tunnel_add.add_argument("--remote-host", default="127.0.0.1")
    remove = tunnel_sub.add_parser("rm", parents=[flags])
    remove.add_argument("name")
    tunnel_sub.add_parser("list", parents=[flags])
    ensure = tunnel_sub.add_parser("ensure", parents=[flags])
    ensure.add_argument("name", nargs="?")

    ssh = add("ssh")
    ssh.add_argument("host")
    ssh.add_argument("--app", choices=("ghostty", "terminal"), default="ghostty")
    add("init", help="create starter configuration files without overwriting")
    add("web", help="start the managed web dashboard")
    add("config", help="show active configuration and state paths")
    doctor = add("doctor", help="check the local environment and SSH hosts")
    doctor.add_argument("--local-only", action="store_true", help="skip remote Host connectivity checks")
    doctor.add_argument("--timeout", type=int, default=8)
    return parser


def _warn_when_unconfigured(command: str | None) -> None:
    if command in ("init", "doctor", None) or is_configured():
        return
    print(
        f"LocalSM: no configuration at {services_file()}. Run 'LocalSM init' to create one.",
        file=sys.stderr,
    )


def _run_init(out: Output) -> int:
    report = scaffold_config()
    lines = [f"created {path}" for path in report["created"]]
    lines += [f"kept {path}" for path in report["skipped"]]
    lines.append(f"config directory: {report['config_dir']}")
    out.emit(report, lines)
    return EXIT_OK


def _run_config(out: Output) -> int:
    services, pool = load_services()
    tunnels = load_tunnels()
    payload = {
        "config_dir": str(config_dir()),
        "services_file": str(services_file()),
        "tunnels_file": str(tunnels_file()),
        "state_dir": str(state_dir()),
        "port_pool": [pool[0], pool[1]],
        "tunnels": len(tunnels),
        "services": [
            {"name": name, "preferred_port": service.preferred_port, "start": service.start}
            for name, service in sorted(services.items())
        ],
    }
    lines = [
        f"config_dir: {payload['config_dir']}",
        f"services_file: {payload['services_file']}",
        f"tunnels_file: {payload['tunnels_file']}",
        f"state_dir: {payload['state_dir']}",
        f"port_pool: {pool[0]}-{pool[1]}",
        f"tunnels: {len(tunnels)}",
        "",
        "services:",
    ]
    for name, service in sorted(services.items()):
        lines.append(f"  {name}: preferred={service.preferred_port or 'auto'} start={service.start}")
    out.emit(payload, lines)
    return EXIT_OK


def _run_doctor(out: Output, local_only: bool, timeout: int) -> int:
    checks = run_doctor(local_only=local_only, timeout=timeout)
    if out.as_json:
        payload = {
            "checks": [dataclasses.asdict(check) for check in checks],
            "failed": sum(check.status == "FAIL" for check in checks),
        }
        out.emit(payload)
        return EXIT_ERROR if payload["failed"] else EXIT_OK
    if out.quiet:
        return EXIT_ERROR if any(check.status == "FAIL" for check in checks) else EXIT_OK
    return print_report(checks)


def _remote_line(item: dict[str, Any]) -> str:
    reach = "reachable" if item.get("reachable") else "unreachable"
    ports = ",".join(str(port) for port in item.get("ports") or []) or "-"
    line = f"{item.get('host')} {reach} ports={ports}"
    if item.get("error"):
        line += f" error={item['error'].splitlines()[0]}"
    return line


def _tunnel_line(item: dict[str, Any]) -> str:
    mapping = f"{item.get('local_port')}->{item.get('remote_host', '127.0.0.1')}:{item.get('remote_port')}"
    line = f"{item.get('name')} {item.get('host')} {mapping} {item.get('state', 'unknown')}"
    if item.get("pid"):
        line += f" pid={item['pid']}"
    return line


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = getattr(args, "command", None)
    out = Output(getattr(args, "json", False), getattr(args, "quiet", False))
    try:
        _warn_when_unconfigured(command)
        if command == "init":
            return _run_init(out)
        if command == "doctor":
            return _run_doctor(out, args.local_only, args.timeout)
        if command == "config":
            return _run_config(out)
        manager = ServiceManager()
        if command in ("up", "restart"):
            names = [args.service] if args.service else sorted(manager.services)
            action = manager.up if command == "up" else manager.restart
            results = [action(name, requested_port=args.port, auto_port=args.auto_port) for name in names]
            out.emit([item.as_dict() for item in results], [_status_line(item) for item in results])
            return EXIT_OK
        if command in ("down", "status"):
            names = [args.service] if args.service else sorted(manager.services)
            results = [manager.down(name) if command == "down" else manager.status(name) for name in names]
            out.emit([item.as_dict() for item in results], [_status_line(item) for item in results])
            return EXIT_OK
        if command == "set-port":
            result = manager.set_port(args.service, args.port) or manager.status(args.service)
            out.emit(result.as_dict(), [_status_line(result)])
            return EXIT_OK
        if command == "exec":
            code = manager.execute(args.service, args.exec_command)
            out.emit({"service": args.service, "command": args.exec_command, "exit_code": code})
            return code
        if command == "logs":
            content = manager.logs(args.service, args.lines)
            out.emit_raw({"service": args.service, "lines": args.lines, "content": content}, content)
            return EXIT_OK
        if command == "remote" and args.remote_command == "scan":
            results = scan_hosts(args.hosts or None, timeout=args.timeout)
            out.emit(results, [_remote_line(item) for item in results])
            return EXIT_OK
        tunnels = TunnelManager()
        if command == "tunnel":
            if args.tunnel_command == "add":
                item = tunnels.add(args.name, args.host, args.local_port, args.remote_port, args.remote_host)
                out.emit(item, [_tunnel_line(item)])
            elif args.tunnel_command == "rm":
                tunnels.remove(args.name)
                out.emit({"removed": args.name}, [f"removed {args.name}"])
            elif args.tunnel_command == "list":
                items = tunnels.list()
                out.emit(items, [_tunnel_line(item) for item in items])
            else:
                items = tunnels.ensure(args.name)
                out.emit(items, [_tunnel_line(item) for item in items])
            return EXIT_OK
        if command == "ssh":
            launch_ssh(args.host, args.app)
            out.emit(
                {"launched": args.host, "app": args.app},
                [f"launched {args.app} SSH session for {args.host}"],
            )
            return EXIT_OK
        if command == "web":
            result = manager.up("web")
            out.emit(result.as_dict(), [_status_line(result)])
            return EXIT_OK
    except (ServiceError, TunnelError, TerminalError, ConfigError) as exc:
        print(f"LocalSM error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_UNHANDLED


if __name__ == "__main__":
    raise SystemExit(main())
