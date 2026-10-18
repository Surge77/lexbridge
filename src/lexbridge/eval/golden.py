"""Assemble the golden set: generated cases plus the hand-written ones.

The file is committed. It is a pure function of the bundle and hard_cases.py, but a
reviewer reads the questions, not the generator, and a diff of the file is how a change
to either shows up.

Usage:
    python -m lexbridge.eval.golden artifacts/v2026-10-18   # writes eval/golden.jsonl
"""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from lexbridge.bundle import Bundle, load_bundle
from lexbridge.eval.cases import Case, write_cases
from lexbridge.eval.generate import map_cases, topic_cases
from lexbridge.eval.hard_cases import HAND, Hand, expand

GOLDEN = Path("eval/golden.jsonl")


class GoldenError(ValueError):
    """The golden set names a section the bundle does not have, or repeats a case."""


def build_golden(bundle: Bundle, hand: Sequence[Hand] = HAND) -> list[Case]:
    cases = [*map_cases(bundle), *topic_cases(bundle), *(expand(h, bundle) for h in hand)]
    repeated = [i for i, n in Counter(c.id for c in cases).items() if n > 1]
    if repeated:
        raise GoldenError(f"repeated cases: {repeated}")
    missing = sorted({
        f"{c.id}: {s}" for c in cases for s in (*c.targets, *c.wrong_regime) if s not in bundle
    })
    if missing:
        raise GoldenError(f"sections not in {bundle.root}: {missing}")
    return cases


def main() -> None:  # pragma: no cover - reads a real bundle
    bundle = load_bundle(Path(sys.argv[1]))
    cases = build_golden(bundle)
    GOLDEN.parent.mkdir(exist_ok=True)
    write_cases(GOLDEN, cases)
    for category, n in sorted(Counter(c.category.value for c in cases).items()):
        print(f"{category:16} {n}")
    print(f"{'total':16} {len(cases)} -> {GOLDEN}")


if __name__ == "__main__":  # pragma: no cover
    main()
