from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

QUEUED = "queued"
WORKING = "working"
INPUT_REQUIRED = "input_required"
COMPLETED = "completed"
FAILED = "failed"
CANCELED = "canceled"
EXPIRED = "expired"

RUNNING = frozenset({QUEUED, WORKING})
OPEN = frozenset({QUEUED, WORKING, INPUT_REQUIRED})
TERMINAL = frozenset({COMPLETED, FAILED, CANCELED, EXPIRED})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nonces (
    key_id TEXT NOT NULL,
    nonce TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    PRIMARY KEY (key_id, nonce)
);
CREATE INDEX IF NOT EXISTS nonces_expiry ON nonces (expires_at);
CREATE TABLE IF NOT EXISTS tasks (
    merchant_task_id TEXT PRIMARY KEY,
    invocation_id TEXT NOT NULL UNIQUE,
    finch_task_id TEXT,
    status TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    language TEXT NOT NULL,
    texts TEXT NOT NULL,
    params TEXT,
    questions TEXT,
    input_rounds INTEGER NOT NULL DEFAULT 0,
    progress_percent INTEGER,
    progress_stage TEXT,
    message TEXT,
    error_code TEXT,
    error_message TEXT,
    deadline_at REAL NOT NULL,
    started_on TEXT,
    accepted TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS tasks_started_on ON tasks (started_on);
CREATE TABLE IF NOT EXISTS replies (
    identity TEXT PRIMARY KEY,
    digest TEXT NOT NULL,
    status INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""

_JSON_FIELDS = frozenset({"texts", "params", "questions"})
_COLUMNS = (
    "merchant_task_id",
    "invocation_id",
    "finch_task_id",
    "status",
    "sequence",
    "language",
    "texts",
    "params",
    "questions",
    "input_rounds",
    "progress_percent",
    "progress_stage",
    "message",
    "error_code",
    "error_message",
    "deadline_at",
    "started_on",
    "accepted",
    "created_at",
    "updated_at",
    "completed_at",
)
_MUTABLE = frozenset(_COLUMNS) - {"merchant_task_id", "invocation_id", "sequence", "created_at", "updated_at"}


@dataclass
class Task:
    merchant_task_id: str
    invocation_id: str
    status: str
    sequence: int
    language: str
    texts: list[str]
    deadline_at: float
    accepted: str
    created_at: float
    updated_at: float
    finch_task_id: str | None = None
    params: dict[str, Any] | None = None
    questions: list[dict[str, str]] | None = None
    input_rounds: int = 0
    progress_percent: int | None = None
    progress_stage: str | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_on: str | None = None
    completed_at: str | None = None


@dataclass(frozen=True)
class StoredReply:
    digest: str
    status: int
    body: str


def _encode(name: str, value: Any) -> Any:
    if name in _JSON_FIELDS and value is not None:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def _row_to_task(row: sqlite3.Row) -> Task:
    values = {name: row[name] for name in _COLUMNS}
    for name in _JSON_FIELDS:
        if values[name] is not None:
            values[name] = json.loads(values[name])
    return Task(**values)


class Store:
    """SQLite state shared by request handlers and the desk worker. One connection, one lock."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=NORMAL")
            self._db.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def ping(self) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1").fetchone()[0] == 1

    def consume_nonce(self, key_id: str, nonce: str, *, expires_at: int, now: int) -> bool:
        with self._lock:
            self._db.execute("DELETE FROM nonces WHERE expires_at < ?", (now,))
            cursor = self._db.execute(
                "INSERT OR IGNORE INTO nonces (key_id, nonce, expires_at) VALUES (?, ?, ?)",
                (key_id, nonce, expires_at),
            )
            return cursor.rowcount == 1

    def insert_task(self, task: Task) -> bool:
        """False when the invocation already has a task; the caller replays the stored receipt."""
        placeholders = ", ".join("?" for _ in _COLUMNS)
        values = tuple(_encode(name, getattr(task, name)) for name in _COLUMNS)
        with self._lock:
            try:
                self._db.execute(
                    f"INSERT INTO tasks ({', '.join(_COLUMNS)}) VALUES ({placeholders})",
                    values,
                )
            except sqlite3.IntegrityError:
                return False
            return True

    def get_task(self, merchant_task_id: str) -> Task | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM tasks WHERE merchant_task_id = ?", (merchant_task_id,)
            ).fetchone()
        return _row_to_task(row) if row else None

    def get_by_invocation(self, invocation_id: str) -> Task | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM tasks WHERE invocation_id = ?", (invocation_id,)
            ).fetchone()
        return _row_to_task(row) if row else None

    def transition(self, merchant_task_id: str, allowed: frozenset[str] | set[str], **fields: Any) -> Task | None:
        """Update fields and bump sequence only while the task is still in an allowed status."""
        unknown = set(fields) - _MUTABLE
        if unknown:
            raise ValueError(f"not updatable: {sorted(unknown)}")
        assignments = ", ".join(f"{name} = ?" for name in fields)
        values = [_encode(name, value) for name, value in fields.items()]
        status_marks = ", ".join("?" for _ in allowed)
        sql = (
            f"UPDATE tasks SET {assignments}{', ' if assignments else ''}"
            "sequence = sequence + 1, updated_at = ? "
            f"WHERE merchant_task_id = ? AND status IN ({status_marks})"
        )
        with self._lock:
            cursor = self._db.execute(sql, (*values, time.time(), merchant_task_id, *allowed))
            if cursor.rowcount != 1:
                return None
            row = self._db.execute(
                "SELECT * FROM tasks WHERE merchant_task_id = ?", (merchant_task_id,)
            ).fetchone()
        return _row_to_task(row)

    def count_started_on(self, day: str) -> int:
        with self._lock:
            return self._db.execute(
                "SELECT COUNT(*) FROM tasks WHERE started_on = ?", (day,)
            ).fetchone()[0]

    def count_running(self) -> int:
        with self._lock:
            return self._db.execute(
                "SELECT COUNT(*) FROM tasks WHERE status IN (?, ?)", (QUEUED, WORKING)
            ).fetchone()[0]

    def resumable_ids(self) -> list[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT merchant_task_id FROM tasks WHERE status IN (?, ?) ORDER BY created_at",
                (QUEUED, WORKING),
            ).fetchall()
        return [row[0] for row in rows]

    def get_reply(self, identity: str) -> StoredReply | None:
        with self._lock:
            row = self._db.execute(
                "SELECT digest, status, body FROM replies WHERE identity = ?", (identity,)
            ).fetchone()
        return StoredReply(row[0], row[1], row[2]) if row else None

    def put_reply(self, identity: str, digest: str, status: int, body: str) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO replies (identity, digest, status, body, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (identity, digest, status, body, time.time()),
            )

    def purge_older_than(self, seconds: float, now: float | None = None) -> None:
        cutoff = (time.time() if now is None else now) - seconds
        with self._lock:
            self._db.execute(
                f"DELETE FROM tasks WHERE updated_at < ? AND status IN ({', '.join('?' for _ in TERMINAL)})",
                (cutoff, *TERMINAL),
            )
            self._db.execute("DELETE FROM replies WHERE created_at < ?", (cutoff,))
