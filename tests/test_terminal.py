import pytest

from localsm import terminal
from localsm.terminal import TerminalError, launch_ssh


class Result:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stderr = stderr


def test_ghostty_and_terminal_commands(monkeypatch):
    calls = []

    monkeypatch.setattr(terminal.subprocess, "run", lambda *args, **kwargs: calls.append(args) or Result())
    launch_ssh("pod-a", "ghostty")
    launch_ssh("pod-a", "terminal")
    assert calls[0][0] == ["open", "-na", "Ghostty", "--args", "-e", "ssh", "pod-a"]
    assert "ssh pod-a" in calls[1][0][-1]


def test_a_missing_ghostty_is_reported(monkeypatch):
    """`open` is the only thing that knows the app is not installed."""
    failure = Result(1, "Unable to find application named 'Ghostty'")
    monkeypatch.setattr(terminal.subprocess, "run", lambda *args, **kwargs: failure)
    with pytest.raises(TerminalError, match="Unable to find application"):
        launch_ssh("pod-a", "ghostty")


def test_a_hung_open_is_reported(monkeypatch):
    def hang(*args, **kwargs):
        raise terminal.subprocess.TimeoutExpired("open", 15)

    monkeypatch.setattr(terminal.subprocess, "run", hang)
    with pytest.raises(TerminalError, match="cannot launch Ghostty"):
        launch_ssh("pod-a", "ghostty")


@pytest.mark.parametrize("host", ["", "pod a", "pod;a", "pod\nb"])
def test_ssh_host_is_validated(host):
    with pytest.raises(TerminalError, match="single"):
        launch_ssh(host)
