import sys

import pytest

from localsm import ports, services
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
