"""Download the statute PDFs and pin each one by SHA-256.

Government hosts are the only sources: the bot quotes this text as law, so a commercial
bare-act PDF is not acceptable even when it is easier to reach.

Usage:
    python -m lexbridge.ingest.fetch            # writes data/raw/*.pdf and data/sources.json
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

# IndiaCode sits behind Akamai, which intermittently answers with a 200-status HTML error
# page or drops the connection. Three attempts with backoff got every file through when
# this was written; a fourth never helped.
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 5.0
TIMEOUT_SECONDS = 90.0
PDF_MAGIC = b"%PDF"
# Some government hosts reject the default Python-urllib agent outright.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) lexbridge/0.1 (+research)"
INDIACODE_CONTENT = "https://indiacode.gov.in/server/api/core/bitstreams"


class NotAPdfError(ValueError):
    """The host answered, but not with a PDF — usually a CDN error page."""


@dataclass(frozen=True)
class Source:
    key: str
    url: str
    filename: str


@dataclass(frozen=True)
class FetchResult:
    key: str
    url: str
    filename: str
    sha256: str
    size: int


SOURCES: tuple[Source, ...] = (
    # As passed and gazetted, 25 Dec 2023. The baseline every amendment is diffed against.
    Source(
        key="bns_original",
        url="https://prsindia.org/files/bills_acts/bills_parliament/2023/"
        "The%20Bharatiya%20Nyaya%20Sanhita,%202023.pdf",
        filename="bns_original.pdf",
    ),
    # IndiaCode moved to indiacode.gov.in (DSpace 7) in 2026; the old nic.in bitstream
    # paths now return the web app's HTML. Files are addressed by bitstream UUID through
    # the REST API.
    # Consolidated BNS, "[As on the 6th October, 2025]", amendments included.
    Source(
        key="bns_current",
        url=f"{INDIACODE_CONTENT}/8007a80e-259b-429d-9ca4-1a2f474b5000/content",
        filename="bns_current.pdf",
    ),
    # The IPC as it stood when repealed: includes the 2013 and 2018 amendments (354A-D,
    # 376DB, 166A). IndiaCode's older handle 4219 is a pre-2013 consolidation and must
    # not be used — it would answer pre-July-2024 questions with superseded law.
    Source(
        key="ipc",
        url=f"{INDIACODE_CONTENT}/337c7a03-60c6-4953-8dd6-90e65c343629/content",
        filename="ipc.pdf",
    ),
    # BNS-to-IPC correspondence table, CAPT Bhopal (a BPR&D police training academy).
    Source(
        key="capt_correspondence",
        url="https://www.keralaprisons.gov.in/userfiles/act-and-rules/"
        "comparison_summary_BNS_to_IPC.pdf",
        filename="capt_correspondence.pdf",
    ),
)

Opener = Callable[[str, float], bytes]


def _urlopen(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        # 4xx means the URL is wrong or gone; asking again will not change the answer.
        return error.code >= 500 or error.code == 429
    return isinstance(error, OSError | NotAPdfError)


def download(
    source: Source,
    dest_dir: Path,
    *,
    opener: Opener = _urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> FetchResult:
    """Fetch one source into dest_dir, rejecting anything that is not a PDF."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            body = opener(source.url, TIMEOUT_SECONDS)
            if not body.startswith(PDF_MAGIC):
                raise NotAPdfError(
                    f"{source.key}: expected a PDF from {source.url}, got {body[:40]!r}"
                )
        except Exception as error:
            if not _is_retryable(error):
                raise
            last_error = error
            if attempt < MAX_ATTEMPTS:
                sleep(BACKOFF_SECONDS * attempt)
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / source.filename).write_bytes(body)
        return FetchResult(
            key=source.key,
            url=source.url,
            filename=source.filename,
            sha256=hashlib.sha256(body).hexdigest(),
            size=len(body),
        )

    assert last_error is not None
    raise last_error


def _from_disk(source: Source, path: Path) -> FetchResult | None:
    if not path.is_file():
        return None
    body = path.read_bytes()
    if not body.startswith(PDF_MAGIC):
        return None
    return FetchResult(
        key=source.key,
        url=source.url,
        filename=source.filename,
        sha256=hashlib.sha256(body).hexdigest(),
        size=len(body),
    )


def fetch_all(
    sources: Iterable[Source],
    raw_dir: Path,
    *,
    opener: Opener = _urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[FetchResult], dict[str, Exception]]:
    """Fetch every source not already on disk; one dead host does not block the rest.

    Skipping valid files makes a rerun cheap after a partial failure, which matters here:
    IndiaCode can stay down for hours while PRS and the CAPT table are fine.
    """
    results: list[FetchResult] = []
    failures: dict[str, Exception] = {}
    for source in sources:
        cached = _from_disk(source, raw_dir / source.filename)
        if cached is not None:
            results.append(cached)
            continue
        try:
            results.append(download(source, raw_dir, opener=opener, sleep=sleep))
        except Exception as error:
            failures[source.key] = error
    return results, failures


def write_manifest(results: Iterable[FetchResult], path: Path) -> None:
    """Record what was read, so a later build can prove it read the same bytes."""
    entries = sorted((asdict(r) for r in results), key=lambda e: e["key"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def main(data_dir: Path = Path("data")) -> None:  # pragma: no cover - network entry point
    results, failures = fetch_all(SOURCES, data_dir / "raw")
    write_manifest(results, data_dir / "sources.json")
    for r in results:
        print(f"{r.key:22} {r.size:>10,} bytes  {r.sha256[:12]}")
    for key, error in failures.items():
        print(f"{key:22} FAILED: {error}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
