import os

import pytest

from localsm import tunnels
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
def tunnel_manager(localsm_home):
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


def test_a_failed_tunnel_quotes_what_ssh_said(tunnel_manager, monkeypatch):
    monkeypatch.setattr(tunnels, "port_available", lambda port: True)

    def popen(*args, **kwargs):
        kwargs["stdout"].write("ssh: Could not resolve hostname pod: unknown\n")
        return FakeProcess(255)

    monkeypatch.setattr(tunnels.subprocess, "Popen", popen)
    with pytest.raises(TunnelError, match="code 255: ssh: Could not resolve hostname pod: unknown"):
        tunnel_manager.add("bad", "pod", 18184, 8080)


def test_a_failure_quotes_this_attempt_not_an_older_one(tunnel_manager, monkeypatch, localsm_home):
    monkeypatch.setattr(tunnels, "port_available", lambda port: True)
    log = localsm_home / "logs" / "tunnel-bad.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("ssh: an unrelated failure from last week\n", encoding="utf-8")
    monkeypatch.setattr(tunnels.subprocess, "Popen", lambda *args, **kwargs: FakeProcess(255))
    with pytest.raises(TunnelError) as failure:
        tunnel_manager.add("bad", "pod", 18185, 8080)
    assert "last week" not in str(failure.value)
    assert str(failure.value).endswith("code 255")


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


def test_a_stopped_tunnel_reports_no_pid(tunnel_manager, monkeypatch):
    monkeypatch.setattr(tunnels, "port_available", lambda port: True)
    monkeypatch.setattr(tunnels.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    tunnel_manager.add("demo", "pod", 18186, 8080)
    monkeypatch.setattr(tunnel_manager, "_alive", lambda pid: False)
    (item,) = tunnel_manager.list()
    assert item["state"] == "stopped"
    assert item["pid"] is None


def test_ensure_rejects_unknown_name(tunnel_manager):
    with pytest.raises(TunnelError, match="not found"):
        tunnel_manager.ensure("missing")
