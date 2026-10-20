from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from lexbridge.api.traces import TraceLog


def test_a_trace_keeps_the_question_hash_never_the_question(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite3"
    log = TraceLog(db)

    trace_id = log.record(question="My neighbour Ravi stole my phone", status="answered",
                          act="BNS", reason="date", citations=("BNS:303",), calls=1,
                          milliseconds=812.0, cached=False)

    rows = sqlite3.connect(db).execute("SELECT * FROM traces").fetchall()
    assert len(rows) == 1 and len(trace_id) == 32
    stored = " ".join(map(str, rows[0]))
    assert "Ravi" not in stored
    assert hashlib.sha256(b"My neighbour Ravi stole my phone").hexdigest() in stored


def test_feedback_is_attached_to_its_trace(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite3"
    log = TraceLog(db)
    trace_id = log.record(question="q", status="clarify", act=None, reason="unknown",
                          citations=(), calls=1, milliseconds=1.0, cached=True)

    assert log.feedback(trace_id, helpful=False) is True
    assert log.feedback("0" * 32, helpful=True) is False
    [(helpful,)] = sqlite3.connect(db).execute("SELECT helpful FROM traces").fetchall()
    assert helpful == 0
