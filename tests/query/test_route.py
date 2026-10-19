from __future__ import annotations

from datetime import date

import pytest

from lexbridge.query.route import Reason, route
from lexbridge.query.understand import Period, periods, understand
from lexbridge.schema import Act


@pytest.mark.parametrize(("text", "start", "end"), [
    ("on 3 May 2024", date(2024, 5, 3), date(2024, 5, 3)),
    ("on the 21st of August 2023", date(2023, 8, 21), date(2023, 8, 21)),
    ("on March 5, 2025", date(2025, 3, 5), date(2025, 3, 5)),
    ("dated 2024-06-30", date(2024, 6, 30), date(2024, 6, 30)),
    ("on 01/07/2024", date(2024, 7, 1), date(2024, 7, 1)),  # day first: 1 July
    ("in Sept 2024", date(2024, 9, 1), date(2024, 9, 30)),
    ("in february 2024", date(2024, 2, 1), date(2024, 2, 29)),  # leap year
    ("back in 2019", date(2019, 1, 1), date(2019, 12, 31)),
    ("मार्च 2024 की घटना", date(2024, 3, 1), date(2024, 3, 31)),
    ("ghatna 2022 ki hai", date(2022, 1, 1), date(2022, 12, 31)),
])
def test_a_stated_period_is_read_at_its_precision(text: str, start: date, end: date) -> None:
    assert periods(text) == (Period(start, end),)


@pytest.mark.parametrize("text", [
    "Under the Bharatiya Nyaya Sanhita, 2023, what is theft?",
    "The Indian Penal Code (45 of 1860) defines cheating.",
    "What does BNS 2023 say about snatching?",
    "a proclamation under section 82 of Act 2 of 1974",
    "Act No. 45 of 2023 repealed the Code",
    "Fake 500 rupee notes",
])
def test_an_act_title_or_an_amount_is_not_a_date(text: str) -> None:
    assert periods(text) == ()


def test_an_impossible_date_is_ignored_rather_than_guessed() -> None:
    # Not salvaged as "some time in 2024": a garbled date is a reason to ask, not to guess.
    assert periods("on 31/02/2024") == ()


def test_a_day_is_not_read_again_as_its_month() -> None:
    assert len(periods("on 3 May 2024 and again in June 2024")) == 2


@pytest.mark.parametrize(("text", "act", "reason"), [
    ("A theft on 30 June 2024", Act.IPC, Reason.DATE),
    ("A theft on 1 July 2024", Act.BNS, Reason.DATE),  # the commencement day is BNS
    ("Cheated in June 2024", Act.IPC, Reason.DATE),
    ("Cheated in July 2024", Act.BNS, Reason.DATE),
    ("A murder in 2024", None, Reason.STRADDLES),
    # The offence comes first; the FIR and the trial follow it.
    ("Theft in June 2024, FIR filed in August 2024", Act.IPC, Reason.DATE),
    ("Trial starts in 2026 for a slap in July 2024", Act.BNS, Reason.DATE),
    ("What did section 124A of the IPC say?", Act.IPC, Reason.NAMED_CODE),
    ("Does the BNS allow community service?", Act.BNS, Reason.NAMED_CODE),
    ("भारतीय न्याय संहिता में चोरी क्या है?", Act.BNS, Reason.NAMED_CODE),
    ("Is IPC 420 now BNS 318?", None, Reason.UNKNOWN),
    ("What is the punishment for theft?", None, Reason.UNKNOWN),
    # The date decides, even against a named code: the law in force is the law that applies.
    ("Under the IPC, what applies to a theft in August 2024?", Act.BNS, Reason.DATE),
])
def test_the_route(text: str, act: Act | None, reason: Reason) -> None:
    decided = route(understand(text))

    assert (decided.act, decided.reason) == (act, reason)


def test_code_names_are_matched_as_words_not_substrings() -> None:
    assert understand("RECIPE for the BNSX").codes == frozenset()
    assert understand("Bharatiya Nyaya Sanhita and the Indian Penal Code").codes == {
        Act.BNS, Act.IPC}
