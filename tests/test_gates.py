from datetime import date

from option_desk.calendar.gates import evaluate_calendar
from option_desk.config import Settings


def test_fomc_in_window_is_hard_skip(monkeypatch):
    monkeypatch.setattr(
        "option_desk.calendar.gates.parse_earnings_dates",
        lambda *args, **kwargs: [],
    )
    gate = evaluate_calendar("NVDA", date(2026, 9, 14), date(2026, 9, 20), Settings())
    assert gate.hard_skip is True
    assert date(2026, 9, 16) in gate.fomc_dates
    assert any("FOMC" in r for r in gate.hard_reasons)


def test_cpi_is_soft_not_hard(monkeypatch):
    monkeypatch.setattr(
        "option_desk.calendar.gates.parse_earnings_dates",
        lambda *args, **kwargs: [],
    )
    gate = evaluate_calendar("NVDA", date(2026, 9, 10), date(2026, 9, 12), Settings())
    assert gate.hard_skip is False
    assert any(m.kind == "CPI" and m.event_date == date(2026, 9, 11) for m in gate.soft_macros)


def test_earnings_in_window_is_hard_skip(monkeypatch):
    monkeypatch.setattr(
        "option_desk.calendar.gates.parse_earnings_dates",
        lambda *args, **kwargs: [date(2026, 9, 10)],
    )
    gate = evaluate_calendar("MSFT", date(2026, 9, 8), date(2026, 9, 12), Settings())
    assert gate.hard_skip is True
    assert date(2026, 9, 10) in gate.earnings_dates
