from datetime import date, datetime, timezone

from option_desk.agents.desk import heuristic_desk
from option_desk.config import Settings
from option_desk.events.search import SearchHit
from option_desk.pipeline import iter_desk, run_desk
from option_desk.schemas import (
    BucketCandidate,
    CalendarGate,
    ContractQuote,
    DeltaBucket,
    EventAction,
    EventMechanism,
    ScoutedEvent,
    TickerSnapshot,
    DeskAction,
)


def _snap(ticker: str = "NVDA") -> TickerSnapshot:
    cid = f"{ticker}-2026-09-11-P-210"
    csp = ContractQuote(
        contract_id=cid,
        ticker=ticker,
        expiry=date(2026, 9, 11),
        dte=7,
        strike=210,
        bid=1.0,
        ask=1.1,
        mid=1.05,
        iv=0.4,
        delta=0.20,
        open_interest=100,
        volume=50,
        spread_pct=0.09,
    )
    cand = BucketCandidate(
        bucket=DeltaBucket.STANDARD,
        target_delta=0.20,
        csp=csp,
        spread=None,
        csp_contracts=2,
        assignment_cash=42000,
        premium_per_contract=105,
    )
    return TickerSnapshot(
        ticker=ticker,
        spot=217.0,
        as_of=date(2026, 9, 2),
        fetched_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        buckets={DeltaBucket.STANDARD: cand},
        calendar=CalendarGate(
            ticker=ticker,
            hard_skip=False,
            holding_start=date(2026, 9, 2),
            holding_end=date(2026, 9, 11),
        ),
    )


def _patch_pipeline(monkeypatch, snap: TickerSnapshot, events: list[ScoutedEvent]) -> None:
    monkeypatch.setattr("option_desk.pipeline.screen_ticker", lambda *a, **k: snap)
    monkeypatch.setattr("option_desk.pipeline._attach_calendar", lambda snapshot, settings: snapshot)
    monkeypatch.setattr("option_desk.pipeline.scout_queries", lambda *a, **k: ["q1", "q2"])
    monkeypatch.setattr(
        "option_desk.pipeline.search_web",
        lambda query, *a, **k: [
            SearchHit(title=query, url="https://example.test", snippet="hit", query=query)
        ],
    )
    monkeypatch.setattr(
        "option_desk.pipeline.classify_scout_hits",
        lambda *a, **k: (events, []),
    )
    monkeypatch.setattr("option_desk.pipeline.make_llm", lambda *a, **k: None)
    desk = heuristic_desk([snap], events, 55000, "zh")
    monkeypatch.setattr("option_desk.pipeline.run_desk_llm", lambda *a, **k: desk)


def test_iter_desk_event_order(monkeypatch):
    snap = _snap()
    events = [
        ScoutedEvent(
            title="NFP week",
            expected_time="2026-09-04",
            tickers=["NVDA"],
            mechanism=EventMechanism.GAP,
            action=EventAction.SPREAD_ONLY,
        )
    ]
    _patch_pipeline(monkeypatch, snap, events)
    settings = Settings(tickers="NVDA", cash=55000, output_language="zh")
    types = [
        event.type
        for event in iter_desk(["NVDA"], as_of=date(2026, 9, 2), settings=settings)
    ]
    assert types[0] == "run_started"
    assert types[-1] == "run_finished"
    for name in (
        "screen_started",
        "screen_done",
        "calendar_started",
        "calendar_done",
        "scout_search_started",
        "scout_hits",
        "scout_llm_started",
        "scout_done",
        "desk_started",
        "desk_done",
    ):
        assert name in types
    assert types.count("scout_hits") == 2


def test_run_desk_still_returns_result(monkeypatch):
    snap = _snap()
    _patch_pipeline(monkeypatch, snap, [])
    settings = Settings(tickers="NVDA", cash=55000, output_language="zh")
    run = run_desk(["NVDA"], as_of=date(2026, 9, 2), settings=settings)
    assert run.snapshots[0].ticker == "NVDA"
    assert run.desk.decisions[0].ticker == "NVDA"
    assert run.language == "zh"


def test_screen_error_continues(monkeypatch):
    snap = _snap()
    _patch_pipeline(monkeypatch, snap, [])

    def boom(*_a, **_k):
        raise ValueError("cannot convert float NaN to integer")

    monkeypatch.setattr("option_desk.pipeline.screen_ticker", boom)
    settings = Settings(tickers="NVDA", cash=55000, output_language="zh")
    types = [
        event.type
        for event in iter_desk(["NVDA"], as_of=date(2026, 9, 2), settings=settings)
    ]
    assert "screen_error" in types
    assert "run_finished" in types
    assert "screen_done" not in types
    assert "calendar_started" not in types
    assert "scout_search_started" not in types
    assert "desk_done" in types


def test_yahoo_metadata_error_is_retryable_message(monkeypatch):
    snap = _snap()
    _patch_pipeline(monkeypatch, snap, [])

    def boom(*_a, **_k):
        raise KeyError("currentTradingPeriod")

    monkeypatch.setattr("option_desk.pipeline.screen_ticker", boom)
    settings = Settings(tickers="NVDA", cash=55000, output_language="zh")
    events = list(iter_desk(["NVDA"], as_of=date(2026, 9, 2), settings=settings))
    err = next(event for event in events if event.type == "screen_error")
    assert "不一定是本机断网" in err.message
    assert "currentTradingPeriod" not in err.message or "元数据" in err.message


def test_empty_buckets_skip_calendar_scout_and_skip(monkeypatch):
    snap = _snap()
    empty = snap.model_copy(update={"buckets": {}, "notes": ["No liquid calls in DTE 3-9."]})
    _patch_pipeline(monkeypatch, empty, [])

    def boom_search(*_a, **_k):
        raise AssertionError("search_web should not run without candidates")

    def boom_classify(*_a, **_k):
        raise AssertionError("classify_scout_hits should not run without candidates")

    def boom_llm(*_a, **_k):
        raise AssertionError("run_desk_llm should not run without candidates")

    monkeypatch.setattr("option_desk.pipeline.search_web", boom_search)
    monkeypatch.setattr("option_desk.pipeline.classify_scout_hits", boom_classify)
    monkeypatch.setattr("option_desk.pipeline.run_desk_llm", boom_llm)

    settings = Settings(tickers="NVDA", cash=55000, output_language="zh", desk_mode="put")
    types = [
        event.type
        for event in iter_desk(["NVDA"], as_of=date(2026, 9, 2), settings=settings)
    ]
    assert types[0] == "run_started"
    assert types[-1] == "run_finished"
    assert "screen_done" in types
    assert "calendar_started" not in types
    assert "scout_search_started" not in types
    assert "scout_done" not in types
    assert "desk_started" in types
    assert "desk_done" in types

    run = run_desk(["NVDA"], as_of=date(2026, 9, 2), settings=settings)
    assert run.desk.used_llm is False
    assert run.desk.decisions[0].action == DeskAction.SKIP
    assert "已跳过日历与事件侦察" in run.desk.decisions[0].why
    assert "无候选档位" in run.desk.portfolio_note


def test_mixed_tickers_still_scout_tradeable(monkeypatch):
    filled = _snap("MSFT")
    empty = _snap("NVDA").model_copy(update={"buckets": {}})
    _patch_pipeline(monkeypatch, filled, [])

    def screen(ticker, *_a, **_k):
        return empty if ticker == "NVDA" else filled

    searched: list[str] = []

    def fake_queries(tickers, *_a, **_k):
        searched.extend(tickers)
        return ["q-msft"]

    monkeypatch.setattr("option_desk.pipeline.screen_ticker", screen)
    monkeypatch.setattr("option_desk.pipeline.scout_queries", fake_queries)

    settings = Settings(tickers="NVDA,MSFT", cash=55000, output_language="zh")
    types = [
        event.type
        for event in iter_desk(["NVDA", "MSFT"], as_of=date(2026, 9, 2), settings=settings)
    ]
    assert "scout_search_started" in types
    assert types.count("calendar_started") == 1
    assert searched == ["MSFT"]
