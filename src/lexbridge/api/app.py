"""The HTTP API over the answer pipeline.

POST /chat answers with a plain JSON body, not a token stream: an answer is checked
against its sources before any of it may be shown (ADR 0004), so streaming would show
section numbers that verification has not passed yet.

The model's free tier is the resource to protect: its daily token budget is shared by
every visitor. So each client is limited per minute and per day, model calls are capped
across all clients, only so many answers run at once, and a repeated question is served
from the cache without a model call.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import math
import sqlite3
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path as PathLib
from typing import Annotated

from fastapi import FastAPI, Path, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from lexbridge.answer.llm import LLMUnavailableError, ProviderError
from lexbridge.answer.service import Answer, Status
from lexbridge.api import errors
from lexbridge.api.errors import ApiError
from lexbridge.api.guard import AnswerCache, Limits, RateLimiter
from lexbridge.api.schemas import (
    SECTION_ID,
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    HealthOut,
    MapOut,
    SectionOut,
)
from lexbridge.api.traces import TraceLog
from lexbridge.bundle import Bundle

logger = logging.getLogger(__name__)
SectionId = Annotated[str, Path(pattern=SECTION_ID)]
# A decline can come from a malformed or unsupported model reply, which a retry may not
# repeat; only answers and clarifications are worth serving again.
CACHEABLE = frozenset({Status.ANSWERED, Status.CLARIFY})
EVERYONE = "*"
STATIC = PathLib(__file__).parent / "static"


@dataclass(frozen=True)
class Services:
    bundle: Bundle
    # The whole pipeline (route, retrieve, model, verify) behind one call, so the API
    # can be tested without models and served with them.
    ask: Callable[[str, date | None], Answer]
    traces: TraceLog
    limits: Limits
    cache: AnswerCache[tuple[str, date | None], Answer]
    # How many addresses trusted proxies append to X-Forwarded-For (1 behind one proxy).
    # 0 trusts the header not at all and limits by the connecting address.
    proxy_hops: int = 0
    max_in_flight: int = 4


def client_of(request: Request, proxy_hops: int) -> str:
    """Who to limit: the address the trusted proxy saw, never one the client wrote.

    A proxy appends the address it received from, so the client controls everything left
    of the last `proxy_hops` entries and nothing at or right of it.
    """
    address = request.client.host if request.client else "unknown"
    if proxy_hops:
        forwarded = [a.strip() for a in request.headers.get("x-forwarded-for", "").split(",")
                     if a.strip()]
        if len(forwarded) >= proxy_hops:
            address = forwarded[-proxy_hops]
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address
    # One IPv6 subscriber is handed a whole /64; limit it as one client.
    return str(ipaddress.ip_network(f"{ip}/64", strict=False)) if ip.version == 6 else str(ip)


def _retry_after(wait: float) -> dict[str, str]:
    return {"Retry-After": str(max(1, math.ceil(wait)))}


def create_app(services: Services) -> FastAPI:
    app = FastAPI(title="LexBridge", version="0.1.0", docs_url=None, redoc_url=None,
                  openapi_url=None)
    errors.install(app)
    s = services
    # Its own threads, so slow model calls cannot starve trace writes and other work.
    pool = ThreadPoolExecutor(max_workers=max(1, s.max_in_flight),
                              thread_name_prefix="answer")
    in_flight = 0  # touched only on the event loop's thread

    def limit(request: Request, *limiters: RateLimiter) -> None:
        client = client_of(request, s.proxy_hops)
        for limiter in limiters:
            if (wait := limiter.wait(client)) > 0:
                raise ApiError(429, "RATE_LIMITED", "Too many requests; please wait a "
                               "moment.", _retry_after(wait))

    async def ask(question: str, offence_date: date | None) -> Answer:
        nonlocal in_flight
        if in_flight >= s.max_in_flight:
            raise ApiError(503, "BUSY", "Several questions are being answered right now. "
                           "Please try again in a few seconds.", _retry_after(5))
        if (wait := s.limits.model_calls.wait(EVERYONE)) > 0:
            raise ApiError(503, "DAILY_LIMIT", "Today's free answering budget is used up. "
                           "Please try again later.", _retry_after(wait))
        in_flight += 1
        try:
            return await asyncio.get_running_loop().run_in_executor(
                pool, s.ask, question, offence_date)
        except LLMUnavailableError as e:
            logger.warning("no model available: %s", e)
            raise ApiError(503, "LLM_UNAVAILABLE", "The answering service is busy. "
                           "Please try again in a few minutes.") from e
        except ProviderError as e:
            logger.error("model provider rejected the request: %s", e)
            raise ApiError(502, "LLM_ERROR", "The answering service failed. "
                           "Please try again later.") from e
        finally:
            in_flight -= 1

    async def trace(question: str, result: Answer, start: float, cached: bool) -> str | None:
        def write() -> str:
            return s.traces.record(
                question=question, status=result.status.value,
                act=result.act.value if result.act else None, reason=result.reason.value,
                citations=result.citations, calls=0 if cached else len(result.calls),
                milliseconds=(time.perf_counter() - start) * 1000, cached=cached)
        try:
            return await asyncio.get_running_loop().run_in_executor(None, write)
        except sqlite3.Error as e:
            # The answer is paid for; losing its trace must not lose it too.
            logger.error("trace not written: %s", type(e).__name__)
            return None

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    async def page() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/health")
    async def health() -> HealthOut:
        return HealthOut(status="ok", bundle=s.bundle.root.name,
                         sections=len(s.bundle.sections))

    @app.get("/section/{section_id}")
    async def section(section_id: SectionId, request: Request) -> SectionOut:
        limit(request, s.limits.lookups)
        if section_id not in s.bundle:
            raise ApiError(404, "NOT_FOUND", "No such section in this bundle.")
        found = s.bundle.section(section_id)
        return SectionOut(id=found.id, act=found.act.value, number=found.number,
                          title=found.title, text=found.text, chapter=found.chapter)

    @app.get("/map/{section_id}")
    async def mapping(section_id: SectionId, request: Request) -> MapOut:
        limit(request, s.limits.lookups)
        if section_id not in s.bundle:
            raise ApiError(404, "NOT_FOUND", "No such section in this bundle.")
        return MapOut(id=section_id, replaced_by=list(s.bundle.replaced_by(section_id)),
                      replaces=list(s.bundle.replaces(section_id)))

    @app.post("/chat")
    async def chat(body: ChatRequest, request: Request) -> ChatResponse:
        limit(request, s.limits.per_minute, s.limits.per_day)
        question = " ".join(body.question.split())
        key = (question.casefold(), body.offence_date)
        start = time.perf_counter()
        result = s.cache.get(key)
        cached = result is not None
        if result is None:
            result = await ask(question, body.offence_date)
            if result.status in CACHEABLE:
                s.cache.put(key, result)
        return ChatResponse(trace_id=await trace(question, result, start, cached),
                            status=result.status.value, text=result.text,
                            act=result.act.value if result.act else None,
                            citations=list(result.citations), sources=list(result.allowed),
                            cached=cached)

    @app.post("/feedback", status_code=204)
    async def feedback(body: FeedbackRequest, request: Request) -> Response:
        limit(request, s.limits.per_minute)
        found = await asyncio.get_running_loop().run_in_executor(
            None, lambda: s.traces.feedback(body.trace_id, helpful=body.helpful))
        if not found:
            raise ApiError(404, "NOT_FOUND", "No answer has that trace id.")
        return Response(status_code=204)

    return app
