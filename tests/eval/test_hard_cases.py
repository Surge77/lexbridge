from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from lexbridge.bundle import Bundle
from lexbridge.eval.cases import Category
from lexbridge.eval.golden import GoldenError, build_golden
from lexbridge.eval.hard_cases import HAND, Hand, expand
from lexbridge.schema import Act

from .factory import build_bundle

THEFT = ("378", "379")


@pytest.fixture
def bundle(tmp_path: Path) -> Bundle:
    return build_bundle(tmp_path / "v1")


def test_a_pre_cutover_date_answers_from_the_ipc(bundle: Bundle) -> None:
    case = expand(Hand("Theft, May 2024", Category.LAY, date(2024, 5, 3), THEFT), bundle)

    assert case.answer_act is Act.IPC
    assert case.targets == ("IPC:378", "IPC:379")
    # The BNS side comes from the graph, never typed in.
    assert case.wrong_regime == ("BNS:303",)


def test_a_post_cutover_date_answers_from_the_graph_successors(bundle: Bundle) -> None:
    case = expand(Hand("Theft, Aug 2024", Category.LAY, date(2024, 8, 1), THEFT), bundle)

    assert (case.answer_act, case.targets, case.wrong_regime) == (
        Act.BNS, ("BNS:303",), ("IPC:378", "IPC:379"))


def test_a_provision_new_in_the_bns_is_named_explicitly(bundle: Bundle) -> None:
    hand = Hand("Snatching, Oct 2024", Category.TRICKY, date(2024, 10, 1), THEFT,
                bns=("304",))

    case = expand(hand, bundle)

    assert case.targets == ("BNS:304",)
    assert case.wrong_regime == ("IPC:378", "IPC:379")


def test_no_date_means_either_code_and_a_question_back(bundle: Bundle) -> None:
    case = expand(Hand("Theft?", Category.HINDI, None, THEFT), bundle)

    assert case.needs_clarification
    assert case.targets == ("IPC:378", "IPC:379", "BNS:303")


def test_naming_the_code_removes_the_need_for_a_date(bundle: Bundle) -> None:
    case = expand(Hand("What did IPC 124A say?", Category.TRICKY, ipc=("124A",),
                       act=Act.IPC), bundle)

    assert (case.needs_clarification, case.targets) == (False, ("IPC:124A",))


def test_out_of_scope_is_declined_without_a_clarifying_question(bundle: Bundle) -> None:
    case = expand(Hand("Capital of Australia?", Category.OUT_OF_SCOPE), bundle)

    assert (case.targets, case.needs_clarification, case.answer_act) == ((), False, None)


def test_the_golden_set_refuses_a_section_the_bundle_lacks(bundle: Bundle) -> None:
    hand = [Hand("Murder in 2022?", Category.LAY, date(2022, 1, 1), ("302",))]

    with pytest.raises(GoldenError, match="IPC:302"):
        build_golden(bundle, hand)


def test_the_golden_set_refuses_a_repeated_question(bundle: Bundle) -> None:
    hand = [Hand("Theft?", Category.LAY, None, THEFT)] * 2

    with pytest.raises(GoldenError, match="repeated"):
        build_golden(bundle, hand)


def test_the_golden_set_combines_generated_and_hand_cases(bundle: Bundle) -> None:
    cases = build_golden(bundle, [Hand("Theft?", Category.LAY, None, THEFT)])

    assert {c.category for c in cases} >= {
        Category.MAP_IPC_TO_BNS, Category.MAP_BNS_TO_IPC, Category.TOPIC_DATED, Category.LAY}


def test_the_hand_cases_cover_every_hard_category_and_never_repeat() -> None:
    counts = Counter(h.category for h in HAND)

    assert set(counts) == {Category.LAY, Category.HINDI, Category.BOUNDARY,
                           Category.TRICKY, Category.OUT_OF_SCOPE}
    assert len({h.question for h in HAND}) == len(HAND)
    # Every in-scope case names at least one provision to derive its targets from.
    assert all(h.ipc or h.bns for h in HAND if h.category is not Category.OUT_OF_SCOPE)
