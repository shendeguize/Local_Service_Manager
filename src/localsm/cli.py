"""Command-line interface for LocalSM."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .config import CONFIG_DIR, SERVICES_FILE, STATE_DIR, TUNNELS_FILE, load_services, load_tunnels
from .doctor import print_report, run_doctor
from .remote import scan_hosts
from .services import ServiceError, ServiceManager
from .terminal import TerminalError, launch_ssh
from .tunnels import TunnelError, TunnelManager


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="LocalSM", description="Manage local services and SSH tunnels.")
    parser.add_argument("--version", action="version", version=f"LocalSM {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    for action in ("up", "restart"):
        command = sub.add_parser(action)
        command.add_argument("service", nargs="?")
        command.add_argument("--port", type=int)
        command.add_argument("--auto-port", action="store_true")
    for action in ("down", "status"):
        command = sub.add_parser(action)
        command.add_argument("service", nargs="?")
    set_port = sub.add_parser("set-port")
    set_port.add_argument("service")
    set_port.add_argument("port", type=int)
    execute = sub.add_parser("exec")
    execute.add_argument("service")
    execute.add_argument("exec_command", nargs=argparse.REMAINDER)
    logs = sub.add_parser("logs")
    logs.add_argument("service")
    logs.add_argument("--lines", type=int, default=40)

    remote = sub.add_parser("remote")
    remote_sub = remote.add_subparsers(dest="remote_command", required=True)
    scan = remote_sub.add_parser("scan")
    scan.add_argument("hosts", nargs="*")
    scan.add_argument("--timeout", type=int, default=8)

    tunnel = sub.add_parser("tunnel")
    tunnel_sub = tunnel.add_subparsers(dest="tunnel_command", required=True)
    add = tunnel_sub.add_parser("add")
    add.add_argument("name")
    add.add_argument("host")
    add.add_argument("local_port", type=int)
    add.add_argument("remote_port", type=int)
    add.add_argument("--remote-host", default="127.0.0.1")
    remove = tunnel_sub.add_parser("rm")
    remove.add_argument("name")
    tunnel_sub.add_parser("list")
    ensure = tunnel_sub.add_parser("ensure")
    ensure.add_argument("name", nargs="?")

    ssh = sub.add_parser("ssh")
    ssh.add_argument("host")
    ssh.add_argument("--app", choices=("ghostty", "terminal"), default="ghostty")
    sub.add_parser("web", help="start the managed web dashboard")
    sub.add_parser("config", help="show active configuration and state paths")
    doctor = sub.add_parser("doctor", help="check the local environment and SSH hosts")
    doctor.add_argument("--local-only", action="store_true", help="skip remote Host connectivity checks")
    doctor.add_argument("--timeout", type=int, default=8)
    return parser


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _show_config() -> int:
    services, pool = load_services()
    tunnels = load_tunnels()
    print(f"config_dir: {CONFIG_DIR}")
    print(f"services_file: {SERVICES_FILE}")
    print(f"tunnels_file: {TUNNELS_FILE}")
    print(f"state_dir: {STATE_DIR}")
    print(f"port_pool: {pool[0]}-{pool[1]}")
    print(f"tunnels: {len(tunnels)}")
    print("\nservices:")
    for name, service in sorted(services.items()):
        preferred = service.preferred_port or "auto"
        print(f"  {name}: preferred={preferred} start={service.start}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            return print_report(run_doctor(local_only=args.local_only, timeout=args.timeout))
        if args.command == "config":
            return _show_config()
        manager = ServiceManager()
        if args.command in ("up", "restart"):
            names = [args.service] if args.service else sorted(manager.services)
            results = [
                (manager.up if args.command == "up" else manager.restart)(
                    name, requested_port=args.port, auto_port=args.auto_port
                )
                for name in names
            ]
            for result in results:
                print(_status_line(result))
            return 0
        if args.command in ("down", "status"):
            names = [args.service] if args.service else sorted(manager.services)
            results = [manager.down(name) if args.command == "down" else manager.status(name) for name in names]
            for result in results:
                print(_status_line(result))
            return 0
        if args.command == "set-port":
            result = manager.set_port(args.service, args.port)
            print(_status_line(result) if result else f"{args.service} port set to {args.port}")
            return 0
        if args.command == "exec":
            return manager.execute(args.service, args.exec_command)
        if args.command == "logs":
            print(manager.logs(args.service, args.lines), end="")
            return 0
        if args.command == "remote":
            if args.remote_command == "scan":
                _print_json(scan_hosts(args.hosts or None, timeout=args.timeout))
                return 0
        tunnels = TunnelManager()
        if args.command == "tunnel":
            if args.tunnel_command == "add":
                _print_json(tunnels.add(args.name, args.host, args.local_port, args.remote_port, args.remote_host))
            elif args.tunnel_command == "rm":
                tunnels.remove(args.name)
                print(f"removed {args.name}")
            elif args.tunnel_command == "list":
                _print_json(tunnels.list())
            else:
                _print_json(tunnels.ensure(args.name))
            return 0
        if args.command == "ssh":
            launch_ssh(args.host, args.app)
            print(f"launched {args.app} SSH session for {args.host}")
            return 0
        if args.command == "web":
            result = manager.up("web")
            print(_status_line(result))
            return 0
    except (ServiceError, TunnelError, TerminalError) as exc:
        print(f"LocalSM error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
