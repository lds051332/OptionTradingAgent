"""Live VIX / SPY / QQQ snapshot and per-ticker close history.

Fails open: a missing Yahoo series never aborts the desk run.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

import yfinance as yf

from option_desk.chain.quality import classify_market_regime, realized_vol, sma
from option_desk.i18n import t
from option_desk.schemas import MarketLabel, MarketRegime

T = TypeVar("T")


def _with_retry(fn: Callable[[], T], attempts: int = 3, pause: float = 0.7) -> T:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(pause * (attempt + 1))
    assert last is not None
    raise last


def fetch_closes(ticker: str, period: str = "8mo") -> list[float]:
    def _once() -> list[float]:
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        if hist is None or getattr(hist, "empty", True) or "Close" not in hist.columns:
            return []
        out: list[float] = []
        for value in hist["Close"].tolist():
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if number > 0:
                out.append(number)
        return out

    try:
        return _with_retry(_once)
    except Exception:
        return []


def _last(closes: list[float]) -> float | None:
    return closes[-1] if closes else None


def localize_market_why(regime: MarketRegime, lang: str) -> str:
    bits: list[str] = []
    if regime.vix is not None:
        bits.append(f"VIX {regime.vix:.1f}")
    if regime.vix_term is not None:
        if regime.vix_term < 0.95:
            bits.append(t(lang, "regime_back"))
        else:
            bits.append(t(lang, "regime_contango"))
    if regime.spy is not None and regime.spy_sma50 is not None:
        if regime.spy < regime.spy_sma50:
            bits.append(t(lang, "regime_spy_below_50"))
        else:
            bits.append(t(lang, "regime_spy_above_50"))
    if regime.qqq is not None and regime.qqq_sma20 is not None:
        if regime.qqq < regime.qqq_sma20:
            bits.append(t(lang, "regime_qqq_below_20"))
        else:
            bits.append(t(lang, "regime_qqq_above_20"))
    return " · ".join(bits)


def build_market_regime(
    vix_closes: list[float],
    spy_closes: list[float],
    qqq_closes: list[float],
    vix3m_closes: list[float],
    lang: str = "en",
) -> MarketRegime | None:
    vix = _last(vix_closes)
    vix3m = _last(vix3m_closes)
    spy = _last(spy_closes)
    qqq = _last(qqq_closes)
    if vix is None and spy is None:
        return None
    vix_term = (vix3m / vix) if vix3m is not None and vix is not None and vix > 0 else None
    spy_sma20 = sma(spy_closes, 20)
    spy_sma50 = sma(spy_closes, 50)
    qqq_sma20 = sma(qqq_closes, 20)
    qqq_sma50 = sma(qqq_closes, 50)
    label = classify_market_regime(vix, spy, spy_sma20, spy_sma50, vix_term)
    regime = MarketRegime(
        label=label,
        vix=vix,
        vix3m=vix3m,
        vix_term=vix_term,
        spy=spy,
        spy_sma20=spy_sma20,
        spy_sma50=spy_sma50,
        spy_hv20=realized_vol(spy_closes, 20),
        qqq=qqq,
        qqq_sma20=qqq_sma20,
        qqq_sma50=qqq_sma50,
        qqq_hv20=realized_vol(qqq_closes, 20),
    )
    regime.why = localize_market_why(regime, lang)
    return regime


def fetch_market_regime(lang: str = "en") -> MarketRegime | None:
    return build_market_regime(
        fetch_closes("^VIX", "3mo"),
        fetch_closes("SPY", "8mo"),
        fetch_closes("QQQ", "8mo"),
        fetch_closes("^VIX3M", "3mo"),
        lang=lang,
    )


def market_reduce(regime: MarketRegime | None) -> bool:
    if regime is None:
        return False
    return regime.label in (MarketLabel.CAUTION, MarketLabel.RISK_OFF)
