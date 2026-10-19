from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from lexbridge.eval.cases import Case, Category
from lexbridge.eval.generation import (
    PER_GENERATED,
    Outcome,
    append_checkpoint,
    by_category,
    code_of,
    expected_status,
    load_checkpoint,
    score,
    subset,
    with_patience,
)
from lexbridge.schema import Act


def case(n: int, category: Category = Category.LAY, **fields: object) -> Case:
    base: dict[str, object] = {
        "id": f"{category}-{n}", "category": category, "question": f"q{n}",
        "offence_date": date(2024, 8, 1), "answer_act": Act.BNS, "targets": ("BNS:318",),
        "wrong_regime": ("IPC:420",), "needs_clarification": False}
    return Case.model_validate({**base, **fields})


UNDATED = {"offence_date": None, "answer_act": None, "needs_clarification": True,
           "wrong_regime": (), "targets": ("IPC:420", "BNS:318")}
OOS = {"offence_date": None, "answer_act": None, "targets": (), "wrong_regime": ()}


def outcome(status: str, *, act: str | None = "BNS", citations: tuple[str, ...] = ("BNS:318",),
            first: tuple[str, ...] = (), final: tuple[str, ...] = (),
            seconds: float = 1.0) -> Outcome:
    return {"id": "x", "category": "lay", "status": status, "act": act,
            "citations": list(citations), "text": "t", "first_draft_unsupported": list(first),
            "final_unsupported": list(final), "calls": 1, "seconds": seconds}


def test_the_subset_keeps_every_hand_case_and_samples_each_generated_category() -> None:
    cases = [case(i) for i in range(3)] + [
        case(i, Category.MAP_IPC_TO_BNS, offence_date=None) for i in range(40)]

    picked = subset(cases)

    assert [c.category for c in picked[:3]] == [Category.LAY] * 3
    maps = [c for c in picked if c.category is Category.MAP_IPC_TO_BNS]
    assert len(maps) == PER_GENERATED
    assert maps[0].id != maps[1].id
    assert subset(cases) == picked  # deterministic


def test_what_each_case_should_get() -> None:
    assert expected_status(case(1)) == "answered"
    assert expected_status(case(2, **UNDATED)) == "clarify"
    assert expected_status(case(3, Category.OUT_OF_SCOPE, **OOS)) == "declined"


def test_the_scores_separate_correctness_from_behaviour() -> None:
    cases = [case(1), case(2), case(3, **UNDATED), case(4, **UNDATED),
             case(5, Category.OUT_OF_SCOPE, **OOS), case(6)]
    outcomes = [
        outcome("answered", first=("999",), seconds=1.0),         # verified, right
        outcome("answered", act="IPC", citations=("IPC:420",)),   # wrong code
        outcome("clarify", act=None, citations=()),
        outcome("answered"),                                       # should have asked
        outcome("declined", act=None, citations=()),
        outcome("declined", citations=(), seconds=9.0),           # wrongly declined
    ]

    s = score(cases, outcomes)

    assert s["n"] == 6
    assert s["hallucinated"] == 0
    assert s["first_draft_unsupported"] == round(1 / 6, 4)
    assert s["correct_section"] == 0.5  # of the two answered with expected "answered"
    assert s["right_code"] == 0.5
    assert s["clarify_precision"] == 1.0
    assert s["clarify_recall"] == 0.5
    assert s["out_of_scope_declined"] == 1.0
    assert s["in_scope_declined"] == 0.2
    assert s["seconds_p95"] >= s["seconds_p50"]


def test_a_final_unsupported_section_fails_the_gate() -> None:
    s = score([case(1)], [outcome("answered", final=("BNS:999",))])

    assert s["hallucinated"] == 1.0
    assert s["clarify_precision"] is None  # nothing was asked


def test_scores_are_also_broken_down_by_category() -> None:
    cases = [case(1), case(2, Category.HINDI)]

    groups = by_category(cases, [outcome("answered"), outcome("answered")])

    assert set(groups) == {"lay", "hindi"}
    assert groups["hindi"]["n"] == 1


def test_patience_waits_out_failures_then_returns() -> None:
    attempts: list[int] = []
    waited: list[float] = []

    def flaky() -> Outcome:
        attempts.append(1)
        if len(attempts) < 3:
            raise TimeoutError
        return outcome("answered")

    result = with_patience(flaky, waits=(1, 2, 3), retry_on=TimeoutError,
                           sleep=waited.append)

    assert result["status"] == "answered"
    assert waited == [1, 2]


def test_patience_gives_up_after_the_last_wait() -> None:
    def broken() -> Outcome:
        raise TimeoutError

    with pytest.raises(TimeoutError):
        with_patience(broken, waits=(1,), retry_on=TimeoutError, sleep=lambda _: None)


def test_codes_are_recorded_as_plain_strings() -> None:
    assert (code_of(Act.IPC), code_of(None)) == ("IPC", None)


def test_an_interrupted_run_resumes_from_its_checkpoint(tmp_path: Path) -> None:
    progress = tmp_path / "gen.partial.jsonl"
    assert load_checkpoint(progress) == {}

    first, second = outcome("answered"), outcome("clarify", act=None)
    first["id"], second["id"] = "lay-1", "lay-2"
    append_checkpoint(progress, first)
    append_checkpoint(progress, second)

    assert load_checkpoint(progress) == {"lay-1": first, "lay-2": second}
