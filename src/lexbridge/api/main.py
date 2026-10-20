"""Build the served app: load the bundle and models once, then answer with them.

    LEXBRIDGE_BUNDLE=artifacts/v2026-10-18 GROQ_API_KEY=... \
        uvicorn --factory lexbridge.api.main:build

Do not pass uvicorn --proxy-headers: client addresses come from X-Forwarded-For only as
far as LEXBRIDGE_PROXY_HOPS trusts it (1 behind a single proxy, such as Hugging Face
Spaces). LEXBRIDGE_TRACE_KEY (hex) keys the question hashes in the trace log.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import date
from pathlib import Path

from fastapi import FastAPI

from lexbridge.api.app import Services, create_app
from lexbridge.api.guard import AnswerCache, Limits, RateLimiter

logger = logging.getLogger(__name__)
DAY = 86_400
# Generous for a person, and far below what it takes for one client to spend the shared
# budget: 50 questions a day is an eighth of it.
PER_MINUTE = 5
QUESTIONS_PER_DAY = 50
# Two Groq models at 200k tokens a day each, ~700 tokens an answer (the 92-case eval spent
# ~65k): about 570 answers. 400 leaves room for scope checks and retries.
MODEL_CALLS_PER_DAY = 400
# Opening an answer's sections costs two lookups each and no model call.
LOOKUPS_PER_MINUTE = 60
CACHED_ANSWERS = 512
# A day: long enough to absorb repeats, short enough that a fixed answer does not linger.
CACHE_SECONDS = DAY


def _trace_key() -> bytes:  # pragma: no cover - reads the environment
    if key := os.environ.get("LEXBRIDGE_TRACE_KEY"):
        return bytes.fromhex(key)
    logger.warning("LEXBRIDGE_TRACE_KEY is not set: repeats are traced within this run only")
    return secrets.token_bytes(32)


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

    limits = Limits(per_minute=RateLimiter(limit=PER_MINUTE, window_seconds=60),
                    per_day=RateLimiter(limit=QUESTIONS_PER_DAY, window_seconds=DAY),
                    model_calls=RateLimiter(limit=MODEL_CALLS_PER_DAY, window_seconds=DAY),
                    lookups=RateLimiter(limit=LOOKUPS_PER_MINUTE, window_seconds=60))
    traces = TraceLog(Path(os.environ.get("LEXBRIDGE_TRACES", "traces.sqlite3")),
                      key=_trace_key())
    return create_app(Services(
        bundle=bundle, ask=ask, traces=traces, limits=limits,
        cache=AnswerCache(capacity=CACHED_ANSWERS, ttl_seconds=CACHE_SECONDS),
        proxy_hops=int(os.environ.get("LEXBRIDGE_PROXY_HOPS", "0"))))
