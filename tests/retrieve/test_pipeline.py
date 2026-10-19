from __future__ import annotations

import sys
import types
from collections.abc import Sequence
from pathlib import Path

import pytest

from lexbridge.bundle import Bundle
from lexbridge.retrieve.base import Hit
from lexbridge.retrieve.dense import DenseIndex
from lexbridge.retrieve.pipeline import PIPELINES, Pipeline, PipelineSpec
from lexbridge.retrieve.rerank import RERANKERS, CrossEncoderScorer, rerank

from ..eval.factory import build_bundle
from .fakes import WordsEmbedder


class LengthScorer:
    """Prefers shorter passages: an order no first stage would produce by accident."""

    name = "length@test"

    def __init__(self) -> None:
        self.calls: list[int] = []

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        self.calls.append(len(passages))
        return [-float(len(p)) for p in passages]


@pytest.fixture
def bundle(tmp_path: Path) -> Bundle:
    return build_bundle(tmp_path / "v1")


def test_rerank_reorders_only_the_head_and_keeps_the_tail() -> None:
    hits = [Hit("A", 0.9), Hit("B", 0.8), Hit("C", 0.7)]

    out = rerank(LengthScorer(), "q", hits, ["long passage", "mid", "x"], depth=2)

    assert [h.section_id for h in out] == ["B", "A", "C"]
    assert rerank(LengthScorer(), "q", [], [], depth=2) == []


def test_routing_keeps_only_the_code_the_date_points_to(bundle: Bundle) -> None:
    dense = DenseIndex.build(bundle, WordsEmbedder())
    routed = Pipeline(bundle, dense, routed=True)

    before = routed.search("theft on 3 May 2024", k=10)
    after = routed.search("theft on 3 August 2024", k=10)
    undated = routed.search("theft", k=10)

    assert before and all(h.section_id.startswith("IPC:") for h in before)
    assert after and all(h.section_id.startswith("BNS:") for h in after)
    # No date and no code named: nothing is filtered, and the answer will have to ask.
    assert {h.section_id.split(":")[0] for h in undated} == {"IPC", "BNS"}


def test_the_reranker_only_sees_the_routed_candidates(bundle: Bundle) -> None:
    scorer = LengthScorer()
    pipeline = Pipeline(bundle, DenseIndex.build(bundle, WordsEmbedder()), scorer=scorer,
                        rerank_depth=20, routed=True)

    hits = pipeline.search("theft on 3 August 2024", k=3)

    assert scorer.calls == [3]  # the three BNS sections, not all nine
    assert hits[0].section_id == "BNS:318"  # the shortest BNS text in the factory


def test_specs_describe_their_stages_in_order() -> None:
    spec = PipelineSpec("bge-m3", reranker="bge-reranker-v2-m3", rerank_depth=20, route=True)

    assert spec.describe() == "dense+route+rerank:bge-reranker-v2-m3@20"
    assert all(s.describe().startswith("dense") for s in PIPELINES.values())


def test_the_cross_encoder_is_pinned_and_scores_every_pair(
        monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    class FakeCrossEncoder:
        def __init__(self, repo: str, **options: object) -> None:
            seen.update(repo=repo, **options)

        def parameters(self) -> list[types.SimpleNamespace]:
            return [types.SimpleNamespace(numel=lambda: 7)]

        def predict(self, pairs: list[tuple[str, str]], batch_size: int) -> list[float]:
            seen["pairs"] = pairs
            return [0.5] * len(pairs)

    module = types.ModuleType("sentence_transformers")
    module.CrossEncoder = FakeCrossEncoder  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)

    scorer = CrossEncoderScorer("bge-reranker-v2-m3")

    assert scorer.score("theft?", ["303. Theft.", "304. Snatching."]) == [0.5, 0.5]
    assert seen["revision"] == RERANKERS["bge-reranker-v2-m3"].revision
    assert (seen["device"], seen["max_length"]) == ("cpu", 512)
    assert seen["pairs"] == [("theft?", "303. Theft."), ("theft?", "304. Snatching.")]
    assert scorer.name.startswith("bge-reranker-v2-m3@953dc6f6")
    assert scorer.parameters == 7


def test_a_cited_section_of_the_other_code_resolves_to_its_counterparts(
        bundle: Bundle) -> None:
    pipeline = Pipeline(bundle, DenseIndex.build(bundle, WordsEmbedder()), routed=True,
                        references=True)

    mapped = pipeline.search("What is the BNS equivalent of IPC section 379?", k=3)
    reverse = pipeline.search("Which IPC section did BNS section 303 replace?", k=3)
    direct = pipeline.search("What did section 124A of the IPC say?", k=3)
    dated = pipeline.search("Under IPC 379, a theft in August 2024", k=3)

    assert mapped[0].section_id == "BNS:303"
    assert [h.section_id for h in reverse[:2]] == ["IPC:378", "IPC:379"]
    assert direct[0].section_id == "IPC:124A"
    # The date puts it under the BNS, so the cited IPC section gives way to its successor.
    assert dated[0].section_id == "BNS:303"
    assert all(h.section_id.startswith("BNS:") for h in dated)


def test_an_unmapped_or_unknown_citation_adds_nothing(bundle: Bundle) -> None:
    pipeline = Pipeline(bundle, DenseIndex.build(bundle, WordsEmbedder()), routed=True,
                        references=True)

    # IPC 124A has no BNS counterpart in the table, and IPC 999 does not exist.
    for question in ("BNS equivalent of IPC 124A?", "What did IPC 999 say?"):
        assert all(h.score != float("inf") for h in pipeline.search(question, k=5))


def test_a_resolved_citation_skips_the_reranker(bundle: Bundle) -> None:
    scorer = LengthScorer()
    pipeline = Pipeline(bundle, DenseIndex.build(bundle, WordsEmbedder()), scorer=scorer,
                        rerank_depth=5, routed=True, references=True)

    pipeline.search("What is the BNS equivalent of IPC section 379?", k=3)
    pipeline.search("theft on 3 August 2024", k=3)

    assert scorer.calls == [3]  # only the uncited question was reranked
