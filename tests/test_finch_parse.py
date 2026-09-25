import pytest

from option_desk.finch.parse import DeskRequest, is_capability_probe, parse_texts


def _parse(*texts: str, max_tickers: int = 3):
    return parse_texts(list(texts), max_tickers)


def test_chinese_put_with_wan_cash():
    result = _parse("NVDA MSFT 卖put 现金5万")
    req = result.request
    assert result.complete
    assert (req.mode, req.tickers, req.cash, req.language) == ("put", ["NVDA", "MSFT"], 50_000, "zh")
    assert req.delta == pytest.approx(0.20)


def test_english_covered_call():
    result = _parse("Covered call on AAPL, 300 shares, cost 180")
    req = result.request
    assert result.complete
    assert (req.mode, req.tickers, req.shares, req.cost_basis, req.language) == ("call", ["AAPL"], 300, 180, "en")


def test_chinese_alias_and_covered_call_fields():
    req = _parse("英伟达 备兑 持股 200 股 成本 150.5").request
    assert (req.mode, req.tickers, req.shares, req.cost_basis) == ("call", ["NVDA"], 200, 150.5)


def test_cashtag_k_units_and_delta():
    result = _parse("sell puts on $nvda cash $50k delta 0.15")
    req = result.request
    assert result.complete
    assert (req.tickers, req.cash) == (["NVDA"], 50_000)
    assert req.delta == pytest.approx(0.15)


def test_stopwords_are_not_tickers():
    req = _parse("I want to SELL a CSP ON NVDA with cash 20000").request
    assert req.tickers == ["NVDA"]


def test_lowercase_tickers_only_in_chinese_text():
    assert _parse("帮我看看nvda和msft卖put 现金 8万").request.tickers == ["NVDA", "MSFT"]
    assert _parse("sell puts on nvda cash 50000").request.tickers == []


def test_too_many_tickers_are_trimmed_and_reported():
    req = _parse("CSP on NVDA, TSLA, AMD, MSFT with 100k").request
    assert req.tickers == ["NVDA", "TSLA", "AMD"]
    assert req.dropped == ["MSFT"]
    assert req.cash == 100_000


def test_missing_fields_are_listed():
    assert _parse("帮我看看").missing == ["tickers", "cash"]
    assert _parse("covered call on AAPL").missing == ["shares", "cost_basis"]


def test_out_of_range_values_become_problems():
    assert "delta" in _parse("NVDA put cash 50000 delta 0.4").problems
    assert "cash" in _parse("NVDA put cash 500").problems
    assert "shares" in _parse("covered call AAPL 50 shares cost 100").problems


def test_later_turns_fill_and_override_earlier_ones():
    result = _parse("NVDA 卖put", "现金 8万")
    assert result.complete
    assert result.request.cash == 80_000
    corrected = _parse("NVDA 卖put 现金 5万", "改成 TSLA", "现金 3万")
    assert (corrected.request.tickers, corrected.request.cash) == (["TSLA"], 30_000)


def test_covered_call_context_carries_into_follow_up():
    result = _parse("备兑 AAPL", "300股 成本180")
    assert result.complete
    assert (result.request.mode, result.request.shares, result.request.cost_basis) == ("call", 300, 180)


def test_delta_percent_style():
    assert _parse("NVDA put cash 50000 delta 15").request.delta == pytest.approx(0.15)


def test_capability_probe_matches_default_prompt_only():
    assert is_capability_probe("Describe your capabilities.")
    assert is_capability_probe("  describe your capabilities ")
    assert not is_capability_probe("Describe your capabilities for NVDA puts")


def test_request_round_trips_through_dict():
    req = DeskRequest(mode="call", tickers=["AAPL"], shares=300, cost_basis=180, language="en")
    assert DeskRequest.from_dict({**req.to_dict(), "unknown": 1}) == req
