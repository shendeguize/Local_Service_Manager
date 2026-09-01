#!/usr/bin/env python3
"""Capture the demo fixtures by driving a real LocalSM dashboard.

The simulated dashboard replays recorded JSON rather than inventing it, so the
demo doubles as a regression test on the web API: rename a field or nest a
payload differently and this script fails, which fails the site build.

The payloads come from the real Flask app through its test client, against a
sandboxed configuration seeded from site/demo/scenario.yaml, with the scenario's
services genuinely started. The remote scan is the one exception: the scenario's
hosts do not exist, so its values are written by hand in the scenario and only
its field names are checked against a real scan of an unknown host.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SCENARIO = ROOT / "site" / "demo" / "scenario.yaml"
TARGET = ROOT / "site" / "public" / "demo" / "fixtures.json"
SHOWN_CONFIG_DIR = "/Users/you/.config/localsm"
SHOWN_STATE_DIR = "/Users/you/.local/state/localsm"


class FixtureError(RuntimeError):
    """Raised when the app cannot be captured or disagrees with the scenario."""


def seed(sandbox: Path, scenario: dict) -> dict[str, str]:
    """Write the scenario into the sandbox and return the substitutions.

    Two things have to be real to capture and unreal to display. A service's
    `working_dir` has to exist before `up` can start it, but should read as a
    path a visitor might have rather than a temporary directory; its start
    command has to be inert, but should read as the command it stands in for.
    Both are created or run for real and mapped back to the shown value
    afterwards, the same way the config and state paths are.
    """
    config = sandbox / "config"
    config.mkdir(parents=True)
    services = {}
    substitutions = {}
    for index, (name, definition) in enumerate(scenario["services"].items()):
        definition = dict(definition)
        substitutions[definition["start"]] = definition.pop("shown_as")
        shown = definition.get("working_dir")
        if shown:
            actual = sandbox / "work" / str(index)
            actual.mkdir(parents=True)
            definition["working_dir"] = str(actual)
            substitutions[str(actual)] = shown
        services[name] = definition
    (config / "services.yaml").write_text(
        yaml.safe_dump(
            {"port_pool": scenario["port_pool"], "services": services},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (config / "tunnels.yaml").write_text(
        yaml.safe_dump({"tunnels": scenario["tunnels"]}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    substitutions[str(config)] = SHOWN_CONFIG_DIR
    substitutions[str(sandbox / "state")] = SHOWN_STATE_DIR
    return substitutions


def get(client, path: str) -> object:
    response = client.get(path)
    if response.status_code != 200:
        raise FixtureError(f"GET {path} returned {response.status_code}: {response.get_data(as_text=True)}")
    return response.get_json()


def post(client, path: str) -> object:
    response = client.post(path, json={})
    if response.status_code >= 400:
        raise FixtureError(f"POST {path} returned {response.status_code}: {response.get_data(as_text=True)}")
    return response.get_json()


def capture_remote(scenario: dict, client) -> list[dict]:
    """Author the scan values, but take the field names from a real scan."""
    probe = post(client, "/api/remote/scan")
    if not isinstance(probe, list):
        raise FixtureError("the scan endpoint did not return a list")
    # With no hosts in the sandbox's ssh config the scan is empty, so fall back to
    # the scanner directly for one unknown host, which still exercises the real
    # record construction.
    if not probe:
        from localsm.remote import scan_hosts

        probe = scan_hosts(["localsm-demo-nonexistent-host"], timeout=1)
    expected = set(probe[0])
    results = []
    for host in scenario["remote"]:
        record = {
            "host": host["host"],
            "reachable": host["reachable"],
            "ports": list(host["ports"]),
            "error": host.get("error"),
            "tunnels": {
                str(port): [
                    tunnel["name"]
                    for tunnel in scenario["tunnels"]
                    if tunnel["host"] == host["host"] and tunnel["remote_port"] == port
                ]
                for port in host["ports"]
            },
        }
        if set(record) != expected:
            raise FixtureError(
                "the demo scan record no longer matches the scanner's: "
                f"missing {sorted(expected - set(record))}, unexpected {sorted(set(record) - expected)}. "
                "Update capture_remote in scripts/gen_demo_fixtures.py."
            )
        results.append(record)
    return results


def substitute(payload: object, replacements: dict[str, str]) -> object:
    """Rewrite sandbox paths anywhere they appear in a captured payload."""
    if isinstance(payload, str):
        for actual, shown in replacements.items():
            payload = payload.replace(actual, shown)
        return payload
    if isinstance(payload, dict):
        return {key: substitute(value, replacements) for key, value in payload.items()}
    if isinstance(payload, list):
        return [substitute(item, replacements) for item in payload]
    return payload


def capture(sandbox: Path, scenario: dict) -> dict:
    substitutions = seed(sandbox, scenario)
    os.environ["LOCALSM_CONFIG_DIR"] = str(sandbox / "config")
    os.environ["LOCALSM_STATE_DIR"] = str(sandbox / "state")
    os.environ["LOCALSM_AGENTS_DIR"] = str(sandbox / "agents")
    # A login shell would source the developer's profile, whose output would end
    # up in the captured logs and differ per machine.
    os.environ["SHELL"] = "/bin/sh"

    from localsm.web import create_app

    running = list(scenario["initial"]["running"])
    launchd = set(scenario["initial"]["launchd"])
    client = create_app().test_client()
    for name in running:
        post(client, f"/api/services/{name}/up")
    try:
        services = get(client, "/api/services")
        logs = {name: get(client, f"/api/logs/{name}?lines=40") for name in running}
        config = get(client, "/api/config")
        tunnels = get(client, "/api/tunnels")
        remote = capture_remote(scenario, client)
    finally:
        for name in running:
            post(client, f"/api/services/{name}/down")

    if not services:
        raise FixtureError("the services endpoint returned nothing")
    for status in services:
        if status["state"] != "running":
            continue
        if not status["port"] or not status["url"]:
            raise FixtureError(
                f"{status['name']} started without a port or URL in its log; "
                "the scenario's start command must announce one"
            )
        # A captured pid belongs to the machine that ran the build and would look
        # like it belongs to the visitor's, so it is replaced with a plausible one.
        status["pid"] = 40000 + sorted(s["name"] for s in services).index(status["name"]) * 137
        status["managed_by"] = "launchd" if status["name"] in launchd else "detached"

    # A real `tunnel add` needs a reachable host, so the ones the demo opens with
    # are marked live here. The record's shape still came from the live endpoint.
    live = set(scenario["initial"]["tunnels"])
    for index, tunnel in enumerate(tunnels):
        if tunnel["name"] in live:
            tunnel["state"] = "running"
            tunnel["pid"] = 41000 + index * 137

    return substitute(
        {
            "generated_by": "scripts/gen_demo_fixtures.py",
            "config": config,
            "services": services,
            "logs": logs,
            "tunnels": tunnels,
            "remote": remote,
        },
        substitutions,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the committed fixtures still match the app")
    parser.add_argument(
        "--seed",
        metavar="DIR",
        type=Path,
        help="write the scenario into DIR as a usable LocalSM home and exit, for the screen recordings",
    )
    args = parser.parse_args()
    scenario = yaml.safe_load(SCENARIO.read_text(encoding="utf-8"))

    if args.seed:
        seed(args.seed, scenario)
        print(args.seed / "config")
        return 0

    try:
        with tempfile.TemporaryDirectory(prefix="localsm-demo-") as directory:
            fixtures = capture(Path(directory), scenario)
    except (FixtureError, subprocess.TimeoutExpired) as exc:
        print(f"demo fixtures failed: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(fixtures, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != rendered:
            print(
                f"{TARGET.relative_to(ROOT)} is out of date with the web API; run `make demo-fixtures`.",
                file=sys.stderr,
            )
            difference = difflib.unified_diff(
                current.splitlines(keepends=True),
                rendered.splitlines(keepends=True),
                fromfile="committed",
                tofile="captured",
            )
            sys.stderr.writelines(difference)
            return 1
        print("Demo fixtures match the web API.")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(rendered, encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(ROOT)}: {len(fixtures['services'])} services, {len(fixtures['remote'])} hosts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
