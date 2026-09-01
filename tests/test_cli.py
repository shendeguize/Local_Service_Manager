import json
from types import SimpleNamespace

import pytest

from localsm import cli
from localsm.services import ServiceStatus


class StubManager:
    """Stand in for ServiceManager so CLI tests never spawn processes."""

    instance = None

    def __init__(self):
        self.services = {"demo": object(), "web": object()}
        self.calls = []
        StubManager.instance = self

    def _status(self, name, state="running"):
        return ServiceStatus(name, state, pid=42, port=8000, url="http://127.0.0.1:8000")

    def up(self, name, requested_port=None, auto_port=False):
        self.calls.append(("up", name, requested_port, auto_port))
        return self._status(name)

    def restart(self, name, requested_port=None, auto_port=False):
        self.calls.append(("restart", name, requested_port, auto_port))
        return self._status(name)

    def down(self, name):
        self.calls.append(("down", name))
        return self._status(name, "stopped")

    def status(self, name):
        self.calls.append(("status", name))
        return self._status(name)

    def set_port(self, name, port):
        self.calls.append(("set_port", name, port))
        return self._status(name)

    def execute(self, name, command):
        self.calls.append(("execute", name, tuple(command)))
        return 3

    def logs(self, name, lines=40):
        self.calls.append(("logs", name, lines))
        return "line one\nline two\n"

    def enable(self, name, requested_port=None):
        self.calls.append(("enable", name, requested_port))
        return {
            "name": name,
            "enabled": True,
            "label": f"com.localsm.{name}",
            "plist": f"/agents/com.localsm.{name}.plist",
            "port": requested_port or 8000,
            "status": self._status(name).as_dict(),
        }

    def disable(self, name, was_enabled=True):
        self.calls.append(("disable", name))
        return {
            "name": name,
            "enabled": False,
            "label": f"com.localsm.{name}",
            "was_enabled": was_enabled,
            "status": self._status(name, "stopped").as_dict(),
        }

    def allocate_service_port(self, name, requested=None, auto=False):
        self.calls.append(("allocate", name, requested, auto))
        return 8765


class StubTunnels:
    def __init__(self):
        self.calls = []

    def add(self, name, host, local_port, remote_port, remote_host):
        self.calls.append(("add", name, host, local_port, remote_port, remote_host))
        return {
            "name": name,
            "host": host,
            "local_port": local_port,
            "remote_host": remote_host,
            "remote_port": remote_port,
            "pid": 99,
            "state": "running",
        }

    def remove(self, name):
        self.calls.append(("remove", name))

    def list(self):
        return [
            {
                "name": "api",
                "host": "pod-a",
                "local_port": 18080,
                "remote_host": "127.0.0.1",
                "remote_port": 8080,
                "state": "running",
                "pid": 7,
            }
        ]

    def ensure(self, name=None):
        self.calls.append(("ensure", name))
        return self.list()


@pytest.fixture
def stub_manager(monkeypatch):
    monkeypatch.setattr(cli, "ServiceManager", StubManager)
    return StubManager


@pytest.fixture
def stub_tunnels(monkeypatch):
    tunnels = StubTunnels()
    monkeypatch.setattr(cli, "TunnelManager", lambda: tunnels)
    return tunnels


def run(argv, capsys):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as error:
        cli.build_parser().parse_args(["--version"])
    assert error.value.code == 0
    assert "LocalSM" in capsys.readouterr().out


def test_parser_preserves_exec_command():
    args = cli.build_parser().parse_args(["exec", "demo", "echo", "hello"])
    assert args.command == "exec"
    assert args.exec_command == ["echo", "hello"]


def test_global_flags_are_accepted_before_and_after_the_subcommand():
    assert cli.build_parser().parse_args(["--json", "status"]).json is True
    assert cli.build_parser().parse_args(["status", "--json"]).json is True
    assert cli.build_parser().parse_args(["tunnel", "list", "--json"]).json is True
    assert not hasattr(cli.build_parser().parse_args(["status"]), "json")


def test_init_creates_configuration(localsm_home, capsys):
    code, out, _ = run(["init"], capsys)
    assert code == 0
    assert (localsm_home / "services.yaml").exists()
    assert "created" in out


def test_init_json_reports_created_and_kept(localsm_home, capsys):
    cli.main(["init"])
    capsys.readouterr()
    code, out, _ = run(["--json", "init"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert payload["created"] == []
    assert len(payload["skipped"]) == 2


def test_unconfigured_run_points_at_init(localsm_home, stub_manager, capsys):
    _, _, err = run(["status", "demo"], capsys)
    assert "LocalSM init" in err


def test_configured_run_is_quiet_about_setup(sample_config, stub_manager, capsys):
    _, _, err = run(["status", "demo"], capsys)
    assert err == ""


def test_init_does_not_warn_about_missing_configuration(localsm_home, capsys):
    _, _, err = run(["init"], capsys)
    assert err == ""


def write_services(home, body):
    (home / "services.yaml").write_text(f"port_pool: [18300, 18310]\nservices:\n{body}", encoding="utf-8")


@pytest.fixture
def fake_editor(monkeypatch):
    """Replace the editor with a callable that rewrites the file in place."""
    rewrites = {}

    def edit(path):
        if rewrites:
            path.write_text(rewrites["content"], encoding="utf-8")

    monkeypatch.setattr(cli, "open_in_editor", edit)
    return rewrites


def test_edit_reports_no_change(sample_config, fake_editor, capsys):
    code, out, _ = run(["edit"], capsys)
    assert code == 0
    assert "no service definitions changed" in out


def test_edit_scaffolds_a_missing_configuration(localsm_home, fake_editor, capsys):
    code, out, _ = run(["edit"], capsys)
    assert code == 0
    assert (localsm_home / "services.yaml").exists()
    assert str(localsm_home / "services.yaml") in out


def test_edit_reports_added_and_removed_services(sample_config, fake_editor, capsys):
    fake_editor["content"] = 'port_pool: [18300, 18310]\nservices:\n  fresh:\n    start: "true"\n'
    code, out, _ = run(["edit"], capsys)
    assert code == 0
    assert "added: fresh" in out
    assert "removed: web" in out


def test_edit_names_the_services_needing_a_restart(sample_config, fake_editor, monkeypatch, capsys):
    fake_editor["content"] = 'port_pool: [18300, 18310]\nservices:\n  web:\n    start: "true --changed"\n'
    monkeypatch.setattr(
        "localsm.services.ServiceManager.status",
        lambda self, name: ServiceStatus(name, "running", pid=11, port=8000),
    )
    code, out, _ = run(["edit"], capsys)
    assert code == 0
    assert "changed: web" in out
    assert "restart to apply: LocalSM restart web" in out


def test_edit_stays_quiet_about_stopped_changed_services(sample_config, fake_editor, capsys):
    fake_editor["content"] = 'port_pool: [18300, 18310]\nservices:\n  web:\n    start: "true --changed"\n'
    code, out, _ = run(["edit"], capsys)
    assert code == 0
    assert "changed: web" in out
    assert "restart to apply" not in out


def test_edit_json_lists_the_differences(sample_config, fake_editor, capsys):
    fake_editor["content"] = 'port_pool: [18300, 18310]\nservices:\n  fresh:\n    start: "true"\n'
    code, out, _ = run(["--json", "edit"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert payload["added"] == ["fresh"]
    assert payload["removed"] == ["web"]
    assert payload["restart_required"] == []


def test_edit_can_target_tunnels(sample_config, fake_editor, capsys):
    code, out, _ = run(["edit", "tunnels"], capsys)
    assert code == 0
    assert "tunnels.yaml" in out


def test_edit_surfaces_invalid_yaml(sample_config, fake_editor, capsys):
    fake_editor["content"] = "services: [not, a, mapping]\n"
    code, _, err = run(["edit"], capsys)
    assert code == 1
    assert "LocalSM error" in err


def test_editor_failures_exit_with_one(sample_config, monkeypatch, capsys):
    def fail(path):
        raise cli.EditorError("vi exited with code 1")

    monkeypatch.setattr(cli, "open_in_editor", fail)
    code, _, err = run(["edit"], capsys)
    assert code == 1
    assert "LocalSM error: vi exited" in err


def test_config_command_reports_paths(sample_config, capsys):
    code, out, _ = run(["config"], capsys)
    assert code == 0
    assert "config_dir:" in out
    assert "services:" in out
    assert "web:" in out


def test_config_json_carries_the_resolved_paths(sample_config, capsys):
    code, out, _ = run(["--json", "config"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert payload["config_dir"] == str(sample_config)
    assert payload["port_pool"] == [18300, 18310]
    assert payload["services"][0]["name"] == "web"


def test_invalid_configuration_exits_with_one(localsm_home, capsys):
    (localsm_home / "services.yaml").write_text("services: [nope]\n", encoding="utf-8")
    code, _, err = run(["config"], capsys)
    assert code == 1
    assert "LocalSM error" in err


@pytest.mark.parametrize("command", ["up", "restart", "down", "status"])
def test_lifecycle_commands_print_status_lines(sample_config, stub_manager, capsys, command):
    code, out, _ = run([command, "demo"], capsys)
    assert code == 0
    assert out.startswith("demo ")
    assert "port=8000" in out


def test_lifecycle_without_a_service_covers_every_service(sample_config, stub_manager, capsys):
    code, out, _ = run(["status"], capsys)
    assert code == 0
    assert out.splitlines()[0].startswith("demo ")
    assert out.splitlines()[1].startswith("web ")


def test_lifecycle_json_is_always_a_list(sample_config, stub_manager, capsys):
    code, out, _ = run(["--json", "up", "demo"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert isinstance(payload, list)
    assert payload[0]["name"] == "demo"
    assert payload[0]["state"] == "running"


def test_up_forwards_port_flags(sample_config, stub_manager, capsys):
    run(["up", "demo", "--port", "9100", "--auto-port"], capsys)
    assert StubManager.instance.calls == [("up", "demo", 9100, True)]


def test_quiet_suppresses_status_output(sample_config, stub_manager, capsys):
    code, out, _ = run(["--quiet", "status", "demo"], capsys)
    assert code == 0
    assert out == ""


def test_set_port_reports_the_service(sample_config, stub_manager, capsys):
    code, out, _ = run(["set-port", "demo", "9200"], capsys)
    assert code == 0
    assert out.startswith("demo ")
    assert StubManager.instance.calls == [("set_port", "demo", 9200)]


def test_exec_propagates_the_child_exit_code(sample_config, stub_manager, capsys):
    code, _, _ = run(["exec", "demo", "echo", "hi"], capsys)
    assert code == 3
    assert StubManager.instance.calls == [("execute", "demo", ("echo", "hi"))]


def test_exec_json_reports_the_exit_code(sample_config, stub_manager, capsys):
    code, out, _ = run(["--json", "exec", "demo", "echo", "hi"], capsys)
    assert code == 3
    assert json.loads(out)["exit_code"] == 3


def test_logs_print_raw_content(sample_config, stub_manager, capsys):
    code, out, _ = run(["logs", "demo", "--lines", "9"], capsys)
    assert code == 0
    assert out == "line one\nline two\n"
    assert StubManager.instance.calls == [("logs", "demo", 9)]


def test_logs_json_wraps_content(sample_config, stub_manager, capsys):
    code, out, _ = run(["--json", "logs", "demo"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert payload["service"] == "demo"
    assert payload["content"] == "line one\nline two\n"


def test_remote_scan_prints_a_summary(sample_config, monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "scan_hosts",
        lambda hosts=None, timeout=8: [
            {"host": "pod-a", "reachable": True, "ports": [8080, 9000], "error": None},
            {"host": "pod-b", "reachable": False, "ports": [], "error": "timed out\ndetail"},
        ],
    )
    code, out, _ = run(["remote", "scan"], capsys)
    assert code == 0
    assert "pod-a reachable ports=8080,9000" in out
    assert "pod-b unreachable ports=- error=timed out" in out


def test_remote_scan_json_passes_through(sample_config, monkeypatch, capsys):
    monkeypatch.setattr(cli, "scan_hosts", lambda hosts=None, timeout=8: [{"host": "pod-a", "reachable": True}])
    code, out, _ = run(["--json", "remote", "scan", "pod-a", "--timeout", "2"], capsys)
    assert code == 0
    assert json.loads(out)[0]["host"] == "pod-a"


def test_tunnel_add_and_remove(sample_config, stub_tunnels, capsys):
    code, out, _ = run(["tunnel", "add", "api", "pod-a", "18080", "8080"], capsys)
    assert code == 0
    assert "api pod-a 18080->127.0.0.1:8080 running pid=99" in out
    code, out, _ = run(["tunnel", "rm", "api"], capsys)
    assert code == 0
    assert out.strip() == "removed api"
    assert ("remove", "api") in stub_tunnels.calls


def test_tunnel_list_and_ensure(sample_config, stub_tunnels, capsys):
    code, out, _ = run(["tunnel", "list"], capsys)
    assert code == 0
    assert out.startswith("api pod-a")
    code, out, _ = run(["--json", "tunnel", "ensure"], capsys)
    assert code == 0
    assert json.loads(out)[0]["name"] == "api"
    assert ("ensure", None) in stub_tunnels.calls


def test_web_starts_the_dashboard_service(sample_config, stub_manager, capsys):
    code, out, _ = run(["web"], capsys)
    assert code == 0
    assert out.startswith("web ")
    assert StubManager.instance.calls == [("up", "web", None, False)]


def test_web_foreground_runs_in_place(sample_config, stub_manager, monkeypatch, capsys):
    served = []

    class FakeApp:
        def run(self, host, port, debug, use_reloader):
            served.append((host, port, debug, use_reloader))

    monkeypatch.setattr("localsm.web.create_app", lambda: FakeApp())
    monkeypatch.setattr(StubManager, "status", lambda self, name: self._status(name, "stopped"))
    code, out, _ = run(["web", "--foreground"], capsys)
    assert code == 0
    assert served == [("127.0.0.1", 8765, False, False)]
    assert "web foreground port=8765" in out
    assert "http://127.0.0.1:8765/" in out


def test_web_foreground_refuses_when_already_running(sample_config, stub_manager, monkeypatch, capsys):
    monkeypatch.setattr("localsm.web.create_app", lambda: None)
    code, _, err = run(["web", "--foreground"], capsys)
    assert code == 1
    assert "already running" in err


def test_web_foreground_stops_cleanly_on_interrupt(sample_config, stub_manager, monkeypatch, capsys):
    class Interrupting:
        def run(self, host, port, debug, use_reloader):
            raise KeyboardInterrupt

    monkeypatch.setattr("localsm.web.create_app", lambda: Interrupting())
    monkeypatch.setattr(StubManager, "status", lambda self, name: self._status(name, "stopped"))
    code, _, _ = run(["web", "--foreground"], capsys)
    assert code == 0


def test_enable_reports_the_frozen_port_and_plist(sample_config, stub_manager, capsys):
    code, out, _ = run(["enable", "demo", "--port", "9300"], capsys)
    assert code == 0
    assert "enabled com.localsm.demo on port 9300" in out
    assert "plist /agents/com.localsm.demo.plist" in out
    assert StubManager.instance.calls == [("enable", "demo", 9300)]


def test_enable_json_carries_the_report(sample_config, stub_manager, capsys):
    code, out, _ = run(["--json", "enable", "demo"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert payload["enabled"] is True
    assert payload["port"] == 8000
    assert payload["status"]["name"] == "demo"


def test_disable_reports_the_removal(sample_config, stub_manager, capsys):
    code, out, _ = run(["disable", "demo"], capsys)
    assert code == 0
    assert "disabled com.localsm.demo" in out


def test_disable_says_so_when_nothing_was_enabled(sample_config, stub_manager, monkeypatch, capsys):
    original = StubManager.disable
    monkeypatch.setattr(StubManager, "disable", lambda self, name: original(self, name, was_enabled=False))
    code, out, _ = run(["disable", "demo"], capsys)
    assert code == 0
    assert "already not managed by launchd" in out


def test_launchd_errors_exit_with_one(sample_config, monkeypatch, capsys):
    class FailingManager:
        services = {"demo": object()}

        def enable(self, name, requested_port=None):
            raise cli.LaunchdError("cannot load com.localsm.demo")

    monkeypatch.setattr(cli, "ServiceManager", FailingManager)
    code, _, err = run(["enable", "demo"], capsys)
    assert code == 1
    assert "LocalSM error: cannot load" in err


@pytest.mark.parametrize("shell", ["zsh", "bash"])
def test_completion_prints_a_script(localsm_home, capsys, shell):
    code, out, _ = run(["completion", shell], capsys)
    assert code == 0
    assert "LocalSM" in out
    assert "completion services" in out


def test_completion_services_lists_configured_names(sample_config, capsys):
    code, out, _ = run(["completion", "services"], capsys)
    assert code == 0
    assert out == "web\n"


def test_completion_services_stays_silent_without_configuration(localsm_home, capsys):
    code, out, err = run(["completion", "services"], capsys)
    assert code == 0
    assert out == ""
    assert err == ""


def test_completion_services_survives_invalid_configuration(localsm_home, capsys):
    (localsm_home / "services.yaml").write_text("services: [broken]\n", encoding="utf-8")
    code, out, _ = run(["completion", "services"], capsys)
    assert code == 0
    assert out == ""


def test_status_line_marks_launchd_managed_services():
    line = cli._status_line({"name": "demo", "state": "running", "pid": 7, "port": 8000, "managed_by": "launchd"})
    assert line == "demo running pid=7 port=8000 launchd"


def test_doctor_command_delegates(monkeypatch):
    expected = [object()]
    monkeypatch.setattr(cli, "run_doctor", lambda local_only, timeout: expected)
    monkeypatch.setattr(cli, "print_report", lambda checks: 7)
    assert cli.main(["doctor", "--local-only", "--timeout", "2"]) == 7


def test_doctor_json_reports_failures(monkeypatch, capsys):
    from localsm.doctor import Check

    monkeypatch.setattr(
        cli,
        "run_doctor",
        lambda local_only, timeout: [Check("A", "good", "PASS", "ok"), Check("A", "bad", "FAIL", "broken")],
    )
    code, out, _ = run(["--json", "doctor"], capsys)
    assert code == 1
    payload = json.loads(out)
    assert payload["failed"] == 1
    assert payload["checks"][1]["name"] == "bad"


def test_doctor_quiet_reports_only_the_exit_code(monkeypatch, capsys):
    from localsm.doctor import Check

    monkeypatch.setattr(cli, "run_doctor", lambda local_only, timeout: [Check("A", "good", "PASS", "ok")])
    code, out, _ = run(["--quiet", "doctor"], capsys)
    assert code == 0
    assert out == ""


def test_ssh_command_delegates(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "launch_ssh", lambda host, app: calls.append((host, app)))
    code, out, _ = run(["ssh", "pod-a", "--app", "terminal"], capsys)
    assert code == 0
    assert calls == [("pod-a", "terminal")]
    assert "launched terminal" in out


def test_ssh_json_reports_the_launch(monkeypatch, capsys):
    monkeypatch.setattr(cli, "launch_ssh", lambda host, app: None)
    code, out, _ = run(["--json", "ssh", "pod-a"], capsys)
    assert code == 0
    assert json.loads(out) == {"launched": "pod-a", "app": "ghostty"}


def test_service_error_is_reported(monkeypatch, capsys):
    class FailingManager:
        services = {"demo": object()}

        def up(self, name, requested_port=None, auto_port=False):
            raise cli.ServiceError(f"cannot start {name}")

    monkeypatch.setattr(cli, "ServiceManager", FailingManager)
    code, _, err = run(["up", "demo"], capsys)
    assert code == 1
    assert "LocalSM error: cannot start demo" in err


def test_main_returns_two_for_unhandled_command_branch(monkeypatch):
    class Parser:
        def parse_args(self, argv):
            return SimpleNamespace(command="unexpected")

    monkeypatch.setattr(cli, "build_parser", lambda: Parser())
    assert cli.main([]) == 2
