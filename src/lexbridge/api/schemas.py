"""What the API accepts and returns. Everything a client sends is checked here first."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A question is forwarded to a third-party model and paid for out of a daily token
# budget, so it is capped; real questions are a sentence or two.
QUESTION_MAX_CHARS = 1000
SECTION_ID = r"^(IPC|BNS):\d{1,3}[A-Z]{0,3}$"
TRACE_ID = r"^[0-9a-f]{32}$"
NOTICE = ("General information about the Indian Penal Code and the Bharatiya Nyaya "
          "Sanhita, not legal advice. Do not include personal details in questions.")


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    # When given, this decides the code instead of any date in the question.
    offence_date: date | None = None

    @field_validator("offence_date")
    @classmethod
    def _not_in_the_future(cls, value: date | None) -> date | None:
        # A day of slack: the server runs on UTC, and India is 5h30 ahead of it, so an
        # Indian user's "today" is the server's tomorrow for part of every day.
        if value is not None and value > date.today() + timedelta(days=1):
            raise ValueError("offence_date cannot be in the future")
        return value


class ChatResponse(BaseModel):
    # None when the trace could not be written: the answer is still given.
    trace_id: str | None
    status: str  # answered | clarify | declined
    text: str
    act: str | None
    citations: list[str]
    # Every section the answer was allowed to name, so a reader can check it.
    sources: list[str]
    cached: bool
    notice: str = NOTICE


class SectionOut(BaseModel):
    id: str
    act: str
    number: str
    title: str
    text: str
    chapter: str | None


class MapOut(BaseModel):
    id: str
    replaced_by: list[str]  # for an IPC section: the BNS provisions that took it over
    replaces: list[str]  # for a BNS section: the IPC sections it took over


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(pattern=TRACE_ID)
    helpful: bool


class HealthOut(BaseModel):
    status: str
    bundle: str
    sections: int
