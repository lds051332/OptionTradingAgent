from __future__ import annotations


def calculate_profit_capture(entry_premium: float, mark: float) -> float | None:
    if entry_premium <= 0:
        return None
    return round((entry_premium - mark) / entry_premium, 4)


def calculate_mark_pnl(entry_premium: float, mark: float, contracts: int) -> float:
    return round((entry_premium - mark) * contracts * 100, 2)


def calculate_estimated_close_pnl(entry_premium: float, close_price: float, contracts: int) -> float:
    return round((entry_premium - close_price) * contracts * 100, 2)
