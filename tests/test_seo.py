import pytest
from fastapi.testclient import TestClient

from option_desk.web.app import create_app
from option_desk.web.seo import HEAD_END, HEAD_START, sitemap_paths

SHELL = (
    '<!doctype html>\n<html lang="zh-CN">\n  <head>\n'
    f"    {HEAD_START}\n    <title>dev</title>\n    {HEAD_END}\n"
    "  </head>\n  <body><div id=\"root\"></div></body>\n</html>\n"
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(SHELL, encoding="utf-8")
    monkeypatch.setattr("option_desk.web.app._dist_dir", lambda: dist)
    monkeypatch.setenv("OPTION_DESK_PUBLIC_URL", "https://desk.example.com/")
    monkeypatch.delenv("OPTION_DESK_GOOGLE_SITE_VERIFICATION", raising=False)
    with TestClient(create_app()) as test_client:
        yield test_client


def test_robots_points_at_sitemap_and_leaves_api_crawlable(client):
    body = client.get("/robots.txt")
    assert body.status_code == 200
    assert body.headers["content-type"].startswith("text/plain")
    assert "Sitemap: https://desk.example.com/sitemap.xml" in body.text
    assert "Disallow: /api" not in body.text


def test_sitemap_lists_each_page_in_both_languages(client):
    body = client.get("/sitemap.xml")
    assert body.status_code == 200
    assert "xml" in body.headers["content-type"]
    for path in sitemap_paths():
        assert f"<loc>https://desk.example.com{path}</loc>" in body.text
        assert f"<loc>https://desk.example.com{path}?lang=zh</loc>" in body.text
        assert f"<loc>https://desk.example.com{path}?lang=en</loc>" in body.text
    assert "/positions" not in body.text
    assert 'hreflang="x-default"' in body.text


def test_home_shell_gets_zh_tags_from_lang_param(client):
    page = client.get("/?lang=zh")
    assert page.status_code == 200
    html = page.text
    assert '<html lang="zh-CN">' in html
    assert "<title>摩根大山 · 美股期权轮式策略决策台</title>" in html
    assert '<link rel="canonical" href="https://desk.example.com/?lang=zh" />' in html
    assert 'hreflang="en" href="https://desk.example.com/?lang=en"' in html
    assert 'hreflang="x-default" href="https://desk.example.com/"' in html
    assert "application/ld+json" in html
    assert "<title>dev</title>" not in html


def test_route_shell_follows_accept_language_without_param(client):
    page = client.get("/put", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert page.status_code == 200
    assert '<html lang="en">' in page.text
    assert "<title>Put desk · 摩根大山</title>" in page.text
    assert '<link rel="canonical" href="https://desk.example.com/put" />' in page.text
    assert "application/ld+json" not in page.text


def test_replay_scenario_uses_its_summary(client):
    page = client.get("/replay/invented-contract?lang=zh")
    assert page.status_code == 200
    assert "编造" in page.text or "不存在的行权价" in page.text


def test_unknown_path_is_a_noindex_404(client):
    page = client.get("/no-such-page")
    assert page.status_code == 404
    assert 'content="noindex"' in page.text
    assert "canonical" not in page.text


def test_google_verification_tag_is_optional(client, monkeypatch):
    assert "google-site-verification" not in client.get("/").text
    monkeypatch.setenv("OPTION_DESK_GOOGLE_SITE_VERIFICATION", "abc123")
    assert '<meta name="google-site-verification" content="abc123" />' in client.get("/").text
