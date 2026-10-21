# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Frontend moves to a framework (user decision, 2026-10-21); framework choice still open. FastAPI keeps serving
the API (`POST /chat`, `GET /section/{id}`, `GET /map/{id}`, `POST /feedback`, `GET /health`) and the built UI.

## Users

Mixed audience, weighted equally:

- **Members of the public** (complainants, families) asking in plain words which section applies to what happened.
- **Legal professionals and students** who know IPC numbers and need the BNS counterpart and the section text fast.

Reviewers of the project (it is a portfolio piece) are a secondary audience served by the proof section.

## Product Purpose

On 1 July 2024 the Bharatiya Nyaya Sanhita (BNS) replaced the Indian Penal Code (IPC) and every section number
changed. LexBridge answers questions about either code: it works out which code applies from the offence date,
retrieves provisions, and cites them. Success: a person leaves with the right section for their date, and can
see the law's own text behind it.

## Positioning

Every section number in an answer is checked against the law's text before it is shown; when the date is
missing it asks instead of guessing; when the sources do not answer it says so. General chatbots give stale IPC
numbers with no date check.

## Operating Context

One question at a time, optional explicit offence date (overrides dates in the question). Answers come back in
~1 s with a status (`answered` | `clarify` | `declined`), the code applied (IPC/BNS), cited section ids, the
wider set of sections the answer was allowed to name, and a cache flag. Any section opens its full text plus
its IPC↔BNS mapping. One helpful/not-helpful vote per answer.

## Capabilities and Constraints

- Corpus: IPC 581 sections, BNS 358 sections; mapping graph (replaced_by 543 edges, 27 unmapped, 21 new in BNS).
- `unmapped` does not mean abolished; never claim a section was dropped.
- Answers are general information, not legal advice; users must not include personal details.
- Rate limits: 5/min and 50/day per client; errors may carry Retry-After.
- Model output is untrusted: render as text, never as markup.
- Not publicly hosted yet (ADR 0006); runs locally.

## Evidence on Hand

From `README.md` / `reports/` (92-question stratified eval, 1,466-question ablation):
- 0/92 answers naming an unsupported section; 100% right code for dated questions; 79.7% a correct section cited;
  date clarification recall/precision 100%/100%; out-of-scope declined 8/8; latency p50 0.94 s / p95 1.29 s.
- Retrieval ladder: date router took wrong-code-first from 25.6% to 0%; cited-section lookup took map questions 1% → 100%.
No testimonials, users, or press exist; none may be invented.

## Product Principles

1. Cited or silent: never show a section the sources do not support.
2. The date decides the law; surface the assumed date in every answer.
3. Plain answer first, the law's text one step away.
4. Show the mechanism, do not claim it.

## Accessibility & Inclusion

Plain-language first for lay users; Hindi-speaking users are a known future audience (lay/Hindi retrieval quality
is a recorded limitation).
