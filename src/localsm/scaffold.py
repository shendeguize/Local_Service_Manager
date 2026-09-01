"""Starter configuration templates written by `LocalSM init`."""

from __future__ import annotations

from pathlib import Path

from .config import config_dir, services_file, tunnels_file

SERVICES_TEMPLATE = """\
# LocalSM services.
# Reference: https://github.com/shendeguize/Local_Service_Manager
#
# Every service needs a `start` command. LocalSM substitutes {port} with the
# port it allocates, {current_port} with the port in use, and {python} with the
# running Python interpreter.

# Ports LocalSM may pick from when a service has no free preferred_port.
port_pool: [8000, 8999]

services:
  # Replace this example with a service of your own.
  example:
    start: "python3 -m http.server {port} --bind 127.0.0.1"
    # Tried first; LocalSM falls back to the pool when this port is taken.
    preferred_port: 8000
    # Read the real URL out of the service log instead of guessing it.
    url_from_log: true
    # Other supported keys:
    # stop: "pkill -f 'http.server'"
    # status_cmd: "example status"
    # set_port: ["example config port {port}"]
    # working_dir: "~/code/example"
    # env: {LOG_LEVEL: debug}

  # The LocalSM dashboard is managed like any other service, so `LocalSM web`
  # needs this entry. Remove it only if you never use the dashboard.
  web:
    start: "{python} -m localsm.web --host 127.0.0.1 --port {port}"
    preferred_port: 8765
    url_from_log: true
"""

TUNNELS_TEMPLATE = """\
# LocalSM SSH tunnels. Prefer `LocalSM tunnel add` over editing this file by
# hand, so the running ssh process and this file stay in agreement.
tunnels: []
"""


def scaffold_config() -> dict[str, list[str]]:
    """Create any missing config file, never touching one that exists."""
    created: list[str] = []
    skipped: list[str] = []
    config_dir().mkdir(parents=True, exist_ok=True)
    for path, template in ((services_file(), SERVICES_TEMPLATE), (tunnels_file(), TUNNELS_TEMPLATE)):
        if path.exists():
            skipped.append(str(path))
            continue
        _write_new(path, template)
        created.append(str(path))
    return {"config_dir": str(config_dir()), "created": created, "skipped": skipped}


def _write_new(path: Path, template: str) -> None:
    # "x" keeps a file that appeared between the exists() check and this write.
    with path.open("x", encoding="utf-8") as handle:
        handle.write(template)
