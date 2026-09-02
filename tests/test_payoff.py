from datetime import date, datetime, timezone

from option_desk.agents.desk import heuristic_desk, run_desk_llm
from option_desk.config import Settings
from option_desk.payoff import attach_payoffs, expiration_pnl
from option_desk.report import render_markdown
from option_desk.schemas import (
    BucketCandidate,
    DeltaBucket,
    DeskAction,
    DeskLLMDecision,
    DeskRun,
    SpreadQuote,
    Structure,
    TickerSnapshot,
)
from tests.test_desk import _csp, _snap


def _spread_snap() -> TickerSnapshot:
    short = _csp("NVDA", 160, 0.20, "NVDA-2026-09-11-P-160")
    long = _csp("NVDA", 150, 0.08, "NVDA-2026-09-11-P-150")
    long = long.model_copy(update={"mid": 0.25, "bid": 0.20, "ask": 0.30})
    spread = SpreadQuote(
        short=short,
        long=long,
        width=10.0,
        max_loss_per_contract=920.0,
        contracts=2,
    )
    cand = BucketCandidate(
        bucket=DeltaBucket.STANDARD,
        target_delta=0.20,
        csp=short,
        spread=spread,
        csp_contracts=3,
        assignment_cash=48000,
        premium_per_contract=105,
    )
    snap = _snap("NVDA")
    return snap.model_copy(update={"buckets": {DeltaBucket.STANDARD: cand}})


def test_csp_expiration_formula():
    # 3 × short 160 put @ 1.05 mid
    assert expiration_pnl(180, short_strike=160, credit_per_share=1.05, contracts=3) == 315
    assert expiration_pnl(160, short_strike=160, credit_per_share=1.05, contracts=3) == 315
    assert round(expiration_pnl(158.95, short_strike=160, credit_per_share=1.05, contracts=3), 2) == 0
    assert expiration_pnl(150, short_strike=160, credit_per_share=1.05, contracts=3) == -2685
    assert expiration_pnl(0, short_strike=160, credit_per_share=1.05, contracts=3) == -47685


def test_spread_uses_net_credit_not_short_premium():
    pnl = expiration_pnl(
        180,
        short_strike=160,
        credit_per_share=0.80,
        long_strike=150,
        contracts=2,
    )
    assert pnl == 160
    floor = expiration_pnl(
        100,
        short_strike=160,
        credit_per_share=0.80,
        long_strike=150,
        contracts=2,
    )
    assert floor == -1840
    assert expiration_pnl(
        155,
        short_strike=160,
        credit_per_share=0.80,
        long_strike=150,
        contracts=2,
    ) == -840


def test_attach_csp_payoff_on_open():
    snap = _snap("NVDA")
    settings = Settings(tickers="NVDA", cash=55000)
    out = run_desk_llm([snap], [], 55000, settings, llm=None)
    decision = out.decisions[0]
    assert decision.action == DeskAction.OPEN
    po = decision.payoff
    assert po is not None
    assert po.structure == Structure.CSP
    assert po.contracts == 3
    assert po.credit_per_share == 1.05
    assert po.breakeven == 158.95
    assert po.max_profit == 315
    assert po.max_loss == 47685
    assert po.loss_limited is False
    assert po.assignment_cash == 48000
    assert po.pnl_at_spot == 315
    assert po.points[0].spot == po.x_min
    assert po.points[-1].spot == po.x_max
    assert any(abs(p.spot - 160) < 1e-6 for p in po.points)
    assert any(abs(p.spot - 158.95) < 1e-6 for p in po.points)


def test_attach_spread_payoff_ignores_csp_premium_field():
    snap = _spread_snap()
    raw = heuristic_desk([snap], events=[], cash=55000)
    raw.decisions[0] = raw.decisions[0].model_copy(
        update={"structure": Structure.BULL_PUT_SPREAD}
    )
    out = attach_payoffs(raw, [snap])
    po = out.decisions[0].payoff
    assert po is not None
    assert po.structure == Structure.BULL_PUT_SPREAD
    assert po.contracts == 2
    assert po.credit_per_share == 0.80
    assert po.max_profit == 160
    assert po.max_loss == 1840
    assert po.loss_limited is True
    assert po.assignment_cash is None
    assert po.long_strike == 150
    # short-only premium would have been $315; chart must not use that
    assert po.max_profit != 315


def test_skip_has_no_payoff():
    snap = _snap("NVDA", hard_skip=True)
    settings = Settings(tickers="NVDA", cash=55000)
    out = run_desk_llm([snap], [], 55000, settings, llm=None)
    assert out.decisions[0].action == DeskAction.SKIP
    assert out.decisions[0].payoff is None


def test_llm_schema_omits_computed_payoff():
    assert "payoff" not in DeskLLMDecision.model_fields


def test_markdown_lists_payoff_numbers():
    snap = _snap("NVDA")
    settings = Settings(tickers="NVDA", cash=55000, output_language="zh")
    out = run_desk_llm([snap], [], 55000, settings, llm=None)
    run = DeskRun(
        as_of=date(2026, 9, 2),
        fetched_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        cash=55000,
        snapshots=[snap],
        events=[],
        desk=out,
        language="zh",
    )
    md = render_markdown(run)
    assert "到期损益" in md
    assert "158.95" in md
    assert "按 mid 估算" in md
