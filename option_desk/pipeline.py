from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timezone

from option_desk.agents.desk import run_desk_llm
from option_desk.agents.llm import make_llm
from option_desk.calendar.gates import evaluate_calendar
from option_desk.chain.screener import screen_ticker
from option_desk.config import Settings
from option_desk.events.scout import classify_scout_hits, scout_queries
from option_desk.events.search import search_web
from option_desk.i18n import normalize_lang, t
from option_desk.schemas import DeskMode, DeskRun, TickerSnapshot
from option_desk.stream import StreamEvent, stream_event


def _attach_calendar(snapshot: TickerSnapshot, settings: Settings) -> TickerSnapshot:
    gate = evaluate_calendar(
        snapshot.ticker,
        snapshot.as_of,
        snapshot.calendar.holding_end,
        settings,
    )
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
            message=f"开始分析 {', '.join(tickers)}",
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
                message=f"正在拉取 {ticker} {right} 链并估算 Delta…",
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
            yield stream_event(
                "screen_done",
                ticker=ticker,
                message=f"{ticker} 现价 {snap.spot:.2f}，筛出 {len(snap.buckets)} 档候选",
                snapshot=_dump(snap),
            )
            yield stream_event(
                "calendar_started",
                ticker=ticker,
                message=f"正在核对 {ticker} 持有期日历（财报 / FOMC / 宏观）…",
            )
            try:
                snap = _attach_calendar(snap, settings)
            except Exception as exc:
                warnings.append(f"{ticker}: calendar failed ({exc})")
                snapshots.append(snap)
                yield stream_event(
                    "calendar_done",
                    ticker=ticker,
                    message=f"{ticker} 日历核对失败：{exc}",
                    calendar=_dump(snap.calendar),
                )
                continue
            snapshots.append(snap)
            cal = snap.calendar
            if cal.hard_skip:
                cal_msg = f"{ticker} 硬性跳过：{'; '.join(cal.hard_reasons) or '日历门控'}"
            elif cal.soft_macros:
                tags = ", ".join(f"{m.kind} {m.event_date.isoformat()}" for m in cal.soft_macros)
                cal_msg = f"{ticker} 软宏观：{tags}"
            else:
                cal_msg = f"{ticker} 持有期内无硬日历冲突"
            yield stream_event(
                "calendar_done",
                ticker=ticker,
                message=cal_msg,
                calendar=_dump(cal),
            )

        yield stream_event("scout_search_started", message="正在搜索日历外突发风险…")
        hits = []
        for query in scout_queries(tickers, as_of):
            batch = search_web(query, settings.tavily_api_key, limit=4)
            hits.extend(batch)
            yield stream_event(
                "scout_hits",
                message=f"已收集 {len(hits)} 条搜索结果",
                query=query,
                hits=[h.as_dict() for h in hits],
            )

        yield stream_event("scout_llm_started", message="正在用 LLM 分类事件…")
        events, scout_warnings = classify_scout_hits(tickers, as_of, settings, llm, hits)
        warnings.extend(scout_warnings)
        yield stream_event(
            "scout_done",
            message=f"侦察完成，{len(events)} 条事件" if events else "侦察完成，无需要跟进的事件",
            events=[_dump(e) for e in events],
            warnings=scout_warnings,
        )

        yield stream_event("desk_started", message="终审中，正在候选档位里选约…")
        desk = run_desk_llm(snapshots, events, settings.cash, settings, llm)
        yield stream_event(
            "desk_done",
            message="终审完成",
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
            message="本轮分析结束",
            run=_dump(run),
        )
    except Exception as exc:
        yield stream_event("run_error", message=f"分析中断：{exc}")


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
