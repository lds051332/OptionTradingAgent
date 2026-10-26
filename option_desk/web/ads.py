"""Google AdSense settings. Everything stays off until OPTION_DESK_ADSENSE_CLIENT is set."""

from __future__ import annotations

import os
import re

ADSENSE_CLIENT_ENV = "OPTION_DESK_ADSENSE_CLIENT"
ADSENSE_SLOT_ENV = "OPTION_DESK_ADSENSE_SLOT"

# Google's fixed certification authority ID for ads.txt.
GOOGLE_TAG_ID = "f08c47fec0942fa0"

_CLIENT_RE = re.compile(r"^ca-pub-\d{10,20}$")
_SLOT_RE = re.compile(r"^\d{6,20}$")


def adsense_client() -> str | None:
    value = os.environ.get(ADSENSE_CLIENT_ENV, "").strip()
    if value.startswith("pub-"):
        value = f"ca-{value}"
    return value if _CLIENT_RE.match(value) else None


def adsense_slot() -> str | None:
    value = os.environ.get(ADSENSE_SLOT_ENV, "").strip()
    return value if _SLOT_RE.match(value) else None


def ads_payload() -> dict | None:
    client = adsense_client()
    if client is None:
        return None
    return {"client": client, "slot": adsense_slot()}


def ads_txt() -> str | None:
    client = adsense_client()
    if client is None:
        return None
    publisher = client.removeprefix("ca-")
    return f"google.com, {publisher}, DIRECT, {GOOGLE_TAG_ID}\n"
