from __future__ import annotations

from datetime import date
from pathlib import Path

from lexbridge.eval.cases import Category
from lexbridge.eval.generate import map_cases, topic_cases
from lexbridge.schema import BNS_IN_FORCE_FROM, Act

from .factory import build_bundle


def test_every_replacement_is_asked_in_both_directions(tmp_path: Path) -> None:
    cases = map_cases(build_bundle(tmp_path / "v1"))

    forward = {c.question: c for c in cases if c.category is Category.MAP_IPC_TO_BNS}
    backward = {c.question: c for c in cases if c.category is Category.MAP_BNS_TO_IPC}
    assert forward["IPC 378 is now which section of the Bharatiya Nyaya Sanhita?"].targets == (
        "BNS:303",)
    # Two IPC sections merged into BNS 303: either one answers the reverse question.
    reverse = next(c for c in backward.values() if "303" in c.question)
    assert reverse.targets == ("IPC:378", "IPC:379")
    # Retrieving the section the question already names is the classic wrong answer.
    assert reverse.wrong_regime == ("BNS:303",)
    # Unmapped and new provisions have no counterpart to ask about.
    assert not any("124A" in q or "304" in q for q in [*forward, *backward])
    assert all(c.answer_act and not c.needs_clarification for c in cases)


def test_topics_rotate_through_before_after_and_undated(tmp_path: Path) -> None:
    cases = topic_cases(build_bundle(tmp_path / "v1"))

    # 378, 379, 420 have unique titles and a successor; 124A has none; 143 and 147 share
    # the heading "Punishment", which names no one provision.
    assert [c.category for c in cases] == [
        Category.TOPIC_DATED, Category.TOPIC_DATED, Category.TOPIC_UNDATED]
    before, after, undated = cases
    assert before.question == "What does the law say about theft? It happened on 4 November 2019."
    assert before.offence_date == date(2019, 11, 4)
    assert (before.answer_act, before.targets, before.wrong_regime) == (
        Act.IPC, ("IPC:378",), ("BNS:303",))

    assert after.offence_date is not None and after.offence_date >= BNS_IN_FORCE_FROM
    assert (after.answer_act, after.targets, after.wrong_regime) == (
        Act.BNS, ("BNS:303",), ("IPC:379",))

    assert undated.question == "What does the law say about cheating and dishonestly " \
                               "inducing delivery of property?"
    assert undated.needs_clarification
    assert undated.targets == ("IPC:420", "BNS:318")


def test_ids_come_from_the_question_so_a_rebuild_keeps_them(tmp_path: Path) -> None:
    first = map_cases(build_bundle(tmp_path / "a"))
    second = map_cases(build_bundle(tmp_path / "b"))

    assert [c.id for c in first] == [c.id for c in second]
    assert len({c.id for c in first}) == len(first)
    assert all(c.id.startswith(f"{c.category}-") for c in first)
