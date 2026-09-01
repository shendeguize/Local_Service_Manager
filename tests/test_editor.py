import pytest

from localsm import editor


@pytest.fixture(autouse=True)
def clean_editor_environment(monkeypatch):
    for name in ("LOCALSM_EDITOR", "VISUAL", "EDITOR"):
        monkeypatch.delenv(name, raising=False)


def test_localsm_editor_wins(monkeypatch):
    monkeypatch.setenv("EDITOR", "nano")
    monkeypatch.setenv("VISUAL", "emacs")
    monkeypatch.setenv("LOCALSM_EDITOR", "code --wait")
    assert editor.resolve_editor() == ["code", "--wait"]


def test_visual_outranks_editor(monkeypatch):
    monkeypatch.setenv("EDITOR", "nano")
    monkeypatch.setenv("VISUAL", "emacs")
    assert editor.resolve_editor() == ["emacs"]


def test_blank_values_are_ignored(monkeypatch):
    monkeypatch.setenv("LOCALSM_EDITOR", "   ")
    monkeypatch.setenv("EDITOR", "nano")
    assert editor.resolve_editor() == ["nano"]


def test_editor_falls_back_to_vi():
    assert editor.resolve_editor() == ["vi"]


def test_open_in_editor_passes_the_path(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setenv("LOCALSM_EDITOR", "fake-editor --wait")
    monkeypatch.setattr(
        editor.subprocess,
        "run",
        lambda command, **kwargs: calls.append(command) or type("R", (), {"returncode": 0})(),
    )
    target = tmp_path / "services.yaml"
    editor.open_in_editor(target)
    assert calls == [["fake-editor", "--wait", str(target)]]


def test_a_failing_editor_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(editor.subprocess, "run", lambda command, **kwargs: type("R", (), {"returncode": 1})())
    with pytest.raises(editor.EditorError, match="left as it was"):
        editor.open_in_editor(tmp_path / "services.yaml")


def test_a_missing_editor_is_reported(monkeypatch, tmp_path):
    def fail(command, **kwargs):
        raise OSError("No such file or directory")

    monkeypatch.setenv("LOCALSM_EDITOR", "absent-editor")
    monkeypatch.setattr(editor.subprocess, "run", fail)
    with pytest.raises(editor.EditorError, match="cannot run 'absent-editor'"):
        editor.open_in_editor(tmp_path / "services.yaml")
