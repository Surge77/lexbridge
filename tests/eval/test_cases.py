from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from lexbridge.eval.cases import Case, Category, read_cases, write_cases
from lexbridge.schema import Act, act_in_force_on


def case(**overrides: object) -> Case:
    fields: dict[str, object] = {
        "id": "lay-0001", "category": Category.LAY, "question": "Cheating on 3 May 2024?",
        "offence_date": date(2024, 5, 3), "answer_act": Act.IPC, "targets": ("IPC:420",),
        "wrong_regime": ("BNS:318",), "needs_clarification": False,
    }
    return Case.model_validate({**fields, **overrides})


@pytest.mark.parametrize(("day", "act"), [
    (date(2024, 6, 30), Act.IPC),
    (date(2024, 7, 1), Act.BNS),  # the commencement day itself is BNS
    (date(1999, 1, 1), Act.IPC),
])
def test_the_code_in_force_turns_over_on_1_july_2024(day: date, act: Act) -> None:
    assert act_in_force_on(day) is act


def test_a_date_must_agree_with_the_code_of_the_answer() -> None:
    with pytest.raises(ValidationError, match="not a BNS date"):
        case(answer_act=Act.BNS, targets=("BNS:318",), wrong_regime=("IPC:420",))


def test_an_undated_question_must_ask_for_the_date() -> None:
    with pytest.raises(ValidationError, match="clarify exactly"):
        case(offence_date=None, answer_act=None, needs_clarification=False)

    asks = case(offence_date=None, answer_act=None, needs_clarification=True,
                targets=("IPC:420", "BNS:318"), wrong_regime=())
    assert asks.needs_clarification


def test_an_out_of_scope_question_is_declined_with_no_targets() -> None:
    declined = case(category=Category.OUT_OF_SCOPE, offence_date=None, answer_act=None,
                    targets=(), wrong_regime=())
    assert declined.targets == ()

    with pytest.raises(ValidationError, match="no answer"):
        case(category=Category.OUT_OF_SCOPE, offence_date=None, answer_act=None)


def test_an_in_scope_question_without_a_target_is_refused() -> None:
    with pytest.raises(ValidationError, match="needs a target"):
        case(targets=(), wrong_regime=())


def test_a_section_cannot_be_both_target_and_wrong_regime() -> None:
    with pytest.raises(ValidationError, match="both right and wrong"):
        case(wrong_regime=("IPC:420",))


def test_cases_round_trip_through_jsonl(tmp_path: Path) -> None:
    cases = [case(), case(id="hindi-0001", category=Category.HINDI,
                          question="धोखाधड़ी की सज़ा क्या है?")]
    path = tmp_path / "golden.jsonl"

    write_cases(path, cases)

    assert read_cases(path) == cases
    # Devanagari is written as-is so the file stays reviewable.
    assert "धोखाधड़ी" in path.read_text(encoding="utf-8")


def test_targets_must_come_from_the_code_of_the_answer() -> None:
    with pytest.raises(ValidationError, match="every target must come from the IPC"):
        case(targets=("BNS:152",), wrong_regime=())


def test_wrong_regime_sections_must_come_from_the_other_code() -> None:
    with pytest.raises(ValidationError, match="from the other code"):
        case(wrong_regime=("IPC:415",))
