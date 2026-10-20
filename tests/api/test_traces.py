from __future__ import annotations

import hashlib
import hmac
import sqlite3
from pathlib import Path

from lexbridge.api.traces import TraceLog

KEY = b"k" * 32


def record(log: TraceLog, question: str = "q") -> str:
    return log.record(question=question, status="answered", act="BNS", reason="date",
                      citations=("BNS:303",), calls=1, milliseconds=812.0, cached=False)


def test_a_trace_keeps_a_keyed_hash_of_the_question_never_the_question(
        tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite3"

    trace_id = record(TraceLog(db, key=KEY), "My neighbour Ravi stole my phone")

    rows = sqlite3.connect(db).execute("SELECT * FROM traces").fetchall()
    stored = " ".join(map(str, rows[0]))
    assert len(rows) == 1 and len(trace_id) == 32
    assert "Ravi" not in stored
    # Keyed: without the server's key, a guessed question cannot be checked against it.
    assert hashlib.sha256(b"My neighbour Ravi stole my phone").hexdigest() not in stored
    assert hmac.new(KEY, b"My neighbour Ravi stole my phone",
                    hashlib.sha256).hexdigest() in stored


def test_only_the_newest_traces_are_kept(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite3"
    log = TraceLog(db, key=KEY, keep=3)

    ids = [record(log) for _ in range(5)]

    kept = {r[0] for r in sqlite3.connect(db).execute("SELECT id FROM traces")}
    assert kept == set(ids[-3:])


def test_feedback_is_attached_to_its_trace(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite3"
    log = TraceLog(db, key=KEY)
    trace_id = record(log)

    assert log.feedback(trace_id, helpful=False) is True
    assert log.feedback("0" * 32, helpful=True) is False
    [(helpful,)] = sqlite3.connect(db).execute("SELECT helpful FROM traces").fetchall()
    assert helpful == 0
