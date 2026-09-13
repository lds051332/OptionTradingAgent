from __future__ import annotations

from datetime import date

import yfinance as yf

from option_desk.chain.greeks import abs_put_delta, call_delta, years_from_dte
from option_desk.chain.screener import (
    _cell_float,
    _cell_int,
    _contract_id,
    _has_nbbo,
    _mid,
    _resolve_iv,
    _spread_pct,
    _with_retry,
)
from option_desk.config import Settings
from option_desk.schemas import ContractQuote, IvSource, QuoteSource


def estimated_close_price(quote: ContractQuote) -> float:
    if quote.ask and quote.ask > 0:
        return quote.ask
    if quote.last and quote.last > 0:
        return quote.last
    return quote.mid


def _relaxed_quote(
    ticker: str,
    expiry: date,
    dte: int,
    row,
    spot: float,
    settings: Settings,
    right: str,
) -> ContractQuote | None:
    strike = _cell_float(row.get("strike"))
    bid = _cell_float(row.get("bid"))
    ask = _cell_float(row.get("ask"))
    last_raw = _cell_float(row.get("lastPrice"))
    last = last_raw or None
    chain_iv = _cell_float(row.get("impliedVolatility"))
    oi = _cell_int(row.get("openInterest"))
    volume = _cell_int(row.get("volume"))
    if strike <= 0:
        return None
    live = _has_nbbo(bid, ask)
    if live:
        mid = _mid(bid, ask, last)
        quote_source = QuoteSource.NBBO
        spread_pct = _spread_pct(bid, ask, mid)
    else:
        if last is None or last <= 0:
            if bid <= 0 and ask <= 0:
                return None
            mid = max(bid, ask)
        else:
            mid = last
        quote_source = QuoteSource.LAST
        spread_pct = 1.0
    if mid <= 0:
        return None
    t_years = years_from_dte(max(dte, 1) if dte <= 0 else dte)
    resolved = _resolve_iv(
        chain_iv,
        mid,
        spot,
        strike,
        t_years,
        right,
        settings,
        prefer_implied=quote_source is QuoteSource.LAST,
    )
    if resolved is None:
        iv, iv_source = settings.iv_floor, IvSource.FLOORED
    else:
        iv, iv_source = resolved
    if right.upper() == "C":
        delta = call_delta(
            spot,
            strike,
            t_years,
            iv,
            r=settings.risk_free_rate,
            q=settings.dividend_yield,
        )
    else:
        delta = abs_put_delta(
            spot,
            strike,
            t_years,
            iv,
            r=settings.risk_free_rate,
            q=settings.dividend_yield,
        )
    if delta is None:
        delta = 0.0
    return ContractQuote(
        contract_id=_contract_id(ticker, expiry, strike, right),
        ticker=ticker,
        expiry=expiry,
        dte=dte,
        strike=strike,
        bid=bid,
        ask=ask,
        mid=round(mid, 4),
        last=last,
        iv=round(iv, 4),
        delta=round(delta, 4),
        open_interest=oi,
        volume=volume,
        spread_pct=round(spread_pct, 4),
        quote_source=quote_source,
        iv_source=iv_source,
    )


def load_expiry_quotes(
    ticker: str,
    expiry: date,
    spot: float,
    as_of: date,
    settings: Settings,
    right: str,
) -> list[ContractQuote]:
    instrument = yf.Ticker(ticker)
    expiry_str = expiry.isoformat()
    try:
        chain = _with_retry(lambda: instrument.option_chain(expiry_str), attempts=2)
    except Exception:
        return []
    flag = "C" if right.upper() == "C" else "P"
    frame = chain.calls if flag == "C" else chain.puts
    if frame is None or frame.empty:
        return []
    dte = (expiry - as_of).days
    quotes: list[ContractQuote] = []
    for _, row in frame.iterrows():
        quote = _relaxed_quote(ticker, expiry, dte, row, spot, settings, flag)
        if quote is not None:
            quotes.append(quote)
    return quotes


def load_open_contract_quote(
    ticker: str,
    expiry: date,
    strike: float,
    right: str,
    spot: float,
    as_of: date,
    settings: Settings,
) -> ContractQuote | None:
    quotes = load_expiry_quotes(ticker, expiry, spot, as_of, settings, right)
    if not quotes:
        return None
    return min(quotes, key=lambda quote: abs(quote.strike - strike))
