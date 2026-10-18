from __future__ import annotations

import pytest
from pydantic import ValidationError

from lexbridge.schema import Act, Section, Status, section_key


def make_section(**overrides: object) -> Section:
    fields: dict[str, object] = {
        "act": Act.BNS,
        "number": "318",
        "title": "Cheating",
        "text": "318. (1) Whoever, by deceiving any person...",
        "chapter": "XVII",
        "status": Status.IN_FORCE,
        "source_key": "bns_original",
        "page": 70,
    }
    fields.update(overrides)
    return Section.model_validate(fields)


def test_id_joins_act_and_number() -> None:
    assert make_section().id == "BNS:318"
    assert make_section(act=Act.IPC, number="498A").id == "IPC:498A"


def test_section_is_immutable() -> None:
    section = make_section()
    with pytest.raises(ValidationError):
        section.title = "Something else"  # type: ignore[misc]


@pytest.mark.parametrize("number", ["", "0", "318 ", "a1", "4A1", "1234"])
def test_malformed_section_numbers_are_rejected(number: str) -> None:
    with pytest.raises(ValidationError):
        make_section(number=number)


def test_section_key_orders_lettered_inserts_between_their_neighbours() -> None:
    numbers = ["121", "120B", "120", "120A", "498A", "498", "499"]
    assert sorted(numbers, key=section_key) == [
        "120", "120A", "120B", "121", "498", "498A", "499",
    ]
