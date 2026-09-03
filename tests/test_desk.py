from datetime import date, datetime, timezone

from option_desk.agents.desk import enforce_desk_rules, heuristic_desk, no_candidate_desk
from option_desk.events.scout import _normalize
from option_desk.schemas import (
    BucketCandidate,
    CalendarGate,
    ContractQuote,
    DeltaBucket,
    DeskAction,
    DeskMode,
    DeskOutput,
    EventAction,
    EventMechanism,
    ScoutedEvent,
    Structure,
    TickerDecision,
    TickerSnapshot,
    QuoteSource,
)


def _csp(ticker: str, strike: float, delta: float, contract_id: str) -> ContractQuote:
    return ContractQuote(
        contract_id=contract_id,
        ticker=ticker,
        expiry=date(2026, 9, 11),
        dte=7,
        strike=strike,
        bid=1.0,
        ask=1.1,
        mid=1.05,
        iv=0.4,
        delta=delta,
        open_interest=100,
        volume=50,
        spread_pct=0.09,
    )


def _snap(ticker: str, hard_skip: bool = False) -> TickerSnapshot:
    cid = f"{ticker}-2026-09-11-P-160"
    csp = _csp(ticker, 160, 0.20, cid)
    cand = BucketCandidate(
        bucket=DeltaBucket.STANDARD,
        target_delta=0.20,
        csp=csp,
        spread=None,
        csp_contracts=3,
        assignment_cash=48000,
        premium_per_contract=105,
    )
    reasons = ["FOMC decision in holding window: 2026-09-16"] if hard_skip else []
    return TickerSnapshot(
        ticker=ticker,
        spot=180.0,
        as_of=date(2026, 9, 2),
        fetched_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        buckets={DeltaBucket.STANDARD: cand},
        calendar=CalendarGate(
            ticker=ticker,
            hard_skip=hard_skip,
            hard_reasons=reasons,
            holding_start=date(2026, 9, 2),
            holding_end=date(2026, 9, 11),
        ),
    )


def test_hard_skip_cannot_be_opened():
    snap = _snap("NVDA", hard_skip=True)
    raw = DeskOutput(
        decisions=[
            TickerDecision(
                ticker="NVDA",
                action=DeskAction.OPEN,
                structure=Structure.CSP,
                delta_bucket=DeltaBucket.STANDARD,
                contract_id="NVDA-2026-09-11-P-160",
                why="ignore the gate",
            )
        ]
    )
    out = enforce_desk_rules(raw, [snap], cash=55000)
    assert out.decisions[0].action == DeskAction.SKIP
    assert out.decisions[0].contract_id is None


def test_invented_contract_id_rejected():
    snap = _snap("NVDA")
    raw = DeskOutput(
        decisions=[
            TickerDecision(
                ticker="NVDA",
                action=DeskAction.OPEN,
                structure=Structure.CSP,
                delta_bucket=DeltaBucket.STANDARD,
                contract_id="NVDA-2026-09-11-P-999",
                why="made up strike",
            )
        ]
    )
    out = enforce_desk_rules(raw, [snap], cash=55000)
    assert out.decisions[0].action == DeskAction.SKIP
    assert "not in the delta buckets" in out.decisions[0].why


def test_heuristic_opens_standard_when_quiet():
    snap = _snap("NVDA")
    out = heuristic_desk([snap], events=[], cash=55000)
    assert out.decisions[0].action == DeskAction.OPEN
    assert out.decisions[0].delta_bucket == DeltaBucket.STANDARD
    assert out.decisions[0].contract_id == "NVDA-2026-09-11-P-160"


def test_heuristic_mentions_last_print():
    snap = _snap("NVDA")
    bucket = snap.buckets[DeltaBucket.STANDARD]
    csp = bucket.csp.model_copy(update={"quote_source": QuoteSource.LAST})
    snap = snap.model_copy(
        update={"buckets": {DeltaBucket.STANDARD: bucket.model_copy(update={"csp": csp})}}
    )
    out = heuristic_desk([snap], events=[], cash=55000, lang="zh")
    assert out.decisions[0].action == DeskAction.OPEN
    assert "非盘口" in out.decisions[0].why


def test_no_candidate_desk_skips_without_llm():
    snap = _snap("NVDA")
    snap = snap.model_copy(update={"buckets": {}, "notes": ["No liquid puts in DTE 3-9."]})
    out = no_candidate_desk([snap], lang="zh", mode="put")
    assert out.used_llm is False
    assert out.decisions[0].action == DeskAction.SKIP
    assert "已跳过日历与事件侦察" in out.decisions[0].why
    assert "No liquid puts" in out.decisions[0].why


def test_undated_geopolitics_forced_ignore():
    event = ScoutedEvent(
        title="War risk rises in the region",
        expected_time=None,
        tickers=["NVDA"],
        mechanism=EventMechanism.GAP,
        action=EventAction.SKIP,
        detail="ongoing conflict",
    )
    got = _normalize(event, ["NVDA"])
    assert got.action == EventAction.IGNORE
    assert got.mechanism == EventMechanism.NOISE


def _call_snap(ticker: str = "NVDA", hard_skip: bool = False, cost_basis: float = 170.0) -> TickerSnapshot:
    cid = f"{ticker}-2026-09-11-C-180"
    short = _csp(ticker, 180, 0.20, cid)
    cand = BucketCandidate(
        bucket=DeltaBucket.STANDARD,
        target_delta=0.20,
        csp=short,
        spread=None,
        csp_contracts=3,
        assignment_cash=54000,
        premium_per_contract=105,
    )
    reasons = ["FOMC decision in holding window: 2026-09-16"] if hard_skip else []
    return TickerSnapshot(
        ticker=ticker,
        spot=175.0,
        as_of=date(2026, 9, 2),
        fetched_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        buckets={DeltaBucket.STANDARD: cand},
        calendar=CalendarGate(
            ticker=ticker,
            hard_skip=hard_skip,
            hard_reasons=reasons,
            holding_start=date(2026, 9, 2),
            holding_end=date(2026, 9, 11),
        ),
        mode=DeskMode.CALL,
        shares=300,
        cost_basis=cost_basis,
    )


def test_heuristic_opens_covered_call_when_quiet():
    snap = _call_snap()
    out = heuristic_desk([snap], events=[], cash=0, lang="zh", mode="call")
    assert out.decisions[0].action == DeskAction.OPEN
    assert out.decisions[0].structure == Structure.COVERED_CALL
    assert out.decisions[0].contract_id == "NVDA-2026-09-11-C-180"
    assert out.decisions[0].assignment_ok is True


def test_call_desk_rejects_put_spread():
    snap = _call_snap()
    raw = DeskOutput(
        decisions=[
            TickerDecision(
                ticker="NVDA",
                action=DeskAction.OPEN,
                structure=Structure.BULL_PUT_SPREAD,
                delta_bucket=DeltaBucket.STANDARD,
                contract_id="NVDA-2026-09-11-C-180",
                why="wrong structure",
            )
        ]
    )
    out = enforce_desk_rules(raw, [snap], cash=0, lang="en", mode="call")
    assert out.decisions[0].action == DeskAction.SKIP


def test_call_coerces_csp_label_to_covered_call():
    snap = _call_snap()
    raw = DeskOutput(
        decisions=[
            TickerDecision(
                ticker="NVDA",
                action=DeskAction.OPEN,
                structure=Structure.CSP,
                delta_bucket=DeltaBucket.STANDARD,
                contract_id="NVDA-2026-09-11-C-180",
                why="llm said csp",
            )
        ]
    )
    out = enforce_desk_rules(raw, [snap], cash=0, lang="en", mode="call")
    assert out.decisions[0].action == DeskAction.OPEN
    assert out.decisions[0].structure == Structure.COVERED_CALL
