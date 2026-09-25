from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from option_desk.config import MAX_RUN_DELTA, MIN_RUN_DELTA
from option_desk.finch.config import FinchConfig
from option_desk.finch.parse import ParseResult, detect_language, is_capability_probe, parse_texts
from option_desk.finch.render import render_capabilities
from option_desk.finch.runner import Runner, utc_stamp
from option_desk.finch.store import (
    CANCELED,
    COMPLETED,
    EXPIRED,
    FAILED,
    INPUT_REQUIRED,
    OPEN,
    QUEUED,
    RUNNING,
    TERMINAL,
    Store,
    Task,
)
from option_desk.finch.text import ft

log = logging.getLogger(__name__)

PROTOCOL_VERSION = "2.0"
QUESTION_ID = "desk_inputs"


class RequestRejected(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


@dataclass(frozen=True)
class Overloaded:
    code: str
    retry_after: int


def _local_day(ts: float) -> str:
    return datetime.fromtimestamp(ts).date().isoformat()


def _seconds_to_local_midnight(ts: float) -> int:
    now = datetime.fromtimestamp(ts)
    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    return max(60, int((tomorrow - now).total_seconds()))


def _text_of(content: Any) -> str:
    if not isinstance(content, list) or not 1 <= len(content) <= 100:
        raise RequestRejected(422, "input_content_invalid")
    parts: list[str] = []
    for part in content:
        if not isinstance(part, dict) or not isinstance(part.get("type"), str):
            raise RequestRejected(422, "input_content_invalid")
        if part["type"] == "text":
            if not isinstance(part.get("text"), str):
                raise RequestRejected(422, "input_content_invalid")
            parts.append(part["text"])
    return "\n".join(parts).strip()[:10_000]


def _parse_deadline(limits: Any, now: float, default_seconds: int) -> float:
    raw = limits.get("deadline_at") if isinstance(limits, dict) else None
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError as exc:
            raise RequestRejected(422, "deadline_invalid") from exc
    return now + default_seconds


def merchant_task_id_for(invocation_id: str) -> str:
    return "odt-" + hashlib.sha256(invocation_id.encode("utf-8")).hexdigest()[:24]


def question_text(result: ParseResult, max_tickers: int) -> str:
    lang = result.request.language
    lines = [ft(lang, "ask_intro")]
    labels = {
        "tickers": ft(lang, "ask_tickers", n=max_tickers),
        "cash": ft(lang, "ask_cash"),
        "shares": ft(lang, "ask_shares"),
        "cost_basis": ft(lang, "ask_cost"),
    }
    lines.extend(labels[name] for name in result.missing)
    problems = {
        "delta": ft(lang, "problem_delta", lo=MIN_RUN_DELTA, hi=MAX_RUN_DELTA),
        "cash": ft(lang, "problem_cash"),
        "shares": ft(lang, "problem_shares"),
        "cost_basis": ft(lang, "problem_cost"),
    }
    lines.extend(problems[name] for name in result.problems)
    if result.request.mode == "put":
        lines.append(ft(lang, "ask_mode"))
    lines.append(ft(lang, "ask_example"))
    return "\n".join(lines)


def snapshot(task: Task) -> dict[str, Any]:
    """Poll body. finch_v2 wants no invocation_id here and no null-valued optional fields."""
    body: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "merchant_task_id": task.merchant_task_id,
        "status": task.status,
        "sequence": task.sequence,
    }
    if task.status in RUNNING:
        body["progress"] = {
            "percent": int(task.progress_percent or 0),
            "stage": task.progress_stage or ft(task.language, "stage_queued"),
        }
    elif task.status == INPUT_REQUIRED:
        body["questions"] = task.questions or []
    elif task.status == COMPLETED:
        if task.completed_at:
            body["completed_at"] = task.completed_at
        body["message"] = {"role": "agent", "content": [{"type": "text", "text": task.message or ""}]}
        body["artifacts"] = []
    elif task.status == FAILED and task.error_code:
        error = {"code": task.error_code}
        if task.error_message:
            error["message"] = task.error_message
        body["error"] = error
    return body


class TaskService:
    def __init__(
        self,
        store: Store,
        config: FinchConfig,
        runner: Runner,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._config = config
        self._runner = runner
        self._clock = clock
        self._admission = threading.Lock()

    def _daily_exhausted(self, now: float) -> bool:
        limit = self._config.daily_limit
        return limit > 0 and self._store.count_started_on(_local_day(now)) >= limit

    def _overloaded(self, now: float) -> Overloaded | None:
        if self._daily_exhausted(now):
            return Overloaded("daily_limit_reached", _seconds_to_local_midnight(now))
        if self._store.count_running() >= self._config.max_concurrency + self._config.max_queue:
            return Overloaded("queue_full", 60)
        return None

    def admit(self, payload: Any) -> tuple[int, dict[str, Any]] | Overloaded:
        """Validate a finch_v2 P2 dispatch and persist the task before the 202 receipt goes out."""
        if not isinstance(payload, dict) or payload.get("protocol_version") != PROTOCOL_VERSION:
            raise RequestRejected(422, "protocol_version_invalid")
        invocation_id = payload.get("invocation_id")
        if not isinstance(invocation_id, str):
            raise RequestRejected(422, "invocation_id_invalid")
        try:
            uuid.UUID(invocation_id)
        except ValueError as exc:
            raise RequestRejected(422, "invocation_id_invalid") from exc
        existing = self._store.get_by_invocation(invocation_id)
        if existing is not None:
            return 202, json.loads(existing.accepted)
        if payload.get("interaction_mode") != "task":
            raise RequestRejected(422, "interaction_mode_unsupported")
        user_input = payload.get("input")
        if not isinstance(user_input, dict):
            raise RequestRejected(422, "input_invalid")
        text = _text_of(user_input.get("content"))
        parameters = user_input.get("parameters") if isinstance(user_input.get("parameters"), dict) else {}
        contract_test = payload.get("contract_test") is True or parameters.get("contract_test") is True

        now = self._clock()
        deadline = _parse_deadline(payload.get("limits"), now, self._config.default_deadline_seconds)
        merchant_task_id = merchant_task_id_for(invocation_id)
        accepted = {
            "protocol_version": PROTOCOL_VERSION,
            "invocation_id": invocation_id,
            "status": "accepted",
            "merchant_task_id": merchant_task_id,
            "poll_after_ms": self._config.poll_after_ms,
        }
        texts = [text]
        language = detect_language(texts)
        task = Task(
            merchant_task_id=merchant_task_id,
            invocation_id=invocation_id,
            status=QUEUED,
            sequence=1,
            language=language,
            texts=texts,
            deadline_at=deadline,
            accepted=json.dumps(accepted, separators=(",", ":")),
            created_at=now,
            updated_at=now,
        )

        with self._admission:
            if contract_test or is_capability_probe(text):
                task.status = COMPLETED
                task.message = render_capabilities(language, self._config.max_tickers)
                task.progress_percent = 100
                task.completed_at = utc_stamp(now)
            else:
                result = parse_texts(texts, self._config.max_tickers)
                if result.complete:
                    busy = self._overloaded(now)
                    if busy is not None:
                        log.info("finch invocation %s refused: %s", invocation_id, busy.code)
                        return busy
                    task.params = result.request.to_dict()
                    task.started_on = _local_day(now)
                    task.progress_percent = 0
                    task.progress_stage = ft(language, "stage_queued")
                else:
                    task.status = INPUT_REQUIRED
                    task.input_rounds = 1
                    task.questions = [
                        {"id": QUESTION_ID, "question": question_text(result, self._config.max_tickers)}
                    ]
            if not self._store.insert_task(task):
                stored = self._store.get_by_invocation(invocation_id)
                return 202, json.loads(stored.accepted) if stored else accepted

        log.info(
            "finch invocation %s -> %s (%s%s)",
            invocation_id,
            merchant_task_id,
            task.status,
            ", contract test" if contract_test else "",
        )
        if task.status == QUEUED:
            self._runner.submit(merchant_task_id)
        return 202, accepted

    def poll(self, merchant_task_id: str) -> dict[str, Any] | None:
        task = self._store.get_task(merchant_task_id)
        if task is None:
            return None
        if task.status in OPEN and self._clock() > task.deadline_at:
            task = self._store.transition(merchant_task_id, OPEN, status=EXPIRED) or self._store.get_task(
                merchant_task_id
            )
        return snapshot(task)

    def supplement(self, merchant_task_id: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict) or payload.get("protocol_version") != PROTOCOL_VERSION:
            raise RequestRejected(422, "protocol_version_invalid")
        message = payload.get("message")
        if not isinstance(message, dict) or message.get("role") != "user":
            raise RequestRejected(422, "message_invalid")
        text = _text_of(message.get("content"))
        finch_task_id = payload.get("task_id") if isinstance(payload.get("task_id"), str) else None

        with self._admission:
            task = self._store.get_task(merchant_task_id)
            if task is None:
                raise RequestRejected(404, "task_not_found")
            now = self._clock()
            if task.status in OPEN and now > task.deadline_at:
                self._store.transition(merchant_task_id, OPEN, status=EXPIRED)
                raise RequestRejected(409, "task_terminal")
            if task.status in TERMINAL:
                raise RequestRejected(409, "task_terminal")
            if task.status != INPUT_REQUIRED:
                raise RequestRejected(409, "task_not_awaiting_input")

            texts = [*task.texts, text]
            result = parse_texts(texts, self._config.max_tickers)
            lang = result.request.language
            common = {"texts": texts, "language": lang, "finch_task_id": finch_task_id or task.finch_task_id}
            if not result.complete:
                if task.input_rounds >= self._config.max_input_rounds:
                    self._store.transition(
                        merchant_task_id,
                        {INPUT_REQUIRED},
                        status=FAILED,
                        error_code="insufficient_input",
                        error_message=ft(lang, "err_input"),
                        **common,
                    )
                else:
                    self._store.transition(
                        merchant_task_id,
                        {INPUT_REQUIRED},
                        input_rounds=task.input_rounds + 1,
                        questions=[{"id": QUESTION_ID, "question": question_text(result, self._config.max_tickers)}],
                        **common,
                    )
            elif self._daily_exhausted(now):
                self._store.transition(
                    merchant_task_id,
                    {INPUT_REQUIRED},
                    status=FAILED,
                    error_code="daily_limit_reached",
                    error_message=ft(lang, "err_daily"),
                    **common,
                )
            else:
                queued = self._store.transition(
                    merchant_task_id,
                    {INPUT_REQUIRED},
                    status=QUEUED,
                    params=result.request.to_dict(),
                    started_on=_local_day(now),
                    questions=None,
                    progress_percent=0,
                    progress_stage=ft(lang, "stage_queued"),
                    **common,
                )
                if queued is not None:
                    self._runner.submit(merchant_task_id)
        return {"protocol_version": PROTOCOL_VERSION, "status": "accepted", "merchant_task_id": merchant_task_id}

    def cancel(self, merchant_task_id: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict) or payload.get("protocol_version") != PROTOCOL_VERSION:
            raise RequestRejected(422, "protocol_version_invalid")
        task = self._store.get_task(merchant_task_id)
        if task is None:
            raise RequestRejected(404, "task_not_found")
        canceled = self._store.transition(merchant_task_id, OPEN, status=CANCELED)
        if canceled is None:
            raise RequestRejected(409, "task_terminal")
        log.info("finch task %s canceled", merchant_task_id)
        return {
            "protocol_version": PROTOCOL_VERSION,
            "status": "canceled",
            "merchant_task_id": merchant_task_id,
            "sequence": canceled.sequence,
        }
