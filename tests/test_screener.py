from datetime import date, datetime, timezone

import pandas as pd

from option_desk.chain.greeks import call_price
from option_desk.chain.screener import (
    _quality_notes,
    _row_quote,
    build_buckets,
    select_bucket,
    uses_last_print,
)
from option_desk.config import Settings
from option_desk.schemas import ContractQuote, DeltaBucket, IvSource, QuoteSource


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


def test_select_bucket_prefers_nbbo_over_last_print():
    live = _quote(contract_id="live", delta=0.20, spread_pct=0.09, volume=10)
    stale = _quote(
        contract_id="stale",
        delta=0.20,
        bid=0,
        ask=0,
        spread_pct=1.0,
        volume=5000,
        quote_source="last",
        iv_source="implied",
    )
    picked = select_bucket([stale, live], target=0.20, band=0.06)
    assert picked is not None
    assert picked.contract_id == "live"


def _last_row(**overrides):
    t = 7 / 365.0
    last = call_price(100.0, 103.0, t, 0.40, r=0.04)
    assert last is not None
    row = {
        "strike": 103.0,
        "bid": 0.0,
        "ask": 0.0,
        "lastPrice": last,
        "impliedVolatility": 0.00001,
        "openInterest": 0,
        "volume": 80,
        "lastTradeDate": datetime(2026, 9, 11, tzinfo=timezone.utc),
    }
    row.update(overrides)
    return pd.Series(row)


def test_row_quote_accepts_last_print_when_nbbo_missing():
    quote = _row_quote(
        "NVDA",
        date(2026, 9, 18),
        7,
        _last_row(),
        100.0,
        Settings(),
        right="C",
        as_of=date(2026, 9, 11),
    )
    assert quote is not None
    assert quote.quote_source is QuoteSource.LAST
    assert quote.iv_source is IvSource.IMPLIED
    assert quote.mid == round(quote.last, 4)
    assert abs(quote.iv - 0.40) < 0.03
    assert 0.05 < quote.delta < 0.45


def test_row_quote_rejects_last_print_without_volume():
    quote = _row_quote(
        "NVDA",
        date(2026, 9, 18),
        7,
        _last_row(volume=1, openInterest=0),
        100.0,
        Settings(),
        right="C",
        as_of=date(2026, 9, 11),
    )
    assert quote is None


def test_row_quote_rejects_stale_last_trade():
    quote = _row_quote(
        "NVDA",
        date(2026, 9, 18),
        7,
        _last_row(lastTradeDate=datetime(2026, 8, 1, tzinfo=timezone.utc)),
        100.0,
        Settings(),
        right="C",
        as_of=date(2026, 9, 11),
    )
    assert quote is None


def test_row_quote_still_rejects_wide_live_spread():
    row = pd.Series(
        {
            "strike": 160.0,
            "bid": 1.0,
            "ask": 2.0,
            "lastPrice": 1.5,
            "impliedVolatility": 0.4,
            "openInterest": 100,
            "volume": 50,
        }
    )
    assert _row_quote("NVDA", date(2026, 9, 11), 7, row, 180.0, Settings()) is None


def test_quality_notes_label_last_print_in_zh():
    cand_quote = _quote(
        quote_source=QuoteSource.LAST,
        iv_source=IvSource.IMPLIED,
        bid=0,
        ask=0,
        spread_pct=1.0,
    )
    from option_desk.schemas import BucketCandidate

    buckets = {
        DeltaBucket.STANDARD: BucketCandidate(
            bucket=DeltaBucket.STANDARD,
            target_delta=0.20,
            csp=cand_quote,
            spread=None,
            csp_contracts=1,
            assignment_cash=16000,
            premium_per_contract=105,
        )
    }
    notes = _quality_notes(buckets, Settings(), "zh")
    assert any("过期成交价" in note for note in notes)
    assert any("不是盘口" in note for note in notes)
    assert any("反推" in note for note in notes)
    assert uses_last_print(buckets)
