"""Assemble the files a Hugging Face Docker Space needs into one directory.

    python deploy/stage_space.py <out-dir> [--bundle artifacts/v2026-10-18]

The Space gets the Dockerfile, the package source, the Space card as its README and one
bundle with its cached vectors: not the raw PDFs, the eval reports or any local cache.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE_FILES = ("manifest.json", "sections.jsonl", "edges.jsonl", "correspondences.jsonl")


def stage(out: Path, bundle: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy2(ROOT / "Dockerfile", out / "Dockerfile")
    shutil.copy2(ROOT / "pyproject.toml", out / "pyproject.toml")
    shutil.copy2(ROOT / "deploy" / "space-card.md", out / "README.md")
    shutil.copytree(ROOT / "src", out / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"))
    target = out / "artifacts" / bundle.name
    target.mkdir(parents=True)
    for name in BUNDLE_FILES:
        shutil.copy2(bundle / name, target / name)
    shutil.copytree(bundle / "vectors", target / "vectors")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--bundle", type=Path, default=ROOT / "artifacts" / "v2026-10-18")
    args = parser.parse_args()
    stage(args.out, args.bundle)
    print(f"staged {sum(1 for p in args.out.rglob('*') if p.is_file())} files in {args.out}")


if __name__ == "__main__":
    main()
