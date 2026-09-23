"""Three recorded desk runs. Quotes and the model proposal are frozen; the stamp uses live rules."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timezone

from option_desk.agents.desk import enforce_desk_rules, heuristic_desk
from option_desk.events.search import SearchHit
from option_desk.i18n import localize_hard_reason, normalize_lang, t
from option_desk.payoff import attach_payoffs
from option_desk.rewrite import decision_changes
from option_desk.schemas import (
    BucketCandidate,
    CalendarGate,
    ContractQuote,
    ContractScore,
    DeltaBucket,
    DeskAction,
    DeskMode,
    DeskOutput,
    DeskRun,
    EventAction,
    EventMechanism,
    IvContext,
    IvRegime,
    MarketLabel,
    MarketRegime,
    ScoutedEvent,
    Structure,
    TickerDecision,
    TickerSnapshot,
)
from option_desk.stream import StreamEvent, stream_event

SCENARIO_IDS = ("hard-gate", "invented-contract", "reduce-risk")

_AS_OF = date(2026, 9, 2)
_EXPIRY = date(2026, 9, 11)
_FETCHED = datetime(2026, 9, 2, 14, 30, tzinfo=timezone.utc)
_CASH = 55_000.0
_TICKER = "NVDA"
_STANDARD_ID = "NVDA-2026-09-11-P-170"
_CONSERVATIVE_ID = "NVDA-2026-09-11-P-155"
_FAKE_ID = "NVDA-2026-09-11-P-999"


def _L(lang: str, en: str, zh: str) -> str:
    return zh if normalize_lang(lang) == "zh" else en


def scenario_ids() -> tuple[str, ...]:
    return SCENARIO_IDS


def list_scenarios(lang: str) -> list[dict[str, str]]:
    lang = normalize_lang(lang)
    return [
        {
            "id": scenario,
            "kicker": _kicker(scenario),
            "title": _title(scenario, lang),
            "summary": _summary(scenario, lang),
        }
        for scenario in SCENARIO_IDS
    ]


@dataclass
class ReplayCase:
    scenario: str
    title: str
    summary: str
    snapshot: TickerSnapshot
    events: list[ScoutedEvent]
    market: MarketRegime
    hits: list[SearchHit]
    proposal: DeskOutput
    stamped: DeskOutput
    rewrite: dict


def build_replay(scenario: str, lang: str = "en") -> ReplayCase:
    if scenario not in SCENARIO_IDS:
        raise KeyError(scenario)
    lang = normalize_lang(lang)
    if scenario == "hard-gate":
        return _hard_gate(lang)
    if scenario == "invented-contract":
        return _invented(lang)
    return _reduce(lang)


def iter_replay(scenario: str, lang: str = "en") -> Iterator[StreamEvent]:
    case = build_replay(scenario, lang)
    lang = normalize_lang(lang)
    snap = _localize_calendar(case.snapshot, lang)
    yield stream_event(
        "run_started",
        message=t(lang, "pipe_run_started", tickers=snap.ticker),
        tickers=[snap.ticker],
        delta=0.20,
        cash=_CASH,
        as_of=_AS_OF.isoformat(),
        llm_label=_L(lang, "replay (recorded proposal)", "回放（录制提案）"),
        language=lang,
        mode=DeskMode.PUT.value,
        scenario=case.scenario,
        title=case.title,
        summary=case.summary,
        replay=True,
    )
    yield stream_event(
        "regime_started",
        message=_L(lang, "Replaying the recorded market regime…", "回放录好的市场体制…"),
    )
    yield stream_event(
        "regime_done",
        message=case.market.why,
        market=case.market.model_dump(mode="json"),
    )
    yield stream_event(
        "screen_started",
        ticker=snap.ticker,
        message=_L(
            lang,
            f"Replaying a recorded {snap.ticker} put chain…",
            f"回放录好的 {snap.ticker} put 链…",
        ),
    )
    yield stream_event(
        "screen_done",
        ticker=snap.ticker,
        message=t(
            lang,
            "pipe_screen_done",
            ticker=snap.ticker,
            spot=f"{snap.spot:.2f}",
            n=len(snap.buckets),
            note="",
        ),
        snapshot=snap.model_dump(mode="json"),
    )
    yield stream_event(
        "calendar_started",
        ticker=snap.ticker,
        message=_L(lang, "Replaying the recorded holding-window calendar…", "回放录好的持有窗口日历…"),
    )
    cal = snap.calendar
    if cal.hard_skip:
        reasons = "; ".join(cal.hard_reasons) or t(lang, "pipe_calendar_gate")
        cal_msg = t(lang, "pipe_calendar_hard", ticker=snap.ticker, reasons=reasons)
    else:
        cal_msg = t(lang, "pipe_calendar_clear", ticker=snap.ticker)
    yield stream_event(
        "calendar_done",
        ticker=snap.ticker,
        message=cal_msg,
        calendar=cal.model_dump(mode="json"),
    )
    yield stream_event(
        "scout_search_started",
        message=_L(lang, "Replaying recorded search hits…", "回放录好的搜索结果…"),
    )
    yield stream_event(
        "scout_hits",
        message=t(lang, "pipe_scout_hits", n=len(case.hits)),
        hits=[hit.as_dict() for hit in case.hits],
    )
    yield stream_event(
        "scout_llm_started",
        message=_L(
            lang,
            "Recorded hits have no dated catalyst, so they stay ignore.",
            "录制结果没有带日期的催化剂，按规则记为 ignore。",
        ),
    )
    yield stream_event(
        "scout_done",
        message=t(lang, "pipe_scout_done", n=len(case.events)),
        events=[event.model_dump(mode="json") for event in case.events],
        warnings=[],
    )
    yield stream_event(
        "desk_started",
        message=_L(
            lang,
            "Sending the recorded proposal through the live rules…",
            "把录好的模型提案送进现行规则…",
        ),
    )
    yield stream_event(
        "desk_done",
        message=t(lang, "pipe_desk_done"),
        desk=case.stamped.model_dump(mode="json"),
        proposal=case.proposal.model_dump(mode="json"),
        rewrite=case.rewrite,
    )
    run = DeskRun(
        as_of=_AS_OF,
        fetched_at=_FETCHED,
        cash=_CASH,
        snapshots=[snap],
        events=case.events,
        desk=case.stamped,
        warnings=[],
        llm_label=_L(lang, "replay (recorded proposal)", "回放（录制提案）"),
        language=lang,
        mode=DeskMode.PUT,
        market=case.market,
    )
    yield stream_event(
        "run_finished",
        message=t(lang, "pipe_run_finished"),
        run=run.model_dump(mode="json"),
        scenario=case.scenario,
    )


def _hard_gate(lang: str) -> ReplayCase:
    snap = _snapshot(lang, hard_skip=True)
    proposal = _proposal(
        lang,
        contract_id=_STANDARD_ID,
        bucket=DeltaBucket.STANDARD,
        why=_L(
            lang,
            "Earnings are this week, but the premium is rich enough. Open the standard put.",
            "本周有财报，但权利金够厚。开标准档 put。",
        ),
    )
    stamped = _enforce(proposal, snap, lang)
    return _case("hard-gate", lang, snap, _quiet_market(lang), proposal, stamped, _hard_rule(lang))


def _invented(lang: str) -> ReplayCase:
    snap = _snapshot(lang, hard_skip=False)
    proposal = _proposal(
        lang,
        contract_id=_FAKE_ID,
        bucket=DeltaBucket.STANDARD,
        why=_L(
            lang,
            "Open the 999 strike. It is safer than either listed bucket.",
            "开 999 行权价。它比列出的两档都更安全。",
        ),
    )
    stamped = _enforce(proposal, snap, lang)
    return _case(
        "invented-contract",
        lang,
        snap,
        _quiet_market(lang),
        proposal,
        stamped,
        _L(
            lang,
            "The enforcer rejected the open: that contract_id is not in either delta bucket.",
            "强制器拒绝开仓：这个 contract_id 不在任一档位里。",
        ),
    )


def _reduce(lang: str) -> ReplayCase:
    snap = _snapshot(lang, hard_skip=False, low_iv=True, standard_inside_em=True)
    market = _risk_off(lang)
    proposal = _proposal(
        lang,
        contract_id=_STANDARD_ID,
        bucket=DeltaBucket.STANDARD,
        why=_L(lang, "Open the standard 0.20 delta put.", "开标准档 0.20Δ put。"),
    )
    heuristic = heuristic_desk([snap], _events(lang), _CASH, lang, market=market)
    stamped = attach_payoffs(enforce_desk_rules(heuristic, [snap], _CASH, lang), [snap])
    stamped = stamped.model_copy(update={"portfolio_note": _replay_note(lang), "used_llm": False})
    return _case(
        "reduce-risk",
        lang,
        snap,
        market,
        proposal,
        stamped,
        _L(
            lang,
            "Risk-off and cheap IV moved the open from standard to conservative. The standard contract itself was legal.",
            "市场处于 risk-off，且 IV 相对近期波动偏便宜，开仓从标准档改到保守档。标准档合约本身是合法的。",
        ),
    )


def _case(
    scenario: str,
    lang: str,
    snap: TickerSnapshot,
    market: MarketRegime,
    proposal: DeskOutput,
    stamped: DeskOutput,
    rule: str,
) -> ReplayCase:
    return ReplayCase(
        scenario=scenario,
        title=_title(scenario, lang),
        summary=_summary(scenario, lang),
        snapshot=snap,
        events=_events(lang),
        market=market,
        hits=_hits(lang),
        proposal=proposal,
        stamped=stamped,
        rewrite={
            "scenario": scenario,
            "rule": rule,
            "changes": _changes(proposal, stamped),
        },
    )


def _enforce(proposal: DeskOutput, snap: TickerSnapshot, lang: str) -> DeskOutput:
    stamped = attach_payoffs(enforce_desk_rules(proposal, [snap], _CASH, lang), [snap])
    return stamped.model_copy(update={"portfolio_note": _replay_note(lang), "used_llm": False})


def _proposal(lang: str, *, contract_id: str, bucket: DeltaBucket, why: str) -> DeskOutput:
    return DeskOutput(
        decisions=[
            TickerDecision(
                ticker=_TICKER,
                action=DeskAction.OPEN,
                structure=Structure.CSP,
                delta_bucket=bucket,
                contract_id=contract_id,
                assignment_ok=True,
                why=why,
            )
        ],
        portfolio_note=_L(lang, "Recorded model proposal, before rules.", "录制的模型提案，规则尚未执行。"),
        used_llm=True,
    )


def _changes(proposal: DeskOutput, stamped: DeskOutput) -> list[dict]:
    return decision_changes(proposal, stamped)


def _snapshot(
    lang: str,
    *,
    hard_skip: bool,
    low_iv: bool = False,
    standard_inside_em: bool = False,
) -> TickerSnapshot:
    standard = _bucket(
        DeltaBucket.STANDARD,
        0.20,
        170,
        _STANDARD_ID,
        mid=1.35,
        inside=standard_inside_em,
        distance=0.0556,
    )
    conservative = _bucket(
        DeltaBucket.CONSERVATIVE,
        0.11,
        155,
        _CONSERVATIVE_ID,
        mid=0.72,
        inside=False,
        distance=0.1389,
    )
    reasons = ["Earnings in holding window: 2026-09-09"] if hard_skip else []
    if low_iv:
        iv = IvContext(
            atm_iv=0.22,
            hv_20=0.32,
            hv_60=0.30,
            hv_120=0.28,
            iv_hv_ratio=round(0.22 / 0.32, 4),
            regime=IvRegime.LOW,
            expected_move_pct=0.08,
            expected_move=14.4,
            expected_move_dte=7,
        )
    else:
        iv = IvContext(
            atm_iv=0.38,
            hv_20=0.36,
            hv_60=0.34,
            hv_120=0.32,
            iv_hv_ratio=round(0.38 / 0.36, 4),
            regime=IvRegime.NORMAL,
            expected_move_pct=0.08,
            expected_move=14.4,
            expected_move_dte=7,
        )
    return TickerSnapshot(
        ticker=_TICKER,
        spot=180.0,
        as_of=_AS_OF,
        fetched_at=_FETCHED,
        buckets={DeltaBucket.CONSERVATIVE: conservative, DeltaBucket.STANDARD: standard},
        calendar=CalendarGate(
            ticker=_TICKER,
            hard_skip=hard_skip,
            hard_reasons=reasons,
            earnings_dates=[date(2026, 9, 9)] if hard_skip else [],
            holding_start=_AS_OF,
            holding_end=_EXPIRY,
        ),
        mode=DeskMode.PUT,
        iv_context=iv,
        notes=[_L(lang, "Recorded chain. No live quote was requested.", "录制的期权链。没有请求实时行情。")],
    )


def _bucket(
    bucket: DeltaBucket,
    delta: float,
    strike: float,
    contract_id: str,
    *,
    mid: float,
    inside: bool,
    distance: float,
) -> BucketCandidate:
    contracts = 3
    return BucketCandidate(
        bucket=bucket,
        target_delta=delta,
        csp=ContractQuote(
            contract_id=contract_id,
            ticker=_TICKER,
            expiry=_EXPIRY,
            dte=7,
            strike=strike,
            bid=round(mid - 0.05, 2),
            ask=round(mid + 0.05, 2),
            mid=mid,
            iv=0.38,
            delta=delta,
            open_interest=900,
            volume=140,
            spread_pct=0.07,
        ),
        spread=None,
        csp_contracts=contracts,
        assignment_cash=strike * 100 * contracts,
        premium_per_contract=round(mid * 100, 2),
        score=ContractScore(
            total=58 if inside else 74,
            delta=22,
            iv=14,
            premium=12,
            spread=12,
            expected_move=4 if inside else 10,
            liquidity=8,
            strike_distance_pct=distance,
            premium_yield=round(mid / strike, 4),
            expected_move_pct=0.08,
            inside_expected_move=inside,
        ),
    )


def _quiet_market(lang: str) -> MarketRegime:
    return MarketRegime(
        label=MarketLabel.NEUTRAL,
        vix=16.4,
        vix3m=18.1,
        vix_term=1.10,
        spy=560.0,
        spy_sma20=555.0,
        spy_sma50=548.0,
        why=_L(lang, "VIX in the mid-teens and SPY above both averages.", "VIX 在十几，SPY 在两条均线上方。"),
    )


def _risk_off(lang: str) -> MarketRegime:
    return MarketRegime(
        label=MarketLabel.RISK_OFF,
        vix=32.0,
        vix3m=28.0,
        vix_term=0.875,
        spy=520.0,
        spy_sma20=540.0,
        spy_sma50=555.0,
        why=_L(lang, "VIX above 30 and SPY under the 50-day average.", "VIX 高于 30，且 SPY 在 50 日均线下方。"),
    )


def _events(lang: str) -> list[ScoutedEvent]:
    return [
        ScoutedEvent(
            title=_L(
                lang,
                "Recorded headlines have no dated catalyst",
                "录制的标题里没有带日期的催化剂",
            ),
            expected_time=None,
            tickers=[_TICKER],
            mechanism=EventMechanism.NOISE,
            already_priced=False,
            action=EventAction.IGNORE,
            sources=["https://example.com/option-desk-replay"],
            detail=_L(
                lang,
                "Replay fixture. Persistent narrative with no date.",
                "回放样本。没有日期的长期叙事。",
            ),
        )
    ]


def _hits(lang: str) -> list[SearchHit]:
    return [
        SearchHit(
            title=_L(lang, "Recorded headline (no live search)", "录制标题（没有实时搜索）"),
            url="https://example.com/option-desk-replay",
            snippet=_L(
                lang,
                "Fixture hit for the replay. Nothing here is a dated catalyst.",
                "回放用的固定命中。这里没有带日期的催化剂。",
            ),
            query=f"{_TICKER} unexpected news this week",
        )
    ]


def _localize_calendar(snap: TickerSnapshot, lang: str) -> TickerSnapshot:
    reasons = [localize_hard_reason(reason, lang) for reason in snap.calendar.hard_reasons]
    if reasons == list(snap.calendar.hard_reasons):
        return snap
    return snap.model_copy(
        update={"calendar": snap.calendar.model_copy(update={"hard_reasons": reasons})}
    )


def _hard_rule(lang: str) -> str:
    return _L(
        lang,
        "Earnings fall inside the holding window, so the hard gate rewrote OPEN to SKIP.",
        "财报落在持有窗口内，硬门控把 OPEN 改成了 SKIP。",
    )


def _replay_note(lang: str) -> str:
    return _L(
        lang,
        "Stamped by the live rule code. No market data request and no model call.",
        "由现行规则代码盖章。没有请求行情，也没有调用模型。",
    )


def _kicker(scenario: str) -> str:
    return {
        "hard-gate": "Hard gate",
        "invented-contract": "Invented contract",
        "reduce-risk": "Reduce risk",
    }[scenario]


def _title(scenario: str, lang: str) -> str:
    titles = {
        "hard-gate": _L(lang, "Hard gate", "硬门控"),
        "invented-contract": _L(lang, "Invented contract", "伪造合约"),
        "reduce-risk": _L(lang, "Reduce risk", "降风险"),
    }
    return titles[scenario]


def _summary(scenario: str, lang: str) -> str:
    summaries = {
        "hard-gate": _L(
            lang,
            "Earnings sit in the holding window. The recorded model still says OPEN. The gate leaves SKIP.",
            "持有期内有财报。录好的模型仍要开仓。门控盖章仍是 SKIP。",
        ),
        "invented-contract": _L(
            lang,
            "The recorded model names a strike that is not on the chain. The enforcer refuses the open.",
            "录好的模型写了一个链上没有的行权价。强制器拒绝开仓。",
        ),
        "reduce-risk": _L(
            lang,
            "Both buckets are real. Risk-off and cheap IV move the open from standard to conservative.",
            "两档都是真合约。risk-off 和偏便宜的 IV 把开仓从标准档改到保守档。",
        ),
    }
    return summaries[scenario]
