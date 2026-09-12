from datetime import date

from option_desk.chain.quality import (
    build_iv_context,
    classify_iv_regime,
    classify_market_regime,
    expected_move_pct,
    realized_vol,
    score_contract,
    sma,
)
from option_desk.chain.market import build_market_regime
from option_desk.schemas import (
    ContractQuote,
    DeskMode,
    IvRegime,
    MarketLabel,
    QuoteSource,
)


def _quote(**overrides) -> ContractQuote:
    base = dict(
        contract_id="NVDA-2026-09-18-P-170",
        ticker="NVDA",
        expiry=date(2026, 9, 18),
        dte=7,
        strike=170.0,
        bid=1.8,
        ask=1.9,
        mid=1.85,
        iv=0.46,
        delta=0.20,
        open_interest=800,
        volume=200,
        spread_pct=0.054,
    )
    base.update(overrides)
    return ContractQuote(**base)


def _closes(start: float, n: int, step: float = 0.0) -> list[float]:
    return [start + i * step for i in range(n)]


def test_expected_move_one_sigma():
    pct = expected_move_pct(0.40, 7)
    assert abs(pct - 0.40 * (7 / 365) ** 0.5) < 1e-9
    assert expected_move_pct(0, 7) == 0.0
    assert expected_move_pct(0.4, 0) == 0.0


def test_realized_vol_needs_enough_obs():
    assert realized_vol(_closes(100, 5), 20) is None
    series = []
    price = 100.0
    for i in range(40):
        price *= 1.01 if i % 2 == 0 else 0.99
        series.append(price)
    hv = realized_vol(series, 20)
    assert hv is not None
    assert 0.05 < hv < 2.0


def test_sma_window():
    assert sma([1, 2, 3, 4], 3) == 3.0
    assert sma([1, 2], 3) is None


def test_iv_regime_thresholds():
    assert classify_iv_regime(0.20, 0.30) is IvRegime.LOW
    assert classify_iv_regime(0.30, 0.30) is IvRegime.NORMAL
    assert classify_iv_regime(0.40, 0.30) is IvRegime.HIGH
    assert classify_iv_regime(0.50, 0.30) is IvRegime.RICH
    assert classify_iv_regime(None, 0.30) is IvRegime.UNKNOWN


def test_market_regime_rules():
    assert classify_market_regime(32, 500, 510, 520) is MarketLabel.RISK_OFF
    assert classify_market_regime(26, 500, 510, 520) is MarketLabel.RISK_OFF
    assert classify_market_regime(23, 530, 520, 510) is MarketLabel.CAUTION
    assert classify_market_regime(12, 530, 520, 510) is MarketLabel.RISK_ON
    assert classify_market_regime(16, 530, 520, 510) is MarketLabel.NEUTRAL
    # Backwardation bumps caution → risk_off
    assert classify_market_regime(23, 530, 520, 510, vix_term=0.90) is MarketLabel.RISK_OFF


def test_score_penalizes_last_print_and_inside_em():
    live = score_contract(
        _quote(strike=160, delta=0.12),
        spot=180,
        target_delta=0.11,
        band=0.05,
        mode=DeskMode.PUT,
        iv_hv_ratio=1.3,
    )
    inside = score_contract(
        _quote(strike=175, delta=0.20, mid=2.5),
        spot=180,
        target_delta=0.20,
        band=0.06,
        mode=DeskMode.PUT,
        iv_hv_ratio=1.3,
    )
    stale = score_contract(
        _quote(quote_source=QuoteSource.LAST, bid=0, ask=0, spread_pct=1.0, strike=160, delta=0.12),
        spot=180,
        target_delta=0.11,
        band=0.05,
        mode=DeskMode.PUT,
        iv_hv_ratio=1.3,
    )
    assert live.inside_expected_move is False
    assert inside.inside_expected_move is True
    assert live.expected_move > inside.expected_move
    assert stale.spread == 0
    assert stale.total < live.total
    assert 0 <= live.total <= 100


def test_iv_context_from_quotes_and_closes():
    quotes = [_quote(strike=180, iv=0.50), _quote(strike=160, iv=0.40)]
    series = []
    price = 100.0
    for i in range(80):
        price *= 1.004 if i % 3 else 0.997
        series.append(price)
    ctx = build_iv_context(quotes, 180.0, series)
    assert ctx is not None
    assert ctx.atm_iv == 0.50
    assert ctx.hv_20 is not None
    assert ctx.expected_move_pct is not None
    assert ctx.expected_move == 180.0 * ctx.expected_move_pct


def test_build_market_regime_localizes_why():
    vix = [18.0] * 5 + [21.0]
    spy = [500 + i * 0.2 for i in range(60)]
    qqq = [400 + i * 0.1 for i in range(60)]
    vix3m = [22.0]
    regime = build_market_regime(vix, spy, qqq, vix3m, lang="zh")
    assert regime is not None
    assert regime.vix == 21.0
    assert "SPY" in regime.why
    assert "50 日均" in regime.why
