"""Dense retrieval: one normalised vector per section, ranked by cosine similarity.

About 940 sections fit in a 940 x 384 matrix, so search is one matrix product. An ANN
index would add a dependency and approximate answers to save microseconds.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from lexbridge.bundle import Bundle
from lexbridge.retrieve.embed import Embedder, Vectors


@dataclass(frozen=True)
class Hit:
    section_id: str
    score: float


class DenseIndex:
    def __init__(self, ids: Sequence[str], vectors: Vectors, embedder: Embedder) -> None:
        if len(ids) != len(vectors):
            raise ValueError(f"{len(ids)} ids for {len(vectors)} vectors")
        self.ids = tuple(ids)
        self._vectors = vectors
        self._embedder = embedder

    @classmethod
    def build(cls, bundle: Bundle, embedder: Embedder, cache_dir: Path | None = None
              ) -> DenseIndex:
        ids = [s.id for s in bundle.sections]
        # Keyed on the weights and the exact section text: vectors are valid for nothing else.
        key = f"{_slug(embedder.name)}-{bundle.sections_sha256[:12]}"
        cache = cache_dir / f"{key}.npy" if cache_dir else None
        if cache and cache.exists():
            return cls(ids, np.load(cache), embedder)
        vectors = embedder.embed_documents([s.text for s in bundle.sections])
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.save(cache, vectors)
        return cls(ids, vectors, embedder)

    def search_many(self, queries: Sequence[str], k: int) -> list[list[Hit]]:
        scores = self._embedder.embed_queries(queries) @ self._vectors.T
        # Stable sort on the negated score: ties keep corpus order, so a rerun ranks
        # identically instead of depending on how the sort breaks ties.
        order = np.argsort(-scores, axis=1, kind="stable")[:, :k]
        return [[Hit(self.ids[j], float(row[j])) for j in top]
                for row, top in zip(scores, order, strict=True)]

    def search(self, query: str, k: int) -> list[Hit]:
        return self.search_many([query], k)[0]


def _slug(name: str) -> str:
    return name.replace("/", "_").replace("@", "-")
