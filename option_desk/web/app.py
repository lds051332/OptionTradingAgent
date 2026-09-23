from __future__ import annotations

import asyncio
import os
import re
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.types import ASGIApp, Receive, Scope, Send

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
from option_desk.geoip import suggested_language
from option_desk.i18n import lang_from_headers, normalize_lang, t
from option_desk.pipeline import iter_desk
from option_desk.replay import iter_replay, list_scenarios, scenario_ids
from option_desk.positions.evaluate import (
    PositionInput,
    RuleSettings,
    evaluate_positions,
)
from option_desk.positions.market import is_us_equity_rth
from option_desk.positions.roll import collect_roll_candidates
from option_desk.schemas import ContractQuote
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


class PositionEvaluateItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    ticker: str
    strategy: Literal["CSP", "COVERED_CALL"]
    option_type: Literal["PUT", "CALL"] = Field(alias="optionType")
    expiry: date
    strike: float
    contracts: int = Field(ge=1)
    entry_premium: float = Field(alias="entryPremium", ge=0)
    assignment_ok: bool = Field(default=True, alias="assignmentOk")


class PositionRuleBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    profit_target: float = Field(default=0.75, alias="profitTarget", gt=0, le=1)
    near_expiry_dte: int = Field(default=2, alias="nearExpiryDte", ge=0, le=14)
    near_expiry_profit_target: float = Field(default=0.50, alias="nearExpiryProfitTarget", gt=0, le=1)


class EvaluateBody(BaseModel):
    positions: list[PositionEvaluateItem]
    settings: PositionRuleBody = Field(default_factory=PositionRuleBody)


class RollBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticker: str
    option_type: Literal["PUT", "CALL"] = Field(alias="optionType")
    expiry: date
    strike: float
    contracts: int = Field(ge=1)
    estimated_close_price: float | None = Field(default=None, alias="estimatedClosePrice")
    target_delta: float | None = Field(default=None, alias="targetDelta")


def _unknown_demo(lang: str) -> str:
    return "没有这条回放" if lang == "zh" else "No such replay"


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


def _one_ticker(raw: str, lang: str) -> str:
    return _normalize_tickers([raw], lang)[0]


def _contract_payload(quote: ContractQuote | None) -> dict | None:
    if quote is None:
        return None
    return quote.model_dump(mode="json")


def _evaluation_payload(item) -> dict:
    return {
        "positionId": item.position_id,
        "fetchedAt": item.fetched_at.isoformat(),
        "marketOpen": item.market_open,
        "underlyingSpot": item.underlying_spot,
        "contract": _contract_payload(item.contract),
        "estimatedClosePrice": item.estimated_close_price,
        "markPnl": item.mark_pnl,
        "estimatedClosePnl": item.estimated_close_pnl,
        "profitCapture": item.profit_capture,
        "itm": item.itm,
        "management": {
            "action": item.management.action,
            "reasons": item.management.reasons,
        },
        "warnings": item.warnings,
    }


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


# Vite already fingerprints /assets/* (Django ManifestStaticFiles / WhiteNoise equivalent).
# HTML and other unhashed public files must revalidate, or browsers keep the old entry.
HTML_CACHE_CONTROL = "no-cache, must-revalidate"
ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"


class HashedStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = ASSET_CACHE_CONTROL
        return response


class SpaCacheMiddleware:
    """Revalidate the SPA shell; hashed /assets/ may be cached forever."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if path.startswith("/api/") or path.startswith("/assets/"):
            await self.app(scope, receive, send)
            return

        async def send_with_cache(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != b"cache-control"
                ]
                headers.append((b"cache-control", HTML_CACHE_CONTROL.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cache)


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
    app.add_middleware(SpaCacheMiddleware)

    @app.get("/api/me")
    def me(request: Request) -> dict:
        settings = get_settings()
        payload = _defaults(settings)
        payload["suggested_language"] = suggested_language(request)
        return payload

    @app.get("/api/demos")
    def demos(request: Request) -> dict:
        return {"scenarios": list_scenarios(_lang(request))}

    @app.post("/api/demos/{scenario}")
    async def play_demo(scenario: str, request: Request) -> StreamingResponse:
        lang = _lang(request)
        if scenario not in scenario_ids():
            raise HTTPException(
                status_code=404,
                detail=_unknown_demo(lang),
            )

        async def stream() -> AsyncIterator[bytes]:
            for event in iter_replay(scenario, lang):
                yield event.to_sse().encode("utf-8")

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

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

    @app.post("/api/positions/evaluate")
    def evaluate_open_positions(body: EvaluateBody, request: Request) -> dict:
        lang = _lang(request)
        fetched_at = datetime.now(timezone.utc)
        market_open = is_us_equity_rth(fetched_at)
        if not body.positions:
            return {
                "evaluations": [],
                "fetchedAt": fetched_at.isoformat(),
                "marketOpen": market_open,
            }
        parsed: list[PositionInput] = []
        for item in body.positions:
            ticker = _one_ticker(item.ticker, lang)
            parsed.append(
                PositionInput(
                    id=item.id,
                    ticker=ticker,
                    strategy=item.strategy,
                    option_type=item.option_type,
                    expiry=item.expiry,
                    strike=item.strike,
                    contracts=item.contracts,
                    entry_premium=item.entry_premium,
                    assignment_ok=item.assignment_ok,
                )
            )
        rules = RuleSettings(
            profit_target=body.settings.profit_target,
            near_expiry_dte=body.settings.near_expiry_dte,
            near_expiry_profit_target=body.settings.near_expiry_profit_target,
        )
        results = evaluate_positions(parsed, rules=rules, now=fetched_at)
        return {
            "evaluations": [_evaluation_payload(item) for item in results],
            "fetchedAt": fetched_at.isoformat(),
            "marketOpen": market_open,
        }

    @app.post("/api/positions/roll-candidates")
    def roll_candidates(body: RollBody, request: Request) -> dict:
        lang = _lang(request)
        ticker = _one_ticker(body.ticker, lang)
        fetched_at = datetime.now(timezone.utc)
        market_open = is_us_equity_rth(fetched_at)
        try:
            candidates, current, _spot = collect_roll_candidates(
                ticker=ticker,
                option_type=body.option_type,
                expiry=body.expiry,
                strike=body.strike,
                contracts=body.contracts,
                estimated_close_price=body.estimated_close_price,
                target_delta=body.target_delta,
            )
        except Exception:
            return {
                "candidates": [],
                "current": None,
                "fetchedAt": fetched_at.isoformat(),
                "marketOpen": market_open,
            }
        return {
            "candidates": [
                {
                    "contract": _contract_payload(item.contract),
                    "estimatedNetPerShare": item.estimated_net_per_share,
                    "estimatedNet": item.estimated_net,
                    "recommended": item.recommended,
                }
                for item in candidates
            ],
            "current": _contract_payload(current),
            "fetchedAt": fetched_at.isoformat(),
            "marketOpen": market_open,
        }

    dist = _dist_dir()
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", HashedStaticFiles(directory=assets), name="assets")

    if dist.is_dir():

        @app.get("/{path:path}")
        def spa(path: str) -> FileResponse:
            target = (dist / path).resolve()
            if dist.resolve() not in (target, *target.parents):
                raise HTTPException(status_code=404)
            if target.is_file():
                return FileResponse(target, headers={"Cache-Control": HTML_CACHE_CONTROL})
            return FileResponse(
                dist / "index.html",
                headers={"Cache-Control": HTML_CACHE_CONTROL},
            )

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
