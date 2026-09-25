"""Probe the Finch runtime the way Finch does, without spending an analysis unless --real is given.

  python scripts/finch_selftest.py --base https://option.xdashan.top/finch/v2
  python scripts/finch_selftest.py --base http://127.0.0.1:8010/finch/v2 --real "NVDA 卖put 现金5万"

Credentials come from FINCH_KEY_ID / FINCH_REQUEST_SECRET (environment or .env.finch).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from option_desk.finch.config import decode_secret, load_finch_env  # noqa: E402
from option_desk.finch.signing import sign  # noqa: E402

TERMINAL = {"completed", "failed", "canceled", "expired"}


class Probe:
    def __init__(self, base: str, key_id: str, secret: bytes) -> None:
        self.base = base.rstrip("/")
        self.key_id = key_id
        self.secret = secret
        host = urlsplit(self.base).hostname or ""
        handlers = [urllib.request.ProxyHandler({})] if host in {"127.0.0.1", "localhost", "::1"} else []
        self.opener = urllib.request.build_opener(*handlers)
        self.failures = 0

    def call(self, method: str, suffix: str, payload: dict | None = None, *, secret: bytes | None = None, nonce: str | None = None):
        url = self.base + suffix
        parts = urlsplit(url)
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        timestamp = str(int(time.time()))
        nonce = nonce or uuid.uuid4().hex
        headers = {
            "Accept": "application/json",
            "Idempotency-Key": uuid.uuid4().hex,
            "X-Platform-Key-Id": self.key_id,
            "X-Platform-Timestamp": timestamp,
            "X-Platform-Nonce": nonce,
            "X-Platform-Signature": sign(secret or self.secret, method, path, timestamp, nonce, body),
        }
        if method == "POST":
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body if method == "POST" else None, method=method, headers=headers)
        try:
            response = self.opener.open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            status = response.status
            got = response.headers
        expected = sign(
            self.secret, method, path, got.get("X-Agent-Timestamp", ""), got.get("X-Agent-Nonce", ""), raw
        )
        signed_ok = got.get("X-Agent-Key-Id") == self.key_id and got.get("X-Agent-Signature") == expected
        data = json.loads(raw) if raw else None
        return status, data, signed_ok

    def check(self, label: str, ok: bool, detail: object = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  -> {detail}" if not ok and detail != "" else ""))
        if not ok:
            self.failures += 1

    def invoke(self, text: str, *, contract_test: bool = False, invocation_id: str | None = None):
        return self.call(
            "POST",
            "/invoke",
            {
                "protocol_version": "2.0",
                "invocation_id": invocation_id or str(uuid.uuid4()),
                "interaction_mode": "task",
                "limits": {"deadline_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 600))},
                "input": {"content": [{"type": "text", "text": text}], "parameters": {"contract_test": contract_test}},
                "output_contract": {"artifacts": {"min_items": 0, "max_items": 0}},
                "artifact_uploads": [],
            },
        )


def wait_terminal(probe: Probe, task_id: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last_stage = None
    while True:
        _, snap, _ = probe.call("GET", f"/tasks/{task_id}")
        stage = (snap.get("progress") or {}).get("stage")
        if stage and stage != last_stage:
            print(f"      {snap['progress']['percent']:>3}%  {stage}")
            last_stage = stage
        if snap["status"] in TERMINAL or snap["status"] == "input_required" or time.monotonic() > deadline:
            return snap
        time.sleep(2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", required=True, help="Runtime base URL ending in /finch/v2")
    parser.add_argument("--real", metavar="TEXT", help="Also run one real analysis with this buyer text")
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    load_finch_env()
    key_id = os.environ.get("FINCH_KEY_ID", "").strip()
    secret = decode_secret(os.environ.get("FINCH_REQUEST_SECRET", ""), "FINCH_REQUEST_SECRET")
    probe = Probe(args.base, key_id, secret)

    status, data, signed_ok = probe.call("GET", "/health")
    probe.check("signed health returns ready", status == 200 and data == {"status": "ready"} and signed_ok, (status, data))

    status, _, _ = probe.call("GET", "/health", secret=os.urandom(32))
    probe.check("wrong secret is rejected", status == 401, status)

    nonce = uuid.uuid4().hex
    probe.call("GET", "/health", nonce=nonce)
    status, _, _ = probe.call("GET", "/health", nonce=nonce)
    probe.check("replayed nonce is rejected", status == 401, status)

    invocation_id = str(uuid.uuid4())
    status, receipt, signed_ok = probe.invoke("Describe your capabilities.", contract_test=True, invocation_id=invocation_id)
    ok = status == 202 and signed_ok and receipt.get("status") == "accepted" and receipt.get("invocation_id") == invocation_id
    probe.check("contract-test invoke is accepted (202)", ok, (status, receipt))
    if ok:
        _, again, _ = probe.invoke("Describe your capabilities.", contract_test=True, invocation_id=invocation_id)
        probe.check("duplicate invocation replays the same task", again == receipt, again)
        _, snap, signed_ok = probe.call("GET", f"/tasks/{receipt['merchant_task_id']}")
        text = ((snap.get("message") or {}).get("content") or [{}])[0].get("text", "")
        probe.check(
            "contract-test task completes with the capability text",
            snap.get("status") == "completed" and "invocation_id" not in snap and bool(text) and signed_ok,
            snap,
        )

    status, receipt, _ = probe.invoke("帮我看看")
    task_id = receipt.get("merchant_task_id") if status == 202 else None
    probe.check("request without tickers is accepted", task_id is not None, (status, receipt))
    if task_id:
        _, snap, _ = probe.call("GET", f"/tasks/{task_id}")
        probe.check("it asks for the missing inputs", snap.get("status") == "input_required" and snap.get("questions"), snap)
        status, answer, _ = probe.call(
            "POST",
            f"/tasks/{task_id}/messages",
            {
                "protocol_version": "2.0",
                "task_id": str(uuid.uuid4()),
                "message": {"role": "user", "content": [{"type": "text", "text": "还没想好"}]},
            },
        )
        probe.check("supplemental input is accepted (202)", status == 202 and answer.get("status") == "accepted", (status, answer))
        status, canceled, _ = probe.call(
            "POST", f"/tasks/{task_id}/cancel", {"protocol_version": "2.0", "reason": "user_requested"}
        )
        probe.check("cancel returns canceled", status == 200 and canceled.get("status") == "canceled", (status, canceled))

    status, _, signed_ok = probe.call("GET", "/tasks/odt-does-not-exist")
    probe.check("unknown task is a signed 404", status == 404 and signed_ok, status)

    if args.real:
        print(f"\nReal analysis: {args.real}")
        status, receipt, _ = probe.invoke(args.real)
        probe.check("real request is accepted", status == 202, (status, receipt))
        if status == 202:
            snap = wait_terminal(probe, receipt["merchant_task_id"], args.timeout)
            probe.check("real analysis completes", snap.get("status") == "completed", snap.get("status"))
            if snap.get("status") == "completed":
                print("\n" + snap["message"]["content"][0]["text"])
            elif snap.get("status") == "input_required":
                print(snap["questions"][0]["question"])

    print(f"\n{'ALL CHECKS PASSED' if probe.failures == 0 else f'{probe.failures} CHECK(S) FAILED'}")
    return 0 if probe.failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
