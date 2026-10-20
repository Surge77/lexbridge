from __future__ import annotations

import pytest

from lexbridge.answer.verify import mentions, strip_unsupported, unsupported

SOURCES = {"BNS:318", "BNS:319", "IPC:420"}


@pytest.mark.parametrize(("text", "coded", "bare"), [
    ("Cheating is punishable under BNS 318(4).", {"BNS:318"}, set()),
    ("See section 420 of the IPC.", {"IPC:420"}, {"420"}),
    ("Sections 303 and 304 cover theft.", set(), {"303", "304"}),
    ("under s. 498A and §420", set(), {"498A", "420"}),
    # A sub-section is not a section number.
    ("Its sub-section (4) applies.", set(), set()),
    ("The equivalent is BNS section 117(2).", {"BNS:117"}, {"117"}),
    ("See sections 318(4) and 319(2)(a).", set(), {"318", "319"}),
    ("Imprisonment up to 7 years and a fine.", set(), set()),
    # A quantity after a section is not another section in a list.
    ("Under section 318, 7 years' jail.", set(), {"318"}),
    ("Section 318 or 3 years", set(), {"318"}),
    # Hindi answers: the word for section, and Devanagari digits.
    ("धारा 999 लागू है।", set(), {"999"}),
    ("धारा ४२० लागू", set(), {"420"}),
])
def test_mentions_are_read_with_and_without_their_code(
        text: str, coded: set[str], bare: set[str]) -> None:
    assert mentions(text) == (coded, bare)


def test_a_number_from_the_sources_is_supported_in_either_form() -> None:
    assert unsupported("BNS 318 and section 319 apply; IPC 420 was the old law.", SOURCES) == []


def test_a_number_no_source_supports_is_reported() -> None:
    assert unsupported("Also see section 415 and BNS 320.", SOURCES) == ["415", "BNS:320"]


def test_the_right_number_in_the_wrong_code_is_unsupported() -> None:
    # 318 is a BNS source; "IPC 318" is a different provision the sources do not show.
    assert unsupported("IPC 318 applies.", SOURCES) == ["IPC:318"]


def test_stripping_removes_only_the_sentences_with_unsupported_mentions() -> None:
    text = "BNS 318 punishes cheating. Section 999 adds more. The fine is unlimited."

    kept, removed = strip_unsupported(text, SOURCES)

    assert kept == "BNS 318 punishes cheating. The fine is unlimited."
    assert removed == ["999"]


@pytest.mark.parametrize("text", [
    # "s." and "Sec." end in a full stop but do not end the sentence.
    "Sec. 999 applies. BNS 318 punishes cheating.",
    "It falls under s. 999 of it. BNS 318 punishes cheating.",
    "धारा 999 लागू है। BNS 318 punishes cheating.",
])
def test_an_abbreviation_does_not_split_a_mention_from_its_sentence(text: str) -> None:
    assert strip_unsupported(text, SOURCES) == ("BNS 318 punishes cheating.", ["999"])
