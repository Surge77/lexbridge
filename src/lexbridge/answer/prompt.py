"""What the model is told, and what is said without asking the model at all.

The code a question is answered from is decided by the router, never by the model, and
the answer opens with that decision in plain words ("Assuming the offence was committed
on 5 August 2024, ..."), so a misread date is visible to the reader. Clarifying questions
are written here from templates: they need no model, and so cannot cite anything.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from lexbridge.query.dates import Period
from lexbridge.query.route import Reason, Route
from lexbridge.schema import Act, Section

CODE_NAME = {Act.IPC: "Indian Penal Code (IPC)", Act.BNS: "Bharatiya Nyaya Sanhita (BNS)"}
# Long sections are cut: the free tier allows ~8,000 tokens a minute, and the operative
# words of a section (definition, punishment) come first.
SOURCE_CHARS = 1200
CUTOVER = (
    "Which law applies depends on when the offence was committed: the Indian Penal Code "
    "for offences before 1 July 2024, the Bharatiya Nyaya Sanhita from that date on.")
WHY_ASK = {
    Reason.STRADDLES: "The period you gave covers both sides of 1 July 2024.",
    Reason.CONFLICT: "The dates you gave point to different laws.",
    Reason.INCOMPLETE: "A date in your question is missing its year.",
    Reason.UNPLACED: "The dates you gave are about the case (a filing, a trial, a birth), "
                     "not about when the offence happened.",
    Reason.UNKNOWN: "Your question does not say when it happened.",
}
SYSTEM = """You answer questions about India's criminal law using ONLY the numbered \
sources below, which are sections of the {code}. {assumption}
Rules:
- Use only what the sources say. Do not add facts, case law or other Acts.
- Name a section number only if it appears in a source heading or in the question.
- If the sources do not answer the question, or it is not about these offences, set \
"status" to "declined" and say briefly what the sources do not cover.
- Write plainly for a non-lawyer, in the language of the question, in under 150 words.
Reply with JSON only: {{"status": "answered" | "declined", "answer": "<text>", \
"citations": [<numbers of the sources you relied on>]}}"""


def _day(d: date) -> str:
    return f"{d.day} {d:%B} {d.year}"


def describe(period: Period) -> str:
    if period.start == date.min:
        return f"on or before {_day(period.end)}"
    if period.end == date.max:
        return f"on or after {_day(period.start)}"
    if period.start == period.end:
        return f"on {_day(period.start)}"
    if (period.start.day == 1 and period.end.month == period.start.month
            and (period.end + timedelta(days=1)).month != period.end.month):
        return f"in {period.start:%B} {period.start.year}"
    if period.start == date(period.start.year, 1, 1) and period.end == date(
            period.start.year, 12, 31):
        return f"in {period.start.year}"
    return f"between {_day(period.start)} and {_day(period.end)}"


def assumption(route: Route, cited: Sequence[str] = ()) -> str:
    """The decision the answer rests on, stated so a reader can correct it."""
    if route.act is None:
        return ""
    code = CODE_NAME[route.act]
    if route.reason is Reason.DATE and route.basis is not None:
        return f"Assuming the offence was committed {describe(route.basis)}, the {code} applies."
    if route.reason is Reason.MAP:
        named = ", ".join(s.replace(":", " ") for s in cited) or "the section you named"
        return f"You asked what {named} corresponds to in the {code}."
    return f"You asked about the {code}."


def clarification(route: Route, candidates: Sequence[Section]) -> str:
    lines = [WHY_ASK.get(route.reason, WHY_ASK[Reason.UNKNOWN]), CUTOVER,
             "When was the offence committed?"]
    if candidates:
        named = "; ".join(f"{s.act} {s.number} ({s.title})" for s in candidates)
        lines.append(f"The provisions that look relevant are {named}.")
    return " ".join(lines)


def messages(question: str, sources: Sequence[Section], route: Route,
             cited: Sequence[str] = ()) -> list[dict[str, str]]:
    if route.act is None:
        raise ValueError("only a routed question is sent to the model; ask for the date")
    blocks =[f"[{i}] {s.act} section {s.number}: {s.title}\n{s.text[:SOURCE_CHARS]}"
              for i, s in enumerate(sources, 1)]
    return [
        {"role": "system", "content": SYSTEM.format(code=CODE_NAME[route.act],
                                                     assumption=assumption(route, cited))},
        {"role": "user", "content": "Sources:\n\n" + "\n\n".join(blocks)
         + f"\n\nQuestion: {question}"},
    ]


@dataclass(frozen=True)
class Reply:
    declined: bool
    text: str
    # 1-based source numbers, as the model cited them; unknown numbers already dropped.
    citations: tuple[int, ...]


class MalformedReplyError(ValueError):
    """The model's reply is not the JSON object the prompt asked for."""


def parse(raw: str, n_sources: int) -> Reply:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise MalformedReplyError(f"not JSON: {e}") from e
    if not isinstance(data, dict) or data.get("status") not in ("answered", "declined"):
        raise MalformedReplyError("missing or unknown status")
    text = data.get("answer")
    if not isinstance(text, str):
        raise MalformedReplyError("answer is not text")
    cited = data.get("citations") or []
    numbers = tuple(dict.fromkeys(
        n for n in cited if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= n_sources))
    return Reply(data["status"] == "declined", text.strip(), numbers)
