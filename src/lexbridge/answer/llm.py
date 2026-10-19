"""LLM gateway: an ordered list of OpenAI-compatible providers, tried until one answers.

Groq and Gemini both expose the OpenAI chat-completions shape, so one small client covers
both and no vendor SDK is needed. A provider is skipped when its key is not set, and the
next one is tried on a rate limit, a server error or a timeout. Anything else (a bad
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
FALLBACK_STATUSES = frozenset({429, 500, 502, 503, 504})


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
    "gemini": Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
                       "gemini-2.5-flash", "GEMINI_API_KEY"),
}


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


def _rejected_json(response: httpx.Response) -> str | None:
    """The model's own text when the provider refused it as invalid JSON, else None.

    Groq validates JSON mode server-side and answers 400 json_validate_failed when the
    model wrote bad JSON. That is the model failing, not the request, so it is handed back
    as a completion for the caller's malformed-reply handling to retry.
    """
    if response.status_code != 400:
        return None
    try:
        error = response.json().get("error", {})
    except ValueError:
        return None
    if error.get("code") != "json_validate_failed":
        return None
    return str(error.get("failed_generation") or "")


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
            except httpx.TimeoutException:
                failures.append(f"{provider.name}: timeout")
                continue
            if response.status_code in FALLBACK_STATUSES:
                failures.append(f"{provider.name}: HTTP {response.status_code}")
                continue
            elapsed = (time.perf_counter() - start) * 1000
            if (rejected := _rejected_json(response)) is not None:
                return Completion(rejected, provider.name, provider.model, elapsed)
            if response.is_error:
                # Raised, not fallen back from: any other 4xx is a bug or a bad key, and
                # the next provider would only hide it. The body says which.
                raise ProviderError(f"{provider.name}: HTTP {response.status_code}: "
                                    f"{response.text[:300]}")
            text = response.json()["choices"][0]["message"]["content"] or ""
            return Completion(text, provider.name, provider.model, elapsed)
        raise LLMUnavailableError("; ".join(failures))
