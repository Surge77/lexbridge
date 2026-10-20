"""The HTTP API over the answer pipeline.

POST /chat answers with a plain JSON body, not a token stream: an answer is checked
against its sources before any of it may be shown (ADR 0004), so streaming would show
section numbers that verification has not passed yet.

Errors share one shape, {"error": {"code", "message"}}, and never carry an exception's
own text: provider messages and paths are for the server log, not the client.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import FastAPI, Path, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from lexbridge.answer.llm import LLMUnavailableError, ProviderError
from lexbridge.answer.service import Answer
from lexbridge.api.guard import AnswerCache, RateLimiter
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


@dataclass(frozen=True)
class Services:
    bundle: Bundle
    # The whole pipeline (route, retrieve, model, verify) behind one call, so the API
    # can be tested without models and served with them.
    ask: Callable[[str, date | None], Answer]
    traces: TraceLog
    limiter: RateLimiter
    cache: AnswerCache[tuple[str, date | None], Answer]


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str,
                 headers: dict[str, str] | None = None) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.headers = status, code, message, headers


def _error(status: int, code: str, message: str, **extra: object) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, **extra}},
                        status_code=status)


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, e: ApiError) -> JSONResponse:
        response = _error(e.status, e.code, e.message)
        response.headers.update(e.headers or {})
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, e: RequestValidationError) -> JSONResponse:
        fields = [{"field": str(err["loc"][-1]), "message": err["msg"]} for err in e.errors()]
        return _error(422, "INVALID_REQUEST", "The request is not valid.", fields=fields)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, e: HTTPException) -> JSONResponse:
        code = "NOT_FOUND" if e.status_code == 404 else "HTTP_ERROR"
        return _error(e.status_code, code, "Not found." if e.status_code == 404
                      else "The request could not be handled.")

    @app.exception_handler(Exception)
    async def unexpected(_: Request, e: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", type(e).__name__)
        return _error(500, "INTERNAL", "Something went wrong. Please try again later.")


def _client(request: Request) -> str:
    # The peer address. Behind a proxy, uvicorn's --proxy-headers rewrites it from the
    # proxy's X-Forwarded-For; a header from the open internet is never trusted here.
    return request.client.host if request.client else "unknown"


def create_app(services: Services) -> FastAPI:
    app = FastAPI(title="LexBridge", version="0.1.0")
    _install_error_handlers(app)
    s = services

    @app.get("/health")
    async def health() -> HealthOut:
        return HealthOut(status="ok", bundle=s.bundle.root.name,
                         sections=len(s.bundle.sections))

    @app.get("/section/{section_id}")
    async def section(section_id: SectionId) -> SectionOut:
        if section_id not in s.bundle:
            raise ApiError(404, "NOT_FOUND", "No such section in this bundle.")
        found = s.bundle.section(section_id)
        return SectionOut(id=found.id, act=found.act.value, number=found.number,
                          title=found.title, text=found.text, chapter=found.chapter)

    @app.get("/map/{section_id}")
    async def mapping(section_id: SectionId) -> MapOut:
        if section_id not in s.bundle:
            raise ApiError(404, "NOT_FOUND", "No such section in this bundle.")
        return MapOut(id=section_id, replaced_by=list(s.bundle.replaced_by(section_id)),
                      replaces=list(s.bundle.replaces(section_id)))

    @app.post("/chat")
    async def chat(body: ChatRequest, request: Request) -> ChatResponse:
        if (wait := s.limiter.wait(_client(request))) > 0:
            raise ApiError(429, "RATE_LIMITED", "Too many questions; please wait a moment.",
                           {"Retry-After": str(math.ceil(wait))})
        key = (body.question.casefold(), body.offence_date)
        loop = asyncio.get_running_loop()
        start = time.perf_counter()
        result = s.cache.get(key)
        cached = result is not None
        if result is None:
            try:
                # Embedding the question and the model call block; keep them off the loop.
                result = await loop.run_in_executor(None, s.ask, body.question,
                                                    body.offence_date)
            except LLMUnavailableError as e:
                logger.warning("no model available: %s", e)
                raise ApiError(503, "LLM_UNAVAILABLE", "The answering service is busy. "
                               "Please try again in a few minutes.") from e
            except ProviderError as e:
                logger.error("model provider rejected the request: %s", e)
                raise ApiError(502, "LLM_ERROR", "The answering service failed. "
                               "Please try again later.") from e
            s.cache.put(key, result)
        answered = result
        trace_id = await loop.run_in_executor(None, lambda: s.traces.record(
            question=body.question, status=answered.status.value,
            act=answered.act.value if answered.act else None,
            reason=answered.reason.value, citations=answered.citations,
            calls=0 if cached else len(answered.calls),
            milliseconds=(time.perf_counter() - start) * 1000, cached=cached))
        return ChatResponse(trace_id=trace_id, status=answered.status.value,
                            text=answered.text,
                            act=answered.act.value if answered.act else None,
                            citations=list(answered.citations),
                            sources=list(answered.allowed), cached=cached)

    @app.post("/feedback", status_code=204)
    async def feedback(body: FeedbackRequest) -> Response:
        loop = asyncio.get_running_loop()
        found = await loop.run_in_executor(
            None, lambda: s.traces.feedback(body.trace_id, helpful=body.helpful))
        if not found:
            raise ApiError(404, "NOT_FOUND", "No answer has that trace id.")
        return Response(status_code=204)

    return app
