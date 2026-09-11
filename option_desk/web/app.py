from __future__ import annotations

import asyncio
import os
import re
import threading
from datetime import date
from pathlib import Path
from typing import AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from option_desk.config import (
    MAX_RUN_DELTA,
    MAX_RUN_TICKERS,
    MIN_RUN_DELTA,
    MIN_RUN_SHARES,
    MAX_RUN_SHARES,
    Settings,
    apply_run_overrides,
    get_settings,
    load_project_env,
    project_root,
)
from option_desk.i18n import lang_from_headers, normalize_lang, t
from option_desk.pipeline import iter_desk
from option_desk.stream import StreamEvent

TICKER_RE = re.compile(r"^[A-Za-z][A-Za-z.]{0,9}$")


class RunBody(BaseModel):
    tickers: list[str] = Field(default_factory=lambda: ["NVDA", "MSFT"])
    delta: float = 0.20
    cash: float = 55000
    mode: Literal["put", "call"] = "put"
    shares: float | None = None
    cost_basis: float | None = None
    language: str | None = None


def _lang(request: Request, explicit: str | None = None) -> str:
    if explicit:
        return normalize_lang(explicit)
    return lang_from_headers(request.headers, fallback=get_settings().output_language)


def _normalize_tickers(raw: list[str], lang: str) -> list[str]:
    seen: list[str] = []
    for item in raw:
        symbol = item.strip().upper()
        if not symbol:
            continue
        if not TICKER_RE.match(symbol):
            raise HTTPException(status_code=422, detail=t(lang, "web_invalid_ticker", item=item))
        if symbol not in seen:
            seen.append(symbol)
    if not seen:
        raise HTTPException(status_code=422, detail=t(lang, "web_need_ticker"))
    if len(seen) > MAX_RUN_TICKERS:
        raise HTTPException(status_code=422, detail=t(lang, "web_too_many_tickers", n=MAX_RUN_TICKERS))
    return seen


def _validate_run(body: RunBody, lang: str) -> tuple[list[str], float, float, str, float, float]:
    tickers = _normalize_tickers(body.tickers, lang)
    if not MIN_RUN_DELTA <= body.delta <= MAX_RUN_DELTA:
        raise HTTPException(
            status_code=422,
            detail=t(lang, "web_delta_range", lo=MIN_RUN_DELTA, hi=MAX_RUN_DELTA),
        )
    mode = body.mode
    if mode == "call":
        shares = float(body.shares if body.shares is not None else 0)
        if shares < MIN_RUN_SHARES or shares > MAX_RUN_SHARES:
            raise HTTPException(
                status_code=422,
                detail=t(lang, "web_shares_range", lo=MIN_RUN_SHARES, hi=MAX_RUN_SHARES),
            )
        cost_basis = float(body.cost_basis if body.cost_basis is not None else 0)
        if cost_basis <= 0 or cost_basis > 1_000_000:
            raise HTTPException(status_code=422, detail=t(lang, "web_cost_range"))
        cash = float(body.cash)
        return tickers, float(body.delta), cash, mode, shares, cost_basis
    if body.cash < 1000 or body.cash > 10_000_000:
        raise HTTPException(status_code=422, detail=t(lang, "web_cash_range"))
    return tickers, float(body.delta), float(body.cash), "put", 100.0, 0.0


def _defaults(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return {
        "ok": True,
        "tickers": settings.ticker_list(),
        "delta": settings.standard_delta,
        "cash": settings.cash,
        "shares": settings.shares,
        "cost_basis": settings.cost_basis or None,
        "language": settings.output_language,
    }


def _dist_dir() -> Path:
    return project_root() / "web" / "dist"


async def _iter_sse(
    tickers: list[str],
    delta: float,
    cash: float,
    *,
    mode: str = "put",
    shares: float = 100,
    cost_basis: float = 0,
    language: str | None = None,
) -> AsyncIterator[bytes]:
    queue: asyncio.Queue[StreamEvent | None | BaseException] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    cancel = threading.Event()
    try:
        settings = apply_run_overrides(
            get_settings(),
            tickers=tickers,
            delta=delta,
            cash=cash,
            language=language,
            desk_mode=mode,
            shares=shares if mode == "call" else None,
            cost_basis=cost_basis if mode == "call" else None,
        )

        def push(item: StreamEvent | None | BaseException) -> bool:
            if cancel.is_set():
                return False
            try:
                asyncio.run_coroutine_threadsafe(queue.put(item), loop)
            except Exception:
                return False
            return True

        def worker() -> None:
            try:
                for event in iter_desk(tickers, as_of=date.today(), settings=settings):
                    if not push(event):
                        return
            except Exception as exc:
                push(exc)
            else:
                push(None)

        threading.Thread(target=worker, daemon=True, name="desk-run").start()
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, BaseException):
                error = StreamEvent(
                    type="run_error",
                    message=t(language or "en", "pipe_run_error", exc=item),
                )
                yield error.to_sse().encode("utf-8")
                break
            yield item.to_sse().encode("utf-8")
    finally:
        cancel.set()


def create_app() -> FastAPI:
    load_project_env()
    app = FastAPI(title="Option Desk", docs_url=None, redoc_url=None)

    @app.get("/api/me")
    def me() -> dict:
        return _defaults()

    @app.post("/api/runs")
    async def create_run(body: RunBody, request: Request) -> StreamingResponse:
        lang = _lang(request, body.language)
        tickers, delta, cash, mode, shares, cost_basis = _validate_run(body, lang)

        async def stream() -> AsyncIterator[bytes]:
            agen = _iter_sse(
                tickers,
                delta,
                cash,
                mode=mode,
                shares=shares,
                cost_basis=cost_basis,
                language=lang,
            )
            try:
                async for chunk in agen:
                    yield chunk
            finally:
                await agen.aclose()

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    dist = _dist_dir()
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    if dist.is_dir():

        @app.get("/{path:path}")
        def spa(path: str) -> FileResponse:
            target = (dist / path).resolve()
            if dist.resolve() not in (target, *target.parents):
                raise HTTPException(status_code=404)
            if target.is_file():
                return FileResponse(target)
            return FileResponse(dist / "index.html")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    load_project_env()
    host = os.environ.get("OPTION_DESK_WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("OPTION_DESK_WEB_PORT", "8000"))
    uvicorn.run(
        "option_desk.web.app:app",
        host=host,
        port=port,
        log_level="info",
    )
