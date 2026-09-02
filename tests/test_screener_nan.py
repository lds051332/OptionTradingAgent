import math

import pandas as pd

from option_desk.chain.screener import _cell_int, _row_quote, fetch_spot
from option_desk.config import Settings
from datetime import date


def test_nan_open_interest_does_not_raise():
    assert _cell_int(float("nan")) == 0
    assert _cell_int(pd.NA) == 0
    assert _cell_int(None) == 0


def test_row_quote_skips_nan_volume():
    row = pd.Series(
        {
            "strike": 160.0,
            "bid": 1.0,
            "ask": 1.1,
            "lastPrice": 1.05,
            "impliedVolatility": 0.4,
            "openInterest": math.nan,
            "volume": math.nan,
        }
    )
    quote = _row_quote("NVDA", date(2026, 9, 11), 7, row, 180.0, Settings())
    # OI and volume both 0 → filtered by min_open_interest unless we only check NaN didn't crash.
    # With default min_open_interest=10 this returns None; that is success (no exception).
    assert quote is None or quote.open_interest == 0


def test_fetch_spot_survives_current_trading_period(monkeypatch):
    class BoomFast:
        def get(self, key, default=None):
            raise KeyError("currentTradingPeriod")

    class FakeTicker:
        fast_info = BoomFast()

        def history(self, period="5d"):
            return pd.DataFrame({"Close": [217.44]})

    monkeypatch.setattr("option_desk.chain.screener.yf.Ticker", lambda _ticker: FakeTicker())
    assert fetch_spot("NVDA") == 217.44
