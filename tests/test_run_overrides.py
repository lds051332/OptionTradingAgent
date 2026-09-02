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
