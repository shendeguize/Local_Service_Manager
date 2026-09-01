import pytest

from localsm import doctor
from localsm.scaffold import scaffold_config


def find(checks, name):
    return next(check for check in checks if check.name == name)


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


def test_missing_configuration_is_a_failure(localsm_home):
    checks = doctor.local_checks()
    services = find(checks, "services.yaml")
    assert services.status == "FAIL"
    assert "LocalSM init" in services.detail


def test_present_configuration_passes(localsm_home):
    scaffold_config()
    checks = doctor.local_checks()
    assert find(checks, "services.yaml").status == "PASS"
    assert find(checks, "tunnels.yaml").status == "PASS"


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        ("demo --port {port}", "demo"),
        ("  spaced   --flag", "spaced"),
        ("{python} -m localsm.web", None),
        ("/usr/local/bin/demo", None),
        ("MODE=test demo", None),
        ("", None),
    ],
)
def test_service_binary_only_resolves_plain_commands(start, expected):
    assert doctor.service_binary(start) == expected


def test_service_checks_come_from_the_user_configuration(localsm_home, monkeypatch):
    (localsm_home / "services.yaml").write_text(
        'services:\n  alpha:\n    start: "alpha serve {port}"\n  beta:\n    start: "{python} -m beta"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor.shutil, "which", lambda command: None)
    names = [check.name for check in doctor.configured_service_checks()]
    assert names == ["alpha"]


def test_service_checks_are_empty_for_invalid_configuration(localsm_home):
    (localsm_home / "services.yaml").write_text("services: [1, 2]\n", encoding="utf-8")
    assert doctor.configured_service_checks() == []
