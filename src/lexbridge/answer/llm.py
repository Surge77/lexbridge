"""LLM gateway: an ordered list of OpenAI-compatible providers, tried until one answers.

Groq and Gemini both expose the OpenAI chat-completions shape, so one small client covers
both and no vendor SDK is needed. A provider is skipped when its key is not set, and the
next one is tried on a rate limit, a server error, a timeout, a broken connection or a
success whose body is not a chat completion. Anything else (a bad
request, a rejected key) is a bug or a configuration error, and is raised rather than
hidden behind a fallback.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import httpx

# Every external call has a deadline; a stuck provider must hand over, not hang a request.
TIMEOUT_SECONDS = 10.0
# 413 is how Groq refuses a request over the tokens-per-minute budget: busy, not wrong.
FALLBACK_STATUSES = frozenset({408, 413, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    model: str
    key_env: str
    # Extra request fields the model needs, merged into every body.
    options: Mapping[str, object] = field(default_factory=dict)


PROVIDERS = {
    # gpt-oss reasons before it answers, and the reasoning is paid for out of
    # max_completion_tokens and the per-minute token budget. Grounded summaries and a
    # yes/no scope check need little of it.
    "groq": Provider("groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b",
                     "GROQ_API_KEY", {"reasoning_effort": "low"}),
    # Groq's free tier caps tokens per day per model (200k), so a second model behind the
    # same key is a second day's budget: when the first is spent it answers 429, and the
    # gateway moves on.
    "groq-large": Provider("groq-large", "https://api.groq.com/openai/v1",
                           "openai/gpt-oss-120b", "GROQ_API_KEY", {"reasoning_effort": "low"}),
    "gemini": Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
                       "gemini-2.5-flash", "GEMINI_API_KEY"),
}
# The order the app and the evaluation try them in.
CHAIN = (PROVIDERS["groq"], PROVIDERS["groq-large"], PROVIDERS["gemini"])


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    model: str
    latency_ms: float


class LLMUnavailableError(RuntimeError):
    """No configured provider could answer."""


class ProviderError(RuntimeError):
    """A provider rejected the request itself: a bug or a bad key, not a busy server."""


def _error(response: httpx.Response) -> dict[str, object]:
    """The OpenAI-shaped {"error": {...}} of a response, or {} for any other body."""
    try:
        body = response.json()
    except ValueError:
        return {}
    error = body.get("error") if isinstance(body, dict) else None
    return error if isinstance(error, dict) else {}


def _rejected_json(response: httpx.Response) -> str | None:
    """The model's own text when the provider refused it as invalid JSON, else None.

    Groq validates JSON mode server-side and answers 400 json_validate_failed when the
    model wrote bad JSON. That is the model failing, not the request, so it is handed back
    as a completion for the caller's malformed-reply handling to retry.
    """
    error = _error(response)
    if response.status_code != 400 or error.get("code") != "json_validate_failed":
        return None
    return str(error.get("failed_generation") or "")


def _content(response: httpx.Response) -> str | None:
    """The reply text of a success, or None when the body is not a chat completion."""
    try:
        return response.json()["choices"][0]["message"]["content"] or ""
    except (ValueError, LookupError, TypeError):
        return None


class Gateway:
    def __init__(self, providers: Sequence[Provider], *, client: httpx.Client | None = None,
                 env: Mapping[str, str] | None = None) -> None:
        env = os.environ if env is None else env
        self._providers = [(p, env[p.key_env]) for p in providers if env.get(p.key_env)]
        if not self._providers:
            names = ", ".join(p.key_env for p in providers)
            raise LLMUnavailableError(f"no LLM key is set; set one of: {names}")
        self._client = client or httpx.Client(timeout=TIMEOUT_SECONDS)

    @property
    def providers(self) -> list[str]:
        return [p.name for p, _ in self._providers]

    def complete(self, messages: Sequence[Mapping[str, str]], *, max_tokens: int = 700,
                 json_mode: bool = True) -> Completion:
        failures: list[str] = []
        for provider, key in self._providers:
            body: dict[str, object] = {"model": provider.model, "messages": list(messages),
                                       "temperature": 0, "max_completion_tokens": max_tokens,
                                       **provider.options}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            start = time.perf_counter()
            try:
                response = self._client.post(f"{provider.base_url}/chat/completions",
                                             json=body,
                                             headers={"Authorization": f"Bearer {key}"})
            except httpx.TransportError as e:  # a timeout, a refused or dropped connection
                failures.append(f"{provider.name}: {type(e).__name__}")
                continue
            if response.status_code in FALLBACK_STATUSES:
                failures.append(f"{provider.name}: HTTP {response.status_code}")
                continue
            elapsed = (time.perf_counter() - start) * 1000
            if (rejected := _rejected_json(response)) is not None:
                return Completion(rejected, provider.name, provider.model, elapsed)
            if response.is_error:
                # Raised, not fallen back from: any other 4xx is a bug or a bad key, and
                # the next provider would only hide it. Only the error code is kept: the
                # body's free text can describe the account, and this message is logged.
                code = _error(response).get("code")
                raise ProviderError(f"{provider.name}: HTTP {response.status_code}"
                                    + (f" {code}" if code else ""))
            if (text := _content(response)) is None:
                failures.append(f"{provider.name}: unreadable response")
                continue
            return Completion(text, provider.name, provider.model, elapsed)
        raise LLMUnavailableError("; ".join(failures))
