"""Run one retriever over the golden set and record the result.

Every run writes reports/runs/<name>.json: scores, the rank of every case, latency, and
what it ran against (bundle text hash, golden-set hash, model commit). reports/ablation.md
is regenerated from all run files, so the table is never edited by hand and every number
in it traces back to a file.

Usage:
    python -m lexbridge.eval.run artifacts/v2026-10-18 v1-hybrid   # a name from PIPELINES
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from statistics import quantiles
from typing import NotRequired, TypedDict

from lexbridge.eval.cases import Case
from lexbridge.eval.metrics import KS, first_rank, score
from lexbridge.retrieve.base import Retriever

RUNS = Path("reports/runs")
# Single-query latency is what a user waits for, so it is timed one query at a time on
# a fixed sample rather than inferred from the batched run.
LATENCY_SAMPLE = 100

# hit@k, mrr and wrong_regime@1 as fractions, plus n; wrong_regime@1 is None where no case
# in the group has a counterpart in the other code.
ScoreRow = dict[str, float | None]


class Measured(TypedDict):
    query_ms: dict[str, float]
    scores: dict[str, ScoreRow]
    # Per case, so two runs can be diffed case by case, not only on averages.
    ranks: dict[str, int | None]


class RunRecord(Measured):
    name: str
    retriever: str
    embedder: str | None
    parameters: int | None
    # Includes the embedding pass only when the vectors were not cached yet.
    index_seconds: float
    bundle_sections_sha256: str
    golden_sha256: str
    # The rung's decision; absent from runs recorded before notes existed.
    note: NotRequired[str]
    # Router decisions against the golden codes, for pipelines that route.
    routing: NotRequired[dict[str, int]]


def _latency_sample(cases: Sequence[Case]) -> list[str]:
    # Evenly spaced within each category, not across the file: the generated templates
    # come first and are short, so a plain stride never reached the longer hand-written
    # and Hindi questions a user actually types.
    groups: dict[str, list[str]] = defaultdict(list)
    for case in cases:
        groups[case.category.value].append(case.question)
    per_group = max(1, LATENCY_SAMPLE // len(groups))
    return [q for _, questions in sorted(groups.items())
            for q in questions[::max(1, len(questions) // per_group)][:per_group]]


def _latency_ms(retriever: Retriever, cases: Sequence[Case]) -> dict[str, float]:
    sample = _latency_sample(cases)
    retriever.search(sample[0], max(KS))  # warm-up: first-call allocations are not latency
    timings = []
    for question in sample:
        start = time.perf_counter()
        retriever.search(question, max(KS))
        timings.append((time.perf_counter() - start) * 1000)
    if len(timings) < 2:
        return {"p50": round(timings[0], 2), "p95": round(timings[0], 2)}
    cuts = quantiles(timings, n=20, method="inclusive")
    return {"p50": round(cuts[9], 2), "p95": round(cuts[18], 2)}


def evaluate(retriever: Retriever, cases: Sequence[Case]) -> Measured:
    questions = [c.question for c in cases]
    rankings = [[h.section_id for h in hits]
                for hits in retriever.search_many(questions, max(KS))]
    scores = score(cases, rankings)
    return {
        "query_ms": _latency_ms(retriever, cases),
        "scores": {
            group: {"n": s.n, **{f"hit@{k}": round(v, 4) for k, v in s.hit.items()},
                    "mrr": round(s.mrr, 4),
                    "wrong_regime@1": None if s.wrong_regime_at_1 is None
                    else round(s.wrong_regime_at_1, 4)}
            for group, s in scores.items()
        },
        "ranks": {c.id: first_rank(c.targets, ranked)
                  for c, ranked in zip(cases, rankings, strict=True) if c.targets},
    }


def write_run(record: RunRecord, runs: Path = RUNS) -> Path:
    runs.mkdir(parents=True, exist_ok=True)
    path = runs / f"{record['name']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")
    return path


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:  # pragma: no cover - loads a real model
    from lexbridge.bundle import load_bundle
    from lexbridge.eval.cases import read_cases
    from lexbridge.eval.golden import GOLDEN
    from lexbridge.eval.metrics import routing
    from lexbridge.eval.report import write_table
    from lexbridge.query.route import route
    from lexbridge.query.understand import understand
    from lexbridge.retrieve.bm25 import BM25Index
    from lexbridge.retrieve.dense import DenseIndex
    from lexbridge.retrieve.embed import SentenceTransformerEmbedder
    from lexbridge.retrieve.pipeline import PIPELINES, Pipeline
    from lexbridge.retrieve.rerank import CrossEncoderScorer

    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("pipeline", choices=sorted(PIPELINES))
    args = parser.parse_args()

    spec = PIPELINES[args.pipeline]
    bundle = load_bundle(args.bundle)
    embedder = SentenceTransformerEmbedder(spec.embedder)
    start = time.perf_counter()
    dense = DenseIndex.build(bundle, embedder, cache_dir=args.bundle / "vectors")
    lexical = BM25Index.build(bundle) if spec.lexical else None
    index_seconds = round(time.perf_counter() - start, 1)
    scorer = CrossEncoderScorer(spec.reranker) if spec.reranker else None
    pipeline = Pipeline(bundle, dense, lexical=lexical, scorer=scorer,
                        rerank_depth=spec.rerank_depth, routed=spec.route,
                        references=spec.references)
    cases = read_cases(GOLDEN)
    record: RunRecord = {
        "name": args.pipeline,
        "retriever": spec.describe(),
        "embedder": embedder.name,
        "parameters": embedder.parameters + (scorer.parameters if scorer else 0),
        "index_seconds": index_seconds,
        "bundle_sections_sha256": bundle.sections_sha256,
        "golden_sha256": sha256_of(GOLDEN),
        "note": spec.note,
        **evaluate(pipeline, cases),
    }
    if spec.route:
        record["routing"] = routing(
            cases, lambda q: route(understand(q), maps=spec.references).act)
    print(write_run(record), "->", write_table())


if __name__ == "__main__":  # pragma: no cover
    main()
