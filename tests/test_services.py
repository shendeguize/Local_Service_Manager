import plistlib
import sys

import pytest

from localsm import launchd, ports, services
from localsm.config import ServiceConfig
from localsm.services import ServiceError, ServiceManager


@pytest.fixture
def manager(localsm_home):
    definition = ServiceConfig("demo", f'{sys.executable} -c "import time; time.sleep(30)"', preferred_port=18150)
    return ServiceManager({"demo": definition}, (18150, 18160))


def test_unknown_service_and_empty_exec(manager):
    with pytest.raises(ServiceError, match="unknown service"):
        manager.status("missing")
    with pytest.raises(ServiceError, match="requires a command"):
        manager.execute("demo", [])


def test_render_rejects_unknown_template_variable(manager):
    definition = ServiceConfig("bad", "echo {unsupported}")
    manager.services["bad"] = definition
    with pytest.raises(ServiceError, match="unsupported command"):
        manager._render(definition.start, 18151)


def test_external_status_command_is_reported(manager, monkeypatch):
    definition = ServiceConfig("demo", "true", status_cmd="external status")
    manager.services["demo"] = definition
    monkeypatch.setattr(manager, "_pid_alive", lambda pid: False)

    class Result:
        returncode = 0
        stdout = "manager: running (launchd) pid 1234 port 7788"
        stderr = ""

    monkeypatch.setattr(services.subprocess, "run", lambda *args, **kwargs: Result())
    result = manager.status("demo")
    assert result.state == "running"
    assert result.pid == 1234
    assert result.port == 7788


def test_set_port_runs_all_configured_commands(manager, monkeypatch):
    calls = []
    definition = ServiceConfig("demo", "true", set_port=("set {port}", "restart"))
    manager.services["demo"] = definition
    monkeypatch.setattr(manager, "_run_command", lambda command, config: calls.append(command))
    result = manager.set_port("demo", 18155)
    assert result.state == "stopped"
    assert calls == ["set 18155", "restart"]
    assert ports.load_ports()["demo"] == 18155


@pytest.fixture
def launchctl(monkeypatch):
    """Capture launchctl verbs so no real agent is loaded during a test."""
    calls = []
    monkeypatch.setattr(launchd, "bootstrap", lambda name: calls.append(("bootstrap", name)))
    monkeypatch.setattr(launchd, "bootout", lambda name: calls.append(("bootout", name)))
    monkeypatch.setattr(launchd, "kickstart", lambda name, restart=False: calls.append(("kickstart", name, restart)))
    monkeypatch.setattr(services.time, "sleep", lambda seconds: None)
    return calls


def test_enable_freezes_the_port_into_the_agent(manager, launchctl):
    report = manager.enable("demo")
    assert report["enabled"] is True
    assert report["label"] == "com.localsm.demo"
    assert report["port"] == 18150
    assert launchd.frozen_port("demo") == 18150
    # The previous generation is unloaded before the new one is bootstrapped.
    assert launchctl == [("bootout", "demo"), ("bootstrap", "demo")]


def test_enable_honours_an_explicit_port(manager, launchctl):
    report = manager.enable("demo", requested_port=18159)
    assert report["port"] == 18159
    assert launchd.frozen_port("demo") == 18159


def test_enable_renders_the_frozen_port_into_the_command(manager, launchctl):
    manager.services["demo"] = ServiceConfig("demo", "demo serve --port {port}", preferred_port=18151)
    manager.enable("demo")
    document = plistlib.loads(launchd.plist_path("demo").read_bytes())
    assert document["ProgramArguments"][2] == "demo serve --port 18151"


def test_enable_stops_a_running_detached_process_first(manager, launchctl, monkeypatch):
    stopped = []
    monkeypatch.setattr(manager, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(manager, "_read_pid", lambda name: 4242)
    monkeypatch.setattr(manager, "down", lambda name: stopped.append(name))
    manager.enable("demo")
    assert stopped == ["demo"]


def test_status_reports_a_launchd_managed_service(manager, launchctl, monkeypatch):
    manager.enable("demo")
    monkeypatch.setattr(launchd, "state", lambda name: launchd.AgentState("com.localsm.demo", True, True, pid=9191))
    result = manager.status("demo")
    assert result.state == "running"
    assert result.pid == 9191
    assert result.port == 18150
    assert result.managed_by == "launchd"


def test_status_reports_a_stopped_launchd_service(manager, launchctl):
    manager.enable("demo")
    result = manager.status("demo")
    assert result.state == "stopped"
    assert result.managed_by == "launchd"
    assert result.port == 18150


def test_down_refuses_to_fight_launchd(manager, launchctl):
    manager.enable("demo")
    with pytest.raises(ServiceError, match="LocalSM disable demo"):
        manager.down("demo")


def test_up_kickstarts_instead_of_spawning(manager, launchctl):
    manager.enable("demo")
    manager.up("demo")
    assert ("kickstart", "demo", False) in launchctl


def test_restart_kickstarts_with_the_restart_flag(manager, launchctl):
    manager.enable("demo")
    manager.restart("demo")
    assert ("kickstart", "demo", True) in launchctl


@pytest.mark.parametrize("kwargs", [{"requested_port": 18152}, {"auto_port": True}])
def test_port_changes_are_refused_under_launchd(manager, launchctl, kwargs):
    manager.enable("demo")
    with pytest.raises(ServiceError, match="frozen in the agent"):
        manager.restart("demo", **kwargs)


def test_set_port_rewrites_the_agent(manager, launchctl):
    manager.enable("demo")
    manager.set_port("demo", 18157)
    assert launchd.frozen_port("demo") == 18157
    assert launchctl.count(("bootstrap", "demo")) == 2


def test_disable_unloads_and_removes_the_agent(manager, launchctl):
    manager.enable("demo")
    report = manager.disable("demo")
    assert report["was_enabled"] is True
    assert report["enabled"] is False
    assert not launchd.plist_path("demo").exists()
    assert manager.status("demo").managed_by is None


def test_disable_is_idempotent(manager, launchctl):
    report = manager.disable("demo")
    assert report["was_enabled"] is False
