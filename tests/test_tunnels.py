import os

import pytest

from localsm import config, tunnels
from localsm.tunnels import TunnelError, TunnelManager


class FakeProcess:
    next_pid = 30000

    def __init__(self, returncode=None):
        FakeProcess.next_pid += 1
        self.pid = FakeProcess.next_pid
        self.returncode = returncode

    def poll(self):
        return self.returncode


@pytest.fixture
def tunnel_manager(tmp_path, monkeypatch):
    (tmp_path / "pids").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(config, "STATE_DIR", tmp_path)
    monkeypatch.setattr(tunnels, "STATE_DIR", tmp_path)
    monkeypatch.setattr(tunnels, "TUNNELS_FILE", tmp_path / "tunnels.yaml")
    return TunnelManager()


def test_add_list_and_remove(tunnel_manager, monkeypatch):
    monkeypatch.setattr(tunnels, "port_available", lambda port: True)
    monkeypatch.setattr(tunnels.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    item = tunnel_manager.add("demo", "pod", 18180, 8080)
    assert item["state"] == "running"
    monkeypatch.setattr(tunnel_manager, "_alive", lambda pid: True)
    assert tunnel_manager.list()[0]["name"] == "demo"
    monkeypatch.setattr(os, "killpg", lambda *args: None)
    tunnel_manager.remove("demo")
    assert tunnel_manager.list() == []


def test_ensure_rebuilds_dead_tunnel(tunnel_manager, monkeypatch):
    monkeypatch.setattr(tunnels, "port_available", lambda port: True)
    monkeypatch.setattr(tunnels.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    tunnel_manager.add("demo", "pod", 18181, 8080)
    monkeypatch.setattr(tunnel_manager, "_alive", lambda pid: False)
    result = tunnel_manager.ensure("demo")
    assert result[0]["state"] == "running"


def test_add_rejects_duplicate_and_ssh_failure(tunnel_manager, monkeypatch):
    monkeypatch.setattr(tunnels, "port_available", lambda port: True)
    monkeypatch.setattr(tunnels.subprocess, "Popen", lambda *args, **kwargs: FakeProcess(1))
    with pytest.raises(TunnelError, match="exited"):
        tunnel_manager.add("bad", "pod", 18182, 8080)
    assert tunnel_manager.list() == []


def test_add_rejects_invalid_port(tunnel_manager):
    with pytest.raises(TunnelError, match="between 1 and 65535"):
        tunnel_manager.add("bad", "pod", 0, 8080)


def test_add_reports_process_start_failure(tunnel_manager, monkeypatch):
    monkeypatch.setattr(tunnels, "port_available", lambda port: True)

    def fail(*args, **kwargs):
        raise OSError("ssh missing")

    monkeypatch.setattr(tunnels.subprocess, "Popen", fail)
    with pytest.raises(TunnelError, match="cannot start tunnel: ssh missing"):
        tunnel_manager.add("bad", "pod", 18183, 8080)


def test_ensure_rejects_unknown_name(tunnel_manager):
    with pytest.raises(TunnelError, match="not found"):
        tunnel_manager.ensure("missing")
