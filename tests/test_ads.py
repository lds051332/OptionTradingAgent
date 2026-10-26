import pytest
from fastapi.testclient import TestClient

from option_desk.web.app import create_app
from option_desk.web.seo import HEAD_END, HEAD_START

SHELL = f'<html lang="zh-CN"><head>{HEAD_START}<title>dev</title>{HEAD_END}</head><body></body></html>'


@pytest.fixture
def client(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(SHELL, encoding="utf-8")
    monkeypatch.setattr("option_desk.web.app._dist_dir", lambda: dist)
    monkeypatch.setenv("OPTION_DESK_PUBLIC_URL", "https://desk.example.com")
    monkeypatch.delenv("OPTION_DESK_ADSENSE_CLIENT", raising=False)
    monkeypatch.delenv("OPTION_DESK_ADSENSE_SLOT", raising=False)
    monkeypatch.setattr("option_desk.web.app.suggested_language", lambda request: None)
    with TestClient(create_app()) as test_client:
        yield test_client


def test_ads_are_off_without_a_publisher_id(client):
    assert client.get("/ads.txt").status_code == 404
    assert client.get("/api/me").json()["ads"] is None
    assert "google-adsense-account" not in client.get("/").text


def test_publisher_id_turns_on_ads_txt_meta_and_config(client, monkeypatch):
    monkeypatch.setenv("OPTION_DESK_ADSENSE_CLIENT", "pub-1234567890123456")
    monkeypatch.setenv("OPTION_DESK_ADSENSE_SLOT", "9876543210")
    ads_txt = client.get("/ads.txt")
    assert ads_txt.status_code == 200
    assert ads_txt.text == "google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0\n"
    assert client.get("/api/me").json()["ads"] == {
        "client": "ca-pub-1234567890123456",
        "slot": "9876543210",
    }
    assert '<meta name="google-adsense-account" content="ca-pub-1234567890123456" />' in client.get("/").text


def test_malformed_ids_are_ignored(client, monkeypatch):
    monkeypatch.setenv("OPTION_DESK_ADSENSE_CLIENT", "ca-pub-123<script>")
    monkeypatch.setenv("OPTION_DESK_ADSENSE_SLOT", "abc")
    assert client.get("/ads.txt").status_code == 404
    assert client.get("/api/me").json()["ads"] is None


def test_about_and_privacy_are_real_pages_in_the_sitemap(client):
    for path, title in (("/about", "关于 · 摩根大山"), ("/privacy", "隐私政策 · 摩根大山")):
        page = client.get(f"{path}?lang=zh")
        assert page.status_code == 200
        assert f"<title>{title}</title>" in page.text
        assert f"<loc>https://desk.example.com{path}</loc>" in client.get("/sitemap.xml").text
