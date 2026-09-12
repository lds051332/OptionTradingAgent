from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable, TypeVar

import pandas as pd
import yfinance as yf

from option_desk.chain.greeks import abs_put_delta, call_delta, implied_vol, years_from_dte
from option_desk.chain.market import fetch_closes
from option_desk.chain.quality import build_iv_context, score_contract
from option_desk.config import Settings
from option_desk.i18n import t
from option_desk.schemas import (
    BucketCandidate,
    CalendarGate,
    ContractQuote,
    DeltaBucket,
    DeskMode,
    IvSource,
    QuoteSource,
    SpreadQuote,
    TickerSnapshot,
)


def _cell_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:
        return default
    return number


def _cell_int(value, default: int = 0) -> int:
    return int(_cell_float(value, float(default)))


def _mid(bid: float, ask: float, last: float | None) -> float:
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    if last and last > 0:
        return last
    return max(bid, ask, last or 0)


def _spread_pct(bid: float, ask: float, mid: float) -> float:
    if mid <= 0 or ask <= 0:
        return 1.0
    return max(ask - bid, 0) / mid


def _has_nbbo(bid: float, ask: float) -> bool:
    return bid > 0 and ask > 0


def _trade_date(value) -> date | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        if hasattr(value, "date"):
            got = value.date()
            if isinstance(got, datetime):
                return got.date()
            if isinstance(got, date):
                return got
        return pd.Timestamp(value).date()
    except (TypeError, ValueError):
        return None


def _last_print_too_old(row: pd.Series, as_of: date, max_age_days: int) -> bool:
    traded = _trade_date(row.get("lastTradeDate"))
    if traded is None:
        return False
    return (as_of - traded).days > max_age_days


def _resolve_iv(
    chain_iv: float,
    price: float,
    spot: float,
    strike: float,
    t_years: float,
    right: str,
    settings: Settings,
    prefer_implied: bool,
) -> tuple[float, IvSource] | None:
    floor = settings.iv_floor
    chain_ok = chain_iv >= floor
    if prefer_implied or not chain_ok:
        implied = implied_vol(
            right,
            spot,
            strike,
            t_years,
            price,
            r=settings.risk_free_rate,
            q=settings.dividend_yield,
        )
        if implied is not None:
            return implied, IvSource.IMPLIED
        if chain_ok:
            return chain_iv, IvSource.CHAIN
        if chain_iv > 0:
            return max(chain_iv, floor), IvSource.FLOORED
        return floor, IvSource.FLOORED
    return chain_iv, IvSource.CHAIN


def _quality_notes(
    buckets: dict[DeltaBucket, BucketCandidate],
    settings: Settings,
    lang: str,
) -> list[str]:
    quotes: list[ContractQuote] = []
    for cand in buckets.values():
        quotes.append(cand.csp)
        if cand.spread:
            quotes.append(cand.spread.long)
    if not quotes:
        return []
    notes: list[str] = []
    if any(q.quote_source is QuoteSource.LAST for q in quotes):
        notes.append(t(lang, "note_last_print"))
    if any(q.iv_source is IvSource.IMPLIED for q in quotes):
        notes.append(t(lang, "note_iv_implied"))
    elif any(q.iv_source is IvSource.FLOORED for q in quotes):
        notes.append(t(lang, "note_iv_floored", floor=f"{settings.iv_floor:.0%}"))
    return notes


def uses_last_print(buckets: dict[DeltaBucket, BucketCandidate]) -> bool:
    return any(cand.csp.quote_source is QuoteSource.LAST for cand in buckets.values())


def _contract_id(ticker: str, expiry: date, strike: float, right: str = "P") -> str:
    flag = "C" if right.upper() == "C" else "P"
    return f"{ticker}-{expiry.isoformat()}-{flag}-{strike:g}"


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


def _spot_from_fast_info(instrument) -> float | None:
    """yfinance FastInfo can KeyError on currentTradingPeriod; never let that abort screening."""
    try:
        fast = getattr(instrument, "fast_info", None)
    except Exception:
        return None
    if fast is None:
        return None
    for key in ("lastPrice", "last_price", "regularMarketPrice"):
        try:
            value = fast.get(key) if hasattr(fast, "get") else getattr(fast, key, None)
        except Exception:
            value = None
        if value:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def fetch_spot(ticker: str) -> float:
    def _once() -> float:
        instrument = yf.Ticker(ticker)
        spot = _spot_from_fast_info(instrument)
        if spot:
            return spot
        hist = instrument.history(period="5d")
        if hist.empty:
            raise ValueError(f"No spot price for {ticker}")
        return float(hist["Close"].iloc[-1])

    return _with_retry(_once)


def _row_quote(
    ticker: str,
    expiry: date,
    dte: int,
    row: pd.Series,
    spot: float,
    settings: Settings,
    right: str = "P",
    as_of: date | None = None,
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
        if spread_pct > settings.max_spread_pct:
            return None
    else:
        if last is None or last <= 0:
            return None
        screen_day = as_of or (expiry - timedelta(days=dte))
        if _last_print_too_old(row, screen_day, settings.max_last_age_days):
            return None
        mid = last
        quote_source = QuoteSource.LAST
        spread_pct = 1.0
    if mid <= 0:
        return None
    if oi < settings.min_open_interest and volume < settings.min_open_interest:
        return None
    t_years = years_from_dte(dte)
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
        return None
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
        return None
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


def load_option_quotes(
    ticker: str,
    spot: float,
    as_of: date,
    settings: Settings,
    right: str = "P",
) -> list[ContractQuote]:
    instrument = yf.Ticker(ticker)
    expirations = _with_retry(lambda: tuple(instrument.options or ()))
    quotes: list[ContractQuote] = []
    flag = "C" if right.upper() == "C" else "P"
    for expiry_str in expirations:
        expiry = date.fromisoformat(expiry_str)
        dte = (expiry - as_of).days
        if dte < settings.min_dte or dte > settings.max_dte:
            continue
        try:
            chain = _with_retry(lambda exp=expiry_str: instrument.option_chain(exp), attempts=2)
        except Exception:
            continue
        frame = chain.calls if flag == "C" else chain.puts
        if frame is None or frame.empty:
            continue
        for _, row in frame.iterrows():
            quote = _row_quote(
                ticker, expiry, dte, row, spot, settings, right=flag, as_of=as_of
            )
            if quote is not None:
                quotes.append(quote)
    return quotes


def load_put_quotes(
    ticker: str,
    spot: float,
    as_of: date,
    settings: Settings,
) -> list[ContractQuote]:
    return load_option_quotes(ticker, spot, as_of, settings, right="P")


def load_call_quotes(
    ticker: str,
    spot: float,
    as_of: date,
    settings: Settings,
) -> list[ContractQuote]:
    return load_option_quotes(ticker, spot, as_of, settings, right="C")


def select_bucket(
    quotes: list[ContractQuote],
    target: float,
    band: float,
) -> ContractQuote | None:
    eligible = [q for q in quotes if abs(q.delta - target) <= band]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda q: (
            abs(q.delta - target),
            0 if q.quote_source is QuoteSource.NBBO else 1,
            q.spread_pct,
            -q.open_interest,
            -q.volume,
        ),
    )


def find_long_put(
    quotes: list[ContractQuote],
    short: ContractQuote,
    width: float,
) -> ContractQuote | None:
    same_expiry = [
        q
        for q in quotes
        if q.expiry == short.expiry and q.strike <= short.strike - width + 0.01
    ]
    if not same_expiry:
        same_expiry = [
            q for q in quotes if q.expiry == short.expiry and q.strike < short.strike
        ]
    if not same_expiry:
        return None
    target = short.strike - width
    return min(same_expiry, key=lambda q: abs(q.strike - target))


def _csp_contracts(cash: float, strike: float) -> int:
    if strike <= 0:
        return 0
    return max(int(cash // (strike * 100)), 0)


def _cc_contracts(shares: float) -> int:
    if shares <= 0:
        return 0
    return max(int(shares // 100), 0)


def _spread_contracts(settings: Settings, short: ContractQuote, long: ContractQuote) -> SpreadQuote:
    width = max(short.strike - long.strike, 0)
    credit = max(short.mid - long.mid, 0)
    max_loss = max(width - credit, 0) * 100
    if max_loss <= 0:
        contracts = 0
    else:
        contracts = max(int(settings.max_spread_loss // max_loss), 0)
    return SpreadQuote(
        short=short,
        long=long,
        width=width,
        max_loss_per_contract=round(max_loss, 2),
        contracts=contracts,
    )


def build_buckets(
    quotes: list[ContractQuote],
    cash: float,
    settings: Settings,
) -> dict[DeltaBucket, BucketCandidate]:
    specs = (
        (DeltaBucket.CONSERVATIVE, settings.conservative_delta, settings.conservative_delta_band),
        (DeltaBucket.STANDARD, settings.standard_delta, settings.standard_delta_band),
    )
    buckets: dict[DeltaBucket, BucketCandidate] = {}
    used_ids: set[str] = set()
    for bucket, target, band in specs:
        short = select_bucket([q for q in quotes if q.contract_id not in used_ids], target, band)
        if short is None:
            continue
        used_ids.add(short.contract_id)
        long = find_long_put(quotes, short, settings.spread_width)
        spread = _spread_contracts(settings, short, long) if long else None
        contracts = _csp_contracts(cash, short.strike)
        buckets[bucket] = BucketCandidate(
            bucket=bucket,
            target_delta=target,
            csp=short,
            spread=spread,
            csp_contracts=contracts,
            assignment_cash=round(contracts * short.strike * 100, 2),
            premium_per_contract=round(short.mid * 100, 2),
        )
    return buckets


def build_call_buckets(
    quotes: list[ContractQuote],
    shares: float,
    settings: Settings,
) -> dict[DeltaBucket, BucketCandidate]:
    specs = (
        (DeltaBucket.CONSERVATIVE, settings.conservative_delta, settings.conservative_delta_band),
        (DeltaBucket.STANDARD, settings.standard_delta, settings.standard_delta_band),
    )
    buckets: dict[DeltaBucket, BucketCandidate] = {}
    used_ids: set[str] = set()
    contracts = _cc_contracts(shares)
    for bucket, target, band in specs:
        short = select_bucket([q for q in quotes if q.contract_id not in used_ids], target, band)
        if short is None:
            continue
        used_ids.add(short.contract_id)
        buckets[bucket] = BucketCandidate(
            bucket=bucket,
            target_delta=target,
            csp=short,
            spread=None,
            csp_contracts=contracts,
            assignment_cash=round(contracts * short.strike * 100, 2),
            premium_per_contract=round(short.mid * 100, 2),
        )
    return buckets


def _score_buckets(
    buckets: dict[DeltaBucket, BucketCandidate],
    spot: float,
    settings: Settings,
    mode: DeskMode,
    iv_hv_ratio: float | None,
) -> dict[DeltaBucket, BucketCandidate]:
    scored: dict[DeltaBucket, BucketCandidate] = {}
    for bucket, cand in buckets.items():
        band = (
            settings.conservative_delta_band
            if bucket is DeltaBucket.CONSERVATIVE
            else settings.standard_delta_band
        )
        score = score_contract(
            cand.csp,
            spot=spot,
            target_delta=cand.target_delta,
            band=band,
            mode=mode,
            iv_hv_ratio=iv_hv_ratio,
        )
        scored[bucket] = cand.model_copy(update={"score": score})
    return scored


def screen_ticker(ticker: str, as_of: date, settings: Settings) -> TickerSnapshot:
    fetched_at = datetime.now(timezone.utc)
    notes: list[str] = []
    spot = fetch_spot(ticker)
    mode = DeskMode.CALL if str(settings.desk_mode).lower() == "call" else DeskMode.PUT
    lang = str(settings.output_language)
    if mode is DeskMode.CALL:
        quotes = load_call_quotes(ticker, spot, as_of, settings)
        empty_msg = t(lang, "note_no_calls", lo=settings.min_dte, hi=settings.max_dte)
        buckets = build_call_buckets(quotes, settings.shares, settings)
        leftover = max(int(settings.shares) - _cc_contracts(settings.shares) * 100, 0)
        if leftover:
            notes.append(t(lang, "note_uncovered", leftover=leftover))
    else:
        quotes = load_put_quotes(ticker, spot, as_of, settings)
        empty_msg = t(lang, "note_no_puts", lo=settings.min_dte, hi=settings.max_dte)
        buckets = build_buckets(quotes, settings.cash, settings)
    if as_of != date.today():
        notes.append(t(lang, "note_as_of"))
    if not quotes:
        notes.append(empty_msg)
    notes.extend(_quality_notes(buckets, settings, str(settings.output_language)))
    if buckets:
        holding_end = max(c.csp.expiry for c in buckets.values())
    else:
        holding_end = as_of + timedelta(days=settings.max_dte)

    iv_context = build_iv_context(quotes, spot, fetch_closes(ticker)) if quotes else None
    if buckets:
        ratio = iv_context.iv_hv_ratio if iv_context else None
        buckets = _score_buckets(buckets, spot, settings, mode, ratio)

    return TickerSnapshot(
        ticker=ticker,
        spot=spot,
        as_of=as_of,
        fetched_at=fetched_at,
        buckets=buckets,
        calendar=CalendarGate(
            ticker=ticker,
            hard_skip=False,
            holding_start=as_of,
            holding_end=holding_end,
        ),
        notes=notes,
        mode=mode,
        shares=settings.shares if mode is DeskMode.CALL else None,
        cost_basis=settings.cost_basis if mode is DeskMode.CALL else None,
        iv_context=iv_context,
    )
