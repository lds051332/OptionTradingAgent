from option_desk.finch.parse import DeskRequest
from option_desk.finch.render import render_capabilities, render_run
from option_desk.replay import iter_replay
from option_desk.schemas import DeskRun


def _run(scenario: str, lang: str) -> DeskRun:
    finished = [event for event in iter_replay(scenario, lang) if event.type == "run_finished"]
    return DeskRun.model_validate(finished[0].data["run"])


def test_open_decision_comes_first_with_payoff_and_disclaimer():
    run = _run("reduce-risk", "en")
    request = DeskRequest(tickers=["NVDA"], cash=55_000, language="en")
    text = render_run(run, request)
    assert text.startswith("### Cash-secured put desk")
    assert text.index("#### Decision") < text.index("#### Candidates")
    assert "**NVDA — OPEN**" in text
    assert "Expiration P/L" in text
    assert "Not investment advice." in text
    assert "replay (recorded proposal)" not in text
    assert len(text.encode("utf-8")) < 16_000


def test_hard_gate_renders_skip_in_chinese():
    run = _run("hard-gate", "zh")
    request = DeskRequest(tickers=["NVDA"], cash=55_000, language="zh")
    text = render_run(run, request)
    assert "### 卖 Put 决策台" in text
    assert "**NVDA — SKIP**" in text
    assert "硬性跳过" in text
    assert "不构成投资建议" in text


def test_dropped_tickers_are_called_out():
    run = _run("reduce-risk", "en")
    request = DeskRequest(tickers=["NVDA"], cash=55_000, language="en", dropped=["AMD"])
    assert "skips AMD" in render_run(run, request)


def test_ticker_without_a_chain_still_gets_a_skip_line():
    run = _run("reduce-risk", "zh")
    request = DeskRequest(tickers=["NVDA", "TSLA"], cash=55_000, language="zh")
    text = render_run(run, request)
    assert "**TSLA — SKIP**" in text
    assert "没拿到这只标的的期权链" in text


def test_capabilities_mention_both_books_and_limit():
    en = render_capabilities("en", 3)
    zh = render_capabilities("zh", 3)
    assert "Cash-secured puts" in en and "Covered calls" in en and "Up to 3 tickers" in en
    assert "备兑 Call" in zh and "最多 3 个标的" in zh
