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
from dataclasses import dataclass

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


PROVIDERS = {
    "groq": Provider("groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b",
                     "GROQ_API_KEY"),
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
                                       "temperature": 0, "max_completion_tokens": max_tokens}
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
            # Raised, not fallen back from: a 400 or 401 is a bug or a bad key, and the
            # next provider would only hide it.
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"] or ""
            return Completion(text, provider.name, provider.model,
                              (time.perf_counter() - start) * 1000)
        raise LLMUnavailableError("; ".join(failures))
