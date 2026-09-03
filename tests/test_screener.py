from datetime import date

from option_desk.chain.screener import build_buckets, select_bucket
from option_desk.config import Settings
from option_desk.schemas import ContractQuote, DeltaBucket


def _quote(**overrides) -> ContractQuote:
    base = dict(
        contract_id="NVDA-2026-09-11-P-160",
        ticker="NVDA",
        expiry=date(2026, 9, 11),
        dte=7,
        strike=160.0,
        bid=1.0,
        ask=1.1,
        mid=1.05,
        last=1.05,
        iv=0.4,
        delta=0.20,
        open_interest=500,
        volume=200,
        spread_pct=0.09,
    )
    base.update(overrides)
    return ContractQuote(**base)


def test_select_bucket_picks_closest_within_band():
    quotes = [
        _quote(contract_id="a", strike=150, delta=0.08),
        _quote(contract_id="b", strike=155, delta=0.11),
        _quote(contract_id="c", strike=165, delta=0.21),
    ]
    picked = select_bucket(quotes, target=0.11, band=0.05)
    assert picked is not None
    assert picked.contract_id == "b"


def test_select_bucket_empty_when_outside_band():
    quotes = [_quote(delta=0.40, strike=180, contract_id="far")]
    assert select_bucket(quotes, target=0.11, band=0.05) is None


def test_build_buckets_csp_qty_and_two_rungs():
    settings = Settings(cash=55000)
    quotes = [
        _quote(
            contract_id="NVDA-2026-09-11-P-150",
            strike=150.0,
            delta=0.11,
            mid=0.60,
            bid=0.55,
            ask=0.65,
        ),
        _quote(
            contract_id="NVDA-2026-09-11-P-140",
            strike=140.0,
            delta=0.06,
            mid=0.30,
            bid=0.25,
            ask=0.35,
        ),
        _quote(
            contract_id="NVDA-2026-09-11-P-160",
            strike=160.0,
            delta=0.20,
            mid=1.20,
            bid=1.10,
            ask=1.30,
        ),
    ]
    buckets = build_buckets(quotes, cash=55000, settings=settings)
    assert DeltaBucket.CONSERVATIVE in buckets
    assert DeltaBucket.STANDARD in buckets
    std = buckets[DeltaBucket.STANDARD]
    assert std.csp.strike == 160.0
    assert std.csp_contracts == int(55000 // (160 * 100))
    assert std.spread is not None
    assert std.spread.long.strike < std.csp.strike


def test_build_call_buckets_qty_from_shares():
    from option_desk.chain.screener import build_call_buckets

    settings = Settings(shares=350, desk_mode="call")
    quotes = [
        _quote(
            contract_id="NVDA-2026-09-11-C-190",
            strike=190.0,
            delta=0.11,
            mid=0.80,
            bid=0.75,
            ask=0.85,
        ),
        _quote(
            contract_id="NVDA-2026-09-11-C-180",
            strike=180.0,
            delta=0.20,
            mid=1.40,
            bid=1.30,
            ask=1.50,
        ),
        _quote(
            contract_id="NVDA-2026-09-11-C-200",
            strike=200.0,
            delta=0.06,
            mid=0.35,
            bid=0.30,
            ask=0.40,
        ),
    ]
    buckets = build_call_buckets(quotes, shares=350, settings=settings)
    assert DeltaBucket.CONSERVATIVE in buckets
    assert DeltaBucket.STANDARD in buckets
    std = buckets[DeltaBucket.STANDARD]
    assert std.csp.strike == 180.0
    assert std.csp_contracts == 3
    assert std.spread is None
    assert std.assignment_cash == 3 * 180 * 100
