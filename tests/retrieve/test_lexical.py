from __future__ import annotations

from pathlib import Path

import pytest

from lexbridge.bundle import Bundle
from lexbridge.retrieve.base import Hit
from lexbridge.retrieve.bm25 import BM25Index, tokenize
from lexbridge.retrieve.dense import DenseIndex
from lexbridge.retrieve.fusion import rrf
from lexbridge.retrieve.pipeline import PIPELINES, Pipeline

from ..eval.factory import build_bundle
from .fakes import WordsEmbedder


@pytest.fixture
def bundle(tmp_path: Path) -> Bundle:
    return build_bundle(tmp_path / "v1")


def test_tokens_keep_hindi_words_whole_and_numbers_as_terms() -> None:
    assert tokenize("धोखाधड़ी की सज़ा") == ["धोखाधड़ी", "की", "सज़ा"]
    assert tokenize("IPC 420, Cheating.") == ["ipc", "420", "cheating"]


def test_bm25_ranks_the_section_with_the_rare_term_first(bundle: Bundle) -> None:
    index = BM25Index.build(bundle)

    hits = index.search("what is snatching", k=5)

    assert hits[0].section_id == "BNS:304"


def test_bm25_matches_a_literal_section_number(bundle: Bundle) -> None:
    hits = BM25Index.build(bundle).search("section 124A", k=3)

    assert hits[0].section_id == "IPC:124A"


def test_bm25_returns_nothing_rather_than_zero_score_noise(bundle: Bundle) -> None:
    assert BM25Index.build(bundle).search("zzz qqq", k=5) == []
    assert BM25Index.build(bundle).search_many(["zzz", "theft"], k=1)[0] == []


def test_rrf_rewards_agreement_between_lists() -> None:
    dense = [Hit("A", 0.9), Hit("B", 0.8), Hit("C", 0.7)]
    lexical = [Hit("B", 12.0), Hit("C", 9.0)]

    fused = rrf([dense, lexical], k=3)

    # A tops one list only; B and C are found by both and overtake it.
    assert [h.section_id for h in fused] == ["B", "C", "A"]


def test_rrf_breaks_ties_in_favour_of_the_first_list() -> None:
    fused = rrf([[Hit("A", 1.0)], [Hit("B", 1.0)]], k=2)

    assert [h.section_id for h in fused] == ["A", "B"]


def test_the_hybrid_pipeline_fuses_dense_and_lexical(bundle: Bundle) -> None:
    dense = DenseIndex.build(bundle, WordsEmbedder())
    plain, hybrid = Pipeline(dense), Pipeline(dense, BM25Index.build(bundle))

    assert len(plain.search("theft", k=2)) == 2
    assert hybrid.search("snatching seizes", k=1)[0].section_id == "BNS:304"
    assert hybrid.search_many(["theft", "sedition"], k=1)[1][0].section_id == "IPC:124A"


def test_every_named_pipeline_describes_its_stages() -> None:
    assert PIPELINES["v0-dense-bge-m3"].describe() == "dense"
    assert PIPELINES["v1-hybrid"].describe() == "dense+bm25/rrf"
