from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lexbridge.bundle import Bundle
from lexbridge.retrieve.dense import DenseIndex

from ..eval.factory import build_bundle
from .fakes import WordsEmbedder


@pytest.fixture
def bundle(tmp_path: Path) -> Bundle:
    return build_bundle(tmp_path / "v1")


def test_the_closest_section_ranks_first(bundle: Bundle) -> None:
    index = DenseIndex.build(bundle, WordsEmbedder())

    hits = index.search("seizes snatching", k=3)

    assert hits[0].section_id == "BNS:304"
    assert len(hits) == 3
    assert hits[0].score >= hits[1].score >= hits[2].score


def test_every_served_section_is_indexed_once(bundle: Bundle) -> None:
    index = DenseIndex.build(bundle, WordsEmbedder())

    assert sorted(index.ids) == sorted(s.id for s in bundle.sections)


def test_a_batch_ranks_each_query_independently(bundle: Bundle) -> None:
    index = DenseIndex.build(bundle, WordsEmbedder())

    batch = index.search_many(["seizes snatching", "cheats induces"], k=1)

    assert [hits[0].section_id for hits in batch] == ["BNS:304", "BNS:318"]
    assert batch[0] == index.search("seizes snatching", k=1)


def test_ties_keep_corpus_order_so_reruns_rank_identically(bundle: Bundle) -> None:
    index = DenseIndex.build(bundle, WordsEmbedder())

    # No query word appears anywhere: every score is 0 and only the tie-break orders them.
    hits = index.search("zzz", k=len(index.ids))

    assert [h.section_id for h in hits] == list(index.ids)


def test_cached_vectors_are_reused_for_the_same_model_and_text(
        bundle: Bundle, tmp_path: Path) -> None:
    first, second = WordsEmbedder(), WordsEmbedder()

    DenseIndex.build(bundle, first, cache_dir=tmp_path / "cache")
    DenseIndex.build(bundle, second, cache_dir=tmp_path / "cache")

    assert first.documents_embedded == len(bundle.sections)
    assert second.documents_embedded == 0
    [cached] = (tmp_path / "cache").iterdir()
    assert cached.name.startswith("words-test-")


def test_ids_and_vectors_must_line_up() -> None:
    with pytest.raises(ValueError, match="2 ids for 1 vectors"):
        DenseIndex(["IPC:1", "IPC:2"], np.zeros((1, 4), dtype=np.float32), WordsEmbedder())
