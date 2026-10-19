from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from lexbridge.eval.cases import Case, Category
from lexbridge.eval.metrics import MACRO
from lexbridge.eval.report import render, write_table
from lexbridge.eval.run import RunRecord, _latency_sample, evaluate, write_run
from lexbridge.retrieve.dense import DenseIndex
from lexbridge.schema import Act

from ..retrieve.fakes import WordsEmbedder
from .factory import build_bundle


def cases() -> list[Case]:
    return [
        Case(id="lay-snatch", category=Category.LAY, question="seizes snatching",
             offence_date=date(2024, 10, 1), answer_act=Act.BNS, targets=("BNS:304",),
             wrong_regime=("IPC:379",), needs_clarification=False),
        Case(id="lay-theft", category=Category.LAY, question="punishment for theft",
             offence_date=date(2023, 1, 1), answer_act=Act.IPC, targets=("IPC:379",),
             wrong_regime=("BNS:303",), needs_clarification=False),
        Case(id="oos-poem", category=Category.OUT_OF_SCOPE, question="a poem",
             offence_date=None, answer_act=None, targets=(), wrong_regime=(),
             needs_clarification=False),
    ]


def record(tmp_path: Path, name: str) -> RunRecord:
    index = DenseIndex.build(build_bundle(tmp_path / name), WordsEmbedder())
    return {"name": name, "retriever": "dense", "embedder": "words@test", "parameters": None,
            "index_seconds": 0.0, "bundle_sections_sha256": "a" * 64,
            "golden_sha256": "b" * 64, **evaluate(index, cases())}


def test_a_run_records_scores_ranks_and_latency(tmp_path: Path) -> None:
    run = record(tmp_path, "v0-test")

    assert run["ranks"]["lay-snatch"] == 1
    # Out of scope is not a retrieval case.
    assert "oos-poem" not in run["ranks"]
    assert run["scores"]["lay"]["n"] == 2
    assert set(run["scores"]) == {"lay", MACRO}
    assert run["query_ms"]["p95"] >= run["query_ms"]["p50"] >= 0


def test_the_table_is_rebuilt_from_every_run_file(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    write_run(record(tmp_path, "v0-a"), runs)
    write_run(record(tmp_path, "v1-b"), runs)

    table = write_table(runs, tmp_path / "ablation.md").read_text(encoding="utf-8")

    rows = [line for line in table.splitlines() if line.startswith("| v")]
    assert [r.split(" | ")[0] for r in rows] == ["| v0-a", "| v1-b", "| v0-a", "| v1-b"]
    assert "Cases per category: lay 2." in table
    assert json.loads((runs / "v0-a.json").read_text(encoding="utf-8"))["name"] == "v0-a"


def test_a_missing_value_renders_as_a_dash(tmp_path: Path) -> None:
    run = record(tmp_path, "v0-a")
    run["embedder"] = None
    run["scores"][MACRO]["wrong_regime@1"] = None

    row = next(line for line in render([run]).splitlines() if line.startswith("| v0-a"))

    assert row.startswith("| v0-a | dense | - |")
    assert " | - | " in row.split("|", 3)[3]


def test_the_latency_sample_reaches_every_category() -> None:
    many = [Case(id=f"m-{n}", category=Category.MAP_IPC_TO_BNS, question=f"IPC {n}?",
                 offence_date=None, answer_act=Act.BNS, targets=("BNS:318",),
                 wrong_regime=(), needs_clarification=False) for n in range(500)]

    sample = _latency_sample([*many, *cases()])

    # A plain stride over 500 templates first would never reach the hand-written questions.
    assert {"seizes snatching", "punishment for theft", "a poem"} <= set(sample)
    assert len(sample) <= 100


def test_a_rung_decision_is_rendered_under_its_name(tmp_path: Path) -> None:
    run = record(tmp_path, "v1-b")
    run["note"] = "Not kept: no gain."

    assert "- **v1-b**: Not kept: no gain." in render([record(tmp_path, "v0-a"), run])
