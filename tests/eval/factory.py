"""A small real bundle for eval and retrieval tests, built through the production writer."""

from __future__ import annotations

from pathlib import Path

from lexbridge.bundle import Bundle, load_bundle
from lexbridge.ingest.graph import Edge, Relation
from lexbridge.ingest.package import write_bundle
from lexbridge.schema import Act, Section, Status

IPC = {
    "378": ("Theft", "378. Theft.—Whoever intends to take dishonestly any movable property."),
    "379": ("Punishment for theft", "379. Punishment for theft.—Whoever commits theft."),
    "420": ("Cheating and dishonestly inducing delivery of property",
            "420. Cheating and dishonestly inducing delivery of property.—Whoever cheats."),
    "124A": ("Sedition", "124A. Sedition.—Whoever by words brings hatred."),
    "143": ("Punishment", "143. Punishment.—Whoever is a member of an unlawful assembly."),
    "147": ("Punishment", "147. Punishment for rioting.—Whoever is guilty of rioting."),
}
BNS = {
    "303": ("Theft", "303. Theft.—(1) Whoever intends to take dishonestly. (2) Punished."),
    "318": ("Cheating", "318. Cheating.—(4) Whoever cheats and dishonestly induces."),
    "304": ("Snatching", "304. Snatching.—(1) Theft is snatching if the offender seizes."),
}
EDGES = [
    Edge("IPC:378", "BNS:303", Relation.REPLACED_BY, "(1)"),
    Edge("IPC:379", "BNS:303", Relation.REPLACED_BY, "(2)"),
    Edge("IPC:420", "BNS:318", Relation.REPLACED_BY, "(4)"),
    Edge("IPC:379", "IPC:378", Relation.REFERS_TO, ""),
    # Not the real mapping: gives a shared heading ("Punishment") a successor, so only the
    # duplicate-title filter keeps it out of the topical questions.
    Edge("IPC:147", "BNS:318", Relation.REPLACED_BY, ""),
    Edge("IPC:124A", "", Relation.UNMAPPED, ""),
    Edge("BNS:304", "", Relation.NEW_IN_BNS, ""),
]


def _sections(act: Act, key: str, table: dict[str, tuple[str, str]]) -> list[Section]:
    return [Section(act=act, number=n, title=title, text=text, chapter=None,
                    status=Status.IN_FORCE, source_key=key, page=1)
            for n, (title, text) in table.items()]


def build_bundle(root: Path) -> Bundle:
    corpus = {"ipc": _sections(Act.IPC, "ipc", IPC),
              "bns_current": _sections(Act.BNS, "bns_current", BNS)}
    return load_bundle(write_bundle(root, corpus=corpus, rows=[], edges=EDGES,
                                    pins={"ipc": "a" * 64}))
