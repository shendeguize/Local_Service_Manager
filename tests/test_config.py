from pathlib import Path

import pytest

from localsm.config import ConfigError, load_services, load_tunnels, save_tunnels


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_load_services_and_command_forms(tmp_path):
    path = write(tmp_path / "services.yaml", """
port_pool: [9000, 9010]
services:
  demo:
    start: "demo --port {port}"
    preferred_port: 9001
    set_port: ["demo config {port}", "demo restart"]
    stop: "demo stop"
    env: {MODE: test}
""")
    services, pool = load_services(path)
    assert pool == (9000, 9010)
    assert services["demo"].set_port == ("demo config {port}", "demo restart")
    assert services["demo"].stop == ("demo stop",)
    assert services["demo"].env == {"MODE": "test"}


@pytest.mark.parametrize("text", [
    "port_pool: [9000]",
    "port_pool: [9000, 70000]",
    "port_pool: [9001, 9000]",
    "services: {demo: {preferred_port: 0}}",
    "services: {demo: {start: '', set_port: [1]}}",
])
def test_load_services_rejects_invalid_data(tmp_path, text):
    with pytest.raises(ConfigError):
        load_services(write(tmp_path / "bad.yaml", text))


def test_load_tunnels_save_and_reload(tmp_path):
    path = tmp_path / "tunnels.yaml"
    tunnels = [{"name": "demo", "host": "pod", "local_port": 18080, "remote_port": 8080}]
    save_tunnels(tunnels, path)
    assert load_tunnels(path) == tunnels


def test_load_tunnels_rejects_missing_fields(tmp_path):
    with pytest.raises(ConfigError):
        load_tunnels(write(tmp_path / "bad.yaml", "tunnels:\n  - name: incomplete\n"))
