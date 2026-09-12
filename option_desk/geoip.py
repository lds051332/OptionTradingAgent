"""Visitor country for the first-visit UI language (China → zh, else en)."""

from __future__ import annotations

import ipaddress
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

from fastapi import Request

COUNTRY_IS_URL = "https://api.country.is"
LOOKUP_TIMEOUT = 1.2
CACHE_OK_TTL = 6 * 3600
CACHE_MISS_TTL = 10 * 60
CACHE_MAX = 4096

_CHINA_IDS = {"CN", "CHN"}
_CHINA_NAMES = {"中国", "中华人民共和国", "china"}

_MISSING = object()
_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, str | None]] = {}


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def public_ip(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return None
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return str(ip) if ip.is_global else None


def client_ip(request: Request) -> str | None:
    return parse_client_ip(request.headers, request.client.host if request.client else None)


def parse_client_ip(headers: Mapping[str, str], peer: str | None = None) -> str | None:
    """Prefer CDN / nginx-injected headers; X-Forwarded-For uses the rightmost public hop."""
    lowered = {str(key).lower(): value for key, value in headers.items()}
    for name in ("cf-connecting-ip", "true-client-ip", "x-real-ip"):
        found = public_ip(lowered.get(name))
        if found:
            return found
    forwarded = lowered.get("x-forwarded-for") or ""
    parts = [part.strip() for part in forwarded.split(",") if part.strip()]
    for part in reversed(parts):
        found = public_ip(part)
        if found:
            return found
    return public_ip(peer)


def lang_from_country(country: str | None) -> str | None:
    cid = (country or "").strip()
    if not cid:
        return None
    if cid.upper() in _CHINA_IDS or cid.lower() in _CHINA_NAMES:
        return "zh"
    return "en"


def suggested_language(request: Request) -> str | None:
    ip = client_ip(request)
    if not ip:
        return None
    return lookup_language(ip)


def lookup_language(ip: str) -> str | None:
    cached = _cache_get(ip)
    if cached is not _MISSING:
        return cached if cached in {"zh", "en"} or cached is None else None
    lang = lang_from_country(_country_is_lookup(ip))
    _cache_set(ip, lang)
    return lang


def _cache_get(ip: str) -> str | None | object:
    now = time.monotonic()
    with _cache_lock:
        item = _cache.get(ip)
        if item is None:
            return _MISSING
        expires, lang = item
        if expires <= now:
            _cache.pop(ip, None)
            return _MISSING
        return lang


def _cache_set(ip: str, lang: str | None) -> None:
    ttl = CACHE_OK_TTL if lang else CACHE_MISS_TTL
    with _cache_lock:
        if len(_cache) >= CACHE_MAX:
            _cache.clear()
        _cache[ip] = (time.monotonic() + ttl, lang)


def _country_is_lookup(ip: str) -> str | None:
    payload = _get_json(f"{COUNTRY_IS_URL}/{urllib.parse.quote(ip)}")
    if not isinstance(payload, dict):
        return None
    country = payload.get("country")
    return str(country) if country else None


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "option-desk/0.1"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=LOOKUP_TIMEOUT) as resp:
            if getattr(resp, "status", 200) >= 400:
                return None
            raw = resp.read()
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None
