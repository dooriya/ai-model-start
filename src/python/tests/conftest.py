from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

PYTHON_EXAMPLE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_EXAMPLE_ROOT))


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access is blocked in offline tests.")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket, "getaddrinfo", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)
    monkeypatch.setattr(socket.socket, "connect_ex", fail_network)
