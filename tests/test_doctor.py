from localsm import doctor


def test_print_report_exit_code(capsys):
    assert (
        doctor.print_report(
            [
                doctor.Check("A", "good", "PASS", "ok"),
                doctor.Check("A", "bad", "FAIL", "broken"),
            ]
        )
        == 1
    )
    output = capsys.readouterr().out
    assert "[A]" in output
    assert "bad" in output


def test_local_only_checks_are_structured(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda command: "/usr/bin/" + command)
    monkeypatch.setattr(doctor.Path, "exists", lambda path: True)
    checks = doctor.run_doctor(local_only=True)
    assert checks
    assert all(item.section != "远端 SSH" for item in checks)
