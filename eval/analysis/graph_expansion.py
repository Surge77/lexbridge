"""Does 1-hop graph expansion put more answers into the context than retrieving deeper?

One-off analysis behind docs/decisions/0003-retrieval-ladder.md, kept so the numbers
there can be reproduced. Not part of the package: the technique it measures was not built.

For each in-scope text question, with the v3-references pipeline:
  top5       a target is among the first 5 hits
  expanded   ... or among the refers_to neighbours of those 5 (both directions, same
             code, at most 8 added)
  same_size  a target is among the first 5 + (number added by expansion) hits
Expansion is worth building only if `expanded` beats `same_size`: the same context budget
spent on plain retrieval is the fair baseline.

Usage:
    HF_HUB_OFFLINE=1 python eval/analysis/graph_expansion.py artifacts/v2026-10-18
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from lexbridge.bundle import load_bundle
from lexbridge.eval.cases import read_cases
from lexbridge.eval.golden import GOLDEN
from lexbridge.eval.metrics import GRAPH_LOOKUPS
from lexbridge.ingest.graph import Relation
from lexbridge.retrieve.dense import DenseIndex
from lexbridge.retrieve.embed import SentenceTransformerEmbedder
from lexbridge.retrieve.pipeline import Pipeline

TOP, CAP = 5, 8


def main() -> None:
    root = Path(sys.argv[1])
    bundle = load_bundle(root)
    neighbours: dict[str, list[str]] = defaultdict(list)
    for e in bundle.edges:
        if e.relation is Relation.REFERS_TO and e.src in bundle and e.dst in bundle:
            neighbours[e.src].append(e.dst)
            neighbours[e.dst].append(e.src)
    dense = DenseIndex.build(bundle, SentenceTransformerEmbedder("bge-m3"),
                             cache_dir=root / "vectors")
    pipeline = Pipeline(bundle, dense, routed=True, references=True)
    cases = [c for c in read_cases(GOLDEN)
             if c.targets and c.category.value not in GRAPH_LOOKUPS]
    rankings = pipeline.search_many([c.question for c in cases], 50)

    rows: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for case, hits in zip(cases, rankings, strict=True):
        ids = [h.section_id for h in hits]
        top = ids[:TOP]
        code = top[0].partition(":")[0] if top else ""
        added: list[str] = []
        for section in top:
            for n in neighbours[section]:
                if n not in top and n not in added and n.startswith(f"{code}:"):
                    added.append(n)
        added = added[:CAP]
        targets = set(case.targets)
        row = rows[case.category.value]
        row["top5"].append(bool(targets & set(top)))
        row["expanded"].append(bool(targets & set(top + added)))
        row["same_size"].append(bool(targets & set(ids[:TOP + len(added)])))
        row["added"].append(len(added))

    for metric in ("top5", "expanded", "same_size"):
        macro = fmean(fmean(r[metric]) for r in rows.values())
        print(f"{metric:10} {macro * 100:.1f}",
              {c: round(fmean(r[metric]) * 100) for c, r in sorted(rows.items())})
    print("mean sections added:", round(fmean(x for r in rows.values() for x in r["added"]), 2))


if __name__ == "__main__":
    main()
