from localsm.logs import parse_actual_port, parse_actual_url


def test_parse_kimi_url_keeps_fragment():
    assert parse_actual_url("open http://127.0.0.1:8080/#token=secret") == "http://127.0.0.1:8080/#token=secret"


def test_parse_latest_url_and_port_from_noisy_log():
    text = """
    old http://127.0.0.1:8000
    dsh selected http://localhost:3081
    """
    assert parse_actual_url(text) == "http://localhost:3081"
    assert parse_actual_port(text) == 3081


def test_parsers_handle_missing_or_invalid_values():
    assert parse_actual_url("server started") is None
    assert parse_actual_port("port: 70000") is None
