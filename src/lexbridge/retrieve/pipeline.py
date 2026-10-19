"""The retrieval ladder: each rung is a named configuration with its own ablation row.

A run is named after its PipelineSpec, so `reports/runs/v1-hybrid.json` always means the
same stages. Rungs are cumulative; a rung that does not earn its cost is switched off in
the later specs, and the reason recorded in reports/ablation.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from lexbridge.retrieve.base import Hit
from lexbridge.retrieve.bm25 import BM25Index
from lexbridge.retrieve.dense import DenseIndex
from lexbridge.retrieve.fusion import rrf

# How deep each first-stage list goes before fusion and cutting to k. Deep enough that a
# target ranked 11th by one retriever can still be fused into the top 10.
CANDIDATES = 50


@dataclass(frozen=True)
class PipelineSpec:
    embedder: str
    lexical: bool = False
    # What the rung's row showed and what was decided, rendered into reports/ablation.md.
    note: str = ""

    def describe(self) -> str:
        return "+".join(["dense", *(["bm25/rrf"] if self.lexical else [])])


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
}


class Pipeline:
    def __init__(self, dense: DenseIndex, lexical: BM25Index | None = None) -> None:
        self._dense = dense
        self._lexical = lexical

    def search_many(self, queries: Sequence[str], k: int) -> list[list[Hit]]:
        dense = self._dense.search_many(queries, CANDIDATES)
        if self._lexical is None:
            return [hits[:k] for hits in dense]
        return [rrf([hits, self._lexical.search(q, CANDIDATES)], k)
                for q, hits in zip(queries, dense, strict=True)]

    def search(self, query: str, k: int) -> list[Hit]:
        return self.search_many([query], k)[0]
