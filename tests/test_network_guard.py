from __future__ import annotations

import socket

import pytest

import lexbridge


def test_package_exposes_a_version() -> None:
    assert lexbridge.__version__


def test_guard_blocks_a_connection_to_a_public_address() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(AssertionError, match="network connection"):
            sock.connect(("93.184.216.34", 443))
    finally:
        sock.close()


def test_guard_lets_loopback_through() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(server.getsockname())
    finally:
        client.close()
        server.close()
