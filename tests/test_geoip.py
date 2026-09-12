from types import SimpleNamespace

from option_desk.geoip import (
    clear_cache,
    lang_from_country,
    lookup_language,
    parse_client_ip,
    suggested_language,
)


def setup_function() -> None:
    clear_cache()


def teardown_function() -> None:
    clear_cache()


def test_lang_from_country():
    assert lang_from_country("CN") == "zh"
    assert lang_from_country("中国") == "zh"
    assert lang_from_country("US") == "en"
    assert lang_from_country("HK") == "en"
    assert lang_from_country("") is None


def test_parse_client_ip_prefers_cdn_then_real_ip():
    assert parse_client_ip({"cf-connecting-ip": "8.8.8.8", "x-real-ip": "1.1.1.1"}) == "8.8.8.8"
    assert parse_client_ip({"x-real-ip": "1.1.1.1", "x-forwarded-for": "8.8.8.8"}) == "1.1.1.1"


def test_parse_client_ip_uses_rightmost_public_forwarded_hop():
    assert parse_client_ip({"x-forwarded-for": "8.8.8.8, 114.114.114.114"}) == "114.114.114.114"
    assert parse_client_ip({"x-forwarded-for": "8.8.8.8, 10.0.0.1"}) == "8.8.8.8"
    assert parse_client_ip({"x-forwarded-for": "127.0.0.1"}, peer="192.168.1.8") is None
    assert parse_client_ip({}, peer="testclient") is None


def test_lookup_uses_country_is_and_caches(monkeypatch):
    calls: list[str] = []

    def fake(ip: str) -> str:
        calls.append(ip)
        return "CN"

    monkeypatch.setattr("option_desk.geoip._country_is_lookup", fake)
    assert lookup_language("1.2.3.4") == "zh"
    assert lookup_language("1.2.3.4") == "zh"
    assert calls == ["1.2.3.4"]


def test_lookup_maps_non_china_to_en(monkeypatch):
    monkeypatch.setattr("option_desk.geoip._country_is_lookup", lambda ip: "US")
    assert lookup_language("8.8.8.8") == "en"


def test_suggested_language_skips_private_peer():
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="testclient"))
    assert suggested_language(request) is None
