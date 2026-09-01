import pytest

from localsm import web

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("127.0.0.1:8765", "127.0.0.1"),
        ("localhost", "localhost"),
        ("LOCALHOST:8765", "localhost"),
        ("[::1]:8765", "[::1]"),
        ("[::1]", "[::1]"),
        ("[::1", "[::1"),
        ("  evil.example.com:80  ", "evil.example.com"),
        ("", ""),
    ],
)
def test_request_hostname_strips_the_port(header, expected):
    assert web.request_hostname(header) == expected


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "[::1]:8765", "localhost"])
def test_loopback_hosts_are_served(sample_config, host):
    client = web.create_app().test_client()
    assert client.get("/api/services", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["attacker.example.com", "localsm.internal:8765", "127.0.0.1.evil.com"])
def test_rebinding_hosts_are_refused(sample_config, host):
    response = web.create_app().test_client().get("/api/services", headers={"Host": host})
    assert response.status_code == 403
    assert "only answers to loopback names" in response.get_json()["error"]


def test_host_refusal_covers_mutating_endpoints(sample_config):
    client = web.create_app().test_client()
    headers = {"Host": "attacker.example.com"}
    assert client.post("/api/services/web/up", headers=headers).status_code == 403
    assert client.post("/api/remote/scan", headers=headers).status_code == 403
    assert client.post("/api/ssh/pod-a", headers=headers).status_code == 403
    assert client.get("/", headers=headers).status_code == 403


def test_an_extra_host_can_be_allowed_by_environment(sample_config, monkeypatch):
    monkeypatch.setenv("LOCALSM_WEB_ALLOWED_HOSTS", "localsm.internal, dev.box")
    client = web.create_app().test_client()
    assert client.get("/api/services", headers={"Host": "localsm.internal:8765"}).status_code == 200
    assert client.get("/api/services", headers={"Host": "dev.box"}).status_code == 200
    assert client.get("/api/services", headers={"Host": "other.box"}).status_code == 403


def test_config_endpoint_is_read_only(sample_config):
    payload = web.create_app().test_client().get("/api/config").get_json()
    assert payload["editable"] is False
    assert payload["edit_command"] == "LocalSM edit"
    assert payload["services_file"] == str(sample_config / "services.yaml")
    assert payload["port_pool"] == [18300, 18310]
    assert [item["name"] for item in payload["services"]] == ["web"]


def test_configuration_changes_are_picked_up_without_a_restart(sample_config):
    client = web.create_app().test_client()
    assert [item["name"] for item in client.get("/api/services").get_json()] == ["web"]
    (sample_config / "services.yaml").write_text(
        'port_pool: [18300, 18310]\nservices:\n  web:\n    start: "true"\n  extra:\n    start: "true"\n',
        encoding="utf-8",
    )
    names = [item["name"] for item in client.get("/api/services").get_json()]
    assert names == ["extra", "web"]


def test_the_manager_is_reused_while_the_file_is_unchanged(sample_config, monkeypatch):
    built = []
    original = web.ServiceManager
    monkeypatch.setattr(web, "ServiceManager", lambda *args, **kwargs: built.append(1) or original(*args, **kwargs))
    watcher = web.ConfigWatcher()
    watcher.manager()
    watcher.manager()
    assert len(built) == 1


def test_the_watcher_survives_a_missing_configuration(localsm_home):
    watcher = web.ConfigWatcher()
    assert watcher.manager().services == {}


def test_dashboard_and_read_endpoints(sample_config):
    client = web.create_app().test_client()
    assert client.get("/").status_code == 200
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/api/services").status_code == 200
    assert client.get("/api/logs/web").status_code == 200
    remote = client.get("/api/remote").get_json()
    assert set(remote) == {"scanned_at", "results"}
    assert client.get("/api/tunnels").status_code == 200


def test_web_errors_and_remote_scan(monkeypatch):
    client = web.create_app().test_client()
    assert client.post("/api/services/missing/up", json={}).status_code == 400
    assert client.post("/api/services/web/invalid", json={}).status_code == 404
    assert client.get("/api/logs/missing").status_code == 400
    monkeypatch.setattr(web, "scan_hosts", lambda hosts=None, timeout=8: [{"host": "pod", "reachable": True}])
    response = client.post("/api/remote/scan", json={"timeout": 1})
    assert response.status_code == 200
    assert response.get_json()[0]["host"] == "pod"


def test_web_ssh_endpoint(monkeypatch):
    calls = []
    monkeypatch.setattr(web, "launch_ssh", lambda host, app: calls.append((host, app)))
    response = web.create_app().test_client().post("/api/ssh/pod-a", json={"app": "terminal"})
    assert response.status_code == 200
    assert calls == [("pod-a", "terminal")]


def test_web_converts_local_errors_to_bad_request(monkeypatch):
    def fail(self, name, requested_port=None, auto_port=False):
        raise web.ServiceError("service is unavailable")

    monkeypatch.setattr(web.ServiceManager, "up", fail)
    response = web.create_app().test_client().post("/api/services/web/up")
    assert response.status_code == 400
    assert response.get_json() == {"error": "service is unavailable"}
