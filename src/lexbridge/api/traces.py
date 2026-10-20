"""A record of every answer given, for evaluation from real use, with no personal data.

The question itself is never stored: questions describe real incidents and people. Only an
HMAC-SHA256 under a server key is kept, which still shows which questions repeat, but
cannot be checked against a guessed question by whoever obtains the file without the key
(a bare hash could). This is pseudonymous, not anonymous. The rest of the row (status,
code, citations, latency) is what an offline review of the service needs.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import threading
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

# Months of traffic for a demo, and a few tens of megabytes at most.
KEEP = 100_000
_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    at TEXT NOT NULL,
    question_hmac TEXT NOT NULL,
    status TEXT NOT NULL,
    act TEXT,
    reason TEXT NOT NULL,
    citations TEXT NOT NULL,
    calls INTEGER NOT NULL,
    milliseconds REAL NOT NULL,
    cached INTEGER NOT NULL,
    helpful INTEGER
)"""


class TraceLog:
    def __init__(self, path: Path, *, key: bytes, keep: int = KEEP) -> None:
        self._key = key
        self._keep = keep
        # One connection shared by the request threads, serialised by a lock: writes are
        # a few per minute at most.
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.execute(_SCHEMA)

    def record(self, *, question: str, status: str, act: str | None, reason: str,
               citations: Sequence[str], calls: int, milliseconds: float,
               cached: bool) -> str:
        trace_id = uuid.uuid4().hex
        row = (trace_id, datetime.now(UTC).isoformat(timespec="seconds"),
               hmac.new(self._key, question.encode("utf-8"), hashlib.sha256).hexdigest(),
               status, act, reason, json.dumps(list(citations)), calls,
               round(milliseconds, 1), int(cached))
        with self._lock, self._db:
            self._db.execute("INSERT INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                             row)
            # Oldest rows go first, so a flood of requests cannot fill the disk.
            self._db.execute("DELETE FROM traces WHERE rowid <= "
                             "(SELECT MAX(rowid) FROM traces) - ?", (self._keep,))
        return trace_id

    def feedback(self, trace_id: str, *, helpful: bool) -> bool:
        """False when no answer has that trace id."""
        with self._lock, self._db:
            cursor = self._db.execute("UPDATE traces SET helpful = ? WHERE id = ?",
                                      (int(helpful), trace_id))
        return cursor.rowcount == 1
