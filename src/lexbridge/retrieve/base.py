"""What every retriever returns and what the evaluation runner calls."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Hit:
    section_id: str
    score: float


class Retriever(Protocol):
    def search_many(self, queries: Sequence[str], k: int) -> list[list[Hit]]: ...

    def search(self, query: str, k: int) -> list[Hit]: ...
