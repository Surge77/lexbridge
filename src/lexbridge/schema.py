"""The record every later stage reads: one provision of one code."""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# 1-3 digits, no leading zero, optional capital-letter suffix for inserted sections
# (IPC 120A, 498A, 376DB). Section "0" does not exist in either code.
SECTION_NUMBER = re.compile(r"[1-9]\d{0,2}[A-Z]{0,3}")

# Notification S.O. 850(E), 23 February 2024. An offence committed before this date is
# tried under the IPC (BNS s.358 saves it), on or after it under the BNS.
BNS_IN_FORCE_FROM = date(2024, 7, 1)


class Act(StrEnum):
    IPC = "IPC"
    BNS = "BNS"


def act_in_force_on(day: date) -> Act:
    return Act.IPC if day < BNS_IN_FORCE_FROM else Act.BNS


class Status(StrEnum):
    IN_FORCE = "in_force"
    REPEALED = "repealed"


class Section(BaseModel):
    model_config = ConfigDict(frozen=True)

    act: Act
    # Anchored at both ends: pydantic's pattern is a search, so "4A1" would otherwise
    # pass on the strength of its trailing "1".
    number: str = Field(pattern=f"^{SECTION_NUMBER.pattern}$")
    title: str
    text: str
    chapter: str | None
    status: Status
    source_key: str
    # 1-based page the section starts on, so a citation can point at the source PDF.
    page: int = Field(ge=1)

    @property
    def id(self) -> str:
        return f"{self.act}:{self.number}"


def section_key(number: str) -> tuple[int, str]:
    """Sort key placing inserts after their base: 120 < 120A < 120B < 121."""
    match = re.fullmatch(r"(\d+)([A-Z]*)", number)
    if match is None:
        raise ValueError(f"not a section number: {number!r}")
    return int(match.group(1)), match.group(2)
