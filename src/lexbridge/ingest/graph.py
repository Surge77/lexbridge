"""Edges between provisions: what replaced what, what is new, what refers to what.

Stored as a flat edge list because retrieval only ever follows one hop, so a dict lookup
is enough and a graph database would be a dependency with no job.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from lexbridge.ingest.mapping import Correspondence
from lexbridge.ingest.xref import cross_references
from lexbridge.schema import Section, Status, section_key


class Relation(StrEnum):
    REPLACED_BY = "replaced_by"  # IPC section -> the BNS provision that took it over
    NEW_IN_BNS = "new_in_bns"  # BNS provision with no IPC origin
    # An in-force IPC section the correspondence table does not map. NOT a claim that
    # the BNS dropped it: the table also omits 143 and 376DA, which have BNS
    # counterparts, and the state amendments IndiaCode folds in (354E, 379A, ...).
    UNMAPPED = "unmapped"
    REFERS_TO = "refers_to"  # a section's text mentions another section of its code


@dataclass(frozen=True, order=True)
class Edge:
    src: str
    dst: str
    relation: Relation
    # The BNS sub-section the IPC provision landed in, e.g. "(4)" for IPC 420 -> BNS 318.
    # Edges are section-level on the IPC side: "23 Clause-1" and "498A Explanation" are
    # recorded as IPC 23 and IPC 498A, so no answer may claim a clause-level mapping.
    detail: str


def _references(sections: Iterable[Section]) -> list[Edge]:
    sections = list(sections)
    numbers = [s.number for s in sections]
    known = set(numbers)
    return [
        Edge(s.id, f"{s.act}:{n}", Relation.REFERS_TO, "")
        for s in sections
        for n in cross_references(s.text, s.act, numbers)
        if n in known and n != s.number
    ]


def build_edges(
    rows: Iterable[Correspondence], *, ipc: Iterable[Section], bns: Iterable[Section]
) -> list[Edge]:
    rows, ipc, bns = list(rows), list(ipc), list(bns)
    edges: list[Edge] = []
    cited: set[str] = set()
    for c in rows:
        if not c.ipc:
            edges.append(Edge(f"BNS:{c.bns_section}", "", Relation.NEW_IN_BNS, c.bns_sub))
        for number in c.ipc:
            cited.add(number)
            edges.append(
                Edge(f"IPC:{number}", f"BNS:{c.bns_section}", Relation.REPLACED_BY, c.bns_sub)
            )
    edges.extend(
        Edge(s.id, "", Relation.UNMAPPED, "")
        for s in ipc
        if s.status is Status.IN_FORCE and s.number not in cited
    )
    edges.extend(_references(ipc))
    edges.extend(_references(bns))
    return sorted(set(edges), key=_edge_order)


def _edge_order(edge: Edge) -> tuple[object, ...]:
    def key(node: str) -> tuple[str, tuple[int, str]]:
        act, _, number = node.partition(":")
        return act, section_key(number) if number else (0, "")

    return edge.relation.value, key(edge.src), key(edge.dst), edge.detail
