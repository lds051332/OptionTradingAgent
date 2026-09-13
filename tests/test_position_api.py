from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from option_desk.positions.evaluate import PositionEvaluation, PositionInput
from option_desk.positions.management import ManagementResult
from option_desk.web.app import create_app


def _eval(position_id: str, action: str | None = "HOLD") -> PositionEvaluation:
    return PositionEvaluation(
        position_id=position_id,
        fetched_at=datetime(2026, 9, 13, tzinfo=timezone.utc),
        market_open=True,
        underlying_spot=180.0,
        contract=None,
        estimated_close_price=None,
        mark_pnl=None,
        estimated_close_pnl=None,
        profit_capture=None,
        itm=False,
        management=ManagementResult(action=action, reasons=[] if action is None else [action]),
        warnings=["QUOTE_UNAVAILABLE"] if action is None else [],
    )


def test_evaluate_empty_does_not_fetch(monkeypatch):
    called = {"n": 0}

    def boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("should not evaluate")

    monkeypatch.setattr("option_desk.web.app.evaluate_positions", boom)
    monkeypatch.setattr("option_desk.web.app.iter_desk", lambda *args, **kwargs: (_ for _ in ()))
    client = TestClient(create_app())
    response = client.post("/api/positions/evaluate", json={"positions": []})
    assert response.status_code == 200
    body = response.json()
    assert body["evaluations"] == []
    assert "fetchedAt" in body
    assert called["n"] == 0


def test_evaluate_partial_failure(monkeypatch):
    def fake_eval(positions, **kwargs):
        assert [item.ticker for item in positions] == ["NVDA", "TSLA"]
        assert all(isinstance(item, PositionInput) for item in positions)
        return [
            _eval("nvda", "HOLD"),
            _eval("tsla", None),
        ]

    monkeypatch.setattr("option_desk.web.app.evaluate_positions", fake_eval)
    client = TestClient(create_app())
    response = client.post(
        "/api/positions/evaluate",
        json={
            "positions": [
                {
                    "id": "nvda",
                    "ticker": "NVDA",
                    "strategy": "CSP",
                    "optionType": "PUT",
                    "expiry": "2026-09-18",
                    "strike": 170,
                    "contracts": 3,
                    "entryPremium": 1.8,
                    "assignmentOk": True,
                },
                {
                    "id": "tsla",
                    "ticker": "TSLA",
                    "strategy": "CSP",
                    "optionType": "PUT",
                    "expiry": "2026-09-18",
                    "strike": 200,
                    "contracts": 1,
                    "entryPremium": 2.0,
                    "assignmentOk": True,
                },
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evaluations"][0]["management"]["action"] == "HOLD"
    assert body["evaluations"][1]["management"]["action"] is None
    assert body["evaluations"][1]["warnings"] == ["QUOTE_UNAVAILABLE"]


def test_evaluate_does_not_call_iter_desk(monkeypatch):
    def fake_eval(positions, **kwargs):
        return [_eval("nvda")]

    monkeypatch.setattr("option_desk.web.app.evaluate_positions", fake_eval)

    def boom(*args, **kwargs):
        raise AssertionError("iter_desk should not run")

    monkeypatch.setattr("option_desk.web.app.iter_desk", boom)
    client = TestClient(create_app())
    response = client.post(
        "/api/positions/evaluate",
        json={
            "positions": [
                {
                    "id": "nvda",
                    "ticker": "NVDA",
                    "strategy": "CSP",
                    "optionType": "PUT",
                    "expiry": "2026-09-18",
                    "strike": 170,
                    "contracts": 3,
                    "entryPremium": 1.8,
                    "assignmentOk": True,
                }
            ]
        },
    )
    assert response.status_code == 200


def test_roll_candidates_payload(monkeypatch):
    from option_desk.positions.roll import RollCandidate
    from option_desk.schemas import ContractQuote, QuoteSource

    quote = ContractQuote(
        contract_id="NVDA-2026-09-25-P-170",
        ticker="NVDA",
        expiry=date(2026, 9, 25),
        dte=7,
        strike=170,
        bid=1.9,
        ask=2.0,
        mid=1.95,
        last=1.95,
        iv=0.4,
        delta=0.21,
        open_interest=100,
        volume=50,
        spread_pct=0.05,
        quote_source=QuoteSource.NBBO,
    )

    def fake_collect(**kwargs):
        return [RollCandidate(quote, 0.5, 150.0, True)], quote, 180.0

    monkeypatch.setattr("option_desk.web.app.collect_roll_candidates", fake_collect)
    client = TestClient(create_app())
    response = client.post(
        "/api/positions/roll-candidates",
        json={
            "ticker": "NVDA",
            "optionType": "PUT",
            "expiry": "2026-09-18",
            "strike": 170,
            "contracts": 3,
            "estimatedClosePrice": 1.45,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["candidates"][0]["recommended"] is True
    assert body["candidates"][0]["estimatedNet"] == 150.0
    assert body["current"]["contract_id"] == "NVDA-2026-09-25-P-170"
