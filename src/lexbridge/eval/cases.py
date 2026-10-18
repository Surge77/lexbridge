"""One evaluation question, and what a correct system does with it."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from lexbridge.schema import Act, act_in_force_on


class Category(StrEnum):
    # Generated from the correspondence graph.
    MAP_IPC_TO_BNS = "map_ipc_to_bns"
    MAP_BNS_TO_IPC = "map_bns_to_ipc"
    # Templated from section titles. The question shares words with the target's
    # heading, so these measure an upper bound, not how a layperson asks.
    TOPIC_DATED = "topic_dated"
    TOPIC_UNDATED = "topic_undated"
    # Hand-written.
    LAY = "lay"
    HINDI = "hindi"
    BOUNDARY = "boundary"  # dates at the cutover, or a period that straddles it
    TRICKY = "tricky"  # unmapped IPC sections, provisions new in the BNS
    OUT_OF_SCOPE = "out_of_scope"


class Case(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    category: Category
    question: str
    # A day inside the period the question states, precise enough to fix the code.
    # None when the question gives no date or a period that straddles 1 July 2024.
    offence_date: date | None
    # The code the answer must come from. None when it cannot be known without asking.
    answer_act: Act | None
    # Section ids; retrieving any one of them counts as a hit.
    targets: tuple[str, ...]
    # The same provision in the other code: right idea, wrong law for this question.
    wrong_regime: tuple[str, ...]
    needs_clarification: bool

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.offence_date and self.answer_act != act_in_force_on(self.offence_date):
            raise ValueError(f"{self.id}: {self.offence_date} is not a {self.answer_act} date")
        if set(self.targets) & set(self.wrong_regime):
            raise ValueError(f"{self.id}: a section cannot be both right and wrong")
        if self.category is Category.OUT_OF_SCOPE:
            # Declined, not clarified: no date would bring it into either code.
            if self.targets or self.wrong_regime or self.answer_act or self.needs_clarification:
                raise ValueError(f"{self.id}: an out-of-scope question has no answer")
        elif not self.targets:
            # It would drop out of every retrieval metric without anyone noticing.
            raise ValueError(f"{self.id}: an in-scope question needs a target section")
        elif self.needs_clarification == (self.answer_act is not None):
            raise ValueError(f"{self.id}: clarify exactly when the code is unknown")
        return self


def case_id(category: Category, question: str) -> str:
    # From the content, not a position, so a case keeps its id when the set is rebuilt
    # and a per-case regression can be followed across runs.
    return f"{category}-{hashlib.sha256(question.encode()).hexdigest()[:10]}"


def write_cases(path: Path, cases: Iterable[Case]) -> None:
    lines = (json.dumps(c.model_dump(mode="json"), ensure_ascii=False) for c in cases)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8", newline="\n")


def read_cases(path: Path) -> list[Case]:
    text = path.read_text(encoding="utf-8")
    return [Case.model_validate_json(line) for line in text.splitlines()]
