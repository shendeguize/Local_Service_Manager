from localsm import remote
from localsm.remote import RemoteScan, SSHHost


def test_parse_ssh_config_skips_wildcards(tmp_path):
    path = tmp_path / "config"
    path.write_text(
        """
Host *
  User ignored
Host pod-a pod-b
  HostName 10.0.0.2
  Port 2222
  User caros
Host wild-*
  HostName ignored
""",
        encoding="utf-8",
    )
    hosts = remote.parse_ssh_config(path)
    assert [item.alias for item in hosts] == ["pod-a", "pod-b"]
    assert hosts[0].hostname == "10.0.0.2"
    assert hosts[1].port == 2222


def test_parse_listener_formats():
    assert remote._parse_ss("LISTEN 0 128 127.0.0.1:8080 0.0.0.0:*\n") == [8080]
    assert remote._parse_ss("COMMAND PID USER FD TYPE NAME\nnode 1 u 3u TCP *:3000 (LISTEN)") == [3000]
    assert remote._parse_ss("") == []


def test_scan_hosts_and_tunnel_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(remote, "parse_ssh_config", lambda: [SSHHost("pod-a"), SSHHost("pod-b")])
    monkeypatch.setattr(remote, "_scan_one", lambda host, timeout: RemoteScan(host.alias, True, [8080]))
    monkeypatch.setattr(remote, "load_tunnels", lambda path: [{"name": "api", "host": "pod-a", "remote_port": 8080}])
    monkeypatch.setattr(remote, "STATE_DIR", tmp_path)
    result = remote.scan_hosts(timeout=1)
    assert result[0]["host"] == "pod-a"
    assert result[0]["tunnels"] == {"8080": ["api"]}
    assert (tmp_path / "remote_scan.json").exists()


def test_unknown_host_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(remote, "parse_ssh_config", lambda: [])
    monkeypatch.setattr(remote, "STATE_DIR", tmp_path)
    result = remote.scan_hosts(["missing"])
    assert result == [
        {
            "host": "missing",
            "reachable": False,
            "ports": [],
            "error": "host not found in ssh config",
            "tunnels": {},
        }
    ]


def test_scan_one_handles_ssh_startup_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise FileNotFoundError("ssh missing")

    monkeypatch.setattr(remote.subprocess, "run", fail)
    result = remote._scan_one(SSHHost("pod-a"))
    assert result == RemoteScan("pod-a", False, [], "ssh missing")


def test_scan_one_reports_non_network_failure(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "host key verification failed"

    monkeypatch.setattr(remote.subprocess, "run", lambda *args, **kwargs: Result())
    result = remote._scan_one(SSHHost("pod-a"))
    assert result.host == "pod-a"
    assert result.reachable is True
    assert result.error == "host key verification failed"
