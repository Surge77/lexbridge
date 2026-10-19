from __future__ import annotations

import json

import httpx
import pytest

from lexbridge.answer.llm import Gateway, LLMUnavailableError, Provider

A = Provider("a", "https://a.test/v1", "model-a", "A_KEY")
B = Provider("b", "https://b.test/v1", "model-b", "B_KEY")
KEYS = {"A_KEY": "ka", "B_KEY": "kb"}


def ok(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def gateway(handler: object, env: dict[str, str] = KEYS) -> Gateway:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return Gateway([A, B], client=httpx.Client(transport=transport), env=env)


def test_the_first_provider_answers_with_its_own_key_and_model() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok('{"ok": true}')

    completion = gateway(handler).complete([{"role": "user", "content": "hi"}])

    assert (completion.text, completion.provider, completion.model) == (
        '{"ok": true}', "a", "model-a")
    [request] = seen
    assert str(request.url) == "https://a.test/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer ka"
    body = json.loads(request.content)
    assert body["model"] == "model-a"
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("status", [429, 503])
def test_a_rate_limit_or_server_error_falls_back_to_the_next(status: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status) if request.url.host == "a.test" else ok("from b")

    assert gateway(handler).complete([{"role": "user", "content": "hi"}]).provider == "b"


def test_a_timeout_falls_back_to_the_next() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "a.test":
            raise httpx.ReadTimeout("slow", request=request)
        return ok("from b")

    assert gateway(handler).complete([{"role": "user", "content": "hi"}]).text == "from b"


def test_a_bad_request_is_raised_not_hidden_behind_a_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad"})

    with pytest.raises(httpx.HTTPStatusError):
        gateway(handler).complete([{"role": "user", "content": "hi"}])


def test_every_provider_failing_names_each_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    with pytest.raises(LLMUnavailableError, match=r"a: HTTP 429; b: HTTP 429"):
        gateway(handler).complete([{"role": "user", "content": "hi"}])


def test_a_provider_without_a_key_is_skipped() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return ok("x")

    g = gateway(handler, env={"B_KEY": "kb"})

    assert g.providers == ["b"]
    g.complete([{"role": "user", "content": "hi"}], json_mode=False)
    assert seen == ["b.test"]


def test_no_key_at_all_is_a_clear_configuration_error() -> None:
    with pytest.raises(LLMUnavailableError, match="A_KEY, B_KEY"):
        Gateway([A, B], env={})
