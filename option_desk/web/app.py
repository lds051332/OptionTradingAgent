from __future__ import annotations

import asyncio
import os
import re
import threading
from datetime import date
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from option_desk.config import (
    MAX_RUN_DELTA,
    MAX_RUN_TICKERS,
    MIN_RUN_DELTA,
    Settings,
    apply_run_overrides,
    get_settings,
    load_project_env,
    project_root,
)
from option_desk.pipeline import iter_desk
from option_desk.stream import StreamEvent
from option_desk.web.auth import (
    check_password,
    clear_session,
    issue_session,
    require_session,
)

TICKER_RE = re.compile(r"^[A-Za-z][A-Za-z.]{0,9}$")
_RUN_LOCK = threading.Lock()


class LoginBody(BaseModel):
    password: str


class RunBody(BaseModel):
    tickers: list[str] = Field(default_factory=lambda: ["NVDA", "MSFT"])
    delta: float = 0.20
    cash: float = 55000


def _normalize_tickers(raw: list[str]) -> list[str]:
    seen: list[str] = []
    for item in raw:
        symbol = item.strip().upper()
        if not symbol:
            continue
        if not TICKER_RE.match(symbol):
            raise HTTPException(status_code=422, detail=f"无效标的：{item}")
        if symbol not in seen:
            seen.append(symbol)
    if not seen:
        raise HTTPException(status_code=422, detail="至少填写一个标的")
    if len(seen) > MAX_RUN_TICKERS:
        raise HTTPException(status_code=422, detail=f"最多 {MAX_RUN_TICKERS} 个标的")
    return seen


def _validate_run(body: RunBody) -> tuple[list[str], float, float]:
    tickers = _normalize_tickers(body.tickers)
    if not MIN_RUN_DELTA <= body.delta <= MAX_RUN_DELTA:
        raise HTTPException(
            status_code=422,
            detail=f"Delta 须在 {MIN_RUN_DELTA}–{MAX_RUN_DELTA} 之间",
        )
    if body.cash < 1000 or body.cash > 10_000_000:
        raise HTTPException(status_code=422, detail="本金须在 $1,000–$10,000,000")
    return tickers, float(body.delta), float(body.cash)


def _defaults(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return {
        "ok": True,
        "tickers": settings.ticker_list(),
        "delta": settings.standard_delta,
        "cash": settings.cash,
    }


def _dist_dir() -> Path:
    return project_root() / "web" / "dist"


async def _iter_sse(
    tickers: list[str],
    delta: float,
    cash: float,
) -> AsyncIterator[bytes]:
    queue: asyncio.Queue[StreamEvent | None | BaseException] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    settings = apply_run_overrides(
        get_settings(),
        tickers=tickers,
        delta=delta,
        cash=cash,
        language="zh",
    )

    def worker() -> None:
        try:
            for event in iter_desk(tickers, as_of=date.today(), settings=settings):
                asyncio.run_coroutine_threadsafe(queue.put(event), loop).result()
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(queue.put(exc), loop).result()
        else:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()
        finally:
            _RUN_LOCK.release()

    threading.Thread(target=worker, daemon=True, name="desk-run").start()
    while True:
        item = await queue.get()
        if item is None:
            break
        if isinstance(item, BaseException):
            error = StreamEvent(type="run_error", message=f"分析中断：{item}")
            yield error.to_sse().encode("utf-8")
            break
        yield item.to_sse().encode("utf-8")


def create_app() -> FastAPI:
    load_project_env()
    app = FastAPI(title="Option Desk", docs_url=None, redoc_url=None)

    @app.post("/api/login")
    def login(body: LoginBody, response: Response) -> dict[str, bool]:
        check_password(body.password)
        issue_session(response)
        return {"ok": True}

    @app.post("/api/logout")
    def logout(response: Response) -> dict[str, bool]:
        clear_session(response)
        return {"ok": True}

    @app.get("/api/me")
    def me(request: Request) -> dict:
        require_session(request)
        return _defaults()

    @app.post("/api/runs")
    async def create_run(body: RunBody, request: Request) -> StreamingResponse:
        require_session(request)
        tickers, delta, cash = _validate_run(body)
        if not _RUN_LOCK.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="已有一轮分析在进行")

        async def stream() -> AsyncIterator[bytes]:
            async for chunk in _iter_sse(tickers, delta, cash):
                yield chunk

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
