from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from datetime import date, datetime, timezone

from option_desk.config import apply_run_overrides, get_settings
from option_desk.finch.config import FinchConfig
from option_desk.finch.parse import DeskRequest
from option_desk.finch.render import render_run
from option_desk.finch.store import COMPLETED, EXPIRED, FAILED, RUNNING, WORKING, Store
from option_desk.finch.text import ft
from option_desk.pipeline import iter_desk
from option_desk.schemas import DeskRun
from option_desk.stream import StreamEvent

log = logging.getLogger(__name__)

Pipeline = Callable[..., Iterator[StreamEvent]]

RATE_LIMIT_MARKERS = ("rate limit", "too many requests")


def utc_stamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Progress:
    """Map iter_desk events onto a monotonic percent + localized stage."""

    def __init__(self, request: DeskRequest) -> None:
        self._lang = request.language
        self._tickers = request.tickers or [""]
        self._last: tuple[int, str] | None = None

    def _ticker_band(self, ticker: str | None, offset: float) -> int:
        index = self._tickers.index(ticker) if ticker in self._tickers else 0
        return 15 + int(35 * (index + offset) / len(self._tickers))

    def _map(self, event: StreamEvent) -> tuple[int, str] | None:
        lang = self._lang
        if event.type == "regime_started":
            return 8, ft(lang, "stage_regime")
        if event.type == "screen_started":
            return self._ticker_band(event.ticker, 0), ft(lang, "stage_screen", ticker=event.ticker)
        if event.type == "calendar_started":
            return self._ticker_band(event.ticker, 0.5), ft(lang, "stage_calendar", ticker=event.ticker)
        if event.type == "scout_search_started":
            return 55, ft(lang, "stage_scout")
        if event.type == "scout_llm_started":
            return 68, ft(lang, "stage_classify")
        if event.type == "desk_started":
            return 80, ft(lang, "stage_desk")
        return None

    def step(self, event: StreamEvent) -> tuple[int, str] | None:
        value = self._map(event)
        if value is None or value == self._last:
            return None
        if self._last is not None and value[0] < self._last[0]:
            return None
        self._last = value
        return value


class Runner:
    """Runs admitted tasks on a small thread pool so the web desk process is never involved."""

    def __init__(
        self,
        store: Store,
        config: FinchConfig,
        *,
        pipeline: Pipeline | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._config = config
        self._pipeline = pipeline or iter_desk
        self._clock = clock
        self._queue: queue.Queue[str] = queue.Queue()

    def start(self) -> None:
        for merchant_task_id in self._store.resumable_ids():
            self._queue.put(merchant_task_id)
        for index in range(self._config.max_concurrency):
            threading.Thread(target=self._work, name=f"finch-desk-{index}", daemon=True).start()

    def submit(self, merchant_task_id: str) -> None:
        self._queue.put(merchant_task_id)

    def _work(self) -> None:
        while True:
            merchant_task_id = self._queue.get()
            try:
                self.process(merchant_task_id)
            except Exception:
                log.exception("finch task %s crashed", merchant_task_id)
                task = self._store.get_task(merchant_task_id)
                lang = task.language if task else "en"
                self._store.transition(
                    merchant_task_id,
                    RUNNING,
                    status=FAILED,
                    error_code="analysis_failed",
                    error_message=ft(lang, "err_analysis"),
                )
            finally:
                self._queue.task_done()

    def process(self, merchant_task_id: str) -> None:
        task = self._store.get_task(merchant_task_id)
        if task is None or task.status not in RUNNING:
            return
        if self._clock() > task.deadline_at:
            self._store.transition(merchant_task_id, RUNNING, status=EXPIRED)
            return
        request = DeskRequest.from_dict(task.params or {})
        lang = request.language
        started = self._store.transition(
            merchant_task_id,
            RUNNING,
            status=WORKING,
            progress_percent=5,
            progress_stage=ft(lang, "stage_starting"),
        )
        if started is None:
            return
        call = request.mode == "call"
        settings = apply_run_overrides(
            get_settings(),
            tickers=request.tickers,
            delta=request.delta,
            cash=None if call else request.cash,
            language=lang,
            desk_mode=request.mode,
            shares=request.shares if call else None,
            cost_basis=request.cost_basis if call else None,
        )
        log.info("finch task %s started: mode=%s tickers=%s", merchant_task_id, request.mode, request.tickers)
        progress = _Progress(request)
        run: DeskRun | None = None
        errored = False
        events = self._pipeline(request.tickers, as_of=date.today(), settings=settings)
        try:
            for event in events:
                current = self._store.get_task(merchant_task_id)
                if current is None or current.status != WORKING:
                    log.info("finch task %s stopped: %s", merchant_task_id, current.status if current else "gone")
                    return
                if self._clock() > current.deadline_at:
                    self._store.transition(merchant_task_id, {WORKING}, status=EXPIRED)
                    return
                if event.type == "run_finished":
                    run = DeskRun.model_validate(event.data["run"])
                elif event.type == "run_error":
                    errored = True
                    log.warning("finch task %s pipeline error: %s", merchant_task_id, event.message)
                else:
                    step = progress.step(event)
                    if step:
                        self._store.transition(
                            merchant_task_id,
                            {WORKING},
                            progress_percent=step[0],
                            progress_stage=step[1],
                        )
        finally:
            close = getattr(events, "close", None)
            if callable(close):
                close()

        if run is None or errored:
            self._store.transition(
                merchant_task_id,
                {WORKING},
                status=FAILED,
                error_code="analysis_failed",
                error_message=ft(lang, "err_analysis"),
            )
            return
        rate_limited = any(marker in warning.lower() for warning in run.warnings for marker in RATE_LIMIT_MARKERS)
        if not run.snapshots and rate_limited:
            log.warning("finch task %s: market data rate-limited for every ticker", merchant_task_id)
            self._store.transition(
                merchant_task_id,
                {WORKING},
                status=FAILED,
                error_code="market_data_unavailable",
                error_message=ft(lang, "err_data"),
            )
            return
        self._store.transition(
            merchant_task_id,
            {WORKING},
            status=COMPLETED,
            message=render_run(run, request),
            progress_percent=100,
            progress_stage=ft(lang, "stage_done"),
            completed_at=utc_stamp(self._clock()),
        )
        log.info("finch task %s completed", merchant_task_id)
