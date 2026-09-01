from pathlib import Path

import pytest

from localsm.config import (
    ConfigError,
    config_dir,
    is_configured,
    load_services,
    load_tunnels,
    save_tunnels,
    services_file,
    state_dir,
    tunnels_file,
)


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_paths_default_to_xdg_directories(monkeypatch, tmp_path):
    for name in ("LOCALSM_CONFIG_DIR", "LOCALSM_STATE_DIR", "LOCALSM_ROOT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xconfig"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xstate"))
    assert config_dir() == tmp_path / "xconfig" / "localsm"
    assert state_dir() == tmp_path / "xstate" / "localsm"


def test_paths_fall_back_to_home_when_xdg_is_unset(monkeypatch, tmp_path):
    for name in ("LOCALSM_CONFIG_DIR", "LOCALSM_STATE_DIR", "LOCALSM_ROOT", "XDG_CONFIG_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert config_dir() == tmp_path / ".config" / "localsm"
    assert state_dir() == tmp_path / ".local" / "state" / "localsm"


def test_root_override_supplies_both_directories(monkeypatch, tmp_path):
    for name in ("LOCALSM_CONFIG_DIR", "LOCALSM_STATE_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LOCALSM_ROOT", str(tmp_path / "root"))
    assert config_dir() == tmp_path / "root" / "config"
    assert state_dir() == tmp_path / "root" / "state"


def test_explicit_directory_overrides_outrank_root(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALSM_ROOT", str(tmp_path / "root"))
    monkeypatch.setenv("LOCALSM_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("LOCALSM_STATE_DIR", str(tmp_path / "st"))
    assert config_dir() == tmp_path / "cfg"
    assert state_dir() == tmp_path / "st"
    assert services_file() == tmp_path / "cfg" / "services.yaml"
    assert tunnels_file() == tmp_path / "cfg" / "tunnels.yaml"


def test_is_configured_tracks_the_services_file(localsm_home):
    assert is_configured() is False
    (localsm_home / "services.yaml").write_text("services: {}\n", encoding="utf-8")
    assert is_configured() is True


def test_missing_files_load_as_empty_defaults(localsm_home):
    services, pool = load_services()
    assert services == {}
    assert pool == (8000, 8999)
    assert load_tunnels() == []


def test_load_services_and_command_forms(tmp_path):
    path = write(
        tmp_path / "services.yaml",
        """
port_pool: [9000, 9010]
services:
  demo:
    start: "demo --port {port}"
    preferred_port: 9001
    set_port: ["demo config {port}", "demo restart"]
    stop: "demo stop"
    env: {MODE: test}
""",
    )
    services, pool = load_services(path)
    assert pool == (9000, 9010)
    assert services["demo"].set_port == ("demo config {port}", "demo restart")
    assert services["demo"].stop == ("demo stop",)
    assert services["demo"].env == {"MODE": "test"}


@pytest.mark.parametrize(
    "text",
    [
        "port_pool: [9000]",
        "port_pool: [9000, 70000]",
        "port_pool: [9001, 9000]",
        "services: {demo: {preferred_port: 0}}",
        "services: {demo: {start: '', set_port: [1]}}",
    ],
)
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
