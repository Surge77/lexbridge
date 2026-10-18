from __future__ import annotations

from pathlib import Path

import pytest

from lexbridge.bundle import BundleIntegrityError, load_bundle
from lexbridge.ingest.graph import Edge, Relation
from lexbridge.ingest.package import write_bundle
from lexbridge.schema import Act, Section, Status


def section(act: Act, number: str, key: str) -> Section:
    return Section(act=act, number=number, title=f"T{number}", text=f"{number}. T.",
                   chapter=None, status=Status.IN_FORCE, source_key=key, page=1)


def build(out: Path) -> Path:
    corpus = {
        "ipc": [section(Act.IPC, "420", "ipc"), section(Act.IPC, "498A", "ipc")],
        "bns_current": [section(Act.BNS, "318", "bns_current"),
                        section(Act.BNS, "85", "bns_current"),
                        section(Act.BNS, "86", "bns_current")],
        "bns_original": [section(Act.BNS, "318", "bns_original")],
    }
    edges = [
        Edge("IPC:420", "BNS:318", Relation.REPLACED_BY, "(4)"),
        Edge("IPC:498A", "BNS:85", Relation.REPLACED_BY, ""),
        Edge("IPC:498A", "BNS:86", Relation.REPLACED_BY, ""),
        Edge("BNS:86", "BNS:85", Relation.REFERS_TO, ""),
    ]
    return write_bundle(out, corpus=corpus, rows=[], edges=edges, pins={"ipc": "a" * 64})


def test_only_the_served_texts_are_loaded(tmp_path: Path) -> None:
    bundle = load_bundle(build(tmp_path / "v1"))

    # The 2023 gazette is provenance, not a second copy of every BNS section to retrieve.
    assert sorted(s.id for s in bundle.sections) == [
        "BNS:318", "BNS:85", "BNS:86", "IPC:420", "IPC:498A"]
    assert {s.source_key for s in bundle.sections} == {"ipc", "bns_current"}
    assert bundle.section("BNS:318").source_key == "bns_current"
    assert "IPC:420" in bundle
    assert "IPC:999" not in bundle


def test_replacement_is_answerable_in_both_directions(tmp_path: Path) -> None:
    bundle = load_bundle(build(tmp_path / "v1"))

    assert bundle.replaced_by("IPC:420") == ("BNS:318",)
    assert bundle.replaced_by("IPC:498A") == ("BNS:85", "BNS:86")
    assert bundle.replaces("BNS:86") == ("IPC:498A",)
    # A cross-reference is not a replacement.
    assert bundle.replaces("BNS:85") == ("IPC:498A",)
    assert bundle.replaced_by("IPC:124A") == ()


def test_an_edited_bundle_file_is_refused(tmp_path: Path) -> None:
    root = build(tmp_path / "v1")
    sections = root / "sections.jsonl"
    sections.write_text(sections.read_text(encoding="utf-8").replace("T420", "T421"),
                        encoding="utf-8")

    with pytest.raises(BundleIntegrityError, match=r"sections\.jsonl"):
        load_bundle(root)


def test_a_manifest_without_hashes_is_refused(tmp_path: Path) -> None:
    root = build(tmp_path / "v1")
    (root / "manifest.json").write_text("{}", encoding="utf-8")

    with pytest.raises(BundleIntegrityError, match="no file hashes"):
        load_bundle(root)
