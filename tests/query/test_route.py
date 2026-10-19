from __future__ import annotations

from datetime import date

import pytest

from lexbridge.query.dates import Period, read_dates
from lexbridge.query.route import Reason, route
from lexbridge.query.understand import understand
from lexbridge.schema import Act


def year(y: int) -> Period:
    return Period(date(y, 1, 1), date(y, 12, 31), specific=False)


@pytest.mark.parametrize(("text", "period"), [
    ("on 3 May 2024", Period(date(2024, 5, 3), date(2024, 5, 3))),
    ("on the 21st of August 2023", Period(date(2023, 8, 21), date(2023, 8, 21))),
    ("on March 5, 2025", Period(date(2025, 3, 5), date(2025, 3, 5))),
    ("dated 2024-06-30", Period(date(2024, 6, 30), date(2024, 6, 30))),
    ("dated 2024/07/01", Period(date(2024, 7, 1), date(2024, 7, 1))),
    ("on 01/07/2024", Period(date(2024, 7, 1), date(2024, 7, 1))),  # day first
    ("on 30-06-2024", Period(date(2024, 6, 30), date(2024, 6, 30))),
    ("in Sept 2024", Period(date(2024, 9, 1), date(2024, 9, 30))),
    ("in Jun-2024", Period(date(2024, 6, 1), date(2024, 6, 30))),
    ("on 5 Sept. 2024", Period(date(2024, 9, 5), date(2024, 9, 5))),
    ("on Sep. 5, 2024", Period(date(2024, 9, 5), date(2024, 9, 5))),
    ("in february 2024", Period(date(2024, 2, 1), date(2024, 2, 29))),  # leap year
    ("back in 2019", year(2019)),
    ("मार्च 2024 की घटना", Period(date(2024, 3, 1), date(2024, 3, 31))),
    ("१० जून २०२४ को चोरी", Period(date(2024, 6, 10), date(2024, 6, 10))),
    ("before 1 July 2024", Period(date.min, date(2024, 6, 30))),
    ("until 5 August 2024", Period(date.min, date(2024, 8, 5))),
    ("after 30 June 2024", Period(date(2024, 7, 1), date.max)),
    ("on or after 30 June 2024", Period(date(2024, 6, 30), date.max)),
    ("not before 1 July 2024", Period(date(2024, 7, 1), date.max)),
    ("no later than 1 July 2024", Period(date.min, date(2024, 7, 1))),
    ("since August 2024", Period(date(2024, 8, 1), date.max)),
])
def test_a_stated_period_is_read_at_its_precision(text: str, period: Period) -> None:
    assert read_dates(text).periods == (period,)


@pytest.mark.parametrize("text", [
    "Under the Bharatiya Nyaya Sanhita, 2023, what is theft?",
    "Bharatiya Nyaya Sanhita (BNS), 2023 section 103",
    "under the 2023 Sanhita",
    "The Indian Penal Code (45 of 1860) defines cheating.",
    "What does BNS 2023 say about snatching?",
    "a proclamation under section 82 of Act 2 of 1974",
    "Act No. 45 of 2023 repealed the Code",
    "under the POCSO Act, 2012",
    "he stole a Rs 2000 note",
    "a fine of ₹2,000",
    "2000 rupees were taken",
    "the court may, in March proceedings",  # "may" and "march" as words
    "a 17 year old boy",
    "FIR No. 7/2024 under IPC",  # a case number, not July
    "Crl. Appeal 12/2024",
    "BNS (2023) offence",
    "Bharatiya Nyaya Sanhita (2023)",
])
def test_an_act_title_an_amount_or_a_word_is_not_a_date(text: str) -> None:
    assert read_dates(text).periods == ()


def test_a_contract_or_hours_are_not_mistaken_for_an_act_or_rupees() -> None:
    assert read_dates("a contract 2024").periods == (year(2024),)
    assert read_dates("after hours 2024").periods != ()


def test_an_impossible_date_is_ignored_rather_than_guessed() -> None:
    assert read_dates("on 31/02/2024").periods == ()


def test_a_month_without_its_year_marks_the_reading_incomplete() -> None:
    assert read_dates("between 15 June and 15 August 2024").incomplete
    assert read_dates("on 30 June or 1 July 2024").incomplete
    assert not read_dates("on 3 May 2024 and in June 2024").incomplete


@pytest.mark.parametrize(("text", "act", "reason"), [
    ("A theft on 30 June 2024", Act.IPC, Reason.DATE),
    ("A theft on 1 July 2024", Act.BNS, Reason.DATE),  # the commencement day is BNS
    ("Cheated in June 2024", Act.IPC, Reason.DATE),
    ("A murder in 2024", None, Reason.STRADDLES),
    # The offence comes first; the FIR and the trial follow it.
    ("Theft in June 2024, FIR filed in August 2024", Act.IPC, Reason.DATE),
    ("Trial starts in 2026 for a slap in July 2024", Act.BNS, Reason.DATE),
    ("What did section 124A of the IPC say?", Act.IPC, Reason.NAMED_CODE),
    ("भारतीय न्याय संहिता में चोरी क्या है?", Act.BNS, Reason.NAMED_CODE),
    ("What is the punishment for theft?", None, Reason.UNKNOWN),
    ("Under the IPC, what applies to a theft in August 2024?", Act.BNS, Reason.DATE),
    # Adversarial phrasings from review, written apart from the golden templates.
    ("Offence on 5 August 2024 under POCSO Act, 2012", Act.BNS, Reason.DATE),
    ("Bharatiya Nyaya Sanhita (BNS), 2023 section 103 murder", Act.BNS, Reason.NAMED_CODE),
    ("He stole a Rs 2000 note on 5 August 2024", Act.BNS, Reason.DATE),
    # A birth year is procedural, so it neither decides nor conflicts.
    ("Born in 1990, he cheated me on 12 Aug 2024", Act.BNS, Reason.DATE),
    ("In 2023 he started cheating; on 12 Aug 2024 he stole", None, Reason.CONFLICT),
    # The FIR date is about the case; the offence began in 2023.
    ("It started in 2023 and the FIR was filed on 5 August 2024", Act.IPC, Reason.DATE),
    ("Theft between 15 June and 15 August 2024", None, Reason.INCOMPLETE),
    ("from 3 May to 4 July 2024", None, Reason.INCOMPLETE),
    ("Theft before 1 July 2024", Act.IPC, Reason.DATE),
    ("Theft after 30 June 2024", Act.BNS, Reason.DATE),
    ("Theft by 5 August 2024", None, Reason.STRADDLES),  # could be either side
    ("१० जून २०२४ को चोरी, FIR 5 July 2024", Act.IPC, Reason.DATE),
    ("Stalking since August 2024", Act.BNS, Reason.DATE),
    # Second review round.
    ("FIR No. 7/2024 under IPC", Act.IPC, Reason.NAMED_CODE),
    ("Criminal Appeal 12/2024 cheating", None, Reason.UNKNOWN),
    ("BNS (2023) offence in 2025", Act.BNS, Reason.DATE),
    ("A man born in 1999 committed theft, punishment?", None, Reason.UNPLACED),
    ("I am 25, born in 1999; he stole my phone", None, Reason.UNPLACED),
    ("FIR filed in 2025, section 420 IPC", None, Reason.UNPLACED),
    ("complaint registered in 2025", None, Reason.UNPLACED),
    ("tried in 2025 for theft", None, Reason.UNPLACED),
    ("The theft was in May 2024 and the FIR was filed on 5 August 2024", Act.IPC, Reason.DATE),
    ("not before 1 July 2024", Act.BNS, Reason.DATE),
    ("no later than 1 July 2024", None, Reason.STRADDLES),
    ("on or after 30 June 2024", None, Reason.STRADDLES),
    ("He sent correspondence about IPC 420 on 3 March 2024", Act.IPC, Reason.DATE),
])
def test_the_route(text: str, act: Act | None, reason: Reason) -> None:
    decided = route(understand(text))

    assert (decided.act, decided.reason) == (act, reason)


def test_code_names_are_matched_as_words_not_substrings() -> None:
    assert understand("RECIPE for the BNSX").codes == frozenset()
    assert understand("Bharatiya Nyaya Sanhita and the Indian Penal Code").codes == {
        Act.BNS, Act.IPC}


@pytest.mark.parametrize(("text", "cited"), [
    ("What is the BNS equivalent of IPC section 420?", ("IPC:420",)),
    ("Which BNS section replaced section 302 of the Indian Penal Code?", ("IPC:302",)),
    ("Section 303 BNS corresponds to which IPC section?", ("BNS:303",)),
    ("Is 498a IPC still there?", ("IPC:498A",)),
    ("IPC s. 376DB and BNS 318(4)", ("IPC:376DB", "BNS:318")),
    ("धारा 420 आईपीसी क्या है?", ("IPC:420",)),
    ("धारा ४२० आईपीसी", ("IPC:420",)),
    ("section 302 IPC read with 34", ("IPC:302",)),
    # One number, one code: the nearest binding wins and is not claimed again.
    ("IPC 302 BNS equivalent", ("IPC:302",)),
    ("BNS 103 IPC counterpart", ("BNS:103",)),
    ("IPC section 420, BNS section 318 comparison", ("IPC:420", "BNS:318")),
    ("IPC 1860 section 420, BNS 2023 section 318", ("IPC:420", "BNS:318")),
    # Quantities and uncoded numbers are not citations.
    ("IPC 420 offence on 3 March 2024", ("IPC:420",)),
    ("under IPC 7 years sentence", ()),
    ("IPC 10 years imprisonment", ()),
    ("What is the punishment under section 138?", ()),
    ("under section 82 of Act 2 of 1974", ()),
    ("What does BNS 2023 say?", ()),
])
def test_a_section_is_a_reference_only_when_its_code_is_named(
        text: str, cited: tuple[str, ...]) -> None:
    assert understand(text).references == cited


@pytest.mark.parametrize(("text", "act", "reason"), [
    ("What is the BNS equivalent of IPC section 420?", Act.BNS, Reason.MAP),
    ("What was BNS 303 under the old Indian Penal Code?", Act.IPC, Reason.MAP),
    ("Theft in 2023: what is the BNS equivalent of IPC 379?", Act.BNS, Reason.MAP),
    ("IPC 302 BNS equivalent", Act.BNS, Reason.MAP),
    # Only one code named, but the words ask what it became.
    ("What replaced IPC 420?", Act.BNS, Reason.MAP),
    ("IPC 420 under the new law?", Act.BNS, Reason.MAP),
    ("IPC 420 offence equivalent in BNS", Act.BNS, Reason.MAP),
    # A cue word alone yields to an offence date; naming the other code does not.
    ("Is the new law applicable? IPC 420 cheating on 3 March 2024", Act.IPC, Reason.DATE),
    ("Cheating on 3 March 2024: what is the BNS equivalent of IPC 420?", Act.BNS, Reason.MAP),
    ("What did section 124A of the IPC say?", Act.IPC, Reason.NAMED_CODE),
    ("Is IPC 420 now BNS 318?", None, Reason.UNKNOWN),  # both cited: nothing to choose
])
def test_asking_what_a_section_became_routes_to_the_other_code(
        text: str, act: Act | None, reason: Reason) -> None:
    decided = route(understand(text), maps=True)

    assert (decided.act, decided.reason) == (act, reason)


def test_without_maps_the_v2_router_leaves_counterpart_questions_unrouted() -> None:
    assert route(understand("What is the BNS equivalent of IPC 420?")).act is None


def test_a_date_route_states_the_period_it_relied_on() -> None:
    decided = route(understand("Theft on 3 May 2024, FIR filed on 9 August 2024"))

    assert decided.act is Act.IPC
    assert decided.basis == Period(date(2024, 5, 3), date(2024, 5, 3))
