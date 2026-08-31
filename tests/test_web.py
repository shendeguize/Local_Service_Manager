from localsm import web


def test_dashboard_and_read_endpoints():
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
