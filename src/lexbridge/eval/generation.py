"""Evaluate whole answers, not rankings: what a user would actually be told.

The free tier allows ~8,000 tokens a minute, so the run uses a fixed, stratified subset:
every hand-written case and a few evenly spaced cases from each generated category. The
headline gate is that no final answer names a section its sources do not support.

Usage:
    python -m lexbridge.eval.generation artifacts/v2026-10-18 v3-references
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from statistics import fmean, quantiles
from typing import TypedDict

from lexbridge.eval.cases import Case, Category
from lexbridge.schema import Act

GENERATED = (Category.MAP_IPC_TO_BNS, Category.MAP_BNS_TO_IPC, Category.TOPIC_DATED,
             Category.TOPIC_UNDATED)
PER_GENERATED = 8


class Outcome(TypedDict):
    id: str
    category: str
    status: str  # answered | clarify | declined
    act: str | None
    citations: list[str]
    text: str
    first_draft_unsupported: list[str]
    final_unsupported: list[str]
    calls: int
    models: list[str]  # the model behind each call, in order
    seconds: float


class GenerationScores(TypedDict):
    n: int
    # The gate: share of answers whose final text names a section nothing supports.
    hallucinated: float
    # What verification caught: share whose first draft did.
    first_draft_unsupported: float
    # Of in-scope questions with a known code that were answered: a target was cited,
    # and the answer came from the right code.
    correct_section: float | None
    right_code: float | None
    clarify_precision: float | None
    clarify_recall: float | None
    out_of_scope_declined: float | None
    in_scope_declined: float | None
    seconds_p50: float
    seconds_p95: float


def subset(cases: Sequence[Case]) -> list[Case]:
    hand = [c for c in cases if c.category not in GENERATED]
    picked: list[Case] = []
    for category in GENERATED:
        group = [c for c in cases if c.category is category]
        step = max(1, len(group) // PER_GENERATED)
        picked += group[::step][:PER_GENERATED]
    return hand + picked


def expected_status(case: Case) -> str:
    if case.category is Category.OUT_OF_SCOPE:
        return "declined"
    return "clarify" if case.needs_clarification else "answered"


def _share(flags: Sequence[bool]) -> float | None:
    return round(fmean(flags), 4) if flags else None


def score(cases: Sequence[Case], outcomes: Sequence[Outcome]) -> GenerationScores:
    pairs = list(zip(cases, outcomes, strict=True))
    answered = [(c, o) for c, o in pairs if o["status"] == "answered"
                and expected_status(c) == "answered"]
    asked = [(c, o) for c, o in pairs if o["status"] == "clarify"]
    should_ask = [(c, o) for c, o in pairs if expected_status(c) == "clarify"]
    oos = [o for c, o in pairs if c.category is Category.OUT_OF_SCOPE]
    in_scope = [o for c, o in pairs if c.category is not Category.OUT_OF_SCOPE]
    seconds = [o["seconds"] for o in outcomes]
    cuts = quantiles(seconds, n=20, method="inclusive") if len(seconds) > 1 else seconds * 19
    return {
        "n": len(pairs),
        "hallucinated": round(fmean(bool(o["final_unsupported"]) for o in outcomes), 4),
        "first_draft_unsupported": round(
            fmean(bool(o["first_draft_unsupported"]) for o in outcomes), 4),
        "correct_section": _share([bool(set(o["citations"]) & set(c.targets))
                                   for c, o in answered]),
        "right_code": _share([o["act"] == (c.answer_act and c.answer_act.value)
                              for c, o in answered]),
        "clarify_precision": _share([expected_status(c) == "clarify" for c, _ in asked]),
        "clarify_recall": _share([o["status"] == "clarify" for _, o in should_ask]),
        "out_of_scope_declined": _share([o["status"] == "declined" for o in oos]),
        "in_scope_declined": _share([o["status"] == "declined" for o in in_scope]),
        "seconds_p50": round(cuts[9], 2),
        "seconds_p95": round(cuts[18], 2),
    }


def by_category(cases: Sequence[Case], outcomes: Sequence[Outcome]
                ) -> dict[str, GenerationScores]:
    groups: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(cases):
        groups[c.category.value].append(i)
    return {name: score([cases[i] for i in idx], [outcomes[i] for i in idx])
            for name, idx in sorted(groups.items())}


def with_patience(call: Callable[[], Outcome], *, waits: Sequence[float] = (20, 40, 60, 60),
                  retry_on: type[Exception] = Exception,
                  sleep: Callable[[float], None] = time.sleep) -> Outcome:
    """Wait out a free tier's per-minute limit instead of recording a failure."""
    for wait in waits:
        try:
            return call()
        except retry_on:
            sleep(wait)
    return call()


def code_of(act: Act | None) -> str | None:
    return act.value if act else None


def load_checkpoint(path: Path) -> dict[str, Outcome]:
    """Outcomes already paid for by an earlier, interrupted run of the same name."""
    if not path.exists():
        return {}
    outcomes: list[Outcome] = [json.loads(line) for line in
                               path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {o["id"]: o for o in outcomes}


def append_checkpoint(path: Path, outcome: Outcome) -> None:
    # One line per answer, written as it arrives: a long rate-limited run that is
    # interrupted loses one answer, not all of them.
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(outcome, ensure_ascii=False) + "\n")


def main() -> None:  # pragma: no cover - calls a real model over the network
    import argparse

    from lexbridge.answer.llm import CHAIN, Gateway, LLMUnavailableError
    from lexbridge.answer.service import answer
    from lexbridge.answer.verify import unsupported
    from lexbridge.bundle import load_bundle
    from lexbridge.eval.cases import read_cases
    from lexbridge.eval.golden import GOLDEN
    from lexbridge.retrieve.dense import DenseIndex
    from lexbridge.retrieve.embed import SentenceTransformerEmbedder
    from lexbridge.retrieve.pipeline import PIPELINES, Pipeline
    from lexbridge.retrieve.rerank import CrossEncoderScorer

    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("pipeline", choices=sorted(PIPELINES))
    parser.add_argument("--name", help="run name; defaults to gen-<pipeline>")
    args = parser.parse_args()

    spec = PIPELINES[args.pipeline]
    bundle = load_bundle(args.bundle)
    dense = DenseIndex.build(bundle, SentenceTransformerEmbedder(spec.embedder),
                             cache_dir=args.bundle / "vectors")
    scorer = CrossEncoderScorer(spec.reranker) if spec.reranker else None
    retriever = Pipeline(bundle, dense, scorer=scorer, rerank_depth=spec.rerank_depth,
                         routed=spec.route, references=spec.references)
    chat = Gateway(CHAIN)
    cases = subset(read_cases(GOLDEN))

    def run(case: Case) -> Outcome:
        start = time.perf_counter()
        a = answer(case.question, retriever=retriever, bundle=bundle, chat=chat)
        return {"id": case.id, "category": case.category.value, "status": a.status.value,
                "act": code_of(a.act), "citations": list(a.citations), "text": a.text,
                "first_draft_unsupported": list(a.first_draft_unsupported),
                # Checked here again, independently of the service's own filtering.
                "final_unsupported": unsupported(a.text, a.allowed),
                "calls": len(a.calls), "models": [c.model for c in a.calls],
                "seconds": round(time.perf_counter() - start, 2)}

    name = args.name or f"gen-{args.pipeline}"
    out = Path("reports/generation") / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    progress = out.with_suffix(".partial.jsonl")
    done = load_checkpoint(progress)
    outcomes = []
    for i, case in enumerate(cases, 1):
        if case.id not in done:
            done[case.id] = with_patience(lambda case=case: run(case),
                                          retry_on=LLMUnavailableError)
            append_checkpoint(progress, done[case.id])
        outcomes.append(done[case.id])
        print(f"{i}/{len(cases)} {case.id} -> {outcomes[-1]['status']}", flush=True)

    record = {"name": name, "pipeline": args.pipeline, "providers": chat.providers,
              # Which models wrote the answers: a provider that ran out mid-run hands over.
              "models": dict(Counter(m for o in outcomes for m in o["models"])),
              "scores": score(cases, outcomes),
              "by_category": by_category(cases, outcomes), "outcomes": outcomes}
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    progress.unlink()
    print(json.dumps(record["scores"], indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
