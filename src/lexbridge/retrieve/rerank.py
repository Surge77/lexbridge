"""Second-stage reranking: a cross-encoder reads the question and each candidate together.

A bi-encoder embeds question and section apart; a cross-encoder attends across both,
which is slower per pair and better at telling near-duplicates apart. Only the top few
candidates are rescored; the rest keep their first-stage order below them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from lexbridge.retrieve.base import Hit


class Scorer(Protocol):
    @property
    def name(self) -> str: ...

    def score(self, query: str, passages: Sequence[str]) -> list[float]: ...


@dataclass(frozen=True)
class RerankerSpec:
    repo: str
    revision: str
    max_tokens: int


RERANKERS = {
    # Measured and not used: 15 s to rerank 10 candidates on an 8-thread CPU. Kept so the
    # measurement in docs/decisions/0003-small-reranker-on-cpu.md can be repeated.
    "bge-reranker-v2-m3": RerankerSpec(
        "BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e", 512),
    # Multilingual (mMARCO, Hindi included), 118M parameters: about 1 s for 10 candidates.
    "mminilm-l12": RerankerSpec(
        "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        "1427fd652930e4ba29e8149678df786c240d8825", 512),
}


class CrossEncoderScorer:
    def __init__(self, key: str) -> None:
        # Imported here for the same reason as the embedder: torch costs seconds to load.
        from sentence_transformers import CrossEncoder

        self.spec = RERANKERS[key]
        self._name = f"{key}@{self.spec.revision[:8]}.{self.spec.max_tokens}"
        self._model = CrossEncoder(self.spec.repo, revision=self.spec.revision, device="cpu",
                                   max_length=self.spec.max_tokens)

    @property
    def name(self) -> str:
        return self._name

    @property
    def parameters(self) -> int:
        return sum(p.numel() for p in self._model.parameters())

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        pairs = [(query, p) for p in passages]
        return [float(s) for s in self._model.predict(pairs, batch_size=len(pairs) or 1)]


def rerank(scorer: Scorer, query: str, hits: Sequence[Hit], texts: Sequence[str],
           depth: int) -> list[Hit]:
    """Rescore the first `depth` hits (texts[i] is the text of hits[i]); keep the rest."""
    head, tail = list(hits[:depth]), list(hits[depth:])
    if not head:
        return tail
    scores = scorer.score(query, texts[:depth])
    # Stable on ties: equal cross-encoder scores keep their first-stage order.
    order = sorted(range(len(head)), key=lambda i: -scores[i])
    return [Hit(head[i].section_id, scores[i]) for i in order] + tail
