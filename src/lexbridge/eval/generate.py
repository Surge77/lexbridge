"""Cases generated from the correspondence graph, so their answers need no human labelling.

Map lookups come straight from replaced_by edges. Topical questions are templated from
IPC section titles. Each section is asked once, and successive sections rotate through a
date before 1 July 2024, a date after it, and no date, so each regime gets a third of the
sections (different sections, so before/after scores are not a paired comparison).
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from lexbridge.bundle import Bundle
from lexbridge.eval.cases import Case, Category, case_id
from lexbridge.schema import Act, Section, Status

IPC_TO_BNS = (
    "What is the BNS equivalent of IPC section {n}?",
    "IPC {n} is now which section of the Bharatiya Nyaya Sanhita?",
    "Which BNS section replaced section {n} of the Indian Penal Code?",
)
BNS_TO_IPC = (
    "Which IPC section did BNS section {n} replace?",
    "What was BNS {n} under the old Indian Penal Code?",
    "Section {n} BNS corresponds to which IPC section?",
)
TOPIC_DATED = (
    "What does the law say about {t}? It happened {d}.",
    "Which section deals with {t} for an offence committed {d}?",
    "{T}: which provision applies to an incident {d}?",
)
TOPIC_UNDATED = (
    "What does the law say about {t}?",
    "Which section deals with {t}?",
)
# A month-only phrase is pinned to the 1st; no month here straddles the cutover.
BEFORE = (
    (date(2019, 11, 4), "on 4 November 2019"),
    (date(2022, 3, 1), "in March 2022"),
    (date(2023, 8, 21), "on 21 August 2023"),
    (date(2024, 6, 28), "on 28 June 2024"),
)
AFTER = (
    (date(2024, 7, 15), "on 15 July 2024"),
    (date(2025, 4, 1), "in April 2025"),
    (date(2025, 12, 2), "on 2 December 2025"),
    (date(2026, 2, 9), "on 9 February 2026"),
)


def _make(category: Category, question: str, **fields: object) -> Case:
    return Case.model_validate(
        {"id": case_id(category, question), "category": category, "question": question,
         **fields}
    )


def map_cases(bundle: Bundle) -> list[Case]:
    cases: list[Case] = []
    for i, s in enumerate(x for x in bundle.sections if bundle.replaced_by(x.id)):
        question = IPC_TO_BNS[i % len(IPC_TO_BNS)].format(n=s.number)
        cases.append(_make(Category.MAP_IPC_TO_BNS, question, offence_date=None,
                           answer_act=Act.BNS, targets=bundle.replaced_by(s.id),
                           wrong_regime=(s.id,), needs_clarification=False))
    for i, s in enumerate(x for x in bundle.sections if bundle.replaces(x.id)):
        question = BNS_TO_IPC[i % len(BNS_TO_IPC)].format(n=s.number)
        cases.append(_make(Category.MAP_BNS_TO_IPC, question, offence_date=None,
                           answer_act=Act.IPC, targets=bundle.replaces(s.id),
                           wrong_regime=(s.id,), needs_clarification=False))
    return cases


def _topics(bundle: Bundle) -> list[Section]:
    ipc = [s for s in bundle.sections if s.act is Act.IPC and s.status is Status.IN_FORCE]
    # A heading shared by several sections ("Punishment") names no one provision.
    titles = Counter(s.title for s in ipc)
    return [s for s in ipc if titles[s.title] == 1 and bundle.replaced_by(s.id)]


def topic_cases(bundle: Bundle) -> list[Case]:
    cases: list[Case] = []
    for i, s in enumerate(_topics(bundle)):
        topic = s.title.rstrip(".")
        t = topic[0].lower() + topic[1:]
        bns = bundle.replaced_by(s.id)
        turn, slot = divmod(i, 3)
        if slot == 2:
            question = TOPIC_UNDATED[turn % len(TOPIC_UNDATED)].format(t=t)
            cases.append(_make(Category.TOPIC_UNDATED, question, offence_date=None,
                               answer_act=None, targets=(s.id, *bns), wrong_regime=(),
                               needs_clarification=True))
            continue
        day, phrase = (BEFORE, AFTER)[slot][turn % len(BEFORE)]
        question = TOPIC_DATED[turn % len(TOPIC_DATED)].format(t=t, T=topic, d=phrase)
        targets, wrong = ((s.id,), bns) if slot == 0 else (bns, (s.id,))
        cases.append(_make(Category.TOPIC_DATED, question, offence_date=day,
                           answer_act=(Act.IPC, Act.BNS)[slot], targets=targets,
                           wrong_regime=wrong, needs_clarification=False))
    return cases
