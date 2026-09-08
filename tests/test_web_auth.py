import asyncio
import threading

import pytest
from fastapi.testclient import TestClient

from option_desk.stream import stream_event
from option_desk.web.app import _iter_sse, create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPTION_DESK_WEB_PASSWORD", "desk-pass")
    monkeypatch.setenv("OPTION_DESK_WEB_SECRET", "unit-test-secret")
    with TestClient(create_app()) as test_client:
        yield test_client


def test_me_requires_login(client):
    assert client.get("/api/me").status_code == 401


def test_runs_requires_login(client):
    response = client.post(
        "/api/runs",
        json={"tickers": ["NVDA"], "delta": 0.2, "cash": 55000},
    )
    assert response.status_code == 401


def test_wrong_password(client):
    response = client.post("/api/login", json={"password": "nope"})
    assert response.status_code == 401


def test_login_then_me(client):
    login = client.post("/api/login", json={"password": "desk-pass"})
    assert login.status_code == 200
    me = client.get("/api/me")
    assert me.status_code == 200
    body = me.json()
    assert body["ok"] is True
    assert "tickers" in body
    assert "delta" in body
    assert "cash" in body


def test_missing_password_is_unavailable(monkeypatch):
    monkeypatch.setenv("OPTION_DESK_WEB_PASSWORD", "")
    monkeypatch.setenv("OPTION_DESK_WEB_SECRET", "unit-test-secret")
    with TestClient(create_app()) as test_client:
        response = test_client.post("/api/login", json={"password": "anything"})
    assert response.status_code == 503


def test_runs_stream_after_login(client, monkeypatch):
    def fake_iter(tickers, as_of=None, settings=None):
        yield stream_event("run_started", message="go", tickers=tickers)
        yield stream_event("desk_done", message="终审完成", desk={"decisions": [], "portfolio_note": "", "used_llm": False})
        yield stream_event("run_finished", message="done", run={"ok": True})

    monkeypatch.setattr("option_desk.web.app.iter_desk", fake_iter)
    client.post("/api/login", json={"password": "desk-pass"})
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
    client.post("/api/login", json={"password": "desk-pass"})
    response = client.post(
        "/api/runs",
        json={"tickers": ["NVDA"], "delta": 0.4, "cash": 55000},
    )
    assert response.status_code == 422


def test_call_run_requires_shares_and_basis(client):
    client.post("/api/login", json={"password": "desk-pass"})
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


def test_login_then_me_includes_shares(client):
    client.post("/api/login", json={"password": "desk-pass"})
    body = client.get("/api/me").json()
    assert "shares" in body
    assert "cost_basis" in body
