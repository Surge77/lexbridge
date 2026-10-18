"""Text embedders behind one small protocol.

Retrieval code depends on Embedder, never on sentence-transformers, so unit tests run a
deterministic fake without importing torch, and swapping models is a registry entry.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import astuple, dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

Vectors = NDArray[np.float32]


class Embedder(Protocol):
    @property
    def name(self) -> str:
        """Identifies the weights and every setting that changes a vector, so cached
        vectors are never reused after either changes."""
        ...

    def embed_documents(self, texts: Sequence[str]) -> Vectors: ...

    def embed_queries(self, texts: Sequence[str]) -> Vectors: ...


@dataclass(frozen=True)
class ModelSpec:
    repo: str
    # A commit on the hub. A branch name would let the weights, and every number in the
    # ablation table, change under the same label.
    revision: str
    query_prefix: str
    document_prefix: str
    # Both models are cut to the same window so the comparison is about the model, not
    # about one of them reading further into long sections. bge-m3 accepts 8192.
    max_tokens: int = 512


MODELS = {
    # e5 is trained with these prefixes; without them its retrieval quality drops.
    "e5-small": ModelSpec("intfloat/multilingual-e5-small",
                          "614241f622f53c4eeff9890bdc4f31cfecc418b3", "query: ", "passage: "),
    "bge-m3": ModelSpec("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", "", ""),
}


class SentenceTransformerEmbedder:
    def __init__(self, key: str, *, batch_size: int = 16) -> None:
        # Imported here: torch takes seconds to import, and only real runs need it.
        from sentence_transformers import SentenceTransformer

        self.spec = MODELS[key]
        # The revision names the weights; the settings hash covers prefixes and the token
        # window, which change the vectors just as much.
        settings = hashlib.sha256(repr(astuple(self.spec)).encode()).hexdigest()[:6]
        self._name = f"{key}@{self.spec.revision[:8]}.{settings}"
        self._batch_size = batch_size
        self._model = SentenceTransformer(self.spec.repo, revision=self.spec.revision,
                                          device="cpu")
        self._model.max_seq_length = self.spec.max_tokens

    @property
    def name(self) -> str:
        return self._name

    @property
    def parameters(self) -> int:
        return sum(p.numel() for p in self._model.parameters())

    def _encode(self, texts: Sequence[str]) -> Vectors:
        vectors = self._model.encode(list(texts), batch_size=self._batch_size,
                                     normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(vectors, dtype=np.float32)

    def embed_documents(self, texts: Sequence[str]) -> Vectors:
        return self._encode([self.spec.document_prefix + t for t in texts])

    def embed_queries(self, texts: Sequence[str]) -> Vectors:
        return self._encode([self.spec.query_prefix + t for t in texts])
