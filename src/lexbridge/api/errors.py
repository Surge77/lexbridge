"""One error shape for every failure, and nothing internal in it.

Errors are {"error": {"code", "message"}}. An exception's own text never reaches a client:
provider messages and paths are for the server log. Even the log gets only an unexpected
error's type and frames, not its message, which can quote the question.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)
# A question is at most 1000 characters; a few KB of JSON is every honest request.
MAX_BODY_BYTES = 8 * 1024


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str,
                 headers: Mapping[str, str] | None = None) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.headers = status, code, message, headers


def error(status: int, code: str, message: str, headers: Mapping[str, str] | None = None,
          **extra: object) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, **extra}},
                        status_code=status, headers=headers)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, e: ApiError) -> JSONResponse:
        return error(e.status, e.code, e.message, e.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, e: RequestValidationError) -> JSONResponse:
        fields = [{"field": str(err["loc"][-1]), "message": err["msg"]} for err in e.errors()]
        return error(422, "INVALID_REQUEST", "The request is not valid.", fields=fields)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, e: HTTPException) -> JSONResponse:
        if e.status_code == 404:
            return error(404, "NOT_FOUND", "Not found.", e.headers)
        # e.headers carries what the status needs, such as Allow on a 405.
        return error(e.status_code, "HTTP_ERROR", "The request could not be handled.",
                     e.headers)

    @app.middleware("http")
    async def contain(request: Request,
                      call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # A middleware, not an exception handler: starlette re-raises after an Exception
        # handler, and the server would then log the full exception, message and all.
        try:
            return await call_next(request)
        except Exception as e:
            logger.error("unhandled %s\n%s", type(e).__name__,
                         "".join(traceback.format_tb(e.__traceback__)))
            return error(500, "INTERNAL", "Something went wrong. Please try again later.")

    @app.middleware("http")
    async def cap_body(request: Request,
                       call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Checked before the body is read, so an oversized one is never buffered.
        if request.method == "POST":
            length = request.headers.get("content-length")
            if length is None:
                return error(411, "LENGTH_REQUIRED", "Send a Content-Length header.")
            if not length.isdigit() or int(length) > MAX_BODY_BYTES:
                return error(413, "TOO_LARGE", "The request body is too large.")
        return await call_next(request)
