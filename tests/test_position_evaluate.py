from datetime import date, datetime, timezone

from option_desk.positions.evaluate import PositionInput, RuleSettings, evaluate_positions
from option_desk.schemas import ContractQuote, QuoteSource


def _quote() -> ContractQuote:
    return ContractQuote(
        contract_id="NVDA-2026-09-18-P-170",
        ticker="NVDA",
        expiry=date(2026, 9, 18),
        dte=5,
        strike=170,
        bid=0.40,
        ask=0.46,
        mid=0.42,
        last=0.43,
        iv=0.4,
        delta=0.07,
        open_interest=100,
        volume=50,
        spread_pct=0.14,
        quote_source=QuoteSource.NBBO,
    )


def test_evaluate_empty_short_circuits():
    assert evaluate_positions([]) == []


def test_evaluate_partial_quote_failure(monkeypatch):
    def fake_spot(ticker: str) -> float:
        if ticker == "TSLA":
            raise RuntimeError("yahoo down")
        return 180.0

    def fake_quotes(ticker, expiry, spot, as_of, settings, right):
        return [_quote()]

    monkeypatch.setattr("option_desk.positions.evaluate.fetch_spot", fake_spot)
    monkeypatch.setattr("option_desk.positions.evaluate.load_expiry_quotes", fake_quotes)
    monkeypatch.setattr("option_desk.positions.evaluate.is_us_equity_rth", lambda now=None: True)

    results = evaluate_positions(
        [
            PositionInput(
                id="ok",
                ticker="NVDA",
                strategy="CSP",
                option_type="PUT",
                expiry=date(2026, 9, 18),
                strike=170,
                contracts=3,
                entry_premium=1.8,
                assignment_ok=True,
            ),
            PositionInput(
                id="bad",
                ticker="TSLA",
                strategy="CSP",
                option_type="PUT",
                expiry=date(2026, 9, 18),
                strike=200,
                contracts=1,
                entry_premium=2.0,
                assignment_ok=True,
            ),
        ],
        as_of=date(2026, 9, 13),
        rules=RuleSettings(),
        now=datetime(2026, 9, 13, 14, 0, tzinfo=timezone.utc),
    )
    by_id = {item.position_id: item for item in results}
    assert by_id["ok"].management.action == "CLOSE"
    assert by_id["ok"].profit_capture == 0.7667
    assert by_id["ok"].mark_pnl == 414
    assert by_id["ok"].estimated_close_pnl == 402
    assert by_id["bad"].management.action is None
    assert "QUOTE_UNAVAILABLE" in by_id["bad"].warnings
