from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from option_desk.config import load_project_env, project_root

PATH_PREFIX = "/finch/v2"


class FinchConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class FinchConfig:
    key_id: str
    request_secret: bytes
    callback_secret: bytes
    db_path: Path
    host: str = "127.0.0.1"
    port: int = 8010
    daily_limit: int = 100
    max_concurrency: int = 1
    max_queue: int = 5
    max_tickers: int = 3
    max_input_rounds: int = 2
    poll_after_ms: int = 3000
    default_deadline_seconds: int = 600


def decode_secret(displayed: str, name: str = "secret") -> bytes:
    """finch_v2 shows each secret as 43-char Base64URL of 32 raw bytes; padded standard Base64 decodes the same."""
    raw = (displayed or "").strip()
    if not raw:
        raise FinchConfigError(f"{name} is not set")
    normalized = raw.replace("+", "-").replace("/", "_").rstrip("=")
    try:
        secret = base64.urlsafe_b64decode(normalized + "=" * (-len(normalized) % 4))
    except (binascii.Error, ValueError) as exc:
        raise FinchConfigError(f"{name} is not Base64URL") from exc
    if len(secret) != 32 or base64.urlsafe_b64encode(secret).decode("ascii").rstrip("=") != normalized:
        raise FinchConfigError(f"{name} must decode to exactly 32 bytes")
    return secret


def load_finch_env() -> None:
    """.env.finch wins over .env; real environment variables (systemd) win over both."""
    path = project_root() / ".env.finch"
    if path.exists():
        load_dotenv(path, override=False)
    load_project_env()


def _int(environ: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = (environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise FinchConfigError(f"{name} must be an integer") from exc
    if not low <= value <= high:
        raise FinchConfigError(f"{name} must be between {low} and {high}")
    return value


def load_config(environ: Mapping[str, str] | None = None) -> FinchConfig:
    env = os.environ if environ is None else environ
    key_id = (env.get("FINCH_KEY_ID") or "").strip()
    if not key_id:
        raise FinchConfigError("FINCH_KEY_ID is not set")
    db_raw = (env.get("FINCH_DB_PATH") or "").strip()
    db_path = Path(db_raw).expanduser() if db_raw else Path.home() / ".option_desk" / "finch.sqlite3"
    return FinchConfig(
        key_id=key_id,
        request_secret=decode_secret(env.get("FINCH_REQUEST_SECRET", ""), "FINCH_REQUEST_SECRET"),
        callback_secret=decode_secret(env.get("FINCH_CALLBACK_SECRET", ""), "FINCH_CALLBACK_SECRET"),
        db_path=db_path,
        host=(env.get("FINCH_HOST") or "127.0.0.1").strip(),
        port=_int(env, "FINCH_PORT", 8010, 1, 65535),
        daily_limit=_int(env, "FINCH_DAILY_LIMIT", 100, 0, 100_000),
        max_concurrency=_int(env, "FINCH_MAX_CONCURRENCY", 1, 1, 4),
        max_queue=_int(env, "FINCH_MAX_QUEUE", 5, 0, 100),
        max_tickers=_int(env, "FINCH_MAX_TICKERS", 3, 1, 5),
        max_input_rounds=_int(env, "FINCH_MAX_INPUT_ROUNDS", 2, 1, 5),
        poll_after_ms=_int(env, "FINCH_POLL_AFTER_MS", 3000, 0, 60_000),
        default_deadline_seconds=_int(env, "FINCH_DEFAULT_DEADLINE_SECONDS", 600, 60, 3600),
    )
