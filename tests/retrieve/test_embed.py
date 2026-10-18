from __future__ import annotations

import sys
import types
from dataclasses import replace

import numpy as np
import pytest

from lexbridge.retrieve.embed import MODELS, SentenceTransformerEmbedder


class FakeModel:
    """Stands in for sentence_transformers.SentenceTransformer; records what it was asked."""

    def __init__(self, repo: str, *, revision: str, device: str) -> None:
        self.loaded = (repo, revision, device)
        self.max_seq_length = 0
        self.seen: list[str] = []

    def encode(self, texts: list[str], **options: object) -> np.ndarray:
        self.seen.extend(texts)
        self.options = options
        return np.ones((len(texts), 3))

    def parameters(self) -> list[FakeParameter]:
        return [FakeParameter(10), FakeParameter(5)]


class FakeParameter:
    def __init__(self, size: int) -> None:
        self.size = size

    def numel(self) -> int:
        return self.size


@pytest.fixture(autouse=True)
def fake_library(monkeypatch: pytest.MonkeyPatch) -> None:
    # Swapping the module keeps torch out of the unit tests entirely.
    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)


def model_of(embedder: SentenceTransformerEmbedder) -> FakeModel:
    model = embedder._model
    assert isinstance(model, FakeModel)
    return model


def test_the_model_is_loaded_at_its_pinned_commit_on_cpu() -> None:
    embedder = SentenceTransformerEmbedder("bge-m3")
    model = model_of(embedder)

    assert model.loaded == ("BAAI/bge-m3", MODELS["bge-m3"].revision, "cpu")
    assert model.max_seq_length == 512
    assert embedder.name.startswith(f"bge-m3@{MODELS['bge-m3'].revision[:8]}.")
    assert embedder.parameters == 15


def test_e5_gets_its_query_and_passage_prefixes() -> None:
    embedder = SentenceTransformerEmbedder("e5-small")

    embedder.embed_documents(["420. Cheating."])
    embedder.embed_queries(["cheating in 2023"])

    assert model_of(embedder).seen == ["passage: 420. Cheating.", "query: cheating in 2023"]


def test_vectors_come_back_normalised_float32() -> None:
    embedder = SentenceTransformerEmbedder("bge-m3")

    vectors = embedder.embed_queries(["theft"])

    assert vectors.dtype == np.float32
    assert model_of(embedder).options["normalize_embeddings"] is True


def test_a_settings_change_changes_the_name_that_keys_cached_vectors(
        monkeypatch: pytest.MonkeyPatch) -> None:
    before = SentenceTransformerEmbedder("e5-small").name
    monkeypatch.setitem(MODELS, "e5-small", replace(MODELS["e5-small"], max_tokens=8192))

    assert SentenceTransformerEmbedder("e5-small").name != before
