"""Command-line interface for LocalSM."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from typing import Any

from . import __version__
from .cli_model import describe
from .completion import SHELLS, render
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
from .editor import EditorError, open_in_editor
from .launchd import LaunchdError
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
    if data.get("managed_by") == "launchd":
        details.append("launchd")
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

    verbs = {
        "up": "start a service, or every service when none is named",
        "restart": "stop and start a service, or every service when none is named",
    }
    for action, description in verbs.items():
        command = add(action, help=description)
        command.add_argument("service", nargs="?", help="service to act on; defaults to all services")
        command.add_argument("--port", type=int, help="bind this exact port instead of the configured one")
        command.add_argument("--auto-port", action="store_true", help="pick a free port from the pool when needed")
    add("down", help="stop a service, or every service when none is named").add_argument(
        "service", nargs="?", help="service to stop; defaults to all services"
    )
    add("status", help="report each service's state, pid, port, and URL").add_argument(
        "service", nargs="?", help="service to report on; defaults to all services"
    )
    set_port = add("set-port", help="move a service to a specific port")
    set_port.add_argument("service", help="service to move")
    set_port.add_argument("port", type=int, help="new port between 1 and 65535")
    execute = add("exec", help="run a command in a service's working directory")
    execute.add_argument("service", help="service whose working directory to use")
    execute.add_argument("exec_command", nargs=argparse.REMAINDER, help="command and arguments to run")
    logs = add("logs", help="show the tail of a service's log")
    logs.add_argument("service", help="service whose log to read")
    logs.add_argument("--lines", type=int, default=40, help="number of trailing lines to show (default: 40)")

    remote = add("remote", help="inspect remote SSH hosts")
    remote_sub = remote.add_subparsers(dest="remote_command", required=True)
    scan = remote_sub.add_parser("scan", parents=[flags], help="scan SSH hosts for listening ports")
    scan.add_argument("hosts", nargs="*", help="SSH host aliases to scan; defaults to every configured host")
    scan.add_argument("--timeout", type=int, default=8, help="per-host SSH timeout in seconds (default: 8)")

    tunnel = add("tunnel", help="manage SSH local port forwards")
    tunnel_sub = tunnel.add_subparsers(dest="tunnel_command", required=True)
    tunnel_add = tunnel_sub.add_parser("add", parents=[flags], help="create and start a tunnel")
    tunnel_add.add_argument("name", help="name to remember this tunnel by")
    tunnel_add.add_argument("host", help="SSH host alias from ~/.ssh/config")
    tunnel_add.add_argument("local_port", type=int, help="port to open on this machine")
    tunnel_add.add_argument("remote_port", type=int, help="port to reach on the remote side")
    tunnel_add.add_argument("--remote-host", default="127.0.0.1", help="remote bind address (default: 127.0.0.1)")
    remove = tunnel_sub.add_parser("rm", parents=[flags], help="stop a tunnel and forget its definition")
    remove.add_argument("name", help="tunnel to remove")
    tunnel_sub.add_parser("list", parents=[flags], help="list tunnel definitions and their state")
    ensure = tunnel_sub.add_parser("ensure", parents=[flags], help="restart any tunnel whose ssh process died")
    ensure.add_argument("name", nargs="?", help="tunnel to check; defaults to all tunnels")

    enable = add("enable", help="hand a service to launchd so it starts at login")
    enable.add_argument("service", help="service to place under launchd")
    enable.add_argument("--port", type=int, help="port to freeze into the launchd agent")
    disable = add("disable", help="return a service from launchd to LocalSM")
    disable.add_argument("service", help="service to take back from launchd")

    ssh = add("ssh", help="open an SSH session in a terminal application")
    ssh.add_argument("host", help="SSH host alias from ~/.ssh/config")
    ssh.add_argument(
        "--app",
        choices=("ghostty", "terminal"),
        default="ghostty",
        help="terminal application to launch (default: ghostty)",
    )
    completion = add("completion", help="print a shell completion script")
    completion.add_argument(
        "shell",
        choices=(*SHELLS, "services"),
        help="shell to generate for, or 'services' to list service names for those scripts",
    )
    add("init", help="create starter configuration files without overwriting")
    edit = add("edit", help="open the configuration in $EDITOR and report what changed")
    edit.add_argument(
        "target",
        nargs="?",
        choices=("services", "tunnels"),
        default="services",
        help="which configuration file to open (default: services)",
    )
    web = add("web", help="start the managed web dashboard")
    web.add_argument(
        "--foreground",
        action="store_true",
        help="run the dashboard in this terminal instead of detaching it",
    )
    add("config", help="show active configuration and state paths")
    doctor = add("doctor", help="check the local environment and SSH hosts")
    doctor.add_argument("--local-only", action="store_true", help="skip remote Host connectivity checks")
    doctor.add_argument("--timeout", type=int, default=8, help="per-host SSH timeout in seconds (default: 8)")
    return parser


def _warn_when_unconfigured(command: str | None) -> None:
    if command in ("init", "edit", "doctor", "completion", None) or is_configured():
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


def _run_completion(shell: str) -> int:
    if shell == "services":
        # Called by the generated completion scripts, so it must stay quiet and
        # keep working when nothing is configured yet.
        try:
            services, _ = load_services()
        except ConfigError:
            return EXIT_OK
        for name in sorted(services):
            print(name)
        return EXIT_OK
    print(render(shell, describe(build_parser())), end="")
    return EXIT_OK


def _run_edit(out: Output, target: str) -> int:
    # Scaffolding first means `edit` works on a fresh install without making
    # the user discover `init` as a separate step.
    scaffold_config()
    path = services_file() if target == "services" else tunnels_file()
    before, _ = load_services()
    open_in_editor(path)
    after, _ = load_services()

    manager = ServiceManager(after)
    changed = sorted(name for name in set(before) & set(after) if before[name] != after[name])
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    restart = [name for name in changed if manager.status(name).state == "running"]

    payload = {
        "path": str(path),
        "added": added,
        "removed": removed,
        "changed": changed,
        "restart_required": restart,
    }
    lines = [f"edited {path}"]
    for label, names in (("added", added), ("removed", removed), ("changed", changed)):
        if names:
            lines.append(f"{label}: {', '.join(names)}")
    if restart:
        lines.append(f"restart to apply: {' '.join(f'LocalSM restart {name}' for name in restart)}")
    elif not (added or removed or changed):
        lines.append("no service definitions changed")
    out.emit(payload, lines)
    return EXIT_OK


def _run_web_foreground(manager: ServiceManager, out: Output) -> int:
    # Imported here so plain CLI invocations do not pay for loading Flask.
    from .web import create_app

    current = manager.status("web")
    if current.state == "running":
        raise ServiceError(f"web is already running (pid={current.pid}); run 'LocalSM down web' first")
    port = manager.allocate_service_port("web")
    url = f"http://127.0.0.1:{port}/"
    out.emit(
        {"name": "web", "state": "foreground", "port": port, "url": url},
        [f"web foreground port={port} url={url}", "press Ctrl-C to stop"],
    )
    try:
        create_app().run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass
    return EXIT_OK


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
        if command == "edit":
            return _run_edit(out, args.target)
        if command == "completion":
            return _run_completion(args.shell)
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
        if command == "enable":
            report = manager.enable(args.service, requested_port=args.port)
            out.emit(
                report,
                [
                    f"enabled {report['label']} on port {report['port']}",
                    f"plist {report['plist']}",
                    _status_line(report["status"]),
                ],
            )
            return EXIT_OK
        if command == "disable":
            report = manager.disable(args.service)
            action = "disabled" if report["was_enabled"] else "already not managed by launchd:"
            out.emit(report, [f"{action} {report['label']}", _status_line(report["status"])])
            return EXIT_OK
        if command == "ssh":
            launch_ssh(args.host, args.app)
            out.emit(
                {"launched": args.host, "app": args.app},
                [f"launched {args.app} SSH session for {args.host}"],
            )
            return EXIT_OK
        if command == "web":
            if args.foreground:
                return _run_web_foreground(manager, out)
            result = manager.up("web")
            out.emit(result.as_dict(), [_status_line(result)])
            return EXIT_OK
    except (ServiceError, TunnelError, TerminalError, ConfigError, LaunchdError, EditorError) as exc:
        print(f"LocalSM error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_UNHANDLED


if __name__ == "__main__":
    raise SystemExit(main())
