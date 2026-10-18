from __future__ import annotations

import hashlib
import http.client
import json
import urllib.error
from pathlib import Path

import pytest

from lexbridge.ingest import fetch
from lexbridge.ingest.fetch import NotAPdfError, Source

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
# What IndiaCode's CDN actually returned on 2026-10-18: status 200, an HTML error page.
AKAMAI_ERROR = b"<HTML><HEAD><TITLE>Error</TITLE></HEAD><BODY>An error occurred</BODY></HTML>"

SOURCE = Source(key="bns_original", url="https://example.test/bns.pdf", filename="bns.pdf")


def serving(*responses: bytes | Exception):
    """An opener that returns (or raises) each response in turn and records calls."""
    queue = list(responses)
    calls: list[str] = []

    def opener(url: str, timeout: float) -> bytes:
        calls.append(url)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return opener, calls


def test_download_writes_the_pdf_and_reports_its_sha256(tmp_path: Path) -> None:
    opener, _ = serving(PDF_BYTES)

    result = fetch.download(SOURCE, tmp_path, opener=opener, sleep=lambda _: None)

    assert (tmp_path / "bns.pdf").read_bytes() == PDF_BYTES
    assert result.sha256 == hashlib.sha256(PDF_BYTES).hexdigest()
    assert result.size == len(PDF_BYTES)


def test_an_html_error_page_served_as_pdf_is_rejected_not_saved(tmp_path: Path) -> None:
    opener, _ = serving(AKAMAI_ERROR, AKAMAI_ERROR, AKAMAI_ERROR)

    with pytest.raises(NotAPdfError, match="bns_original"):
        fetch.download(SOURCE, tmp_path, opener=opener, sleep=lambda _: None)

    assert not (tmp_path / "bns.pdf").exists()


def test_a_transient_failure_is_retried_until_the_pdf_arrives(tmp_path: Path) -> None:
    opener, calls = serving(TimeoutError("read timed out"), AKAMAI_ERROR, PDF_BYTES)

    result = fetch.download(SOURCE, tmp_path, opener=opener, sleep=lambda _: None)

    assert len(calls) == 3
    assert result.size == len(PDF_BYTES)


def test_a_404_is_not_retried(tmp_path: Path) -> None:
    gone = urllib.error.HTTPError(SOURCE.url, 404, "Not Found", None, None)  # type: ignore[arg-type]
    opener, calls = serving(gone, PDF_BYTES)

    with pytest.raises(urllib.error.HTTPError):
        fetch.download(SOURCE, tmp_path, opener=opener, sleep=lambda _: None)

    assert len(calls) == 1


def test_manifest_records_every_source_sorted_by_key(tmp_path: Path) -> None:
    results = [
        fetch.FetchResult(key="ipc", url="u2", filename="ipc.pdf", sha256="b" * 64, size=2),
        fetch.FetchResult(key="bns_original", url="u1", filename="b.pdf", sha256="a" * 64, size=1),
    ]
    path = tmp_path / "sources.json"

    fetch.write_manifest(results, path)

    entries = json.loads(path.read_text(encoding="utf-8"))
    assert [e["key"] for e in entries] == ["bns_original", "ipc"]
    assert entries[0]["sha256"] == "a" * 64


def test_every_registered_source_has_a_unique_key_and_filename() -> None:
    keys = [s.key for s in fetch.SOURCES]
    names = [s.filename for s in fetch.SOURCES]
    assert len(set(keys)) == len(keys)
    assert len(set(names)) == len(names)
    assert all(s.url.startswith("https://") for s in fetch.SOURCES)


def test_fetch_all_skips_a_valid_file_already_on_disk(tmp_path: Path) -> None:
    (tmp_path / SOURCE.filename).write_bytes(PDF_BYTES)
    opener, calls = serving()

    results, failures = fetch.fetch_all([SOURCE], tmp_path, opener=opener, sleep=lambda _: None)

    assert calls == []
    assert failures == {}
    assert results[0].sha256 == hashlib.sha256(PDF_BYTES).hexdigest()


def test_fetch_all_refetches_a_file_on_disk_that_is_not_a_pdf(tmp_path: Path) -> None:
    (tmp_path / SOURCE.filename).write_bytes(AKAMAI_ERROR)
    opener, calls = serving(PDF_BYTES)

    results, _ = fetch.fetch_all([SOURCE], tmp_path, opener=opener, sleep=lambda _: None)

    assert len(calls) == 1
    assert results[0].size == len(PDF_BYTES)


def test_one_dead_host_does_not_stop_the_other_sources(tmp_path: Path) -> None:
    dead = Source(key="dead", url="https://down.test/x.pdf", filename="x.pdf")
    down = urllib.error.HTTPError(dead.url, 504, "Gateway Time-out", None, None)  # type: ignore[arg-type]
    opener, _ = serving(down, down, down, PDF_BYTES)

    results, failures = fetch.fetch_all(
        [dead, SOURCE], tmp_path, opener=opener, sleep=lambda _: None
    )

    assert [r.key for r in results] == ["bns_original"]
    assert set(failures) == {"dead"}


PINNED = hashlib.sha256(PDF_BYTES).hexdigest()
OTHER_PDF = b"%PDF-1.7\nsomething else entirely\n%%EOF\n"


def test_a_download_that_does_not_match_its_pin_is_rejected_and_not_saved(tmp_path: Path) -> None:
    opener, _ = serving(OTHER_PDF)

    results, failures = fetch.fetch_all(
        [SOURCE], tmp_path, pins={SOURCE.key: PINNED}, opener=opener, sleep=lambda _: None
    )

    assert results == []
    assert isinstance(failures[SOURCE.key], fetch.PinMismatchError)
    assert not (tmp_path / SOURCE.filename).exists()


def test_a_cached_file_that_drifted_from_its_pin_is_fetched_again(tmp_path: Path) -> None:
    (tmp_path / SOURCE.filename).write_bytes(OTHER_PDF)
    opener, calls = serving(PDF_BYTES)

    results, failures = fetch.fetch_all(
        [SOURCE], tmp_path, pins={SOURCE.key: PINNED}, opener=opener, sleep=lambda _: None
    )

    assert len(calls) == 1
    assert failures == {}
    assert results[0].sha256 == PINNED
    assert (tmp_path / SOURCE.filename).read_bytes() == PDF_BYTES


def test_a_truncated_read_is_retried(tmp_path: Path) -> None:
    opener, calls = serving(http.client.IncompleteRead(b"%PDF-1.7 partial"), PDF_BYTES)

    fetch.download(SOURCE, tmp_path, opener=opener, sleep=lambda _: None)

    assert len(calls) == 2


def test_no_partial_file_is_left_behind_after_a_download(tmp_path: Path) -> None:
    opener, _ = serving(PDF_BYTES)

    fetch.download(SOURCE, tmp_path, opener=opener, sleep=lambda _: None)

    assert sorted(p.name for p in tmp_path.iterdir()) == [SOURCE.filename]


def test_merging_the_manifest_keeps_the_pin_of_a_source_that_failed(tmp_path: Path) -> None:
    path = tmp_path / "sources.json"
    old = fetch.FetchResult(key="ipc", url="u", filename="ipc.pdf", sha256="a" * 64, size=1)
    fetch.write_manifest([old], path)
    new = fetch.FetchResult(key="bns_original", url="u", filename="b.pdf", sha256="b" * 64, size=2)

    fetch.merge_manifest([new], path)

    assert fetch.load_pins(path) == {"bns_original": "b" * 64, "ipc": "a" * 64}


def test_pins_are_empty_when_there_is_no_manifest_yet(tmp_path: Path) -> None:
    assert fetch.load_pins(tmp_path / "missing.json") == {}
