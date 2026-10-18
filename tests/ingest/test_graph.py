from __future__ import annotations

from lexbridge.ingest.graph import Edge, Relation, build_edges
from lexbridge.ingest.mapping import Correspondence
from lexbridge.schema import Act, Section, Status


def section(act: Act, number: str, text: str = "", status: Status = Status.IN_FORCE) -> Section:
    return Section(act=act, number=number, title=f"T{number}", text=text or f"{number}. T.",
                   chapter=None, status=status, source_key=act.value.lower(), page=1)


def row(bns: str, sub: str, *ipc: str) -> Correspondence:
    return Correspondence(bns_section=bns, bns_sub=sub, ipc=ipc, subject="", summary="",
                          page=1)


def test_edges_cover_replacement_new_provisions_and_unmapped_sections() -> None:
    ipc = [section(Act.IPC, "420"), section(Act.IPC, "124A"),
           section(Act.IPC, "13", status=Status.REPEALED)]
    bns = [section(Act.BNS, "318"), section(Act.BNS, "111"),
           section(Act.BNS, "319", text="319. Cheating by personation, see section 318.")]
    rows = [row("318", "(4)", "420"), row("111", "")]

    edges = set(build_edges(rows, ipc=ipc, bns=bns))

    assert Edge("IPC:420", "BNS:318", Relation.REPLACED_BY, "(4)") in edges
    assert Edge("BNS:111", "", Relation.NEW_IN_BNS, "") in edges
    # In force, never cited by the table. Reported as unmapped, not as "dropped".
    assert Edge("IPC:124A", "", Relation.UNMAPPED, "") in edges
    # Repealed long before 2023: not a BNS question at all.
    assert not any(e.src == "IPC:13" for e in edges)
    assert Edge("BNS:319", "BNS:318", Relation.REFERS_TO, "") in edges


def test_a_cross_reference_to_a_section_that_does_not_exist_is_dropped() -> None:
    bns = [section(Act.BNS, "1", text="1. See section 999.")]

    assert list(build_edges([], ipc=[], bns=bns)) == []


def test_a_section_does_not_refer_to_itself() -> None:
    bns = [section(Act.BNS, "5", text="5. Nothing in this section 5 applies.")]

    assert list(build_edges([], ipc=[], bns=bns)) == []


def test_edges_come_out_in_a_stable_order() -> None:
    bns = [section(Act.BNS, "2"), section(Act.BNS, "1")]
    rows = [row("2", ""), row("1", "")]

    first = build_edges(rows, ipc=[], bns=bns)
    assert first == build_edges(list(reversed(rows)), ipc=[], bns=list(reversed(bns)))
