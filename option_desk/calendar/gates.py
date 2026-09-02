from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from importlib.resources import files

import yaml
import yfinance as yf

from option_desk.config import Settings
from option_desk.schemas import CalendarGate, SoftMacroEvent


@lru_cache
def load_macro_dates() -> dict[str, list[date]]:
    raw = files("option_desk.calendar").joinpath("macro_dates.yaml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw) or {}
    out: dict[str, list[date]] = {}
    for key, values in parsed.items():
        out[key] = [date.fromisoformat(str(v)) for v in values or []]
    return out


def _in_window(day: date, start: date, end: date) -> bool:
    return start <= day <= end


def _coerce_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime().date()
        except Exception:
            return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return None
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_earnings_dates(ticker: str, start: date, end: date) -> list[date]:
    instrument = yf.Ticker(ticker)
    found: list[date] = []
    try:
        frame = instrument.get_earnings_dates(limit=12)
    except Exception:
        frame = None
    if frame is not None and not getattr(frame, "empty", True):
        for stamp in frame.index:
            day = _coerce_date(stamp)
            if day and _in_window(day, start, end):
                found.append(day)
    calendar = getattr(instrument, "calendar", None)
    if isinstance(calendar, dict):
        earnings = calendar.get("Earnings Date") or calendar.get("earningsDate")
        if earnings is not None:
            items = earnings if isinstance(earnings, (list, tuple)) else [earnings]
            for item in items:
                day = _coerce_date(item)
                if day and _in_window(day, start, end):
                    found.append(day)
    return sorted(set(found))


def evaluate_calendar(
    ticker: str,
    as_of: date,
    holding_end: date,
    settings: Settings,
) -> CalendarGate:
    start = as_of
    end = holding_end or (as_of + timedelta(days=settings.max_dte))
    macros = load_macro_dates()
    earnings = parse_earnings_dates(ticker, start, end)
    fomc = [d for d in macros.get("fomc", []) if _in_window(d, start, end)]
    hard_reasons: list[str] = []
    if earnings:
        hard_reasons.append(
            "Earnings in holding window: " + ", ".join(d.isoformat() for d in earnings)
        )
    if fomc:
        hard_reasons.append(
            "FOMC decision in holding window: " + ", ".join(d.isoformat() for d in fomc)
        )
    soft: list[SoftMacroEvent] = []
    for kind, key in (("CPI", "cpi"), ("NFP", "nfp"), ("PCE", "pce")):
        for day in macros.get(key, []):
            if _in_window(day, start, end):
                soft.append(SoftMacroEvent(name=f"{kind} release", event_date=day, kind=kind))
    return CalendarGate(
        ticker=ticker,
        hard_skip=bool(hard_reasons),
        hard_reasons=hard_reasons,
        earnings_dates=earnings,
        fomc_dates=fomc,
        soft_macros=soft,
        holding_start=start,
        holding_end=end,
    )
