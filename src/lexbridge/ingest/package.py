"""Write the corpus as a versioned, reproducible bundle.

Two builds from the same pinned PDFs produce byte-identical files: records are sorted,
JSON is serialised with sorted keys, and nothing time-dependent goes inside. The bundle
directory name carries the version; the manifest pins its sources and hashes its files,
so a served answer can always be traced back to exact bytes.

Usage:
    python -m lexbridge.ingest.package v2026-10-18   # writes artifacts/v2026-10-18/
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from pathlib import Path

from lexbridge.ingest.graph import Edge
from lexbridge.ingest.mapping import Correspondence
from lexbridge.schema import Section, section_key

BUNDLE_FILES = ("sections.jsonl", "correspondences.jsonl", "edges.jsonl")


def _jsonl(path: Path, records: Iterable[Mapping[str, object]]) -> None:
    lines = (json.dumps(r, ensure_ascii=False, sort_keys=True) for r in records)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def write_bundle(
    out_dir: Path,
    *,
    corpus: Mapping[str, list[Section]],
    rows: Iterable[Correspondence],
    edges: Iterable[Edge],
    pins: Mapping[str, str],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    sections = sorted(
        (s for found in corpus.values() for s in found),
        key=lambda s: (s.source_key, section_key(s.number)),
    )
    edges = list(edges)
    _jsonl(out_dir / "sections.jsonl", (s.model_dump(mode="json") for s in sections))
    _jsonl(out_dir / "correspondences.jsonl", (asdict(c) for c in rows))
    _jsonl(out_dir / "edges.jsonl", (asdict(e) for e in edges))

    manifest = {
        "sources": dict(sorted(pins.items())),
        "sections": {key: len(found) for key, found in sorted(corpus.items())},
        "edges": dict(sorted(Counter(e.relation.value for e in edges).items())),
        "files": {
            name: hashlib.sha256((out_dir / name).read_bytes()).hexdigest()
            for name in BUNDLE_FILES
        },
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out_dir


def main() -> None:  # pragma: no cover - builds from the real PDFs
    from lexbridge.ingest.corpus import load_correspondences, load_sections
    from lexbridge.ingest.fetch import load_pins
    from lexbridge.ingest.graph import build_edges

    version = sys.argv[1] if len(sys.argv) > 1 else "dev"
    data = Path("data")
    pins = load_pins(data / "sources.json")
    corpus = load_sections(data / "raw", pins)
    rows = load_correspondences(data / "raw", pins, corpus)
    edges = build_edges(rows, ipc=corpus["ipc"], bns=corpus["bns_current"])
    out = write_bundle(Path("artifacts") / version, corpus=corpus, rows=rows, edges=edges,
                       pins=pins)
    print(json.loads((out / "manifest.json").read_text(encoding="utf-8")))


if __name__ == "__main__":  # pragma: no cover
    main()
