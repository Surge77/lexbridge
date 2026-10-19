"""Answer one question: route, retrieve, ask the model, check it, and say what was assumed.

The order is fixed by what each part can be trusted with. The router decides the code;
retrieval decides the sources; the model only writes, and judges whether the sources
answer the question at all. Every section the reply names is then checked against the
sources and the question. A reply that names an unsupported section gets one chance to
answer again; whatever it still names without support is cut out.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from lexbridge.answer.llm import Completion
from lexbridge.answer.prompt import (
    MalformedReplyError,
    assumption,
    clarification,
    messages,
    parse,
)
from lexbridge.answer.verify import strip_unsupported, unsupported
from lexbridge.bundle import Bundle
from lexbridge.query.route import Reason, route
from lexbridge.query.understand import understand
from lexbridge.retrieve.base import Retriever
from lexbridge.schema import Act, Section

# Sources shown to the model. Retrieval puts the answer in the top 4 for most text
# questions (reports/ablation.md), and every extra source costs tokens on a free tier.
SOURCES = 4
MAX_ATTEMPTS = 2
SCOPE_SYSTEM = (
    "Decide if the question asks about an offence or general principle of Indian "
    "criminal law of the kind these provisions deal with. Questions about other laws "
    "(civil, tax, traffic fines, cheques), procedure (bail, FIR, divorce) or unrelated "
    'topics are not. Reply with JSON only: {"in_scope": true | false}')
NO_ANSWER = ("I could not produce an answer whose every section is supported by the "
             "provisions I retrieved, so I am not giving one.")


class Status(StrEnum):
    ANSWERED = "answered"
    CLARIFY = "clarify"  # the code depends on a date the question does not settle
    DECLINED = "declined"  # outside these codes, or the sources do not answer it


class Chat(Protocol):
    def complete(self, messages: Sequence[Mapping[str, str]], *, max_tokens: int = 700,
                 json_mode: bool = True) -> Completion: ...


@dataclass(frozen=True)
class Answer:
    status: Status
    text: str
    citations: tuple[str, ...]
    act: Act | None
    reason: Reason
    # For evaluation: what the first draft named without support, and what was cut.
    first_draft_unsupported: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    calls: list[Completion] = field(default_factory=list)


def _in_scope(chat: Chat, question: str, sources: Sequence[Section],
              calls: list[Completion]) -> bool:
    titles = "\n".join(f"- {s.act} {s.number}: {s.title}" for s in sources)
    completion = chat.complete([
        {"role": "system", "content": SCOPE_SYSTEM},
        {"role": "user", "content": f"Provisions:\n{titles}\n\nQuestion: {question}"},
    ], max_tokens=50)
    calls.append(completion)
    try:
        return bool(json.loads(completion.text).get("in_scope"))
    except (json.JSONDecodeError, AttributeError):
        return True  # unsure: asking for the date is the cautious answer


def _candidates(sources: Sequence[Section]) -> list[Section]:
    """The first source from each code, to show what the answer will turn on."""
    first: dict[Act, Section] = {}
    for s in sources:
        first.setdefault(s.act, s)
    return [first[a] for a in (Act.IPC, Act.BNS) if a in first]


def answer(question: str, *, retriever: Retriever, bundle: Bundle, chat: Chat) -> Answer:
    facts = understand(question)
    decided = route(facts, maps=True)
    sources = [bundle.section(h.section_id) for h in retriever.search(question, SOURCES)]
    calls: list[Completion] = []

    if decided.act is None:
        if not _in_scope(chat, question, sources, calls):
            return Answer(Status.DECLINED, "This is outside the Indian Penal Code and the "
                          "Bharatiya Nyaya Sanhita, which are the only laws I cover.", (),
                          None, decided.reason, calls=calls)
        return Answer(Status.CLARIFY, clarification(decided, _candidates(sources)), (), None,
                      decided.reason, calls=calls)

    allowed = {s.id for s in sources} | set(facts.references)
    convo = messages(question, sources, decided, facts.references)
    first_bad: list[str] | None = None
    reply = None
    for _ in range(MAX_ATTEMPTS):
        completion = chat.complete(convo)
        calls.append(completion)
        try:
            reply = parse(completion.text, len(sources))
        except MalformedReplyError as e:
            reply = None
            convo = [*convo, {"role": "assistant", "content": completion.text},
                     {"role": "user", "content": f"That was not valid ({e}). Reply with "
                      "the JSON object only."}]
            continue
        if reply.declined:
            return Answer(Status.DECLINED, reply.text, (), decided.act, decided.reason,
                          calls=calls)
        bad = unsupported(reply.text, allowed)
        if first_bad is None:
            first_bad = bad
        if not bad:
            break
        convo = [*convo, {"role": "assistant", "content": completion.text},
                 {"role": "user", "content": "Your answer names sections that are not in "
                  f"the sources: {', '.join(bad)}. Answer again, naming only sections "
                  "that appear in the numbered sources or the question."}]

    if reply is None:
        return Answer(Status.DECLINED, NO_ANSWER, (), decided.act, decided.reason,
                      calls=calls)
    text, removed = strip_unsupported(reply.text, allowed)
    if not text:
        return Answer(Status.DECLINED, NO_ANSWER, (), decided.act, decided.reason,
                      tuple(first_bad or ()), tuple(removed), calls)
    lead = assumption(decided, facts.references)
    return Answer(Status.ANSWERED, f"{lead} {text}".strip(),
                  tuple(sources[n - 1].id for n in reply.citations), decided.act,
                  decided.reason, tuple(first_bad or ()), tuple(removed), calls)
