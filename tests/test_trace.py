from datetime import date, datetime, timezone
from types import SimpleNamespace

from option_desk.agents.desk import trace_desk
from option_desk.agents.structured import invoke_structured_traced, structured_methods
from option_desk.config import Settings
from option_desk.events.search import SearchHit
from option_desk.pipeline import iter_desk
from option_desk.rewrite import decision_changes
from option_desk.schemas import (
    BucketCandidate,
    CalendarGate,
    ContractQuote,
    DeltaBucket,
    DeskAction,
    DeskRun,
    EventList,
    TickerSnapshot,
)


def _snap() -> TickerSnapshot:
    cid = "NVDA-2026-09-11-P-210"
    quote = ContractQuote(
        contract_id=cid,
        ticker="NVDA",
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
    return TickerSnapshot(
        ticker="NVDA",
        spot=217.0,
        as_of=date(2026, 9, 2),
        fetched_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        buckets={
            DeltaBucket.STANDARD: BucketCandidate(
                bucket=DeltaBucket.STANDARD,
                target_delta=0.20,
                csp=quote,
                spread=None,
                csp_contracts=2,
                assignment_cash=42000,
                premium_per_contract=105,
            )
        },
        calendar=CalendarGate(
            ticker="NVDA",
            hard_skip=False,
            holding_start=date(2026, 9, 2),
            holding_end=date(2026, 9, 11),
        ),
    )


class _UsageLLM:
    def __init__(self, schema_payload: dict):
        self.schema_payload = schema_payload

    def with_structured_output(self, schema, method=None, include_raw=False):
        payload = self.schema_payload

        class _Bound:
            def invoke(self, messages):
                parsed = schema.model_validate(payload)
                raw = SimpleNamespace(
                    content="{}",
                    usage_metadata={"input_tokens": 11, "output_tokens": 5},
                    response_metadata={},
                    additional_kwargs={},
                )
                if include_raw:
                    return {"raw": raw, "parsed": parsed, "parsing_error": None}
                return parsed

        return _Bound()


class _FallbackLLM:
    def with_structured_output(self, schema, method=None, include_raw=False):
        class _Bound:
            def invoke(self, messages):
                raise RuntimeError("schema rejected")

        return _Bound()

    def invoke(self, messages):
        return SimpleNamespace(
            content='{"events": []}',
            usage_metadata={},
            response_metadata={},
            additional_kwargs={},
        )


def test_traced_call_reports_usage_and_method():
    settings = Settings(tickers="NVDA", output_language="en")
    provider = settings.llm_endpoint().provider
    parsed, call = invoke_structured_traced(
        _UsageLLM(
            {
                "events": [
                    {
                        "title": "dated",
                        "expected_time": "2026-09-04",
                        "tickers": ["NVDA"],
                        "mechanism": "gap",
                        "already_priced": False,
                        "action": "ignore",
                        "sources": [],
                        "detail": "",
                    }
                ]
            }
        ),
        EventList,
        [],
        provider,
    )
    assert parsed.events[0].title == "dated"
    assert call.method == structured_methods(provider)[0]
    assert call.token_source == "usage"
    assert call.input_tokens == 11
    assert call.output_tokens == 5
    assert call.error is None


def test_json_fallback_estimates_tokens():
    _parsed, call = invoke_structured_traced(_FallbackLLM(), EventList, [], "deepseek")
    assert call.method == "json_fallback"
    assert call.token_source == "estimate"
    assert call.output_tokens and call.output_tokens > 0
    assert "json_mode" in (call.error or "")


class _JsonModeThenFunctionLLM:
    def with_structured_output(self, schema, method=None, include_raw=False):
        class _Bound:
            def invoke(self, messages):
                if method == "json_mode":
                    raise RuntimeError(
                        'Failed to parse DeskLLMResult from completion {"action": "OPEN", "ticker": "NVDA"}'
                    )
                parsed = schema.model_validate({"events": []})
                raw = SimpleNamespace(
                    content="{}",
                    usage_metadata={"input_tokens": 3, "output_tokens": 2},
                    response_metadata={},
                    additional_kwargs={},
                )
                if include_raw:
                    return {"raw": raw, "parsed": parsed, "parsing_error": None}
                return parsed

        return _Bound()


def test_later_method_drops_the_failed_completion():
    _parsed, call = invoke_structured_traced(_JsonModeThenFunctionLLM(), EventList, [], "deepseek")
    assert call.method == "function_calling"
    assert call.token_source == "usage"
    assert "json_mode" in (call.error or "")
    assert "NVDA" not in (call.error or "")
    assert "from completion" not in (call.error or "")


def test_trace_desk_without_model_is_heuristic():
    settings = Settings(tickers="NVDA", cash=55000, output_language="en")
    traced = trace_desk([_snap()], [], 55000, settings, llm=None)
    assert traced.call.method == "heuristic"
    assert traced.call.input_tokens is None
    assert traced.output.decisions[0].action == DeskAction.OPEN
    assert all(not row["changed"] for row in decision_changes(traced.proposal, traced.output))


def test_trace_desk_rejects_invented_contract():
    settings = Settings(tickers="NVDA", cash=55000, output_language="en")
    llm = _UsageLLM(
        {
            "decisions": [
                {
                    "ticker": "NVDA",
                    "action": "OPEN",
                    "structure": "CSP",
                    "delta_bucket": "standard",
                    "contract_id": "NVDA-2026-09-11-P-999",
                    "why": "invented",
                }
            ],
            "portfolio_note": "",
        }
    )
    from option_desk.schemas import DeskLLMResult

    traced = trace_desk([_snap()], [], 55000, settings, llm)
    assert traced.call.method == structured_methods(settings.llm_endpoint().provider)[0]
    assert traced.call.token_source == "usage"
    assert traced.proposal.decisions[0].contract_id == "NVDA-2026-09-11-P-999"
    assert traced.output.decisions[0].action == DeskAction.SKIP
    changed = {row["field"]: row for row in decision_changes(traced.proposal, traced.output)}
    assert changed["contract_id"]["changed"] is True
    assert changed["contract_id"]["before"] == "NVDA-2026-09-11-P-999"
    assert changed["action"]["after"] == "SKIP"


def _patch_market(monkeypatch, snap: TickerSnapshot) -> None:
    monkeypatch.setattr("option_desk.pipeline.screen_ticker", lambda *a, **k: snap)
    monkeypatch.setattr("option_desk.pipeline._attach_calendar", lambda snapshot, settings: snapshot)
    monkeypatch.setattr("option_desk.pipeline.fetch_market_regime", lambda *_a, **_k: None)
    monkeypatch.setattr("option_desk.pipeline.scout_queries", lambda *a, **k: ["recorded query"])
    monkeypatch.setattr(
        "option_desk.pipeline.search_web",
        lambda query, *a, **k: [
            SearchHit(title="hit", url="https://example.test", snippet="note", query=query)
        ],
    )


def test_pipeline_records_heuristic_call_without_a_key(monkeypatch):
    _patch_market(monkeypatch, _snap())
    monkeypatch.setattr("option_desk.pipeline.make_llm", lambda *a, **k: None)
    settings = Settings(tickers="NVDA", cash=55000, output_language="zh")
    events = list(iter_desk(["NVDA"], as_of=date(2026, 9, 2), settings=settings))
    scout = next(event for event in events if event.type == "scout_done")
    desk = next(event for event in events if event.type == "desk_done")
    finished = next(event for event in events if event.type == "run_finished")
    assert scout.data["call"]["method"] == "heuristic"
    assert desk.data["call"]["method"] == "heuristic"
    assert desk.data["call"]["input_tokens"] is None
    assert all(not row["changed"] for row in desk.data["changes"])
    run = DeskRun.model_validate(finished.data["run"])
    assert "proposal" not in finished.data["run"]
    assert run.desk.decisions[0].ticker == "NVDA"


def test_pipeline_streams_enforcer_rewrite(monkeypatch):
    snap = _snap()
    _patch_market(monkeypatch, snap)
    settings = Settings(tickers="NVDA", cash=55000, output_language="en")
    monkeypatch.setattr(
        "option_desk.pipeline.make_llm",
        lambda *a, **k: _UsageLLM(
            {
                "decisions": [
                    {
                        "ticker": "NVDA",
                        "action": "OPEN",
                        "structure": "CSP",
                        "delta_bucket": "standard",
                        "contract_id": "NVDA-2026-09-11-P-999",
                        "why": "invented",
                    }
                ],
                "portfolio_note": "from the model",
            }
        ),
    )
    monkeypatch.setattr(
        "option_desk.pipeline.classify_scout_hits",
        lambda *a, **k: ([], [], None),
    )
    events = list(iter_desk(["NVDA"], as_of=date(2026, 9, 2), settings=settings))
    desk = next(event for event in events if event.type == "desk_done")
    hits = next(event for event in events if event.type == "scout_hits")
    assert hits.data["query"] == "recorded query"
    assert desk.data["call"]["token_source"] == "usage"
    assert desk.data["proposal"]["decisions"][0]["contract_id"] == "NVDA-2026-09-11-P-999"
    assert desk.data["desk"]["decisions"][0]["action"] == "SKIP"
    changed = {row["field"]: row for row in desk.data["changes"]}
    assert changed["contract_id"]["changed"] is True
