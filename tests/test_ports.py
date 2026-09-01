import socket

import pytest

from localsm import ports
from localsm.ports import PortError


def test_port_available_and_sticky_state(localsm_home):
    assert ports.port_available(0) is True
    assert ports.port_available(18101) is True
    ports.save_port("demo", 18101)
    assert ports.load_ports() == {"demo": 18101}
    assert ports.allocate_port("demo", 18101, (18101, 18102)) == 18101


def test_allocate_requested_and_auto_port(localsm_home, monkeypatch):
    occupied = socket.socket()
    occupied.bind(("127.0.0.1", 18110))
    monkeypatch.setattr(ports, "port_available", lambda port: port != 18110)
    assert ports.allocate_port("demo", 18110, (18110, 18112), auto=True) == 18111
    assert ports.allocate_port("fixed", 18110, (18110, 18112), requested=18112) == 18112
    occupied.close()


def test_allocate_reports_exhaustion(localsm_home, monkeypatch):
    monkeypatch.setattr(ports, "port_available", lambda port: False)
    with pytest.raises(PortError, match="no free port"):
        ports.allocate_port("demo", None, (18120, 18120), auto=True)
    with pytest.raises(PortError, match="already in use"):
        ports.allocate_port("demo", 18120, (18120, 18121), requested=18120)
    with pytest.raises(PortError, match="between"):
        ports.allocate_port("demo", None, (18120, 18121), requested=0)
