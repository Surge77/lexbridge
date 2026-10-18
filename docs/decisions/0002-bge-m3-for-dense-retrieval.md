# 0002 — Use bge-m3 for dense retrieval, not multilingual-e5-small

**Status:** accepted · 2026-10-19

## Context
Dense retrieval needs one embedding model for both sections and queries. Some questions
arrive in Hindi or Hinglish, so it has to be multilingual. Two MIT-licensed candidates
were measured on the golden set (`eval/golden.jsonl`, 1,474 cases), both on CPU, both
pinned to a hub commit, and both cut to 512 tokens. Each index was built from scratch
on an otherwise idle machine. Full results are in `reports/ablation.md`.

| | multilingual-e5-small | bge-m3 |
|---|---:|---:|
| Parameters | 118M | 568M |
| hit@5, macro over text categories | 51.7 | **64.3** |
| hit@10, macro | 62.4 | **78.1** |
| MRR, macro | 41.7 | **49.3** |
| hit@5: lay / Hindi / boundary / tricky | 39 / 20 / 50 / 25 | **54 / 30 / 67 / 50** |
| Query latency, p50 / p95 (sampled across every category) | **13 / 16 ms** | 110 / 147 ms |
| Index build, 939 sections | **43 s** | 519 s |

The macro averages the six text-retrieval categories. The two map-lookup categories are
graph lookups that neither model can answer (about 1% hit@5). They are reported
separately.

The hand-written categories are small (6 to 28 cases each), so the per-category gaps
come down to a few questions. The paired view settles it. On the 52 hand-written
in-scope cases, bge-m3 finds 10 answers in its top 5 that e5 misses, and e5 finds 2
that bge-m3 misses (exact two-sided sign test, p ≈ 0.04). Across all 1,466 retrieval
cases the count is 55 to 19 (p ≈ 3×10⁻⁵).

## Decision
Use **bge-m3** (`BAAI/bge-m3` at `5617a9f6`) as the dense retriever from v0 on. The
registry key in `lexbridge/retrieve/embed.py` is the only switch.

## Consequences
- A query costs about 110 ms on CPU instead of 13 ms. The answer will wait about a
  second on an LLM call anyway, so the gap is affordable.
- The index takes about 9 minutes to build. It is built once per bundle and cached
  under a key of model commit plus section-text hash. For deployment the vectors are
  baked into the image, so a running server never builds them.
- About 2.3 GB of fp32 weights at runtime. That fits a free Hugging Face CPU Space
  (16 GB). It does not fit a 512 MB container.
- bge-m3 is published only as `pytorch_model.bin`, a pickle. It loads at a pinned commit
  through transformers 5, which uses torch's `weights_only` loading. Moving the
  pin to a new commit means re-checking that.
- Neither model solves the two failures the baseline exposes. Map lookups ("IPC 420 is
  now which section?") score about 1% hit@5, because a vector carries no usable notion of a section
  number. On dated questions, about a quarter of first results are the right provision from the
  wrong code. Those are P4's jobs: the graph shortcut and the date router.
- bge-m3's higher wrong-regime@1 (25.6 vs 18.6) is not a regression in disguise. It finds
  the concept more often, and an IPC section and its BNS successor share most of their
  wording, so it lands on the twin more often too.
