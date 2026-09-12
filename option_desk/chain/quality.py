"""Expected move, realized vol, IV regime, and contract score.

No network, no storage. IV regime is IV versus recent realized vol of the
same ticker — not a historical IV percentile.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import log, sqrt

from option_desk.schemas import (
    ContractQuote,
    ContractScore,
    DeskMode,
    IvContext,
    IvRegime,
    MarketLabel,
    QuoteSource,
)

# Contract score weights. Missing IV drops that slice and renormalizes.
_SCORE_WEIGHTS = {
    "delta": 25,
    "iv": 20,
    "premium": 20,
    "spread": 15,
    "expected_move": 10,
    "liquidity": 10,
}


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(round(max(lo, min(hi, value))))


def expected_move_pct(iv: float, dte: int) -> float:
    """1-sigma move as a fraction of spot: IV * sqrt(DTE/365)."""
    if iv <= 0 or dte <= 0:
        return 0.0
    return iv * sqrt(dte / 365.0)


def strike_distance_pct(spot: float, strike: float) -> float:
    if spot <= 0:
        return 0.0
    return (strike - spot) / spot


def cushion_pct(spot: float, strike: float, mode: DeskMode) -> float:
    """OTM cushion as a signed-positive fraction of spot. Negative = already ITM."""
    dist = strike_distance_pct(spot, strike)
    if mode is DeskMode.CALL:
        return dist
    return -dist


def log_returns(closes: Sequence[float]) -> list[float]:
    out: list[float] = []
    prev: float | None = None
    for price in closes:
        if price <= 0:
            continue
        if prev is not None and prev > 0:
            out.append(log(price / prev))
        prev = price
    return out


def realized_vol(closes: Sequence[float], window: int, min_obs: int = 10) -> float | None:
    """Annualized close-to-close vol. Simple returns, 252-day year."""
    rets = log_returns(closes)
    sample = rets[-window:] if len(rets) >= window else rets
    if len(sample) < min_obs:
        return None
    mean = sum(sample) / len(sample)
    var = sum((item - mean) ** 2 for item in sample) / (len(sample) - 1)
    if var < 0:
        return None
    return sqrt(var) * sqrt(252.0)


def sma(closes: Sequence[float], window: int) -> float | None:
    if window <= 0 or len(closes) < window:
        return None
    chunk = closes[-window:]
    return sum(chunk) / len(chunk)


def classify_iv_regime(iv: float | None, hv: float | None) -> IvRegime:
    if iv is None or hv is None or iv <= 0 or hv <= 0:
        return IvRegime.UNKNOWN
    ratio = iv / hv
    if ratio < 0.85:
        return IvRegime.LOW
    if ratio < 1.15:
        return IvRegime.NORMAL
    if ratio < 1.50:
        return IvRegime.HIGH
    return IvRegime.RICH


def classify_market_regime(
    vix: float | None,
    spy: float | None,
    spy_sma20: float | None,
    spy_sma50: float | None,
    vix_term: float | None = None,
) -> MarketLabel:
    """Deterministic VIX + SPY trend. Backwardation can bump one notch."""
    if vix is None or vix <= 0:
        return MarketLabel.NEUTRAL
    below_50 = spy is not None and spy_sma50 is not None and spy < spy_sma50
    above_20 = spy is not None and spy_sma20 is not None and spy > spy_sma20
    above_50 = spy is not None and spy_sma50 is not None and spy > spy_sma50
    if vix >= 30 or (vix >= 25 and below_50):
        label = MarketLabel.RISK_OFF
    elif vix >= 22 or below_50:
        label = MarketLabel.CAUTION
    elif vix < 14 and above_20 and above_50:
        label = MarketLabel.RISK_ON
    else:
        label = MarketLabel.NEUTRAL
    if vix_term is not None and 0 < vix_term < 0.95:
        if label is MarketLabel.RISK_ON:
            label = MarketLabel.NEUTRAL
        elif label is MarketLabel.NEUTRAL:
            label = MarketLabel.CAUTION
        elif label is MarketLabel.CAUTION:
            label = MarketLabel.RISK_OFF
    return label


def pick_atm(quotes: Sequence[ContractQuote], spot: float) -> ContractQuote | None:
    if not quotes:
        return None
    live = [q for q in quotes if q.quote_source is QuoteSource.NBBO]
    pool = live or list(quotes)
    return min(pool, key=lambda q: abs(q.strike - spot))


def build_iv_context(
    quotes: Sequence[ContractQuote],
    spot: float,
    closes: Sequence[float],
) -> IvContext | None:
    atm = pick_atm(quotes, spot)
    hv20 = realized_vol(closes, 20)
    hv60 = realized_vol(closes, 60)
    hv120 = realized_vol(closes, 120)
    atm_iv = atm.iv if atm is not None and atm.iv > 0 else None
    dte = atm.dte if atm is not None else None
    em_pct = expected_move_pct(atm_iv, dte) if atm_iv is not None and dte else None
    if atm_iv is None and hv20 is None and hv60 is None and hv120 is None:
        return None
    ratio = (atm_iv / hv20) if atm_iv and hv20 and hv20 > 0 else None
    return IvContext(
        atm_iv=atm_iv,
        hv_20=hv20,
        hv_60=hv60,
        hv_120=hv120,
        iv_hv_ratio=ratio,
        regime=classify_iv_regime(atm_iv, hv20),
        expected_move_pct=em_pct,
        expected_move=(spot * em_pct) if em_pct is not None and spot > 0 else None,
        expected_move_dte=dte,
    )


def _delta_score(delta: float, target: float, band: float) -> int:
    if band <= 0:
        return 100 if abs(delta - target) < 1e-9 else 0
    return clamp(100.0 * (1.0 - abs(delta - target) / band))


def _iv_score(ratio: float | None) -> int | None:
    if ratio is None or ratio <= 0:
        return None
    # 0.5 → 0, 1.0 → 50, 1.5 → 100. Selling premium likes rich IV vs HV.
    return clamp(50.0 + (ratio - 1.0) * 100.0)


def _premium_score(yield_pct: float) -> int:
    # Period yield on capital. ~1.5% in a 3–9 DTE window is excellent.
    return clamp(yield_pct / 0.015 * 100.0)


def _spread_score(quote: ContractQuote) -> int:
    if quote.quote_source is QuoteSource.LAST:
        return 0
    # 5% spread → 100, 25% → 0.
    return clamp(100.0 * (1.0 - (quote.spread_pct - 0.05) / 0.20))


def _em_score(coverage: float) -> int:
    # coverage = cushion / EM. 0.5 → 0, 1.0 → 50, 1.5 → 100.
    return clamp((coverage - 0.5) / 1.0 * 100.0)


def _liq_score(quote: ContractQuote) -> int:
    oi = min(quote.open_interest / 500.0, 1.0)
    vol = min(quote.volume / 100.0, 1.0)
    return clamp(50.0 * oi + 50.0 * vol)


def score_contract(
    quote: ContractQuote,
    *,
    spot: float,
    target_delta: float,
    band: float,
    mode: DeskMode,
    iv_hv_ratio: float | None,
) -> ContractScore:
    em_pct = expected_move_pct(quote.iv, quote.dte)
    cushion = cushion_pct(spot, quote.strike, mode)
    coverage = (cushion / em_pct) if em_pct > 0 else 0.0
    capital = quote.strike if mode is DeskMode.PUT else spot
    yield_pct = (quote.mid / capital) if capital > 0 else 0.0
    parts: dict[str, int | None] = {
        "delta": _delta_score(quote.delta, target_delta, band),
        "iv": _iv_score(iv_hv_ratio),
        "premium": _premium_score(yield_pct),
        "spread": _spread_score(quote),
        "expected_move": _em_score(coverage),
        "liquidity": _liq_score(quote),
    }
    weighted = 0.0
    mass = 0.0
    for key, weight in _SCORE_WEIGHTS.items():
        value = parts[key]
        if value is None:
            continue
        weighted += value * weight
        mass += weight
    total = clamp(weighted / mass) if mass else 0
    return ContractScore(
        total=total,
        delta=int(parts["delta"] or 0),
        iv=int(parts["iv"] or 0),
        premium=int(parts["premium"] or 0),
        spread=int(parts["spread"] or 0),
        expected_move=int(parts["expected_move"] or 0),
        liquidity=int(parts["liquidity"] or 0),
        strike_distance_pct=round(strike_distance_pct(spot, quote.strike), 6),
        premium_yield=round(yield_pct, 6),
        expected_move_pct=round(em_pct, 6),
        inside_expected_move=em_pct > 0 and cushion < em_pct,
    )
