"""The retrieval ladder: each rung is a named configuration with its own ablation row.

A run is named after its PipelineSpec, so `reports/runs/v1-hybrid.json` always means the
same stages. Rungs are cumulative; a rung that does not earn its cost is switched off in
the later specs, and the reason recorded in reports/ablation.md.

Stage order: dense (+ BM25 fusion) -> keep only the routed code -> rerank -> put cited
sections first -> cut to k. Filtering before reranking spends the expensive model only on
sections that can be right.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from lexbridge.bundle import Bundle
from lexbridge.query.route import route
from lexbridge.query.understand import Facts, understand
from lexbridge.retrieve.base import Hit
from lexbridge.retrieve.bm25 import BM25Index
from lexbridge.retrieve.dense import DenseIndex
from lexbridge.retrieve.fusion import rrf
from lexbridge.retrieve.rerank import Scorer, rerank

# How deep each first-stage list goes before fusion, filtering and cutting to k. Deep
# enough that routing away the other code's half still leaves a full top 10.
CANDIDATES = 50
# The score of a cited section: above any cosine, BM25, RRF or cross-encoder score, and
# finite, because infinity is not valid JSON and these scores will reach an API response.
CITED_SCORE = 1e9


@dataclass(frozen=True)
class PipelineSpec:
    embedder: str
    lexical: bool = False
    reranker: str | None = None
    rerank_depth: int = 0
    route: bool = False
    # Cited sections ("IPC 420") go first, resolved through the graph into the routed code;
    # also turns on map routing, since a map question is a citation plus the other code.
    references: bool = False
    # What the rung's row showed and what was decided, rendered into reports/ablation.md.
    note: str = ""

    def describe(self) -> str:
        stages = ["dense"]
        stages += ["bm25/rrf"] if self.lexical else []
        stages += ["route"] if self.route else []
        stages += [f"rerank:{self.reranker}@{self.rerank_depth}"] if self.reranker else []
        stages += ["references"] if self.references else []
        return "+".join(stages)


PIPELINES = {
    "v0-dense-e5-small": PipelineSpec("e5-small"),
    "v0-dense-bge-m3": PipelineSpec("bge-m3", note=(
        "Chosen embedder: +12.6 macro hit@5 over e5-small for 9x the query latency; on the "
        "hand-written cases it finds 10 answers e5 misses and misses 2 that e5 finds. "
        "See docs/decisions/0002-bge-m3-for-dense-retrieval.md.")),
    "v1-hybrid": PipelineSpec("bge-m3", lexical=True, note=(
        "Not kept. Macro hit@5 fell 64.3 -> 62.5 (lay lost 2 cases, tricky gained 1), and "
        "as a candidate generator it found no more: recall@20 84.3 vs 83.6, recall@50 87.6 "
        "vs 88.1. Its halved wrong-regime@1 is incidental; BM25 knows nothing of dates. "
        "Later rungs build on dense alone; the code stays so this row reproduces.")),
    # Deterministic stages are measured before the expensive model, so the reranker has to
    # earn its latency on top of them rather than take credit for what routing fixes.
    "v2-route": PipelineSpec("bge-m3", route=True, note=(
        "Kept. hit@1 36.9 -> 52.0 on the text categories: 131 cases gained, none lost "
        "(sign test p ~ 1e-40). wrong-regime@1 25.6 -> 0. The router decided 584 of 584 "
        "in-scope non-map questions correctly with no confident error; map lookups name "
        "both codes and are left unrouted at this rung.")),
    "v3-references": PipelineSpec("bge-m3", route=True, references=True, note=(
        "Kept; the default pipeline. Map lookups 1% -> 100% hit@5, close to by construction "
        "(the same project wrote the templates and the citation patterns; unit tests carry "
        "other phrasings). Text macro hit@5 +2.1 from cited sections in tricky questions. "
        "The router now decides all 1,466 in-scope questions with no confident error.")),
    # Depth 10 is set by the latency budget (about 1 s of CPU), not tuned on the golden set.
    "v4-rerank": PipelineSpec("bge-m3", route=True, references=True,
                              reranker="mminilm-l12", rerank_depth=10, note=(
        "Not in the default pipeline yet. Text macro hit@5 +4.2 (10 cases gained, 2 lost, "
        "p ~ 0.04; hand-written +5/-1, not significant; hit@1 +47/-37, not significant) for "
        "query p50 100 -> 1,294 ms. Decided in P5 on answer quality and on the deploy host's "
        "latency. bge-reranker-v2-m3 took 15 s per query and was not run.")),
}


class Pipeline:
    def __init__(self, bundle: Bundle, dense: DenseIndex, *, lexical: BM25Index | None = None,
                 scorer: Scorer | None = None, rerank_depth: int = 0,
                 routed: bool = False, references: bool = False) -> None:
        self._bundle = bundle
        self._dense = dense
        self._lexical = lexical
        self._scorer = scorer
        self._rerank_depth = rerank_depth
        self._routed = routed
        self._references = references

    def _first_stage(self, queries: Sequence[str]) -> list[list[Hit]]:
        dense = self._dense.search_many(queries, CANDIDATES)
        if self._lexical is None:
            return dense
        return [rrf([hits, self._lexical.search(q, CANDIDATES)], CANDIDATES)
                for q, hits in zip(queries, dense, strict=True)]

    def _resolve(self, facts: Facts, act: str | None) -> list[str]:
        """Cited sections in the routed code, or their counterparts when cited from the other."""
        resolved: list[str] = []
        for section in (s for s in facts.references if s in self._bundle):
            if act is None or section.startswith(f"{act}:"):
                resolved.append(section)
            elif section.startswith("IPC:"):
                resolved.extend(self._bundle.replaced_by(section))
            else:
                resolved.extend(self._bundle.replaces(section))
        return list(dict.fromkeys(resolved))

    def _finish(self, query: str, hits: list[Hit], k: int, facts: Facts | None) -> list[Hit]:
        facts = facts or understand(query)
        act = route(facts, maps=self._references).act if self._routed else None
        if act:
            hits = [h for h in hits if h.section_id.startswith(f"{act}:")]
        resolved = self._resolve(facts, act) if self._references else []
        cited = [Hit(s, CITED_SCORE) for s in resolved]
        # When the question cites its answer, reranking the rest is cost with no benefit.
        if self._scorer and not cited:
            texts = [self._bundle.section(h.section_id).text for h in hits[:self._rerank_depth]]
            hits = rerank(self._scorer, query, hits, texts, self._rerank_depth)
        seen = {h.section_id for h in cited}
        return (cited + [h for h in hits if h.section_id not in seen])[:k]

    def search_many(self, queries: Sequence[str], k: int) -> list[list[Hit]]:
        return [self._finish(q, hits, k, None)
                for q, hits in zip(queries, self._first_stage(queries), strict=True)]

    def search(self, query: str, k: int, *, facts: Facts | None = None) -> list[Hit]:
        """facts: what the caller already understood of the query, so retrieval routes the
        same way the answer does, including an offence date the user gave explicitly."""
        [hits] = self._first_stage([query])
        return self._finish(query, hits, k, facts)
