import asyncio
import threading

import pytest
from fastapi.testclient import TestClient

from option_desk.stream import stream_event
from option_desk.web.app import _iter_sse, create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def test_me_is_open(client):
    me = client.get("/api/me")
    assert me.status_code == 200
    body = me.json()
    assert body["ok"] is True
    assert "tickers" in body
    assert "delta" in body
    assert "cash" in body


def test_runs_stream(client, monkeypatch):
    def fake_iter(tickers, as_of=None, settings=None):
        yield stream_event("run_started", message="go", tickers=tickers)
        yield stream_event("desk_done", message="终审完成", desk={"decisions": [], "portfolio_note": "", "used_llm": False})
        yield stream_event("run_finished", message="done", run={"ok": True})

    monkeypatch.setattr("option_desk.web.app.iter_desk", fake_iter)
    with client.stream(
        "POST",
        "/api/runs",
        json={"tickers": ["NVDA"], "delta": 0.2, "cash": 55000},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "run_started" in body
    assert "run_finished" in body


async def _drain(stream) -> bytes:
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    return b"".join(chunks)


def test_two_runs_can_proceed_together(monkeypatch):
    started = threading.Barrier(2)
    resume = threading.Event()
    seen: list[str] = []
    guard = threading.Lock()

    def fake_iter(tickers, as_of=None, settings=None):
        with guard:
            seen.append(tickers[0])
        yield stream_event("run_started", message="go", tickers=tickers)
        started.wait(timeout=5)
        resume.wait(timeout=10)
        yield stream_event("run_finished", message="done", run={"ok": True})

    monkeypatch.setattr("option_desk.web.app.iter_desk", fake_iter)

    async def scenario() -> None:
        first, second = _iter_sse(["NVDA"], 0.2, 55000), _iter_sse(["MSFT"], 0.2, 55000)
        head1, head2 = await asyncio.gather(anext(first), anext(second))
        assert b"run_started" in head1
        assert b"run_started" in head2
        resume.set()
        rest1, rest2 = await asyncio.gather(_drain(first), _drain(second))
        assert b"run_finished" in rest1
        assert b"run_finished" in rest2
        assert set(seen) == {"NVDA", "MSFT"}

    asyncio.run(scenario())


def test_disconnect_stops_stream(monkeypatch):
    resume = threading.Event()
    started = threading.Event()

    def fake_iter(tickers, as_of=None, settings=None):
        yield stream_event("run_started", message="go", tickers=tickers)
        started.set()
        resume.wait(timeout=10)
        yield stream_event("run_finished", message="done", run={"ok": True})

    monkeypatch.setattr("option_desk.web.app.iter_desk", fake_iter)

    async def scenario() -> None:
        stream = _iter_sse(["NVDA"], 0.2, 55000)
        try:
            first = await anext(stream)
            assert b"run_started" in first
            assert await asyncio.to_thread(started.wait, 5)
            await stream.aclose()
        finally:
            resume.set()
            await stream.aclose()

    asyncio.run(scenario())


def test_delta_out_of_range(client):
    response = client.post(
        "/api/runs",
        json={"tickers": ["NVDA"], "delta": 0.4, "cash": 55000},
    )
    assert response.status_code == 422


def test_call_run_requires_shares_and_basis(client):
    missing = client.post(
        "/api/runs",
        json={"tickers": ["NVDA"], "delta": 0.2, "mode": "call"},
    )
    assert missing.status_code == 422
    ok_shape = client.post(
        "/api/runs",
        json={
            "tickers": ["NVDA"],
            "delta": 0.2,
            "mode": "call",
            "shares": 50,
            "cost_basis": 170,
        },
    )
    assert ok_shape.status_code == 422


def test_me_includes_shares(client):
    body = client.get("/api/me").json()
    assert "shares" in body
    assert "cost_basis" in body
    assert body["language"] in {"en", "zh"}


def test_runs_uses_request_language(client, monkeypatch):
    seen: dict[str, str] = {}

    def fake_iter(tickers, as_of=None, settings=None):
        seen["lang"] = settings.output_language
        yield stream_event("run_started", message="go", tickers=tickers)
        yield stream_event("run_finished", message="done", run={"ok": True})

    monkeypatch.setattr("option_desk.web.app.iter_desk", fake_iter)
    with client.stream(
        "POST",
        "/api/runs",
        json={"tickers": ["NVDA"], "delta": 0.2, "cash": 55000, "language": "en"},
        headers={"X-Option-Desk-Lang": "en"},
    ) as response:
        assert response.status_code == 200
        "".join(response.iter_text())
    assert seen["lang"] == "en"


def test_invalid_ticker_follows_language(client):
    zh = client.post(
        "/api/runs",
        json={"tickers": ["123"], "delta": 0.2, "cash": 55000},
        headers={"X-Option-Desk-Lang": "zh"},
    )
    assert zh.status_code == 422
    assert "无效标的" in zh.json()["detail"]
    en = client.post(
        "/api/runs",
        json={"tickers": ["123"], "delta": 0.2, "cash": 55000},
        headers={"X-Option-Desk-Lang": "en"},
    )
    assert en.status_code == 422
    assert "Invalid ticker" in en.json()["detail"]


def test_spa_html_revalidates_and_assets_are_immutable(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><script src='/assets/index-abc.js'></script>",
        encoding="utf-8",
    )
    (dist / "favicon.png").write_bytes(b"\x89PNG")
    (assets / "index-abc.js").write_text("console.log(1)", encoding="utf-8")
    monkeypatch.setattr("option_desk.web.app._dist_dir", lambda: dist)

    with TestClient(create_app()) as test_client:
        html = test_client.get("/")
        assert html.status_code == 200
        assert "no-cache" in html.headers["cache-control"]

        icon = test_client.get("/favicon.png")
        assert icon.status_code == 200
        assert "no-cache" in icon.headers["cache-control"]

        js = test_client.get("/assets/index-abc.js")
        assert js.status_code == 200
        cache = js.headers["cache-control"]
        assert "immutable" in cache
        assert "max-age=31536000" in cache
