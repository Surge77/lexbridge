"""The committed golden set must be exactly what the real bundle generates.

Otherwise a change to the generator, the hand cases or the corpus could ship with a
stale eval/golden.jsonl, and every score after it would be measured on questions nobody
reviewed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lexbridge.bundle import load_bundle
from lexbridge.eval.cases import read_cases
from lexbridge.eval.golden import build_golden
from lexbridge.ingest.corpus import load_correspondences, load_sections
from lexbridge.ingest.fetch import SOURCES, fetch_all, load_pins
from lexbridge.ingest.graph import build_edges
from lexbridge.ingest.package import write_bundle

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


def test_the_committed_golden_set_matches_the_real_bundle(tmp_path: Path) -> None:
    raw, pins = ROOT / "data" / "raw", load_pins(ROOT / "data" / "sources.json")
    _, failures = fetch_all(SOURCES, raw, pins=pins)
    if failures:
        pytest.fail(f"could not fetch: {sorted(failures)}")
    corpus = load_sections(raw, pins)
    rows = load_correspondences(raw, pins, corpus)
    edges = build_edges(rows, ipc=corpus["ipc"], bns=corpus["bns_current"])
    bundle = load_bundle(write_bundle(tmp_path / "v", corpus=corpus, rows=rows, edges=edges,
                                      pins=pins))

    assert build_golden(bundle) == read_cases(ROOT / "eval" / "golden.jsonl"), (
        "eval/golden.jsonl is stale: python -m lexbridge.eval.golden <bundle>")
