import pytest
from fastapi.testclient import TestClient

from option_desk.stream import stream_event
from option_desk.web.app import _RUN_LOCK, create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPTION_DESK_WEB_PASSWORD", "desk-pass")
    monkeypatch.setenv("OPTION_DESK_WEB_SECRET", "unit-test-secret")
    with TestClient(create_app()) as test_client:
        yield test_client
    if _RUN_LOCK.locked():
        _RUN_LOCK.release()


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


def test_second_run_conflict(client):
    client.post("/api/login", json={"password": "desk-pass"})
    assert _RUN_LOCK.acquire(blocking=False)
    try:
        response = client.post(
            "/api/runs",
            json={"tickers": ["NVDA"], "delta": 0.2, "cash": 55000},
        )
        assert response.status_code == 409
    finally:
        if _RUN_LOCK.locked():
            _RUN_LOCK.release()


def test_delta_out_of_range(client):
    client.post("/api/login", json={"password": "desk-pass"})
    response = client.post(
        "/api/runs",
        json={"tickers": ["NVDA"], "delta": 0.4, "cash": 55000},
    )
    assert response.status_code == 422
