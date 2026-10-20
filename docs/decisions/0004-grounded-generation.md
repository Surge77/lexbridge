# 0004 — Generation: the model writes, everything else is decided and checked

**Status:** accepted · 2026-10-20

## Context
P5 turns retrieval into an answer a non-lawyer reads. The failure this project exists to
prevent is a wrong section number stated with confidence, so the headline gate is that
no final answer names a section its sources do not support. It is measured on a fixed,
stratified 92-case subset of the golden set (every hand-written case plus 8 evenly
spaced cases from each generated category), because the Groq free tier allows about
8,000 tokens a minute. `python -m lexbridge.eval.generation` writes
`reports/generation/<run>.json` with every outcome.

## Decisions

**The router decides the code, retrieval decides the sources, the model only writes.**
The model never chooses between the IPC and the BNS. The answer opens with the router's
decision in plain words ("Assuming the offence was committed in November 2024, the BNS
applies"), so a misread date is visible instead of silent (ADR 0003). Clarifying
questions are templates and never reach the model.

**Every section the prose names is checked, not only the citations.** Citations are
source numbers, so they cannot leave the retrieved set; the prose can. A reply naming an
unsupported section gets one retry with the reason. Sentences still naming one are cut,
and an answer that is nothing but such sentences is withheld.

**What counts as supported.** The retrieved sources, the sections the question cites,
their rows of the official correspondence table, and the sections the sources' own text
names (`refers_to` edges).

**No reranker-score abstention (`gate.py` in the plan).** The reranker was deferred in
ADR 0003. Abstention is the model's `declined` status when the sources do not answer,
plus a scope check for questions the router cannot place.

**Model: `openai/gpt-oss-20b` on Groq, `reasoning_effort=low`.** Gemini is wired as a
fallback on 429/5xx/timeout but had no key for these runs.

## Results

| run | hallucinated | first draft unsupported | correct section | right code | clarify P / R | out-of-scope declined | in-scope declined | p50 / p95 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| first run | 1.1% (1) | 3.3% (3) | 76.4% | 100% | 94.1 / 100 | 87.5% | 15.5% | 0.86 / 1.89 |
| after fixes | **0** | **0** | 77.2% | 100% | 94.1 / 100 | 87.5% | 13.1% | 0.71 / 1.01 |

**All four flags in the first run were the checker's errors, not the model's.**
- Three first drafts were flagged for "section 2". The model had written the correct
  "BNS section 117(2)"; the checker read the sub-section as a section. One of them was
  withheld as a result. A number right after "(" is now a sub-section.
- The one "hallucination" was a template clarification quoting IPC 438's title
  ("... described in section 437 ..."). Statute text is now grounded via `refers_to`.

The eval's re-check is independent of the service's filtering but uses the same
detector, so a detector bug fails both together. A gate failure is first a question
about the gate.

## Consequences
- Declines are retrieval misses, not refusals: in-scope declines concentrate where hit@5
  is lowest (Hindi 40%, boundary 33%, lay 14%), and the decline texts typically list
  what the retrieved sources cover instead. The model said "not covered" instead of inventing a section. Better
  retrieval for lay and Hindi questions (the deferred reranker: lay hit@5 67.9 → 78.6)
  is the lever, not the prompt.
- One out-of-scope question was asked for a date instead of declined (7 of 8 declined).
  Asking is the cautious failure: it cites nothing.
- The 92-case subset is small: one case is 1.1 points overall and 12.5 points in a
  category of 8. The gate is the absolute count (0), not a rate.
- P6 serves `Answer.allowed` so the UI can show the sources the answer was held to.
