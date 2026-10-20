from __future__ import annotations

import asyncio
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from lexbridge.answer.llm import LLMUnavailableError, ProviderError
from lexbridge.answer.service import Answer, Status
from lexbridge.api.app import Services, create_app
from lexbridge.api.guard import AnswerCache, Limits, RateLimiter
from lexbridge.api.traces import TraceLog
from lexbridge.query.route import Reason
from lexbridge.schema import Act

from ..eval.factory import build_bundle

ANSWER = Answer(Status.ANSWERED, "Assuming ..., theft is punished under BNS 303(2).",
                ("BNS:303",), Act.BNS, Reason.DATE, ("BNS:303", "IPC:379"))


class Asker:
    """Stands in for the answer pipeline; records what it was asked."""

    def __init__(self, outcome: Answer | Exception = ANSWER) -> None:
        self.outcome = outcome
        self.asked: list[tuple[str, date | None]] = []

    def __call__(self, question: str, offence_date: date | None) -> Answer:
        self.asked.append((question, offence_date))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class Client:
    """Calls the app in process through httpx's ASGI transport.

    Not starlette's TestClient: from starlette 1.x it wants the separate httpx2 package,
    and this project already pins httpx.
    """

    def __init__(self, app: FastAPI) -> None:
        # raise_app_exceptions=False: a 500 is checked as the client would see it.
        self._transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    def _call(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        async def go() -> httpx.Response:
            async with httpx.AsyncClient(transport=self._transport,
                                         base_url="http://test") as c:
                return await c.request(method, path, **kwargs)  # type: ignore[arg-type]
        return asyncio.run(go())

    def get(self, path: str) -> httpx.Response:
        return self._call("GET", path)

    def post(self, path: str, json: object,
             headers: dict[str, str] | None = None) -> httpx.Response:
        return self._call("POST", path, json=json, headers=headers)


class BrokenTraces(TraceLog):
    def record(self, **_: object) -> str:  # type: ignore[override]
        raise sqlite3.OperationalError("disk I/O error")


def client_for(tmp_path: Path, asker: Asker, *, per_minute: int = 100, model_calls: int = 100,
               max_in_flight: int = 4, proxy_hops: int = 0,
               traces: type[TraceLog] = TraceLog) -> Client:
    limits = Limits(per_minute=RateLimiter(limit=per_minute, window_seconds=60),
                    per_day=RateLimiter(limit=100, window_seconds=86_400),
                    model_calls=RateLimiter(limit=model_calls, window_seconds=86_400),
                    lookups=RateLimiter(limit=100, window_seconds=60))
    services = Services(bundle=build_bundle(tmp_path / "v1"), ask=asker,
                        traces=traces(tmp_path / "traces.sqlite3", key=b"k" * 32),
                        limits=limits, cache=AnswerCache(capacity=8, ttl_seconds=60),
                        proxy_hops=proxy_hops, max_in_flight=max_in_flight)
    return Client(create_app(services))


@pytest.fixture
def asker() -> Asker:
    return Asker()


@pytest.fixture
def client(tmp_path: Path, asker: Asker) -> Client:
    return client_for(tmp_path, asker)


def test_health_names_the_bundle_it_serves(client: Client) -> None:
    assert client.get("/health").json() == {"status": "ok", "bundle": "v1", "sections": 9}


def test_a_section_is_served_by_its_id(client: Client) -> None:
    body = client.get("/section/IPC:420").json()

    assert (body["id"], body["act"], body["number"]) == ("IPC:420", "IPC", "420")
    assert body["text"].startswith("420. Cheating")


@pytest.mark.parametrize(("path", "status"), [("/section/IPC:999", 404),
                                              ("/section/../../etc", 404),
                                              ("/section/ipc:420", 422),
                                              ("/map/CrPC:41", 422)])
def test_an_unknown_or_malformed_section_id_is_refused(
        client: Client, path: str, status: int) -> None:
    response = client.get(path)

    assert response.status_code == status
    assert set(response.json()["error"]) >= {"code", "message"}


def test_the_map_gives_both_directions_of_the_table(client: Client) -> None:
    assert client.get("/map/IPC:420").json() == {"id": "IPC:420", "replaced_by": ["BNS:318"],
                                                  "replaces": []}
    assert client.get("/map/BNS:303").json()["replaces"] == ["IPC:378", "IPC:379"]


def test_a_question_is_answered_with_its_sources_and_a_trace_id(
        client: Client, asker: Asker) -> None:
    body = client.post("/chat", json={"question": "  Theft in 2025?  ",
                                      "offence_date": "2025-01-02"}).json()

    assert asker.asked == [("Theft in 2025?", date(2025, 1, 2))]
    assert (body["status"], body["act"], body["citations"]) == ("answered", "BNS",
                                                                ["BNS:303"])
    assert body["sources"] == ["BNS:303", "IPC:379"]
    assert len(body["trace_id"]) == 32 and body["cached"] is False
    assert "not legal advice" in body["notice"]


@pytest.mark.parametrize(("payload", "field"), [
    ({"question": ""}, "question"),
    ({"question": "x" * 1001}, "question"),
    ({"question": "theft", "offence_date": str(date.today() + timedelta(days=2))},
     "offence_date"),
    ({"question": "theft", "extra": 1}, "extra"),
])
def test_an_invalid_request_is_refused_field_by_field(
        client: Client, asker: Asker, payload: dict[str, object], field: str) -> None:
    response = client.post("/chat", json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_REQUEST"
    assert field in [f["field"] for f in error["fields"]]
    assert asker.asked == []


def test_a_repeated_question_is_served_from_the_cache(
        client: Client, asker: Asker) -> None:
    first = client.post("/chat", json={"question": "Theft in 2025?"}).json()
    again = client.post("/chat", json={"question": "theft in 2025?"}).json()

    assert len(asker.asked) == 1
    assert (first["cached"], again["cached"]) == (False, True)
    assert first["trace_id"] != again["trace_id"]


def test_a_client_over_its_limit_is_told_when_to_return(tmp_path: Path) -> None:
    client = client_for(tmp_path, Asker(), per_minute=1)
    client.post("/chat", json={"question": "Theft in 2025?"})

    response = client.post("/chat", json={"question": "Theft in 2025?"})

    assert response.status_code == 429
    assert int(response.headers["retry-after"]) >= 1
    assert response.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.parametrize(("error", "status", "code"), [
    (LLMUnavailableError("groq: HTTP 429"), 503, "LLM_UNAVAILABLE"),
    (ProviderError("groq: HTTP 401 invalid_api_key"), 502, "LLM_ERROR"),
    (RuntimeError("bundle path C:/secret"), 500, "INTERNAL"),
])
def test_a_failure_is_reported_without_its_internal_detail(
        tmp_path: Path, error: Exception, status: int, code: str) -> None:
    response = client_for(tmp_path, Asker(error)).post("/chat",
                                                       json={"question": "Theft in 2025?"})

    assert (response.status_code, response.json()["error"]["code"]) == (status, code)
    assert str(error) not in response.text


def test_feedback_is_accepted_for_a_real_answer_only(client: Client) -> None:
    trace_id = client.post("/chat", json={"question": "Theft in 2025?"}).json()["trace_id"]

    assert client.post("/feedback", json={"trace_id": trace_id,
                                          "helpful": True}).status_code == 204
    assert client.post("/feedback", json={"trace_id": "0" * 32,
                                          "helpful": True}).status_code == 404
    assert client.post("/feedback", json={"trace_id": "nope",
                                          "helpful": True}).status_code == 422


def test_the_shared_model_budget_stops_new_questions_but_not_cached_ones(
        tmp_path: Path) -> None:
    asker = Asker()
    client = client_for(tmp_path, asker, model_calls=1)
    client.post("/chat", json={"question": "Theft in 2025?"})

    refused = client.post("/chat", json={"question": "Cheating in 2025?"})
    repeat = client.post("/chat", json={"question": "Theft in 2025?"})

    assert (refused.status_code, refused.json()["error"]["code"]) == (503, "DAILY_LIMIT")
    assert int(refused.headers["retry-after"]) >= 1
    assert repeat.status_code == 200 and repeat.json()["cached"] is True
    assert len(asker.asked) == 1


def test_when_every_answer_slot_is_taken_a_question_is_turned_away_at_once(
        tmp_path: Path) -> None:
    asker = Asker()

    response = client_for(tmp_path, asker, max_in_flight=0).post(
        "/chat", json={"question": "Theft in 2025?"})

    assert (response.status_code, response.json()["error"]["code"]) == (503, "BUSY")
    assert asker.asked == []


@pytest.mark.parametrize(("hops", "forwarded", "limited"), [
    # Behind one proxy: the client wrote everything left of the address it appended.
    (1, ["6.6.6.1, 1.2.3.4", "6.6.6.2, 1.2.3.4"], True),
    (1, ["1.2.3.4", "5.6.7.8"], False),
    # Trusting no proxy, the header is ignored and the connecting address is limited.
    (0, ["1.2.3.4", "5.6.7.8"], True),
])
def test_the_limit_follows_the_address_the_trusted_proxy_saw(
        tmp_path: Path, hops: int, forwarded: list[str], limited: bool) -> None:
    client = client_for(tmp_path, Asker(), per_minute=1, proxy_hops=hops)

    codes = [client.post("/chat", json={"question": "Theft in 2025?"},
                         headers={"X-Forwarded-For": f}).status_code for f in forwarded]

    assert (codes[1] == 429) is limited


def test_a_decline_is_not_cached(tmp_path: Path) -> None:
    asker = Asker(Answer(Status.DECLINED, "I could not answer.", (), Act.BNS, Reason.DATE))
    client = client_for(tmp_path, asker)

    client.post("/chat", json={"question": "Theft in 2025?"})
    client.post("/chat", json={"question": "Theft in 2025?"})

    assert len(asker.asked) == 2


def test_internal_spacing_and_case_do_not_defeat_the_cache(
        client: Client, asker: Asker) -> None:
    client.post("/chat", json={"question": "Theft  in\n2025?"})
    client.post("/chat", json={"question": "THEFT in 2025?"})

    assert asker.asked == [("Theft in 2025?", None)]


def test_an_answer_is_still_given_when_its_trace_cannot_be_written(tmp_path: Path) -> None:
    response = client_for(tmp_path, Asker(), traces=BrokenTraces).post(
        "/chat", json={"question": "Theft in 2025?"})

    assert response.status_code == 200
    assert response.json()["trace_id"] is None


def test_an_oversized_body_is_refused_before_it_is_read(client: Client, asker: Asker) -> None:
    response = client.post("/chat", json={"question": "x" * 9000})

    assert (response.status_code, response.json()["error"]["code"]) == (413, "TOO_LARGE")
    assert asker.asked == []


def test_a_wrong_method_keeps_its_allow_header(client: Client) -> None:
    response = client.get("/chat")

    assert response.status_code == 405
    assert response.headers["allow"] == "POST"


def test_the_interactive_docs_are_not_served(client: Client) -> None:
    assert [client.get(p).status_code for p in ("/docs", "/openapi.json")] == [404, 404]


def test_the_page_and_its_assets_are_served_with_a_strict_policy(client: Client) -> None:
    page = client.get("/")
    script = client.get("/static/app.js")

    assert page.status_code == 200 and "<title>LexBridge</title>" in page.text
    assert script.status_code == 200 and "textContent" in script.text
    policy = page.headers["content-security-policy"]
    assert "default-src 'self'" in policy and "unsafe-inline" not in policy
    # Hugging Face shows a Space inside its own page.
    assert "frame-ancestors 'self' https://huggingface.co" in policy
    assert page.headers["x-content-type-options"] == "nosniff"


def test_looking_up_sections_does_not_use_up_the_question_allowance(tmp_path: Path) -> None:
    client = client_for(tmp_path, Asker(), per_minute=1)
    for _ in range(4):
        assert client.get("/section/IPC:420").status_code == 200
        assert client.get("/map/IPC:420").status_code == 200

    assert client.post("/chat", json={"question": "Theft in 2025?"}).status_code == 200
