"""Flask dashboard and local API for LocalSM."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from .config import config_dir, load_services, services_file, state_dir, tunnels_file
from .launchd import LaunchdError
from .remote import scan_hosts
from .services import ServiceError, ServiceManager
from .terminal import TerminalError, launch_ssh
from .tunnels import TunnelError, TunnelManager

# The dashboard has no authentication by design: it binds to loopback and is
# reached over SSH tunnels. That makes DNS rebinding the one way a web page
# could drive it, since an attacker-controlled name resolving to 127.0.0.1
# would otherwise reach these endpoints with the browser's cooperation.
# Pinning the Host header to loopback names closes that path.
LOOPBACK_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


def request_hostname(header: str) -> str:
    """Return the hostname part of a Host header, without its port."""
    value = header.strip().lower()
    if value.startswith("["):
        end = value.find("]")
        return value[: end + 1] if end != -1 else value
    return value.rsplit(":", 1)[0] if ":" in value else value


def allowed_hostnames() -> frozenset[str]:
    extra = os.environ.get("LOCALSM_WEB_ALLOWED_HOSTS", "")
    names = {item.strip().lower() for item in extra.split(",") if item.strip()}
    return LOOPBACK_HOSTNAMES | names


class ConfigWatcher:
    """Rebuild the ServiceManager when services.yaml changes on disk.

    `LocalSM edit` and any text editor change the file behind the dashboard's
    back. Watching its mtime means the next refresh picks up new services
    without restarting the web process.
    """

    def __init__(self) -> None:
        self._manager: ServiceManager | None = None
        self._signature: tuple[int, int] | None = None

    @staticmethod
    def _signature_of(path: Path) -> tuple[int, int] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        return (stat.st_mtime_ns, stat.st_size)

    def manager(self) -> ServiceManager:
        signature = self._signature_of(services_file())
        if self._manager is None or signature != self._signature:
            self._manager = ServiceManager()
            self._signature = signature
        return self._manager


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")
    watcher = ConfigWatcher()
    tunnels = TunnelManager()

    @app.before_request
    def reject_non_loopback_host() -> Any:
        hostname = request_hostname(request.headers.get("Host", ""))
        if hostname in allowed_hostnames():
            return None
        return jsonify(
            {
                "error": (
                    f"refused Host {hostname!r}: the LocalSM dashboard only answers to loopback names. "
                    "Set LOCALSM_WEB_ALLOWED_HOSTS to add one."
                )
            }
        ), 403

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/services")
    def services() -> Any:
        return jsonify([item.as_dict() for item in watcher.manager().all_status()])

    @app.get("/api/config")
    def configuration() -> Any:
        """Read-only view of the service definitions; edits go through the CLI."""
        definitions, pool = load_services()
        return jsonify(
            {
                "config_dir": str(config_dir()),
                "services_file": str(services_file()),
                "tunnels_file": str(tunnels_file()),
                "state_dir": str(state_dir()),
                "port_pool": [pool[0], pool[1]],
                "editable": False,
                "edit_command": "LocalSM edit",
                "services": [
                    {
                        "name": name,
                        "start": definition.start,
                        "preferred_port": definition.preferred_port,
                        "working_dir": definition.working_dir,
                        "url_from_log": definition.url_from_log,
                    }
                    for name, definition in sorted(definitions.items())
                ],
            }
        )

    @app.get("/api/logs/<name>")
    def logs(name: str) -> Any:
        try:
            lines = max(1, min(500, int(request.args.get("lines", 80))))
        except ValueError:
            lines = 80
        return jsonify({"service": name, "lines": lines, "content": watcher.manager().logs(name, lines)})

    @app.post("/api/services/<name>/<action>")
    def service_action(name: str, action: str) -> Any:
        payload = request.get_json(silent=True) or {}
        manager = watcher.manager()
        if action == "up":
            result = manager.up(name, requested_port=payload.get("port"), auto_port=bool(payload.get("auto_port")))
        elif action == "down":
            result = manager.down(name)
        elif action == "restart":
            result = manager.restart(name, requested_port=payload.get("port"), auto_port=bool(payload.get("auto_port")))
        elif action == "set-port":
            result = manager.set_port(name, int(payload["port"]))
        else:
            return jsonify({"error": f"unknown action {action}"}), 404
        return jsonify(result.as_dict() if result else {"name": name, "state": "stopped"})

    @app.get("/api/remote")
    def remote() -> Any:
        path = state_dir() / "remote_scan.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            scanned_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
            return jsonify({"scanned_at": scanned_at, "results": payload})
        except (OSError, ValueError):
            return jsonify({"scanned_at": None, "results": []})

    @app.post("/api/remote/scan")
    def remote_scan() -> Any:
        payload = request.get_json(silent=True) or {}
        return jsonify(scan_hosts(payload.get("hosts") or None, timeout=int(payload.get("timeout", 8))))

    @app.get("/api/tunnels")
    def tunnel_list() -> Any:
        return jsonify(tunnels.list())

    @app.post("/api/tunnels")
    def tunnel_add() -> Any:
        payload = request.get_json(force=True)
        result = tunnels.add(
            str(payload["name"]),
            str(payload["host"]),
            int(payload["local_port"]),
            int(payload["remote_port"]),
            str(payload.get("remote_host", "127.0.0.1")),
        )
        return jsonify(result), 201

    @app.post("/api/tunnels/ensure")
    def tunnel_ensure() -> Any:
        payload = request.get_json(silent=True) or {}
        return jsonify(tunnels.ensure(payload.get("name")))

    @app.delete("/api/tunnels/<name>")
    def tunnel_remove(name: str) -> Any:
        tunnels.remove(name)
        return jsonify({"removed": name})

    @app.post("/api/ssh/<host>")
    def ssh(host: str) -> Any:
        payload = request.get_json(silent=True) or {}
        launch_ssh(host, str(payload.get("app", "ghostty")))
        return jsonify({"launched": host})

    def local_error(error: Exception) -> Any:
        return jsonify({"error": str(error)}), 400

    for error_type in (ServiceError, TunnelError, TerminalError, LaunchdError):
        app.register_error_handler(error_type, local_error)

    return app


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the LocalSM dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    create_app().run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
