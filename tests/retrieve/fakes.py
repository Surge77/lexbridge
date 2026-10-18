"""Test doubles for retrieval: deterministic, offline, no torch."""

from __future__ import annotations

import re
import zlib
from collections.abc import Sequence

import numpy as np

from lexbridge.retrieve.embed import Vectors

DIMENSIONS = 64


class WordsEmbedder:
    """Bag of words hashed into a fixed vector: overlap in words is similarity."""

    name = "words@test"

    def __init__(self) -> None:
        self.documents_embedded = 0

    def _embed(self, texts: Sequence[str]) -> Vectors:
        out = np.zeros((len(texts), DIMENSIONS), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"[a-z]+", text.lower()):
                out[row, zlib.crc32(word.encode()) % DIMENSIONS] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return (out / np.where(norms == 0, 1, norms)).astype(np.float32)

    def embed_documents(self, texts: Sequence[str]) -> Vectors:
        self.documents_embedded += len(texts)
        return self._embed(texts)

    def embed_queries(self, texts: Sequence[str]) -> Vectors:
        return self._embed(texts)
