from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import pytest

from lexbridge.answer.llm import Completion
from lexbridge.answer.service import NO_ANSWER, NOT_COVERED, Status, answer
from lexbridge.bundle import Bundle
from lexbridge.query.route import Reason
from lexbridge.query.understand import Facts
from lexbridge.retrieve.base import Hit
from lexbridge.retrieve.dense import DenseIndex
from lexbridge.retrieve.pipeline import Pipeline
from lexbridge.schema import Act

from ..eval.factory import build_bundle
from ..retrieve.fakes import WordsEmbedder


class Script:
    """Replies in order, and records every conversation it was sent."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.sent: list[list[Mapping[str, str]]] = []

    def complete(self, messages: Sequence[Mapping[str, str]], *, max_tokens: int = 700,
                 json_mode: bool = True) -> Completion:
        self.sent.append(list(messages))
        return Completion(self.replies.pop(0), "stub", "stub-model", 1.0)


class Fixed:
    def __init__(self, *ids: str) -> None:
        self.ids = ids

    def search(self, query: str, k: int, *, facts: Facts | None = None) -> list[Hit]:
        return [Hit(i, 1.0) for i in self.ids[:k]]


def reply(text: str, *citations: int, status: str = "answered") -> str:
    return json.dumps({"status": status, "answer": text, "citations": list(citations)})


@pytest.fixture
def bundle(tmp_path: Path) -> Bundle:
    return build_bundle(tmp_path / "v1")


def test_a_dated_question_is_answered_from_its_code_with_the_date_stated(
        bundle: Bundle) -> None:
    chat = Script(reply("Theft is punished under BNS 303(2).", 1))

    result = answer("My phone was stolen on 5 August 2024.", retriever=Fixed("BNS:303"),
                    bundle=bundle, chat=chat)

    assert result.status is Status.ANSWERED
    assert result.text == ("Assuming the offence was committed on 5 August 2024, the "
                           "Bharatiya Nyaya Sanhita (BNS) applies. Theft is punished under "
                           "BNS 303(2).")
    assert (result.citations, result.act, result.reason) == (("BNS:303",), Act.BNS,
                                                             Reason.DATE)
    assert "[1] BNS section 303: Theft" in chat.sent[0][1]["content"]


def test_an_explicit_offence_date_overrides_the_dates_in_the_text(bundle: Bundle) -> None:
    chat = Script(reply("Theft is punished under IPC 379.", 1))

    result = answer("My phone was stolen on 5 August 2024.", retriever=Fixed("IPC:379"),
                    bundle=bundle, chat=chat, offence_date=date(2024, 3, 5))

    assert (result.act, result.reason) == (Act.IPC, Reason.DATE)
    assert result.text.startswith("Assuming the offence was committed on 5 March 2024, "
                                  "the Indian Penal Code (IPC) applies.")


def test_an_explicit_offence_date_also_decides_which_sources_are_retrieved(
        bundle: Bundle) -> None:
    retriever = Pipeline(bundle, DenseIndex.build(bundle, WordsEmbedder()), routed=True,
                         references=True)
    chat = Script(reply("Theft is punished with imprisonment.", 1))

    result = answer("My phone was stolen on 5 August 2024.", retriever=retriever,
                    bundle=bundle, chat=chat, offence_date=date(2024, 3, 5))

    assert result.act is Act.IPC
    shown = chat.sent[0][1]["content"]
    assert "] IPC section" in shown and "] BNS section" not in shown


def test_an_explicit_date_does_not_turn_a_named_counterpart_question_into_a_dated_one(
        bundle: Bundle) -> None:
    chat = Script(reply("IPC 379 became BNS 303.", 1))

    result = answer("What is the BNS equivalent of IPC 379?", retriever=Fixed("BNS:303"),
                    bundle=bundle, chat=chat, offence_date=date(2020, 1, 1))

    # It asks for the other code by name: the map answers it, whatever the date.
    assert (result.act, result.reason) == (Act.BNS, Reason.MAP)


def test_an_explicit_offence_date_answers_a_question_that_gives_none(bundle: Bundle) -> None:
    chat = Script(reply("Theft is punished under BNS 303(2).", 1))

    result = answer("What is the punishment for theft?", retriever=Fixed("BNS:303"),
                    bundle=bundle, chat=chat, offence_date=date(2025, 1, 2))

    assert (result.status, result.act) == (Status.ANSWERED, Act.BNS)
    assert len(chat.sent) == 1  # no scope check: the question was routed


def test_an_unsupported_section_gets_one_retry_with_the_reason(bundle: Bundle) -> None:
    chat = Script(reply("See BNS 303 and section 999.", 1), reply("See BNS 303.", 1))

    result = answer("Theft on 5 August 2024?", retriever=Fixed("BNS:303"), bundle=bundle,
                    chat=chat)

    assert result.text.endswith("See BNS 303.")
    assert result.first_draft_unsupported == ("999",)
    assert result.removed == ()
    assert "not in the sources: 999" in chat.sent[1][-1]["content"]


def test_what_is_still_unsupported_after_the_retry_is_cut(bundle: Bundle) -> None:
    chat = Script(reply("BNS 303 applies. Also BNS 999.", 1),
                  reply("BNS 303 applies. Also BNS 999.", 1))

    result = answer("Theft on 5 August 2024?", retriever=Fixed("BNS:303"), bundle=bundle,
                    chat=chat)

    assert result.text.endswith("BNS 303 applies.")
    assert result.removed == ("BNS:999",)


def test_an_answer_that_is_nothing_but_unsupported_claims_is_withheld(
        bundle: Bundle) -> None:
    chat = Script(reply("BNS 999 applies.", 1), reply("BNS 998 applies.", 1))

    result = answer("Theft on 5 August 2024?", retriever=Fixed("BNS:303"), bundle=bundle,
                    chat=chat)

    assert (result.status, result.text) == (Status.DECLINED, NO_ANSWER)


def test_a_malformed_reply_is_asked_again_then_given_up_on(bundle: Bundle) -> None:
    chat = Script("not json", "still not json")

    result = answer("Theft on 5 August 2024?", retriever=Fixed("BNS:303"), bundle=bundle,
                    chat=chat)

    assert (result.status, len(result.calls)) == (Status.DECLINED, 2)
    assert "JSON object only" in chat.sent[1][-1]["content"]


def test_a_malformed_retry_does_not_discard_a_usable_first_reply(bundle: Bundle) -> None:
    chat = Script(reply("BNS 303 applies. Also BNS 999.", 1), "not json")

    result = answer("Theft on 5 August 2024?", retriever=Fixed("BNS:303"), bundle=bundle,
                    chat=chat)

    assert result.status is Status.ANSWERED
    assert result.text.endswith("BNS 303 applies.")
    assert (result.first_draft_unsupported, result.removed) == (("BNS:999",), ("BNS:999",))


@pytest.mark.parametrize("text", ["Section 999 covers this, not the sources.", ""])
def test_a_decline_names_no_unsupported_section_and_is_never_empty(
        bundle: Bundle, text: str) -> None:
    chat = Script(reply(text, status="declined"))

    result = answer("Cheque bounce in 2025?", retriever=Fixed("BNS:318"), bundle=bundle,
                    chat=chat)

    assert (result.status, result.text) == (Status.DECLINED, NOT_COVERED)


def test_a_scope_verdict_of_the_string_false_is_out_of_scope(bundle: Bundle) -> None:
    result = answer("What is the capital of Australia?", retriever=Fixed("IPC:420"),
                    bundle=bundle, chat=Script('{"in_scope": "false"}'))

    assert result.status is Status.DECLINED


def test_the_model_may_decline_when_the_sources_do_not_answer(bundle: Bundle) -> None:
    chat = Script(reply("The sources do not cover cheque bounce.", status="declined"))

    result = answer("Cheque bounce in 2025?", retriever=Fixed("BNS:318"), bundle=bundle,
                    chat=chat)

    assert (result.status, result.text) == (Status.DECLINED,
                                            "The sources do not cover cheque bounce.")


def test_a_question_the_router_cannot_place_is_asked_back_without_a_model_answer(
        bundle: Bundle) -> None:
    chat = Script('{"in_scope": true}')

    result = answer("What is the punishment for theft?",
                    retriever=Fixed("IPC:379", "BNS:303", "IPC:378"), bundle=bundle,
                    chat=chat)

    assert result.status is Status.CLARIFY
    assert "When was the offence committed?" in result.text
    assert result.text.endswith("IPC 379 (Punishment for theft); BNS 303 (Theft).")
    # Only the scope check reached the model, and it saw titles, not section text.
    [scope] = chat.sent
    assert "IPC 379: Punishment for theft" in scope[1]["content"]


def test_a_section_a_source_itself_names_may_be_named_in_the_answer(bundle: Bundle) -> None:
    # The factory's IPC 379 refers to 378, as IPC 438's text names 437.
    chat = Script(reply("Theft is defined in section 378 and punished under section 379.", 1))

    result = answer("My phone was stolen on 5 March 2024.", retriever=Fixed("IPC:379"),
                    bundle=bundle, chat=chat)

    assert result.status is Status.ANSWERED
    assert result.removed == () and result.first_draft_unsupported == ()
    assert "IPC:378" in result.allowed


def test_a_clarification_may_name_what_its_candidates_name(bundle: Bundle) -> None:
    result = answer("What is the punishment for theft?", retriever=Fixed("IPC:379"),
                    bundle=bundle, chat=Script('{"in_scope": true}'))

    assert result.status is Status.CLARIFY
    assert set(result.allowed) == {"IPC:379", "IPC:378"}


def test_an_out_of_scope_question_is_declined_not_asked_for_a_date(bundle: Bundle) -> None:
    result = answer("What is the capital of Australia?", retriever=Fixed("IPC:420"),
                    bundle=bundle, chat=Script('{"in_scope": false}'))

    assert result.status is Status.DECLINED
    assert result.citations == ()


def test_an_unreadable_scope_verdict_errs_towards_asking(bundle: Bundle) -> None:
    result = answer("What is the punishment for theft?", retriever=Fixed("IPC:379"),
                    bundle=bundle, chat=Script("garbled"))

    assert result.status is Status.CLARIFY


def test_a_cited_section_from_the_question_may_be_named_in_the_answer(
        bundle: Bundle) -> None:
    chat = Script(reply("IPC 379 became BNS 303.", 1))

    result = answer("What is the BNS equivalent of IPC 379?", retriever=Fixed("BNS:303"),
                    bundle=bundle, chat=chat)

    assert result.status is Status.ANSWERED
    assert result.removed == () and result.first_draft_unsupported == ()
    assert result.text.startswith("You asked what IPC 379 corresponds to in the Bharatiya")
