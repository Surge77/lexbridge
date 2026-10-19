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
    ("Imprisonment up to 7 years and a fine.", set(), set()),
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
