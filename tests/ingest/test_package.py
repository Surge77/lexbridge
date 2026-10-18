from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lexbridge.ingest.graph import Edge, Relation
from lexbridge.ingest.mapping import Correspondence
from lexbridge.ingest.package import BUNDLE_FILES, write_bundle
from lexbridge.schema import Act, Section, Status


def section(act: Act, number: str, key: str) -> Section:
    return Section(act=act, number=number, title=f"T{number}", text=f"{number}. Text — ok.",
                   chapter="I — PRELIMINARY", status=Status.IN_FORCE, source_key=key, page=1)


CORPUS = {
    "ipc": [section(Act.IPC, "420", "ipc"), section(Act.IPC, "2", "ipc")],
    "bns_current": [section(Act.BNS, "318", "bns_current")],
}
ROWS = [Correspondence("318", "(4)", ("420",), "Cheating.", "No change.", 86)]
EDGES = [Edge("IPC:420", "BNS:318", Relation.REPLACED_BY, "(4)")]
PINS = {"ipc": "a" * 64, "bns_current": "b" * 64}


def build(out: Path) -> Path:
    return write_bundle(out, corpus=CORPUS, rows=ROWS, edges=EDGES, pins=PINS)


def test_every_bundle_file_is_written(tmp_path: Path) -> None:
    out = build(tmp_path / "v1")

    assert sorted(p.name for p in out.iterdir()) == sorted([*BUNDLE_FILES, "manifest.json"])


def test_sections_are_one_json_object_per_line_in_code_order(tmp_path: Path) -> None:
    out = build(tmp_path / "v1")

    lines = (out / "sections.jsonl").read_text(encoding="utf-8").splitlines()
    ids = [(r["source_key"], r["number"]) for r in map(json.loads, lines)]
    assert ids == [("bns_current", "318"), ("ipc", "2"), ("ipc", "420")]
    # Unicode is written as-is, so the text stays readable in the file.
    assert "—" in lines[0]


def test_the_manifest_records_pins_counts_and_a_hash_of_every_file(tmp_path: Path) -> None:
    out = build(tmp_path / "v1")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["sources"] == PINS
    assert manifest["sections"] == {"bns_current": 1, "ipc": 2}
    assert manifest["edges"] == {"replaced_by": 1}
    for name in BUNDLE_FILES:
        digest = hashlib.sha256((out / name).read_bytes()).hexdigest()
        assert manifest["files"][name] == digest


def test_two_builds_from_the_same_input_are_byte_identical(tmp_path: Path) -> None:
    first, second = build(tmp_path / "a"), build(tmp_path / "b")

    for name in [*BUNDLE_FILES, "manifest.json"]:
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_building_into_a_used_directory_is_refused(tmp_path: Path) -> None:
    # Stale files from an earlier build would sit beside a manifest that does not list them.
    out = tmp_path / "v1"
    out.mkdir()
    (out / "old.jsonl").write_text("stale\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="v1"):
        build(out)
