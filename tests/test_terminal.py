import pytest

from localsm import terminal
from localsm.terminal import TerminalError, launch_ssh


def test_ghostty_and_terminal_commands(monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(terminal.subprocess, "Popen", lambda *args, **kwargs: calls.append(("Popen", args)))
    monkeypatch.setattr(terminal.subprocess, "run", lambda *args, **kwargs: (calls.append(("run", args)) or Result()))
    launch_ssh("pod-a", "ghostty")
    launch_ssh("pod-a", "terminal")
    assert calls[0][1][0] == ["open", "-na", "Ghostty", "--args", "-e", "ssh", "pod-a"]
    assert "ssh pod-a" in calls[1][1][0][-1]


@pytest.mark.parametrize("host", ["", "pod a", "pod;a", "pod\nb"])
def test_ssh_host_is_validated(host):
    with pytest.raises(TerminalError, match="single"):
        launch_ssh(host)
