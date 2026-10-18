"""Download the statute PDFs and pin each one by SHA-256.

Government hosts are the only sources: the bot quotes this text as law, so a commercial
bare-act PDF is not acceptable even when it is easier to reach.

Usage:
    python -m lexbridge.ingest.fetch            # fetch, verifying against data/sources.json
    python -m lexbridge.ingest.fetch --repin    # re-download everything and rewrite the pins
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
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


class PinMismatchError(ValueError):
    """The bytes differ from the SHA-256 committed in data/sources.json.

    Never retried and never written: a changed statute file must be re-pinned on
    purpose (--repin), not absorbed silently by the next build.
    """


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
    # HTTPException covers IncompleteRead: Akamai sometimes drops the body mid-transfer.
    return isinstance(error, OSError | NotAPdfError | http.client.HTTPException)


def _result(source: Source, body: bytes) -> FetchResult:
    return FetchResult(
        key=source.key,
        url=source.url,
        filename=source.filename,
        sha256=hashlib.sha256(body).hexdigest(),
        size=len(body),
    )


def _write_atomically(path: Path, body: bytes) -> None:
    """A killed process must not leave a truncated file that still starts with %PDF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(body)
    os.replace(partial, path)


def download(
    source: Source,
    dest_dir: Path,
    *,
    expected_sha256: str | None = None,
    opener: Opener = _urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> FetchResult:
    """Fetch one source into dest_dir, rejecting anything that is not the pinned PDF."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            body = opener(source.url, TIMEOUT_SECONDS)
            if not body.startswith(PDF_MAGIC):
                raise NotAPdfError(
                    f"{source.key}: expected a PDF from {source.url}, got {body[:40]!r}"
                )
        except Exception as error:
            if not _is_retryable(error) or attempt == MAX_ATTEMPTS:
                raise
            sleep(BACKOFF_SECONDS * attempt)
            continue

        result = _result(source, body)
        if expected_sha256 is not None and result.sha256 != expected_sha256:
            raise PinMismatchError(
                f"{source.key}: got sha256 {result.sha256[:12]}, pinned {expected_sha256[:12]}"
            )
        _write_atomically(dest_dir / source.filename, body)
        return result
    raise AssertionError("unreachable: the last attempt either returns or raises")


def _from_disk(source: Source, path: Path) -> FetchResult | None:
    if not path.is_file():
        return None
    body = path.read_bytes()
    return _result(source, body) if body.startswith(PDF_MAGIC) else None


def fetch_all(
    sources: Iterable[Source],
    raw_dir: Path,
    *,
    pins: Mapping[str, str] | None = None,
    opener: Opener = _urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[FetchResult], dict[str, Exception]]:
    """Fetch every source not already on disk; one dead host does not block the rest.

    Skipping valid files makes a rerun cheap after a partial failure, which matters here:
    IndiaCode can stay down for hours while PRS and the CAPT table are fine. A file on
    disk is reused only if it matches its pin; anything fetched must match it too.
    """
    pins = pins or {}
    results: list[FetchResult] = []
    failures: dict[str, Exception] = {}
    for source in sources:
        pin = pins.get(source.key)
        cached = _from_disk(source, raw_dir / source.filename)
        if cached is not None and (pin is None or cached.sha256 == pin):
            results.append(cached)
            continue
        try:
            results.append(
                download(source, raw_dir, expected_sha256=pin, opener=opener, sleep=sleep)
            )
        except Exception as error:
            failures[source.key] = error
    return results, failures


def write_manifest(results: Iterable[FetchResult], path: Path) -> None:
    """Record what was read, so a later build can prove it read the same bytes."""
    entries = sorted((asdict(r) for r in results), key=lambda e: e["key"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def load_pins(path: Path) -> dict[str, str]:
    """Committed SHA-256 per source key; empty before the first fetch."""
    if not path.is_file():
        return {}
    return {e["key"]: e["sha256"] for e in json.loads(path.read_text(encoding="utf-8"))}


def merge_manifest(results: Iterable[FetchResult], path: Path) -> None:
    """Update the manifest with these results, keeping entries for sources not fetched.

    Rewriting it from this run alone would drop the pin of any source whose host was
    down, and the next run would then accept whatever that host served.
    """
    existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    merged = {e["key"]: FetchResult(**e) for e in existing} | {r.key: r for r in results}
    write_manifest(merged.values(), path)


def main(data_dir: Path = Path("data")) -> None:  # pragma: no cover - network entry point
    manifest = data_dir / "sources.json"
    repin = "--repin" in sys.argv
    raw = data_dir / "raw"
    if repin:
        # A repin is for when upstream changed, so cached files must not be reused.
        for source in SOURCES:
            (raw / source.filename).unlink(missing_ok=True)
    results, failures = fetch_all(SOURCES, raw, pins={} if repin else load_pins(manifest))
    merge_manifest(results, manifest)
    for r in results:
        print(f"{r.key:22} {r.size:>10,} bytes  {r.sha256[:12]}")
    for key, error in failures.items():
        print(f"{key:22} FAILED: {error}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
