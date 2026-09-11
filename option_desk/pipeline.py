from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timezone

from option_desk.agents.desk import no_candidate_desk, run_desk_llm
from option_desk.agents.llm import make_llm
from option_desk.calendar.gates import evaluate_calendar
from option_desk.chain.screener import screen_ticker, uses_last_print
from option_desk.config import Settings
from option_desk.events.scout import classify_scout_hits, scout_queries
from option_desk.events.search import search_web
from option_desk.i18n import localize_hard_reason, normalize_lang, t
from option_desk.schemas import DeskMode, DeskRun, TickerSnapshot
from option_desk.stream import StreamEvent, stream_event


def _attach_calendar(snapshot: TickerSnapshot, settings: Settings) -> TickerSnapshot:
    gate = evaluate_calendar(
        snapshot.ticker,
        snapshot.as_of,
        snapshot.calendar.holding_end,
        settings,
    )
    reasons = [localize_hard_reason(reason, settings.output_language) for reason in gate.hard_reasons]
    if reasons != list(gate.hard_reasons):
        gate = gate.model_copy(update={"hard_reasons": reasons})
    return snapshot.model_copy(update={"calendar": gate})


def _dump(model) -> dict:
    return model.model_dump(mode="json")


def _screen_error_message(ticker: str, exc: BaseException, lang: str) -> str:
    blob = f"{type(exc).__name__}: {exc}"
    if "currentTradingPeriod" in blob:
        return t(lang, "screen_yahoo_meta").format(ticker=ticker)
    return t(lang, "screen_failed").format(ticker=ticker, exc=exc)


def iter_desk(
    tickers: list[str],
    as_of: date | None = None,
    settings: Settings | None = None,
) -> Iterator[StreamEvent]:
    """Yield progress events, then a final run_finished (or run_error)."""
    from option_desk.config import get_settings

    try:
        settings = settings or get_settings()
        lang = normalize_lang(settings.output_language)
        if lang != settings.output_language:
            settings = settings.model_copy(update={"output_language": lang})
        as_of = as_of or date.today()
        warnings: list[str] = []
        snapshots: list[TickerSnapshot] = []
        mode = DeskMode.CALL if str(settings.desk_mode).lower() == "call" else DeskMode.PUT
        right = "call" if mode is DeskMode.CALL else "put"

        endpoint = settings.llm_endpoint()
        llm = make_llm(settings, endpoint)
        llm_label = (
            endpoint.label() if llm else f"heuristic (no key; provider={endpoint.provider})"
        )

        yield stream_event(
            "run_started",
            message=t(lang, "pipe_run_started", tickers=", ".join(tickers)),
            tickers=tickers,
            delta=settings.standard_delta,
            cash=settings.cash,
            as_of=as_of.isoformat(),
            llm_label=llm_label,
            language=lang,
            mode=mode.value,
            shares=settings.shares if mode is DeskMode.CALL else None,
            cost_basis=settings.cost_basis if mode is DeskMode.CALL else None,
        )

        for ticker in tickers:
            yield stream_event(
                "screen_started",
                ticker=ticker,
                message=t(lang, "pipe_screen_started", ticker=ticker, right=right),
            )
            try:
                snap = screen_ticker(ticker, as_of, settings)
            except Exception as exc:
                msg = _screen_error_message(ticker, exc, lang)
                warnings.append(msg)
                yield stream_event(
                    "screen_error",
                    ticker=ticker,
                    message=msg,
                )
                continue
            last_note = t(lang, "pipe_last_print_note") if uses_last_print(snap.buckets) else ""
            yield stream_event(
                "screen_done",
                ticker=ticker,
                message=t(
                    lang,
                    "pipe_screen_done",
                    ticker=ticker,
                    spot=f"{snap.spot:.2f}",
                    n=len(snap.buckets),
                    note=last_note,
                ),
                snapshot=_dump(snap),
            )
            if not snap.buckets:
                snapshots.append(snap)
                continue
            yield stream_event(
                "calendar_started",
                ticker=ticker,
                message=t(lang, "pipe_calendar_started", ticker=ticker),
            )
            try:
                snap = _attach_calendar(snap, settings)
            except Exception as exc:
                warnings.append(t(lang, "pipe_calendar_failed", ticker=ticker, exc=exc))
                snapshots.append(snap)
                yield stream_event(
                    "calendar_done",
                    ticker=ticker,
                    message=t(lang, "pipe_calendar_failed", ticker=ticker, exc=exc),
                    calendar=_dump(snap.calendar),
                )
                continue
            snapshots.append(snap)
            cal = snap.calendar
            if cal.hard_skip:
                cal_msg = t(
                    lang,
                    "pipe_calendar_hard",
                    ticker=ticker,
                    reasons="; ".join(cal.hard_reasons) or t(lang, "pipe_calendar_gate"),
                )
            elif cal.soft_macros:
                tags = ", ".join(f"{m.kind} {m.event_date.isoformat()}" for m in cal.soft_macros)
                cal_msg = t(lang, "pipe_calendar_soft", ticker=ticker, tags=tags)
            else:
                cal_msg = t(lang, "pipe_calendar_clear", ticker=ticker)
            yield stream_event(
                "calendar_done",
                ticker=ticker,
                message=cal_msg,
                calendar=_dump(cal),
            )

        tradeable = [snap for snap in snapshots if snap.buckets]
        events = []
        if not tradeable:
            yield stream_event(
                "desk_started",
                message=t(lang, "pipe_no_candidates"),
            )
            desk = no_candidate_desk(snapshots, lang, mode=mode.value)
            yield stream_event(
                "desk_done",
                message=t(lang, "pipe_desk_skip_all"),
                desk=_dump(desk),
            )
        else:
            yield stream_event("scout_search_started", message=t(lang, "pipe_scout_search"))
            hits = []
            scout_names = [snap.ticker for snap in tradeable]
            for query in scout_queries(scout_names, as_of):
                batch = search_web(query, settings.tavily_api_key, limit=4)
                hits.extend(batch)
                yield stream_event(
                    "scout_hits",
                    message=t(lang, "pipe_scout_hits", n=len(hits)),
                    query=query,
                    hits=[h.as_dict() for h in hits],
                )

            yield stream_event("scout_llm_started", message=t(lang, "pipe_scout_llm"))
            events, scout_warnings = classify_scout_hits(scout_names, as_of, settings, llm, hits)
            warnings.extend(scout_warnings)
            yield stream_event(
                "scout_done",
                message=t(lang, "pipe_scout_done", n=len(events)) if events else t(lang, "pipe_scout_done_empty"),
                events=[_dump(e) for e in events],
                warnings=scout_warnings,
            )

            yield stream_event("desk_started", message=t(lang, "pipe_desk_started"))
            desk = run_desk_llm(snapshots, events, settings.cash, settings, llm)
            yield stream_event(
                "desk_done",
                message=t(lang, "pipe_desk_done"),
                desk=_dump(desk),
            )

        fetched_at = snapshots[0].fetched_at if snapshots else datetime.now(timezone.utc)
        run = DeskRun(
            as_of=as_of,
            fetched_at=fetched_at,
            cash=settings.cash,
            snapshots=snapshots,
            events=events,
            desk=desk,
            warnings=warnings,
            llm_label=llm_label,
            language=lang,
            mode=mode,
            shares=settings.shares if mode is DeskMode.CALL else None,
            cost_basis=settings.cost_basis if mode is DeskMode.CALL else None,
        )
        yield stream_event(
            "run_finished",
            message=t(lang, "pipe_run_finished"),
            run=_dump(run),
        )
    except Exception as exc:
        err_lang = normalize_lang(getattr(settings, "output_language", None) if settings else None)
        yield stream_event("run_error", message=t(err_lang, "pipe_run_error", exc=exc))


def run_desk(
    tickers: list[str],
    as_of: date | None = None,
    settings: Settings | None = None,
) -> DeskRun:
    """Single entry used by the CLI and later by a web wrapper."""
    finished: DeskRun | None = None
    error: str | None = None
    for event in iter_desk(tickers, as_of=as_of, settings=settings):
        if event.type == "run_finished":
            finished = DeskRun.model_validate(event.data["run"])
        elif event.type == "run_error":
            error = event.message
    if finished is not None:
        return finished
    raise RuntimeError(error or "desk run ended without a result")
