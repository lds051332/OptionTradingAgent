import json
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from option_desk.finch.app import create_finch_app
from option_desk.finch.config import FinchConfig
from option_desk.finch.runner import Runner
from option_desk.finch.signing import sign
from option_desk.finch.store import Store
from option_desk.replay import iter_replay
from option_desk.schemas import DeskOutput, DeskRun
from option_desk.stream import stream_event

KEY_ID = "finch.agenton.00000000-0000-4000-8000-000000000000"
REQUEST_SECRET = bytes(range(32))
CALLBACK_SECRET = bytes(range(32, 64))
PREFIX = "/finch/v2"


class Desk:
    def __init__(self, client: TestClient, runner: Runner, store: Store, calls: list):
        self.client = client
        self.runner = runner
        self.store = store
        self.calls = calls

    def call(self, method, path, payload=None, *, secret=REQUEST_SECRET, timestamp=None, nonce=None, key=None, raw=None):
        body = raw if raw is not None else (b"" if payload is None else json.dumps(payload).encode())
        timestamp = str(int(time.time()) if timestamp is None else timestamp)
        nonce = nonce or uuid.uuid4().hex
        headers = {
            "X-Platform-Key-Id": KEY_ID,
            "X-Platform-Timestamp": timestamp,
            "X-Platform-Nonce": nonce,
            "X-Platform-Signature": sign(secret, method, path, timestamp, nonce, body),
            "Idempotency-Key": key or uuid.uuid4().hex,
        }
        if method == "POST":
            headers["Content-Type"] = "application/json"
        response = self.client.request(method, path, content=body if method == "POST" else None, headers=headers)
        expected = sign(
            REQUEST_SECRET,
            method,
            path,
            response.headers["X-Agent-Timestamp"],
            response.headers["X-Agent-Nonce"],
            response.content,
        )
        assert response.headers["X-Agent-Key-Id"] == KEY_ID
        assert response.headers["X-Agent-Signature"] == expected
        return response

    def invoke(self, text, *, contract_test=False, mode="task", invocation_id=None, deadline=None):
        payload = {
            "protocol_version": "2.0",
            "invocation_id": invocation_id or str(uuid.uuid4()),
            "dispatch_id": str(uuid.uuid4()),
            "service_version_id": str(uuid.uuid4()),
            "offer_id": str(uuid.uuid4()),
            "offer_revision": 1,
            "interaction_mode": mode,
            "quantity": "1",
            "terms_hash": "0x" + "a" * 64,
            "request_hash": "0x" + "b" * 64,
            "limits": {
                "deadline_at": (deadline or datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
            },
            "callback": {"url": "https://finch.example/callbacks/x", "callback_key_id": KEY_ID},
            "input": {"content": [{"type": "text", "text": text}], "parameters": {"contract_test": contract_test}},
            "output_contract": {
                "artifacts": {
                    "min_items": 0,
                    "max_items": 0,
                    "allowed_media_types": ["text/plain"],
                    "max_bytes_per_asset": 0,
                    "max_total_bytes": 0,
                }
            },
            "artifact_uploads": [],
        }
        return self.call("POST", f"{PREFIX}/invoke", payload)

    def poll(self, task_id):
        return self.call("GET", f"{PREFIX}/tasks/{task_id}")

    def answer(self, task_id, text, key=None):
        payload = {
            "protocol_version": "2.0",
            "task_id": str(uuid.uuid5(uuid.NAMESPACE_URL, task_id)),
            "message": {"role": "user", "content": [{"type": "text", "text": text}]},
        }
        return self.call("POST", f"{PREFIX}/tasks/{task_id}/messages", payload, key=key)

    def cancel(self, task_id):
        return self.call(
            "POST", f"{PREFIX}/tasks/{task_id}/cancel", {"protocol_version": "2.0", "reason": "user_requested"}
        )


def _no_nulls(value):
    if isinstance(value, dict):
        return all(v is not None and _no_nulls(v) for v in value.values())
    if isinstance(value, list):
        return all(_no_nulls(v) for v in value)
    return True


@pytest.fixture
def make_desk(tmp_path, monkeypatch):
    stores = []

    def build(pipeline=None, **overrides):
        config = FinchConfig(
            key_id=KEY_ID,
            request_secret=REQUEST_SECRET,
            callback_secret=CALLBACK_SECRET,
            db_path=tmp_path / f"finch-{len(stores)}.sqlite3",
            **overrides,
        )
        calls = []

        def replay_pipeline(tickers, as_of=None, settings=None):
            calls.append({"tickers": tickers, "settings": settings})
            yield from iter_replay("reduce-risk", settings.output_language)

        store = Store(config.db_path)
        stores.append(store)
        runner = Runner(store, config, pipeline=pipeline or replay_pipeline)
        client = TestClient(create_finch_app(config, store, runner))
        return Desk(client, runner, store, calls)

    yield build
    for store in stores:
        store.close()


def test_signed_health(make_desk):
    desk = make_desk()
    response = desk.call("GET", f"{PREFIX}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_bad_signature_is_rejected_and_still_signed(make_desk):
    desk = make_desk()
    response = desk.call("GET", f"{PREFIX}/health", secret=bytes(32))
    assert response.status_code == 401
    assert response.json() == {"code": "auth_failed"}


def test_stale_timestamp_and_nonce_replay_are_rejected(make_desk):
    desk = make_desk()
    assert desk.call("GET", f"{PREFIX}/health", timestamp=int(time.time()) - 400).status_code == 401
    assert desk.call("GET", f"{PREFIX}/health", nonce="same-nonce").status_code == 200
    assert desk.call("GET", f"{PREFIX}/health", nonce="same-nonce").status_code == 401


def test_contract_test_completes_with_capabilities_and_no_pipeline(make_desk):
    desk = make_desk()
    accepted = desk.invoke("Describe your capabilities.", contract_test=True)
    assert accepted.status_code == 202
    receipt = accepted.json()
    assert receipt["status"] == "accepted" and receipt["protocol_version"] == "2.0"
    assert receipt["merchant_task_id"].startswith("odt-")
    snap = desk.poll(receipt["merchant_task_id"]).json()
    assert snap["status"] == "completed"
    assert snap["merchant_task_id"] == receipt["merchant_task_id"]
    assert "invocation_id" not in snap
    assert snap["message"]["role"] == "agent"
    assert "Cash-secured puts" in snap["message"]["content"][0]["text"]
    assert snap["artifacts"] == []
    assert _no_nulls(snap)
    assert desk.calls == []


def test_duplicate_invocation_returns_the_same_receipt(make_desk):
    desk = make_desk()
    invocation_id = str(uuid.uuid4())
    first = desk.invoke("Describe your capabilities.", invocation_id=invocation_id).json()
    second = desk.invoke("Describe your capabilities.", invocation_id=invocation_id).json()
    assert first == second


def test_non_task_mode_is_rejected(make_desk):
    desk = make_desk()
    response = desk.invoke("hi", mode="conversation_turn")
    assert response.status_code == 422
    assert response.json() == {"code": "interaction_mode_unsupported"}


def test_input_required_then_answer_runs_the_desk(make_desk):
    desk = make_desk()
    task_id = desk.invoke("帮我看看").json()["merchant_task_id"]
    asked = desk.poll(task_id).json()
    assert asked["status"] == "input_required"
    assert "标的代码" in asked["questions"][0]["question"]

    reply = desk.answer(task_id, "NVDA 卖put 现金5万")
    assert reply.status_code == 202
    assert reply.json() == {"protocol_version": "2.0", "status": "accepted", "merchant_task_id": task_id}
    queued = desk.poll(task_id).json()
    assert queued["status"] == "queued"
    assert queued["sequence"] > asked["sequence"]

    desk.runner.process(task_id)
    done = desk.poll(task_id).json()
    assert done["status"] == "completed"
    assert done["sequence"] > queued["sequence"]
    text = done["message"]["content"][0]["text"]
    assert "卖 Put 决策台" in text and "NVDA" in text and "不构成投资建议" in text
    settings = desk.calls[0]["settings"]
    assert desk.calls[0]["tickers"] == ["NVDA"]
    assert (settings.cash, settings.desk_mode, settings.output_language) == (50_000, "put", "zh")


def test_covered_call_request_reaches_the_pipeline_as_call_mode(make_desk):
    desk = make_desk()
    task_id = desk.invoke("Covered call on AAPL, 300 shares, cost 180").json()["merchant_task_id"]
    desk.runner.process(task_id)
    settings = desk.calls[0]["settings"]
    assert (settings.desk_mode, settings.shares, settings.cost_basis) == ("call", 300, 180)


def test_answer_idempotency(make_desk):
    desk = make_desk()
    task_id = desk.invoke("帮我看看").json()["merchant_task_id"]
    first = desk.answer(task_id, "还没想好", key="k1")
    again = desk.answer(task_id, "还没想好", key="k1")
    assert first.status_code == again.status_code == 202
    assert first.content == again.content
    assert desk.answer(task_id, "不同内容", key="k1").status_code == 409


def test_answer_when_not_waiting_is_a_conflict(make_desk):
    desk = make_desk()
    task_id = desk.invoke("NVDA 卖put 现金5万").json()["merchant_task_id"]
    response = desk.answer(task_id, "NVDA")
    assert response.status_code == 409
    assert response.json() == {"code": "task_not_awaiting_input"}


def test_input_rounds_are_bounded(make_desk):
    desk = make_desk(max_input_rounds=2)
    task_id = desk.invoke("帮我看看").json()["merchant_task_id"]
    desk.answer(task_id, "嗯")
    assert desk.poll(task_id).json()["status"] == "input_required"
    desk.answer(task_id, "还是不知道")
    snap = desk.poll(task_id).json()
    assert snap["status"] == "failed"
    assert snap["error"]["code"] == "insufficient_input"
    assert desk.calls == []


def test_cancel_stops_a_queued_task(make_desk):
    desk = make_desk()
    task_id = desk.invoke("NVDA 卖put 现金5万").json()["merchant_task_id"]
    response = desk.cancel(task_id)
    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
    desk.runner.process(task_id)
    assert desk.calls == []
    assert desk.poll(task_id).json()["status"] == "canceled"
    assert desk.cancel(task_id).status_code == 409


def test_daily_limit_refuses_before_accepting(make_desk):
    desk = make_desk(daily_limit=1)
    assert desk.invoke("NVDA 卖put 现金5万").status_code == 202
    refused = desk.invoke("MSFT 卖put 现金5万")
    assert refused.status_code == 429
    assert refused.json() == {"code": "daily_limit_reached"}
    assert int(refused.headers["Retry-After"]) >= 60
    assert desk.invoke("Describe your capabilities.", contract_test=True).status_code == 202


def test_queue_limit_refuses_before_accepting(make_desk):
    desk = make_desk(max_queue=0)
    assert desk.invoke("NVDA 卖put 现金5万").status_code == 202
    refused = desk.invoke("MSFT 卖put 现金5万")
    assert refused.status_code == 429
    assert refused.json() == {"code": "queue_full"}


def test_past_deadline_expires(make_desk):
    desk = make_desk()
    past = datetime.now(timezone.utc) - timedelta(seconds=5)
    task_id = desk.invoke("帮我看看", deadline=past).json()["merchant_task_id"]
    assert desk.poll(task_id).json()["status"] == "expired"


def test_pipeline_error_fails_without_leaking_details(make_desk):
    def broken(tickers, as_of=None, settings=None):
        yield stream_event("run_started", message="start")
        yield stream_event("run_error", message="Run interrupted: secret stack detail")

    desk = make_desk(pipeline=broken)
    task_id = desk.invoke("NVDA 卖put 现金5万").json()["merchant_task_id"]
    desk.runner.process(task_id)
    snap = desk.poll(task_id).json()
    assert snap["status"] == "failed"
    assert snap["error"]["code"] == "analysis_failed"
    assert "secret" not in json.dumps(snap)


def test_rate_limited_market_data_fails_instead_of_an_empty_report(make_desk):
    def rate_limited(tickers, as_of=None, settings=None):
        run = DeskRun(
            as_of=date.today(),
            fetched_at=datetime.now(timezone.utc),
            cash=50_000,
            snapshots=[],
            events=[],
            desk=DeskOutput(decisions=[]),
            warnings=["NVDA: screen failed (Too Many Requests. Rate limited. Try after a while.)"],
            language=settings.output_language,
        )
        yield stream_event("run_finished", run=run.model_dump(mode="json"))

    desk = make_desk(pipeline=rate_limited)
    task_id = desk.invoke("NVDA 卖put 现金5万").json()["merchant_task_id"]
    desk.runner.process(task_id)
    snap = desk.poll(task_id).json()
    assert snap["status"] == "failed"
    assert snap["error"] == {"code": "market_data_unavailable", "message": "行情数据源暂时限流，请几分钟后再试。"}


def test_unknown_task_and_route_are_signed_404(make_desk):
    desk = make_desk()
    assert desk.poll("odt-missing").status_code == 404
    assert desk.call("GET", f"{PREFIX}/nope").status_code == 404


def test_invalid_json_is_rejected(make_desk):
    desk = make_desk()
    response = desk.call("POST", f"{PREFIX}/invoke", raw=b"{not json")
    assert response.status_code == 400
    assert response.json() == {"code": "body_invalid"}


def test_restart_resumes_queued_tasks(make_desk):
    desk = make_desk()
    task_id = desk.invoke("NVDA 卖put 现金5万").json()["merchant_task_id"]
    assert desk.store.resumable_ids() == [task_id]
