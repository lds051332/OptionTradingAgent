from __future__ import annotations

import os
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "desk_session"
COOKIE_MAX_AGE = 14 * 24 * 3600
SALT = "option-desk-web"


@dataclass(frozen=True)
class WebAuthConfig:
    password: str
    secret: str
    secure_cookie: bool


def load_web_auth() -> WebAuthConfig:
    return WebAuthConfig(
        password=(os.environ.get("OPTION_DESK_WEB_PASSWORD") or "").strip(),
        secret=(os.environ.get("OPTION_DESK_WEB_SECRET") or "dev-change-me").strip(),
        secure_cookie=os.environ.get("OPTION_DESK_WEB_SECURE_COOKIE", "").strip()
        in {"1", "true", "True", "yes"},
    )


def _signer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=SALT)


def issue_session(response: Response, cfg: WebAuthConfig | None = None) -> None:
    cfg = cfg or load_web_auth()
    token = _signer(cfg.secret).dumps({"ok": True})
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        secure=cfg.secure_cookie,
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def session_ok(request: Request, cfg: WebAuthConfig | None = None) -> bool:
    cfg = cfg or load_web_auth()
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        payload = _signer(cfg.secret).loads(token, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return bool(payload.get("ok"))


def require_session(request: Request) -> None:
    if not session_ok(request):
        raise HTTPException(status_code=401, detail="未登录")


def check_password(password: str, cfg: WebAuthConfig | None = None) -> None:
    cfg = cfg or load_web_auth()
    if not cfg.password:
        raise HTTPException(
            status_code=503,
            detail="服务器未设置 OPTION_DESK_WEB_PASSWORD",
        )
    if not secrets.compare_digest(password, cfg.password):
        raise HTTPException(status_code=401, detail="口令错误")
