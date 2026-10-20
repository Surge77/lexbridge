# Changelog

All notable changes to LexBridge. Versions follow [semantic versioning](https://semver.org/).

## [0.1.0] - 2026-10-20

First complete version: a question in, a cited answer from the right code out.

### Added
- **Ingest** (P1–P2): fetches the IPC, BNS and the IPC–BNS correspondence table, pinned by
  SHA-256; parses them with pdfplumber into 581 IPC and 358 BNS sections; builds a graph of
  543 `replaced_by`, 289 `refers_to`, 27 `unmapped` and 21 `new_in_bns` edges; packages a
  versioned, hash-verified bundle. An integration gate checks the 2013/2018 inserts, so a
  stale source cannot pass on section counts alone.
- **Evaluation** (P3): 1,466 golden questions generated from the correspondence table plus
  hand-written lay, Hindi, boundary, tricky and out-of-scope cases; per-category hit@k, MRR
  and wrong-code rates (`reports/ablation.md`).
- **Retrieval** (P4): dense bge-m3, a rule-based date router that abstains on weak
  evidence, and cited-section lookup. The default pipeline puts the right code first every
  time and answers map questions from the graph. BM25 hybrid was measured and dropped;
  the reranker was measured and deferred (ADR 0003).
- **Generation** (P5): answers from four numbered sources through an OpenAI-compatible
  gateway (Groq gpt-oss-20b → gpt-oss-120b → Gemini), opening with the date assumed. Every
  section number in the prose is checked; unsupported ones get one retry, then are cut. 0
  of 92 evaluated answers named an unsupported section (ADR 0004).
- **API** (P6): `POST /chat` with an optional explicit `offence_date`, `GET /section`,
  `GET /map`, `POST /feedback`, `GET /health`; per-client and global limits that protect
  the free tier's daily token budget; a cache; traces that keep an HMAC of the question,
  never its text (ADR 0005).
- **Interface and image** (P7): a one-page UI served by the API, under a strict CSP, and a
  Dockerfile with staging for a Hugging Face Space (ADR 0006).

### Not done
- Public hosting: Hugging Face Docker Spaces now require PRO; the image is ready for any
  host with ~3 GB of RAM.
