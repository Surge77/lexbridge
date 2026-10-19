"""Okapi BM25 over section text.

Written out rather than imported: it is a few lines of arithmetic over ~940 documents,
and the maintained-looking package (rank-bm25) has had no release since 2022.
Lexical matching catches what embeddings blur: rare statutory terms ("voyeurism",
"dacoity") and literal section numbers.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from lexbridge.bundle import Bundle
from lexbridge.retrieve.base import Hit

# Devanagari vowel signs are combining marks, which \w does not match, so the block is
# listed explicitly or a Hindi word would be cut at every matra.
TOKEN = re.compile(r"[\wऀ-ॿ]+")
# The usual Okapi defaults; not tuned on the golden set, so the eval stays honest.
K1, B = 1.5, 0.75


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


class BM25Index:
    def __init__(self, ids: Sequence[str], texts: Sequence[str]) -> None:
        self.ids = tuple(ids)
        docs = [Counter(tokenize(t)) for t in texts]
        self._docs = docs
        self._lengths = [sum(d.values()) for d in docs]
        self._average = sum(self._lengths) / len(docs) if docs else 0.0
        frequency = Counter(term for d in docs for term in d)
        n = len(docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in frequency.items()}

    @classmethod
    def build(cls, bundle: Bundle) -> BM25Index:
        return cls([s.id for s in bundle.sections], [s.text for s in bundle.sections])

    def _scores(self, query: str) -> list[float]:
        terms = [t for t in set(tokenize(query)) if t in self._idf]
        scores = []
        for doc, length in zip(self._docs, self._lengths, strict=True):
            norm = K1 * (1 - B + B * length / self._average)
            scores.append(sum(self._idf[t] * doc[t] * (K1 + 1) / (doc[t] + norm)
                              for t in terms if t in doc))
        return scores

    def search(self, query: str, k: int) -> list[Hit]:
        scores = self._scores(query)
        # Sorted by score, then corpus position, so ties rank the same on every run.
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        return [Hit(self.ids[i], scores[i]) for i in order[:k] if scores[i] > 0]

    def search_many(self, queries: Sequence[str], k: int) -> list[list[Hit]]:
        return [self.search(q, k) for q in queries]
