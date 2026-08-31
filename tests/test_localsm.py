from __future__ import annotations

import socket
import sys
import tempfile
import unittest
from pathlib import Path

from localsm import config, logs, ports, services
from localsm.remote import parse_ssh_config
from localsm.services import ServiceConfig, ServiceManager


class LocalSMTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        for module in (config, logs, ports, services):
            module.STATE_DIR = root
        self.service = ServiceConfig(
            name="dummy",
            start=f"{sys.executable} -m http.server {{port}} --bind 127.0.0.1",
            preferred_port=18000,
            url_from_log=False,
        )
        self.manager = ServiceManager({"dummy": self.service}, (18000, 18100))

    def tearDown(self) -> None:
        try:
            self.manager.down("dummy")
        finally:
            self.tempdir.cleanup()

    def test_lifecycle_exec_and_sticky_port(self) -> None:
        first = self.manager.up("dummy", requested_port=18001)
        self.assertEqual(first.state, "running")
        self.assertEqual(first.port, 18001)
        self.assertEqual(self.manager.execute("dummy", [sys.executable, "-c", "raise SystemExit(0)"]), 0)
        restarted = self.manager.restart("dummy")
        self.assertEqual(restarted.state, "running")
        self.assertEqual(restarted.port, 18001)
        self.assertEqual(self.manager.down("dummy").state, "stopped")

    def test_auto_port_skips_occupied_preferred_port(self) -> None:
        occupied = socket.socket()
        occupied.bind(("127.0.0.1", 18000))
        self.addCleanup(occupied.close)
        result = self.manager.up("dummy", auto_port=True)
        self.assertEqual(result.state, "running")
        self.assertNotEqual(result.port, 18000)

    def test_log_parsers_keep_url_fragment(self) -> None:
        self.assertEqual(logs.parse_actual_url("Open http://127.0.0.1:8080/#token=abc"), "http://127.0.0.1:8080/#token=abc")
        self.assertEqual(logs.parse_actual_port("Listening at http://0.0.0.0:3081"), 3081)

    def test_ssh_config_parser(self) -> None:
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as handle:
            handle.write("Host pod-a\n  HostName 10.0.0.2\n  User caros\n  Port 2222\n\nHost *\n  ServerAliveInterval 30\n")
            handle.flush()
            hosts = parse_ssh_config(Path(handle.name))
        self.assertEqual(len(hosts), 1)
        self.assertEqual(hosts[0].hostname, "10.0.0.2")
        self.assertEqual(hosts[0].port, 2222)


if __name__ == "__main__":
    unittest.main()
