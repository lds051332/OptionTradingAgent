from __future__ import annotations

from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage

from option_desk.agents.structured import invoke_structured
from option_desk.config import Settings, missing_llm_key_hint
from option_desk.events.search import SearchHit, search_web
from option_desk.i18n import language_instruction, t
from option_desk.schemas import EventAction, EventList, EventMechanism, ScoutedEvent


QUERY_TEMPLATES = (
    "{names} export control OR BIS OR TSMC OR NVIDIA China restriction",
    "{names} Azure OR hyperscaler AI capex cut OR cloud spending",
    "{names} antitrust OR DOJ OR lawsuit OR guidance cut",
    "this week FOMC OR CPI OR NFP OR PCE market impact {as_of}",
    "{names} earnings OR unexpected news this week",
)

GEOPOLITIC_HINTS = (
    "war",
    "invasion",
    "missile",
    "strait",
    "geopolit",
    "conflict",
    "military",
)

SYSTEM = """You extract tradable event risk for a 3-9 DTE cash-secured put desk on US mega-cap stocks.

Rules:
- Only keep events that could cause a gap or a sharp reprice during the holding window.
- Persistent narratives (AI boom, "war risk" with no dated catalyst) are noise → action=ignore, mechanism=noise.
- If expected_time is unknown AND mechanism is not a clearly dated catalyst, action must be ignore.
- Export controls, hyperscaler capex cuts, unexpected lawsuits, supply shocks: skip or reduce depending on whether they land this week.
- Do not invent dates. If a source does not give a date, expected_time is null.
- tickers must be a subset of the universe provided.
- action is exactly one of ignore, reduce, spread_only, skip.
- mechanism is exactly one of gap, repricing, noise.
"""


def _queries(tickers: list[str], as_of: date) -> list[str]:
    names = " OR ".join(tickers)
    return [template.format(names=names, as_of=as_of.isoformat()) for template in QUERY_TEMPLATES]


def _normalize(event: ScoutedEvent, universe: list[str]) -> ScoutedEvent:
    tickers = [t.upper() for t in event.tickers if t.upper() in universe]
    if not tickers:
        tickers = list(universe)
    action = event.action
    mechanism = event.mechanism
    expected = (event.expected_time or "").strip() or None
    title_l = event.title.lower()
    geo = any(h in title_l or h in event.detail.lower() for h in GEOPOLITIC_HINTS)
    if not expected:
        if mechanism == EventMechanism.NOISE or geo:
            action = EventAction.IGNORE
            mechanism = EventMechanism.NOISE
        elif action != EventAction.IGNORE and mechanism != EventMechanism.GAP:
            action = EventAction.IGNORE
            mechanism = EventMechanism.NOISE
    return event.model_copy(
        update={
            "tickers": tickers,
            "action": action,
            "mechanism": mechanism,
            "expected_time": expected,
        }
    )


def scout_queries(tickers: list[str], as_of: date) -> list[str]:
    return _queries(tickers, as_of)


def classify_scout_hits(
    tickers: list[str],
    as_of: date,
    settings: Settings,
    llm,
    hits: list[SearchHit],
) -> tuple[list[ScoutedEvent], list[str]]:
    warnings: list[str] = []
    if not hits:
        warnings.append(t(settings.output_language, "search_empty"))
        return [], warnings
    if llm is None:
        warnings.append(missing_llm_key_hint() + t(settings.output_language, "skipped_classify"))
        return [], warnings

    digest = "\n".join(
        f"- [{h.query}] {h.title} | {h.snippet} | {h.url}" for h in hits[:24]
    )
    prompt = (
        f"Universe: {', '.join(tickers)}\n"
        f"As-of date: {as_of.isoformat()}\n"
        f"Holding window: about {settings.min_dte}-{settings.max_dte} calendar days.\n\n"
        f"Search hits:\n{digest}"
    )
    try:
        parsed = invoke_structured(
            llm,
            EventList,
            [
                SystemMessage(content=SYSTEM + language_instruction(settings.output_language)),
                HumanMessage(content=prompt),
            ],
            provider=settings.llm_endpoint().provider,
        )
    except Exception as exc:
        warnings.append(t(settings.output_language, "scout_failed").format(exc=exc))
        return [], warnings
    events = [_normalize(event, tickers) for event in parsed.events]
    return events, warnings


def scout_events(
    tickers: list[str],
    as_of: date,
    settings: Settings,
    llm,
) -> tuple[list[ScoutedEvent], list[SearchHit], list[str]]:
    hits: list[SearchHit] = []
    for query in scout_queries(tickers, as_of):
        hits.extend(search_web(query, settings.tavily_api_key, limit=4))
    events, warnings = classify_scout_hits(tickers, as_of, settings, llm, hits)
    return events, hits, warnings
