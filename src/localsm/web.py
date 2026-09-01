"""Flask dashboard and local API for LocalSM."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from flask import Flask, jsonify, render_template, request

from .config import state_dir
from .remote import scan_hosts
from .services import ServiceError, ServiceManager
from .terminal import TerminalError, launch_ssh
from .tunnels import TunnelError, TunnelManager


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")
    manager = ServiceManager()
    tunnels = TunnelManager()

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/services")
    def services() -> Any:
        return jsonify([item.as_dict() for item in manager.all_status()])

    @app.get("/api/logs/<name>")
    def logs(name: str) -> Any:
        try:
            lines = max(1, min(500, int(request.args.get("lines", 80))))
        except ValueError:
            lines = 80
        return jsonify({"service": name, "lines": lines, "content": manager.logs(name, lines)})

    @app.post("/api/services/<name>/<action>")
    def service_action(name: str, action: str) -> Any:
        payload = request.get_json(silent=True) or {}
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

    for error_type in (ServiceError, TunnelError, TerminalError):
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
