from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from typing import Mapping

MAX_CLOCK_SKEW_SECONDS = 300
SIGNATURE_RE = re.compile(r"^v1=[0-9a-f]{64}$")
TIMESTAMP_RE = re.compile(r"^[+-]?[0-9]+$")
REQUEST_HEADERS = (
    "x-platform-key-id",
    "x-platform-timestamp",
    "x-platform-nonce",
    "x-platform-signature",
)


class AuthError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def canonical_string(method: str, path_with_query: str, timestamp: str, nonce: str, body: bytes) -> str:
    return "\n".join(
        (method.upper(), path_with_query, timestamp, nonce, hashlib.sha256(body).hexdigest())
    )


def sign(secret: bytes, method: str, path_with_query: str, timestamp: str, nonce: str, body: bytes) -> str:
    canonical = canonical_string(method, path_with_query, timestamp, nonce, body)
    return "v1=" + hmac.new(secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _same(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def agent_headers(
    key_id: str,
    secret: bytes,
    method: str,
    path_with_query: str,
    body: bytes,
    now: float | None = None,
) -> dict[str, str]:
    """X-Agent-* headers for a synchronous response. Canonicalized with the original request method and path."""
    timestamp = str(int(time.time() if now is None else now))
    nonce = secrets.token_hex(32)
    return {
        "X-Agent-Key-Id": key_id,
        "X-Agent-Timestamp": timestamp,
        "X-Agent-Nonce": nonce,
        "X-Agent-Signature": sign(secret, method, path_with_query, timestamp, nonce, body),
    }


def verify_platform_request(
    *,
    key_id: str,
    secret: bytes,
    method: str,
    path_with_query: str,
    body: bytes,
    headers: Mapping[str, str],
    now: float | None = None,
) -> tuple[str, int]:
    """Return (nonce, signed_at) for a valid X-Platform-* request. The caller must still consume the nonce."""
    presented_key = headers.get("x-platform-key-id", "")
    timestamp = headers.get("x-platform-timestamp", "").strip()
    nonce = headers.get("x-platform-nonce", "")
    presented = headers.get("x-platform-signature", "")
    if not (presented_key and timestamp and nonce and presented):
        raise AuthError("auth_headers_invalid")
    if not _same(presented_key, key_id):
        raise AuthError("key_id_invalid")
    if not SIGNATURE_RE.match(presented):
        raise AuthError("signature_invalid")
    if not TIMESTAMP_RE.match(timestamp) or len(nonce) > 256:
        raise AuthError("timestamp_invalid")
    signed_at = int(timestamp)
    current = int(time.time() if now is None else now)
    if abs(current - signed_at) > MAX_CLOCK_SKEW_SECONDS:
        raise AuthError("timestamp_invalid")
    if method.upper() == "GET" and body:
        raise AuthError("get_body_invalid")
    expected = sign(secret, method, path_with_query, timestamp, nonce, body)
    if not _same(expected, presented):
        raise AuthError("signature_invalid")
    return nonce, signed_at
