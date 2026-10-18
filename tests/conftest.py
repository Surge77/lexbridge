"""Shared fixtures.

Unit tests never reach the network. The guard sits at the socket layer rather than on
one HTTP library, because this project will talk to government sites, an embedding hub
and two LLM providers through different clients — a guard on urllib alone would let the
others through.
"""

from __future__ import annotations

import ipaddress
import socket

import pytest


def _is_loopback(address: object) -> bool:
    host = address[0] if isinstance(address, tuple) else address
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(str(host)).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def no_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any unmarked test that opens a non-loopback connection.

    Loopback stays open so FastAPI's TestClient and local servers keep working.
    """
    if request.node.get_closest_marker("integration"):
        return

    real_connect = socket.socket.connect

    def guard(self: socket.socket, address: object) -> None:
        if not _is_loopback(address):
            raise AssertionError(
                f"unit test attempted a network connection to {address}. Stub the "
                "boundary, or mark the test @pytest.mark.integration."
            )
        real_connect(self, address)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", guard)
