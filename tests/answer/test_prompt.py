from __future__ import annotations

from datetime import date

import pytest

from lexbridge.answer.prompt import (
    MalformedReplyError,
    assumption,
    clarification,
    correspondence,
    describe,
    messages,
    parse,
)
from lexbridge.ingest.graph import Edge, Relation
from lexbridge.query.dates import Period
from lexbridge.query.route import Reason, Route
from lexbridge.schema import Act, Section, Status


def section(act: Act, number: str, title: str, text: str = "") -> Section:
    return Section(act=act, number=number, title=title, text=text or f"{number}. {title}.",
                   chapter=None, status=Status.IN_FORCE, source_key="x", page=1)


@pytest.mark.parametrize(("period", "words"), [
    (Period(date(2024, 8, 5), date(2024, 8, 5)), "on 5 August 2024"),
    (Period(date(2024, 2, 1), date(2024, 2, 29)), "in February 2024"),
    (Period(date(2023, 1, 1), date(2023, 12, 31), specific=False), "in 2023"),
    (Period(date.min, date(2024, 6, 30)), "on or before 30 June 2024"),
    (Period(date(2024, 7, 1), date.max), "on or after 1 July 2024"),
    (Period(date(2024, 6, 3), date(2024, 6, 9)), "between 3 June 2024 and 9 June 2024"),
])
def test_a_period_is_described_at_its_precision(period: Period, words: str) -> None:
    assert describe(period) == words


def test_the_assumption_names_the_date_and_the_code() -> None:
    route = Route(Act.BNS, Reason.DATE, Period(date(2024, 8, 5), date(2024, 8, 5)))

    assert assumption(route) == (
        "Assuming the offence was committed on 5 August 2024, the Bharatiya Nyaya Sanhita "
        "(BNS) applies.")
    assert assumption(Route(Act.IPC, Reason.NAMED_CODE)) == (
        "You asked about the Indian Penal Code (IPC).")
    assert assumption(Route(Act.BNS, Reason.MAP), ["IPC:420"]) == (
        "You asked what IPC 420 corresponds to in the Bharatiya Nyaya Sanhita (BNS).")
    assert assumption(Route(None, Reason.UNKNOWN)) == ""


def test_a_clarification_says_why_and_lists_the_candidates_without_a_model() -> None:
    text = clarification(Route(None, Reason.STRADDLES),
                         [section(Act.IPC, "379", "Punishment for theft"),
                          section(Act.BNS, "303", "Theft")])

    assert text.startswith("The period you gave covers both sides of 1 July 2024.")
    assert "When was the offence committed?" in text
    assert text.endswith("IPC 379 (Punishment for theft); BNS 303 (Theft).")


def test_the_prompt_numbers_sources_and_states_the_code() -> None:
    route = Route(Act.BNS, Reason.DATE, Period(date(2024, 8, 5), date(2024, 8, 5)))
    long_text = "303. Theft.—" + "x" * 5000

    system, user = messages("Theft in August 2024?", [section(Act.BNS, "303", "Theft",
                                                              long_text)], route)

    assert "sections of the Bharatiya Nyaya Sanhita (BNS)" in system["content"]
    assert "Assuming the offence was committed on 5 August 2024" in system["content"]
    assert user["content"].startswith("Sources:\n\n[1] BNS section 303: Theft\n")
    assert user["content"].endswith("Question: Theft in August 2024?")
    assert len(user["content"]) < 1400  # the section text was cut


def test_an_unrouted_question_is_never_sent_to_the_model() -> None:
    with pytest.raises(ValueError, match="ask for the date"):
        messages("Theft?", [], Route(None, Reason.UNKNOWN))


def test_a_reply_keeps_only_citations_that_name_a_source() -> None:
    reply = parse('{"status": "answered", "answer": " Yes. ", "citations": [2, 9, 2, 0, true]}',
                  n_sources=3)

    assert (reply.declined, reply.text, reply.citations) == (False, "Yes.", (2,))
    assert parse('{"status": "declined", "answer": "No."}', 3).declined


@pytest.mark.parametrize("raw", [
    "not json", '["a"]', '{"status": "maybe", "answer": "x"}', '{"status": "answered"}',
])
def test_a_malformed_reply_is_refused(raw: str) -> None:
    with pytest.raises(MalformedReplyError):
        parse(raw, n_sources=3)


def test_correspondence_rows_for_a_cited_section_reach_the_model() -> None:
    edges = [Edge("IPC:420", "BNS:318", Relation.REPLACED_BY, "(4)"),
             Edge("IPC:379", "BNS:303", Relation.REPLACED_BY, "(2)"),
             Edge("BNS:319", "BNS:318", Relation.REFERS_TO, "")]

    table = correspondence(edges, ["IPC:420"])
    _, user = messages("BNS equivalent of IPC 420?", [section(Act.BNS, "318", "Cheating")],
                       Route(Act.BNS, Reason.MAP), ["IPC:420"], table)

    assert table == [edges[0]]
    assert "Official IPC-BNS correspondence table:\n- IPC 420 was replaced by BNS 318(4)" \
        in user["content"]
