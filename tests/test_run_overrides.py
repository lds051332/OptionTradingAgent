from option_desk.config import Settings, apply_run_overrides


def test_delta_scales_conservative_bucket():
    base = Settings(standard_delta=0.20, conservative_delta=0.11, cash=55000)
    overlay = apply_run_overrides(base, tickers=["nvda", "msft"], delta=0.25, cash=40000, language="zh")
    assert overlay.ticker_list() == ["NVDA", "MSFT"]
    assert overlay.standard_delta == 0.25
    assert overlay.conservative_delta == 0.14
    assert overlay.cash == 40000
    assert overlay.output_language == "zh"
    assert base.standard_delta == 0.20
    assert base.cash == 55000


def test_call_overrides_shares_and_basis():
    base = Settings(shares=100, cost_basis=0, desk_mode="put")
    overlay = apply_run_overrides(
        base,
        desk_mode="call",
        shares=300,
        cost_basis=172.4,
        delta=0.18,
    )
    assert overlay.desk_mode == "call"
    assert overlay.shares == 300
    assert overlay.cost_basis == 172.4
    assert overlay.standard_delta == 0.18
    assert base.desk_mode == "put"
