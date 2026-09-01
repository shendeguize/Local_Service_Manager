import plistlib
import subprocess
from pathlib import Path

import pytest
from conftest import FakeResult, stub_subprocess

from localsm import launchd

LIST_OUTPUT = """{
\t"LimitLoadToSessionType" = "Aqua";
\t"Label" = "com.localsm.demo";
\t"OnDemand" = false;
\t"LastExitStatus" = 0;
\t"PID" = 4321;
}
"""


@pytest.fixture
def agents(tmp_path, monkeypatch):
    """Redirect ~/Library/LaunchAgents so no real agent is ever written."""
    directory = tmp_path / "LaunchAgents"
    directory.mkdir()
    monkeypatch.setattr(launchd, "agents_dir", lambda: directory)
    return directory


@pytest.fixture
def calls(launchctl):
    """The shared launchctl recorder, under the name these tests read best with."""
    return launchctl


def write_agent(agents: Path, name: str, port: int | None = 8100) -> Path:
    path = agents / f"com.localsm.{name}.plist"
    document = {"Label": f"com.localsm.{name}"}
    if port is not None:
        document["EnvironmentVariables"] = {"LOCALSM_PORT": str(port)}
    with path.open("wb") as handle:
        plistlib.dump(document, handle)
    return path


def test_labels_and_targets_are_namespaced(agents, monkeypatch):
    monkeypatch.setattr(launchd.os, "getuid", lambda: 501)
    assert launchd.label_for("demo") == "com.localsm.demo"
    assert launchd.plist_path("demo") == agents / "com.localsm.demo.plist"
    assert launchd.domain_target() == "gui/501"
    assert launchd.service_target("demo") == "gui/501/com.localsm.demo"


def test_enabled_services_lists_only_localsm_agents(agents):
    write_agent(agents, "demo")
    write_agent(agents, "other")
    (agents / "com.example.unrelated.plist").write_text("", encoding="utf-8")
    assert launchd.enabled_services() == ["demo", "other"]


def test_enabled_services_tolerates_a_missing_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(launchd, "agents_dir", lambda: tmp_path / "absent")
    assert launchd.enabled_services() == []


def test_write_plist_records_the_frozen_port_and_log_paths(agents, tmp_path):
    log = tmp_path / "logs" / "demo.log"
    path = launchd.write_plist(
        "demo",
        "demo serve --port 8100",
        shell="/bin/zsh",
        log_file=log,
        port=8100,
        working_dir="/tmp",
        env={"MODE": "test"},
    )
    document = plistlib.loads(path.read_bytes())
    assert document["Label"] == "com.localsm.demo"
    assert document["ProgramArguments"] == ["/bin/zsh", "-lc", "demo serve --port 8100"]
    assert document["RunAtLoad"] is True
    assert document["KeepAlive"] is True
    assert document["StandardOutPath"] == str(log)
    assert document["StandardErrorPath"] == str(log)
    assert document["WorkingDirectory"] == "/tmp"
    assert document["EnvironmentVariables"] == {"MODE": "test", "LOCALSM_PORT": "8100"}
    assert log.parent.is_dir()


def test_write_plist_omits_optional_keys(agents, tmp_path):
    path = launchd.write_plist("demo", "demo", shell="/bin/sh", log_file=tmp_path / "demo.log")
    document = plistlib.loads(path.read_bytes())
    assert "WorkingDirectory" not in document
    assert "EnvironmentVariables" not in document


def test_write_plist_reports_filesystem_failure(agents, tmp_path, monkeypatch):
    monkeypatch.setattr(launchd, "agents_dir", lambda: tmp_path / "denied")
    monkeypatch.setattr(Path, "mkdir", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("read-only")))
    with pytest.raises(launchd.LaunchdError, match="cannot write"):
        launchd.write_plist("demo", "demo", shell="/bin/sh", log_file=tmp_path / "demo.log")


def test_frozen_port_round_trips(agents):
    write_agent(agents, "demo", port=8123)
    assert launchd.frozen_port("demo") == 8123


@pytest.mark.parametrize("port", [None, "not-a-port"])
def test_frozen_port_is_none_without_a_usable_value(agents, port):
    path = agents / "com.localsm.demo.plist"
    document = {"Label": "com.localsm.demo"}
    if port is not None:
        document["EnvironmentVariables"] = {"LOCALSM_PORT": port}
    with path.open("wb") as handle:
        plistlib.dump(document, handle)
    assert launchd.frozen_port("demo") is None


def test_frozen_port_is_none_for_a_missing_or_broken_plist(agents):
    assert launchd.frozen_port("absent") is None
    (agents / "com.localsm.broken.plist").write_text("not a plist", encoding="utf-8")
    assert launchd.frozen_port("broken") is None


def test_remove_plist_reports_whether_it_existed(agents):
    write_agent(agents, "demo")
    assert launchd.remove_plist("demo") is True
    assert launchd.remove_plist("demo") is False


def test_state_reads_pid_and_exit_status(agents, calls):
    write_agent(agents, "demo")
    calls.results["list"] = FakeResult(stdout=LIST_OUTPUT)
    result = launchd.state("demo")
    assert result.enabled is True
    assert result.loaded is True
    assert result.pid == 4321
    assert result.last_exit_status == 0


def test_state_reports_an_enabled_but_unloaded_agent(agents, calls):
    write_agent(agents, "demo")
    calls.results["list"] = FakeResult(returncode=113, stderr="Could not find service")
    result = launchd.state("demo")
    assert result.enabled is True
    assert result.loaded is False
    assert result.pid is None


def test_state_skips_launchctl_when_no_agent_exists(agents, calls):
    result = launchd.state("demo")
    assert result.enabled is False
    assert result.loaded is False
    assert calls.commands == []


def test_bootstrap_and_bootout_use_the_gui_domain(agents, calls, monkeypatch):
    monkeypatch.setattr(launchd.os, "getuid", lambda: 501)
    write_agent(agents, "demo")
    launchd.bootstrap("demo")
    launchd.bootout("demo")
    assert calls[0] == ("launchctl", "bootstrap", "gui/501", str(launchd.plist_path("demo")))
    assert calls[1] == ("launchctl", "bootout", "gui/501/com.localsm.demo")


def test_bootstrap_accepts_an_already_loaded_agent(agents, calls):
    calls.results["bootstrap"] = FakeResult(returncode=37, stderr="Bootstrap failed: already loaded")
    launchd.bootstrap("demo")


def test_bootstrap_reports_a_real_failure(agents, calls):
    calls.results["bootstrap"] = FakeResult(returncode=5, stderr="Input/output error")
    with pytest.raises(launchd.LaunchdError, match="Input/output error"):
        launchd.bootstrap("demo")


@pytest.mark.parametrize(
    "result",
    [
        FakeResult(returncode=3, stderr="No such process"),
        FakeResult(returncode=113, stderr="Could not find service"),
    ],
)
def test_bootout_accepts_an_already_unloaded_agent(agents, calls, result):
    calls.results["bootout"] = result
    launchd.bootout("demo")


def test_bootout_reports_a_real_failure(agents, calls):
    calls.results["bootout"] = FakeResult(returncode=5, stderr="Operation not permitted")
    with pytest.raises(launchd.LaunchdError, match="Operation not permitted"):
        launchd.bootout("demo")


def test_kickstart_can_request_a_restart(agents, calls, monkeypatch):
    monkeypatch.setattr(launchd.os, "getuid", lambda: 501)
    launchd.kickstart("demo")
    launchd.kickstart("demo", restart=True)
    assert calls[0] == ("launchctl", "kickstart", "gui/501/com.localsm.demo")
    assert calls[1] == ("launchctl", "kickstart", "-k", "gui/501/com.localsm.demo")


def test_kickstart_reports_failure(agents, calls):
    calls.results["kickstart"] = FakeResult(returncode=5, stderr="Operation not permitted")
    with pytest.raises(launchd.LaunchdError, match="Operation not permitted"):
        launchd.kickstart("demo")


def test_launchctl_wraps_process_failures(agents, monkeypatch):
    write_agent(agents, "demo")

    def fail(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 15)

    monkeypatch.setattr(launchd, "subprocess", stub_subprocess(fail))
    with pytest.raises(launchd.LaunchdError, match="failed"):
        launchd.state("demo")


def test_agents_directory_follows_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALSM_AGENTS_DIR", str(tmp_path / "explicit"))
    assert launchd.agents_dir() == tmp_path / "explicit"
    monkeypatch.delenv("LOCALSM_AGENTS_DIR")
    monkeypatch.setenv("LOCALSM_ROOT", str(tmp_path / "root"))
    assert launchd.agents_dir() == tmp_path / "root" / "LaunchAgents"
