from option_desk.positions.calculations import (
    calculate_estimated_close_pnl,
    calculate_mark_pnl,
    calculate_profit_capture,
)


def test_profit_capture_example():
    assert calculate_profit_capture(1.80, 0.42) == 0.7667


def test_mark_pnl_example():
    assert calculate_mark_pnl(1.80, 0.42, 3) == 414


def test_ask_pnl_example():
    assert calculate_estimated_close_pnl(1.80, 0.46, 3) == 402


def test_profit_capture_invalid_entry():
    assert calculate_profit_capture(0, 0.42) is None
