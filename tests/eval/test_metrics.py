from __future__ import annotations

from datetime import date

import pytest

from lexbridge.eval.cases import Case, Category
from lexbridge.eval.metrics import MACRO, first_rank, routing, score
from lexbridge.schema import Act


def dated(category: Category = Category.LAY, n: int = 0) -> Case:
    return Case(id=f"{category}-{n}", category=category, question=f"q{n}",
                offence_date=date(2023, 1, 1), answer_act=Act.IPC, targets=("IPC:420",),
                wrong_regime=("BNS:318",), needs_clarification=False)


def test_first_rank_is_one_based_and_stops_at_ten() -> None:
    assert first_rank(["IPC:420"], ["IPC:420"]) == 1
    assert first_rank(["IPC:415", "IPC:420"], ["BNS:318", "IPC:420", "IPC:415"]) == 2
    eleventh = [f"IPC:{n}" for n in range(1, 11)] + ["IPC:420"]
    assert first_rank(["IPC:420"], eleventh) is None


def test_hits_mrr_and_wrong_regime_for_one_category() -> None:
    cases = [dated(n=1), dated(n=2), dated(n=3), dated(n=4)]
    rankings = [
        ["IPC:420"],                                     # rank 1
        ["BNS:318", "IPC:420"],                          # rank 2, wrong code first
        ["IPC:1", "IPC:2", "IPC:3", "IPC:4", "IPC:5", "IPC:420"],  # rank 6
        ["BNS:318"],                                     # missed, wrong code first
    ]

    lay = score(cases, rankings)["lay"]

    assert lay.n == 4
    assert lay.hit == {1: 0.25, 5: 0.5, 10: 0.75}
    assert lay.mrr == pytest.approx((1 + 1 / 2 + 1 / 6 + 0) / 4)
    assert lay.wrong_regime_at_1 == 0.5


def test_the_macro_mean_weighs_categories_equally() -> None:
    cases = [dated(Category.TOPIC_DATED, n) for n in range(9)] + [dated(Category.LAY)]
    rankings = [["IPC:420"]] * 9 + [["IPC:1"]]

    scores = score(cases, rankings)

    # 9 of 10 cases hit, but one of the two categories misses entirely.
    assert scores[MACRO].hit[1] == 0.5
    assert scores[MACRO].n == 10


def test_out_of_scope_cases_are_not_scored_for_retrieval() -> None:
    declined = Case(id="oos-1", category=Category.OUT_OF_SCOPE, question="poem?",
                    offence_date=None, answer_act=None, targets=(), wrong_regime=(),
                    needs_clarification=False)

    scores = score([dated(), declined], [["IPC:420"], ["IPC:420"]])

    assert "out_of_scope" not in scores
    assert scores[MACRO].n == 1


def test_a_group_with_no_wrong_regime_counterpart_reports_none() -> None:
    undated = Case(id="u-1", category=Category.TOPIC_UNDATED, question="theft?",
                   offence_date=None, answer_act=None, targets=("IPC:378", "BNS:303"),
                   wrong_regime=(), needs_clarification=True)

    scores = score([undated], [["BNS:303"]])

    assert scores["topic_undated"].wrong_regime_at_1 is None
    assert scores[MACRO].wrong_regime_at_1 is None


def test_cases_and_rankings_must_line_up() -> None:
    with pytest.raises(ValueError, match="1 cases for 0 rankings"):
        score([dated()], [])


def test_map_lookups_are_scored_but_kept_out_of_the_text_macro() -> None:
    lookup = Case(id="m-1", category=Category.MAP_IPC_TO_BNS, question="IPC 420 now?",
                  offence_date=None, answer_act=Act.BNS, targets=("BNS:318",),
                  wrong_regime=("IPC:420",), needs_clarification=False)

    scores = score([dated(), lookup], [["IPC:420"], ["IPC:420"]])

    # A graph lookup a text retriever cannot answer must not drag the text headline down.
    assert scores["map_ipc_to_bns"].hit[1] == 0
    assert scores[MACRO].hit[1] == 1
    assert scores[MACRO].n == 1


def test_routing_separates_confident_errors_from_asking() -> None:
    undated = Case(id="u-1", category=Category.TOPIC_UNDATED, question="theft?",
                   offence_date=None, answer_act=None, targets=("IPC:378", "BNS:303"),
                   wrong_regime=(), needs_clarification=True)
    declined = Case(id="o-1", category=Category.OUT_OF_SCOPE, question="poem",
                    offence_date=None, answer_act=None, targets=(), wrong_regime=(),
                    needs_clarification=False)
    decisions = {"q1": Act.IPC, "q2": Act.BNS, "q3": None, "theft?": Act.BNS, "poem": Act.IPC}

    counts = routing([dated(n=1), dated(n=2), dated(n=3), undated, declined], decisions.get)

    assert counts == {"correct": 1, "wrong": 1, "unrouted": 1, "over_routed": 1}
