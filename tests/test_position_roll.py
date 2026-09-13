from datetime import date

from option_desk.positions.roll import find_roll_candidates
from option_desk.schemas import ContractQuote, QuoteSource


def _quote(**overrides) -> ContractQuote:
    base = dict(
        contract_id="NVDA-2026-09-25-P-170",
        ticker="NVDA",
        expiry=date(2026, 9, 25),
        dte=7,
        strike=170.0,
        bid=1.9,
        ask=2.0,
        mid=1.95,
        last=1.95,
        iv=0.4,
        delta=0.20,
        open_interest=500,
        volume=200,
        spread_pct=0.05,
        quote_source=QuoteSource.NBBO,
    )
    base.update(overrides)
    return ContractQuote(**base)


def test_find_roll_candidates_excludes_current_and_ranks_delta():
    current_expiry = date(2026, 9, 18)
    quotes = [
        _quote(contract_id="old", expiry=current_expiry, strike=170, delta=0.61, mid=3.8, dte=2),
        _quote(contract_id="far", expiry=date(2026, 9, 25), strike=180, delta=0.45, mid=2.8),
        _quote(contract_id="best", expiry=date(2026, 9, 25), strike=170, delta=0.21, mid=1.97),
        _quote(contract_id="low", expiry=date(2026, 9, 25), strike=165, delta=0.18, mid=1.25),
    ]
    picked = find_roll_candidates(
        quotes,
        current_expiry=current_expiry,
        current_strike=170,
        target_delta=0.20,
        estimated_close_price=2.00,
        contracts=3,
    )
    assert [item.contract.contract_id for item in picked] == ["best", "low", "far"]
    assert picked[0].recommended is True
    assert picked[0].estimated_net_per_share == -0.03
    assert picked[0].estimated_net == -9.0
