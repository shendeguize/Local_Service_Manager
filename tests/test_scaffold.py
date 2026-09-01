from pathlib import Path

from localsm.config import load_services, load_tunnels, services_file, tunnels_file
from localsm.scaffold import SERVICES_TEMPLATE, scaffold_config

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_tracked_example_matches_the_shipped_template():
    example = REPO_ROOT / "config" / "services.example.yaml"
    assert example.read_text(encoding="utf-8") == SERVICES_TEMPLATE


def test_scaffold_creates_both_files(localsm_home):
    report = scaffold_config()
    assert sorted(report["created"]) == sorted([str(services_file()), str(tunnels_file())])
    assert report["skipped"] == []
    assert services_file().exists()
    assert tunnels_file().exists()


def test_scaffold_never_overwrites_existing_config(localsm_home):
    services_file().parent.mkdir(parents=True, exist_ok=True)
    services_file().write_text("services: {}\n", encoding="utf-8")
    report = scaffold_config()
    assert report["skipped"] == [str(services_file())]
    assert report["created"] == [str(tunnels_file())]
    assert services_file().read_text(encoding="utf-8") == "services: {}\n"


def test_scaffold_is_idempotent(localsm_home):
    scaffold_config()
    first = services_file().read_text(encoding="utf-8")
    report = scaffold_config()
    assert report["created"] == []
    assert services_file().read_text(encoding="utf-8") == first


def test_generated_template_is_valid_configuration(localsm_home):
    scaffold_config()
    services, pool = load_services()
    assert pool == (8000, 8999)
    assert "web" in services
    assert load_tunnels() == []
