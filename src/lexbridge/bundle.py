"""Read a built bundle back: the one input that evaluation, retrieval and serving share.

Loading checks every file against the manifest hashes, so an edited or half-copied
bundle fails at startup instead of answering from text nobody can trace to a source PDF.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from lexbridge.ingest.graph import Edge, Relation
from lexbridge.ingest.package import BUNDLE_FILES
from lexbridge.schema import Section

# The texts that get indexed and cited. bns_original is the 2023 gazette, kept in the
# bundle as provenance; indexing it beside bns_current would return every BNS section twice.
SERVED_SOURCES = ("ipc", "bns_current")


class BundleIntegrityError(RuntimeError):
    """A bundle file does not match the hash its manifest recorded."""


@dataclass(frozen=True)
class Bundle:
    root: Path
    manifest: Mapping[str, object]
    sections: tuple[Section, ...]
    edges: tuple[Edge, ...]
    _by_id: Mapping[str, Section] = field(repr=False)
    _replaced_by: Mapping[str, tuple[str, ...]] = field(repr=False)
    _replaces: Mapping[str, tuple[str, ...]] = field(repr=False)

    def section(self, section_id: str) -> Section:
        return self._by_id[section_id]

    def __contains__(self, section_id: object) -> bool:
        return section_id in self._by_id

    def replaced_by(self, ipc_id: str) -> tuple[str, ...]:
        """BNS sections that took over an IPC section; empty when the table has none."""
        return self._replaced_by.get(ipc_id, ())

    def replaces(self, bns_id: str) -> tuple[str, ...]:
        """IPC sections a BNS section took over; empty for provisions new in the BNS."""
        return self._replaces.get(bns_id, ())


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _verify(root: Path, manifest: Mapping[str, object]) -> None:
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise BundleIntegrityError(f"{root}/manifest.json lists no file hashes")
    for name in BUNDLE_FILES:
        digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if files.get(name) != digest:
            raise BundleIntegrityError(f"{root}/{name} does not match its manifest hash")


def _index(edges: Iterable[Edge]) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    forward: dict[str, set[str]] = defaultdict(set)
    backward: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        if e.relation is Relation.REPLACED_BY:
            forward[e.src].add(e.dst)
            backward[e.dst].add(e.src)
    return (
        {k: tuple(sorted(v)) for k, v in forward.items()},
        {k: tuple(sorted(v)) for k, v in backward.items()},
    )


def load_bundle(root: Path) -> Bundle:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    _verify(root, manifest)
    sections = tuple(
        s
        for s in map(Section.model_validate, _read_jsonl(root / "sections.jsonl"))
        if s.source_key in SERVED_SOURCES
    )
    edges = tuple(
        Edge(str(r["src"]), str(r["dst"]), Relation(r["relation"]), str(r["detail"]))
        for r in _read_jsonl(root / "edges.jsonl")
    )
    forward, backward = _index(edges)
    return Bundle(
        root=root,
        manifest=manifest,
        sections=sections,
        edges=edges,
        _by_id={s.id: s for s in sections},
        _replaced_by=forward,
        _replaces=backward,
    )
