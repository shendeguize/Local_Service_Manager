import pytest

from localsm import cli


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as error:
        cli.build_parser().parse_args(["--version"])
    assert error.value.code == 0
    assert "LocalSM" in capsys.readouterr().out


def test_parser_preserves_exec_command():
    args = cli.build_parser().parse_args(["exec", "demo", "echo", "hello"])
    assert args.command == "exec"
    assert args.exec_command == ["echo", "hello"]


def test_config_command_reports_paths(capsys):
    assert cli.main(["config"]) == 0
    output = capsys.readouterr().out
    assert "config_dir:" in output
    assert "services:" in output
    assert "web:" in output


def test_doctor_command_delegates(monkeypatch):
    expected = [object()]
    monkeypatch.setattr(cli, "run_doctor", lambda local_only, timeout: expected)
    monkeypatch.setattr(cli, "print_report", lambda checks: 7)
    assert cli.main(["doctor", "--local-only", "--timeout", "2"]) == 7


def test_ssh_command_delegates(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "launch_ssh", lambda host, app: calls.append((host, app)))
    assert cli.main(["ssh", "pod-a", "--app", "terminal"]) == 0
    assert calls == [("pod-a", "terminal")]
    assert "launched terminal" in capsys.readouterr().out
