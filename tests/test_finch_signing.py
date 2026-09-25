import base64
import hashlib
import hmac
import os

import pytest

from option_desk.finch.config import FinchConfigError, decode_secret, load_config
from option_desk.finch.signing import AuthError, agent_headers, sign, verify_platform_request

SECRET = bytes(range(32))
NOW = 1_800_000_000


def _headers(signature: str, *, key_id: str = "finch.agenton.test", timestamp: int = NOW, nonce: str = "n1") -> dict:
    return {
        "x-platform-key-id": key_id,
        "x-platform-timestamp": str(timestamp),
        "x-platform-nonce": nonce,
        "x-platform-signature": signature,
    }


def test_sign_matches_documented_canonical_string():
    body = b'{"a":1}'
    canonical = "\n".join(("POST", "/finch/v2/invoke?x=1", str(NOW), "n1", hashlib.sha256(body).hexdigest()))
    expected = "v1=" + hmac.new(SECRET, canonical.encode(), hashlib.sha256).hexdigest()
    assert sign(SECRET, "post", "/finch/v2/invoke?x=1", str(NOW), "n1", body) == expected


def test_health_is_signed_as_get_with_empty_body():
    empty_hash = hashlib.sha256(b"").hexdigest()
    canonical = f"GET\n/finch/v2/health\n{NOW}\nn1\n{empty_hash}"
    expected = "v1=" + hmac.new(SECRET, canonical.encode(), hashlib.sha256).hexdigest()
    assert sign(SECRET, "GET", "/finch/v2/health", str(NOW), "n1", b"") == expected


def test_decode_secret_accepts_base64url_and_padded_base64():
    raw = os.urandom(32)
    displayed = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    assert len(displayed) == 43
    assert decode_secret(displayed) == raw
    assert decode_secret(base64.b64encode(raw).decode()) == raw


@pytest.mark.parametrize("value", ["", "short", base64.urlsafe_b64encode(os.urandom(31)).decode()])
def test_decode_secret_rejects_wrong_length(value):
    with pytest.raises(FinchConfigError):
        decode_secret(value)


def test_load_config_requires_key_and_secrets():
    with pytest.raises(FinchConfigError):
        load_config({})
    secret = base64.urlsafe_b64encode(SECRET).decode().rstrip("=")
    config = load_config(
        {
            "FINCH_KEY_ID": "finch.agenton.x",
            "FINCH_REQUEST_SECRET": secret,
            "FINCH_CALLBACK_SECRET": secret,
            "FINCH_DAILY_LIMIT": "7",
        }
    )
    assert config.request_secret == SECRET
    assert config.daily_limit == 7
    assert config.port == 8010


def test_verify_accepts_valid_request():
    body = b"{}"
    signature = sign(SECRET, "POST", "/finch/v2/invoke", str(NOW), "n1", body)
    nonce, signed_at = verify_platform_request(
        key_id="finch.agenton.test",
        secret=SECRET,
        method="POST",
        path_with_query="/finch/v2/invoke",
        body=body,
        headers=_headers(signature),
        now=NOW + 10,
    )
    assert (nonce, signed_at) == ("n1", NOW)


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda kw: kw.update(body=b'{"x":2}'), "signature_invalid"),
        (lambda kw: kw.update(path_with_query="/finch/v2/invoke?x=1"), "signature_invalid"),
        (lambda kw: kw.update(now=NOW + 301), "timestamp_invalid"),
        (lambda kw: kw.update(key_id="finch.agenton.other"), "key_id_invalid"),
    ],
)
def test_verify_rejects_tampering(mutate, code):
    body = b"{}"
    signature = sign(SECRET, "POST", "/finch/v2/invoke", str(NOW), "n1", body)
    kwargs = dict(
        key_id="finch.agenton.test",
        secret=SECRET,
        method="POST",
        path_with_query="/finch/v2/invoke",
        body=body,
        headers=_headers(signature),
        now=NOW,
    )
    mutate(kwargs)
    with pytest.raises(AuthError) as err:
        verify_platform_request(**kwargs)
    assert err.value.code == code


def test_verify_rejects_get_with_body_and_bad_format():
    signature = sign(SECRET, "GET", "/finch/v2/health", str(NOW), "n1", b"x")
    with pytest.raises(AuthError):
        verify_platform_request(
            key_id="finch.agenton.test",
            secret=SECRET,
            method="GET",
            path_with_query="/finch/v2/health",
            body=b"x",
            headers=_headers(signature),
            now=NOW,
        )
    with pytest.raises(AuthError):
        verify_platform_request(
            key_id="finch.agenton.test",
            secret=SECRET,
            method="GET",
            path_with_query="/finch/v2/health",
            body=b"",
            headers=_headers("v1=XYZ"),
            now=NOW,
        )


def test_agent_headers_sign_exact_response_bytes():
    body = b'{"status":"ready"}'
    headers = agent_headers("finch.agenton.test", SECRET, "GET", "/finch/v2/health", body, now=NOW)
    assert headers["X-Agent-Key-Id"] == "finch.agenton.test"
    assert headers["X-Agent-Timestamp"] == str(NOW)
    expected = sign(SECRET, "GET", "/finch/v2/health", str(NOW), headers["X-Agent-Nonce"], body)
    assert headers["X-Agent-Signature"] == expected
