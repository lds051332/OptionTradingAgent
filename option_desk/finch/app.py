from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import Response

from option_desk.finch.config import PATH_PREFIX, FinchConfig
from option_desk.finch.runner import Runner
from option_desk.finch.service import Overloaded, RequestRejected, TaskService
from option_desk.finch.signing import (
    MAX_CLOCK_SKEW_SECONDS,
    REQUEST_HEADERS,
    AuthError,
    agent_headers,
    verify_platform_request,
)
from option_desk.finch.store import Store

log = logging.getLogger(__name__)

MAX_BODY_BYTES = 1_048_576


def _path_with_query(request: Request) -> str:
    """The exact target Finch signed: raw path bytes plus query, untouched by routing."""
    raw = request.scope.get("raw_path") or request.url.path.encode("utf-8")
    query = request.scope.get("query_string") or b""
    path = raw.decode("latin-1")
    return f"{path}?{query.decode('latin-1')}" if query else path


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def create_finch_app(
    config: FinchConfig,
    store: Store,
    runner: Runner,
    *,
    clock: Callable[[], float] = time.time,
) -> FastAPI:
    service = TaskService(store, config, runner, clock=clock)
    app = FastAPI(title="Option Desk Finch runtime", docs_url=None, redoc_url=None, openapi_url=None)

    def signed(request: Request, status: int, body: bytes, headers: dict[str, str] | None = None) -> Response:
        auth = agent_headers(
            config.key_id,
            config.request_secret,
            request.method,
            _path_with_query(request),
            body,
            now=clock(),
        )
        return Response(
            content=body,
            status_code=status,
            media_type="application/json",
            headers={**auth, "Cache-Control": "no-store", **(headers or {})},
        )

    def reply(request: Request, status: int, payload: dict[str, Any], headers: dict[str, str] | None = None) -> Response:
        return signed(request, status, _json_bytes(payload), headers)

    async def authenticate(request: Request) -> bytes | Response:
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            return reply(request, 413, {"code": "request_too_large"})
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            return reply(request, 413, {"code": "request_too_large"})
        try:
            headers: dict[str, str] = {}
            for name in REQUEST_HEADERS:
                values = request.headers.getlist(name)
                if len(values) != 1:
                    raise AuthError("auth_headers_invalid")
                headers[name] = values[0]
            nonce, signed_at = verify_platform_request(
                key_id=config.key_id,
                secret=config.request_secret,
                method=request.method,
                path_with_query=_path_with_query(request),
                body=body,
                headers=headers,
                now=clock(),
            )
        except AuthError as exc:
            log.warning("finch auth rejected %s %s: %s", request.method, request.url.path, exc.code)
            return reply(request, 401, {"code": "auth_failed"})
        fresh = store.consume_nonce(
            config.key_id,
            nonce,
            expires_at=signed_at + MAX_CLOCK_SKEW_SECONDS + 1,
            now=int(clock()),
        )
        if not fresh:
            log.warning("finch nonce replay on %s", request.url.path)
            return reply(request, 401, {"code": "auth_failed"})
        return body

    def parse_body(body: bytes) -> Any:
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RequestRejected(400, "body_invalid") from exc

    def idempotent(request: Request, body: bytes, handler: Callable[[], tuple[int, dict[str, Any]]]) -> Response:
        """Same Idempotency-Key + same bytes replays the stored reply; different bytes is a conflict."""
        key = request.headers.get("idempotency-key", "")
        identity = f"{request.method} {_path_with_query(request)}\n{key}"
        digest = hashlib.sha256(body).hexdigest()
        if key:
            stored = store.get_reply(identity)
            if stored is not None:
                if stored.digest != digest:
                    return reply(request, 409, {"code": "idempotency_conflict"})
                return signed(request, stored.status, stored.body.encode("utf-8"))
        status, payload = handler()
        raw = _json_bytes(payload)
        if key:
            store.put_reply(identity, digest, status, raw.decode("utf-8"))
        return signed(request, status, raw)

    def guarded(request: Request, action: Callable[[], Response]) -> Response:
        try:
            return action()
        except RequestRejected as exc:
            return reply(request, exc.status, {"code": exc.code})
        except Exception:
            log.exception("finch handler failed on %s", request.url.path)
            return reply(request, 500, {"code": "internal_error"})

    @app.get(f"{PATH_PREFIX}/health")
    async def health(request: Request) -> Response:
        auth = await authenticate(request)
        if isinstance(auth, Response):
            return auth
        try:
            ready = store.ping()
        except Exception:
            log.exception("finch store unavailable")
            ready = False
        if not ready:
            return reply(request, 503, {"status": "unavailable"})
        return reply(request, 200, {"status": "ready"})

    @app.post(f"{PATH_PREFIX}/invoke")
    async def invoke(request: Request) -> Response:
        auth = await authenticate(request)
        if isinstance(auth, Response):
            return auth

        def action() -> Response:
            outcome = service.admit(parse_body(auth))
            if isinstance(outcome, Overloaded):
                return reply(
                    request,
                    429,
                    {"code": outcome.code},
                    headers={"Retry-After": str(outcome.retry_after)},
                )
            status, payload = outcome
            return reply(request, status, payload)

        return guarded(request, action)

    @app.get(f"{PATH_PREFIX}/tasks/{{merchant_task_id}}")
    async def poll(merchant_task_id: str, request: Request) -> Response:
        auth = await authenticate(request)
        if isinstance(auth, Response):
            return auth

        def action() -> Response:
            body = service.poll(merchant_task_id)
            if body is None:
                return reply(request, 404, {"code": "task_not_found"})
            return reply(request, 200, body)

        return guarded(request, action)

    @app.post(f"{PATH_PREFIX}/tasks/{{merchant_task_id}}/messages")
    async def messages(merchant_task_id: str, request: Request) -> Response:
        auth = await authenticate(request)
        if isinstance(auth, Response):
            return auth
        return guarded(
            request,
            lambda: idempotent(request, auth, lambda: (202, service.supplement(merchant_task_id, parse_body(auth)))),
        )

    @app.post(f"{PATH_PREFIX}/tasks/{{merchant_task_id}}/cancel")
    async def cancel(merchant_task_id: str, request: Request) -> Response:
        auth = await authenticate(request)
        if isinstance(auth, Response):
            return auth
        return guarded(
            request,
            lambda: idempotent(request, auth, lambda: (200, service.cancel(merchant_task_id, parse_body(auth)))),
        )

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def not_found(path: str, request: Request) -> Response:
        auth = await authenticate(request)
        if isinstance(auth, Response):
            return auth
        return reply(request, 404, {"code": "not_found"})

    return app
