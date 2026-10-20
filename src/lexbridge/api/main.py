"""Build the served app: load the bundle and models once, then answer with them.

    LEXBRIDGE_BUNDLE=artifacts/v2026-10-18 GROQ_API_KEY=... \
        uvicorn --factory lexbridge.api.main:build

Behind a proxy (Hugging Face Spaces), add --proxy-headers --forwarded-allow-ips=<proxy>
so the rate limit sees each client's address rather than the proxy's.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI

from lexbridge.api.app import Services, create_app
from lexbridge.api.guard import AnswerCache, RateLimiter

# Ten questions a minute is generous for a person and keeps one client from spending the
# free tier's daily token budget (200k tokens per model) for everyone.
CHAT_PER_MINUTE = 10
CACHED_ANSWERS = 512


def build() -> FastAPI:  # pragma: no cover - loads real models and reads the environment
    from lexbridge.answer.llm import CHAIN, Gateway
    from lexbridge.answer.service import Answer, answer
    from lexbridge.api.traces import TraceLog
    from lexbridge.bundle import load_bundle
    from lexbridge.retrieve.dense import DenseIndex
    from lexbridge.retrieve.embed import SentenceTransformerEmbedder
    from lexbridge.retrieve.pipeline import PIPELINES, Pipeline
    from lexbridge.retrieve.rerank import CrossEncoderScorer

    logging.basicConfig(level=logging.INFO)
    root = Path(os.environ.get("LEXBRIDGE_BUNDLE", "artifacts/v2026-10-18"))
    spec = PIPELINES[os.environ.get("LEXBRIDGE_PIPELINE", "v3-references")]
    bundle = load_bundle(root)
    dense = DenseIndex.build(bundle, SentenceTransformerEmbedder(spec.embedder),
                             cache_dir=root / "vectors")
    scorer = CrossEncoderScorer(spec.reranker) if spec.reranker else None
    retriever = Pipeline(bundle, dense, scorer=scorer, rerank_depth=spec.rerank_depth,
                         routed=spec.route, references=spec.references)
    chat = Gateway(CHAIN)

    def ask(question: str, offence_date: date | None) -> Answer:
        return answer(question, retriever=retriever, bundle=bundle, chat=chat,
                      offence_date=offence_date)

    traces = TraceLog(Path(os.environ.get("LEXBRIDGE_TRACES", "traces.sqlite3")))
    return create_app(Services(bundle=bundle, ask=ask, traces=traces,
                               limiter=RateLimiter(limit=CHAT_PER_MINUTE, window_seconds=60),
                               cache=AnswerCache(capacity=CACHED_ANSWERS)))
