# 0006 — Deploy: an image ready to ship, a public host on hold

**Status:** accepted · 2026-10-20

## Context
P7 planned a Hugging Face Docker Space: free CPU hardware, 16 GB of RAM, and a public URL.
The served app keeps bge-m3 in memory (about 2.5 GB with torch), which rules out the free
tiers that give 512 MB, such as Render's.

On 2026-10-20 creating the Space failed with `402 Payment Required`: Hugging Face now
hosts Docker and Gradio Spaces on its free CPU hardware only for PRO subscribers. Static
Spaces are still free, but this app needs a Python process.

## Decisions
- **The deployable unit is finished and kept.** The `Dockerfile` installs CPU torch, the
  package, and the embedder's pinned weights at build time, and copies in the bundle the
  evaluation measured (the statute PDFs are not refetched: government sites fail
  intermittently, and the manifest hashes prove which bundle it is).
  `deploy/stage_space.py` assembles exactly what a Space needs. Either works unchanged on
  any container host with about 3 GB of RAM.
- **No public host for now**, by the owner's choice over paying for HF PRO ($9/month),
  Railway (usage-based, ~$5/month) or Google Cloud Run (free tier, card on file, cold
  starts while bge-m3 loads). The app runs locally:
  `uvicorn --factory lexbridge.api.main:build`, at http://127.0.0.1:8000 by default.
- **A one-page interface ships with the API** instead of the plan's Gradio app: three
  static files served by FastAPI, no new dependency and no second server, under a CSP that
  allows only the page's own script and style.

## Consequences
- P7's gate (live `/health` and 10 eval questions against a public URL) is not met. The
  same checks ran against the local server (ADR 0005's smoke test).
- Deploying later is: pick a host, set `GROQ_API_KEY` and `LEXBRIDGE_TRACE_KEY` as
  secrets, set `LEXBRIDGE_PROXY_HOPS` to the host's proxy depth (confirm by checking what
  the app receives), build the image.
- A free path would need the query embedding off the machine (a hosted embedding API,
  checked for parity with the cached section vectors) so the server needs no torch. That
  is a retrieval change with its own evaluation, not a deploy setting.
