# 0003 — The retrieval ladder: route and look up first, rerank only if it pays

**Status:** accepted · 2026-10-19

## Context
The plan's P4 ladder was: BM25 + RRF, then a cross-encoder reranker, then the date
router, then 1-hop graph expansion, then citation lookup. Each rung was measured on the
golden set (`reports/ablation.md`), with paired sign tests between consecutive rungs,
because the hand-written categories are 6 to 28 cases each.

## Decisions

**Order.** Deterministic, cheap stages (routing, citation lookup) are measured before
the reranker. In the plan's order the reranker would have taken credit for what routing
fixes, and its latency would have counted 882 map lookups that never need it.

**BM25 + RRF (v1): not kept.** Macro hit@5 fell from 64.3 to 62.5. As a candidate
generator for a later stage it found nothing extra either (recall@20 84.3 vs 83.6,
recall@50 87.6 vs 88.1).

**Date router (v2): kept.** hit@1 rose from 36.9 to 52.0. 131 cases were gained and none
lost (p ≈ 10⁻⁴⁰). wrong-regime@1 fell from 25.6% to 0. Writing it found one real bug:
"Act 2 of 1974" had been read as the offence date. Statute citations are now masked
before dates are read.

**Citation lookup + map routing (v3): kept; this is the default pipeline.**
- A cited section in the routed code goes first.
- A section cited from the other code is replaced by its graph counterparts.
- Map lookups went from 1% to 100% hit@5. That is close to by construction, because the
  same project wrote the templates and the patterns, so the unit tests carry the other
  phrasings.
- The router now decides all 1,466 in-scope questions with no confident error.

**Reranker (v4): measured, not in the default pipeline yet.**

| Reranker | CPU time, 10 candidates | Outcome |
|---|---:|---|
| bge-reranker-v2-m3 (568M) | 15.3 s (27.9 s for 20) | Not run on the eval |
| mmarco-mMiniLMv2-L12 (118M, Apache-2.0, multilingual) | ≈1 s | v4 row |
| jina-reranker-v2-multilingual | – | Rejected: CC-BY-NC licence |

With the small model at depth 10:
- Text macro hit@5 rose from 71.9 to 76.1: 10 cases gained, 2 lost (p ≈ 0.04).
- Hand-written cases: +5 / −1, not significant. hit@1: +47 / −37, not significant.
- Query p50 rose from 100 ms to 1,294 ms on an 8-thread CPU. A 2-vCPU free host will be
  slower.

The gain is real but small, and the cost is large. Whether it is worth paying is decided
in P5, against answer correctness and latency on the deploy host.

**Graph expansion (plan's v4): not built.** Adding the `refers_to` neighbours of the top 5
put a target in context 73.8% of the time, against 71.9% for the top 5 alone. Spending
the same context budget (about 2.5 extra sections) on plain retrieval reaches 76.1%.
Retrieval already ranks the useful neighbours above what the citation graph adds.
`eval/analysis/graph_expansion.py` reproduces this.

## Consequences
- The default pipeline is `v3-references`: dense (bge-m3) → route → cited-section lookup.
  It has no extra model, and a query takes about 100 ms on CPU.
- Hindi stays the weakest category (30% hit@5) at every rung. No retrieval stage moved
  it, so it is a corpus and embedding limit, not a ranking one. It is listed in the
  README limitations.
- The router is rules, not a model. It answers "which code?" with no confident error on
  the golden set, and it asks rather than guesses when a period straddles 1 July 2024.
