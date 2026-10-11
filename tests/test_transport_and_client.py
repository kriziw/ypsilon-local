"""Tests for transport/client contracts and bounded delivery behavior.

The transport contract is asynchronous since `python-broadlink` 1.0, so these
drive it with `asyncio.run` rather than taking a `pytest-asyncio` dependency -
CI installs only `pytest` and the library itself.

Note there is no `asyncio.sleep` monkeypatch. `transient_delays=(0.0, 0.0)`
plus the `random.uniform` patch already makes the backoff `asyncio.sleep(0.0)`,
which returns immediately. Patching `asyncio.sleep` globally for the duration
of a test would also reach whatever `asyncio.run` uses internally.
"""

from __future__ import annotations

import asyncio

import broadlink.exceptions
import pytest

from .helpers import load

client_mod = load("runxin.client")
framing = load("runxin.framing")
transport_mod = load("transport.broadlink_bl3372")


async def _noop_session() -> None:
    """Async stand-in for `_drop_session`, which now awaits `aclose()`."""
    return None


def _empty_write_response() -> bytes:
    header = [0x5A, 0x5C, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0x12, 0, 0]
    inner = [0xDF, 0xFD, 0, framing.WRITE_RESPONSE_CODE, 0, 0xDE]
    header[15] = len(inner)
    inner[2] = len(inner)
    inner[-2] = sum(inner[:-2]) & 0xFF
    frame = header + inner + [0, 0xA5]
    frame[2] = len(frame)
    frame[-2] = sum(frame[:-2]) & 0xFF
    return bytes(frame)


def test_client_prefers_write_specific_hook() -> None:
    class Fake:
        def __init__(self) -> None:
            self.reads = 0
            self.writes = 0

        async def transact(self, frame: bytes) -> bytes:
            self.reads += 1
            return _empty_write_response()

        async def transact_write(self, frame: bytes) -> bytes:
            self.writes += 1
            return _empty_write_response()

    fake = Fake()
    client = client_mod.F79DClient(fake)
    asyncio.run(client.write_fields({43: 50}))
    assert fake.writes == 1
    assert fake.reads == 0


def test_write_path_never_retries_ambiguous_error(monkeypatch) -> None:
    transport = transport_mod.BroadlinkBL3372Transport("192.0.2.1")
    calls = 0

    async def fail_once(frame: bytes) -> bytes:
        nonlocal calls
        calls += 1
        raise transport_mod.BroadlinkOuterError(-5)

    monkeypatch.setattr(transport, "_transact_once", fail_once)
    monkeypatch.setattr(transport, "_drop_session", _noop_session)
    with pytest.raises(transport_mod.BroadlinkOuterError):
        asyncio.run(transport.transact_write(b"frame"))
    assert calls == 1


def test_read_transient_retries_are_bounded(monkeypatch) -> None:
    transport = transport_mod.BroadlinkBL3372Transport(
        "192.0.2.1", transient_delays=(0.0, 0.0)
    )
    calls = 0

    async def eventually_ok(frame: bytes) -> bytes:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise transport_mod.BroadlinkOuterError(-5)
        return b"ok"

    monkeypatch.setattr(transport, "_transact_once", eventually_ok)
    monkeypatch.setattr(transport_mod.random, "uniform", lambda _a, _b: 0.0)
    assert asyncio.run(transport.transact(b"frame")) == b"ok"
    assert calls == 3
    assert transport.transient_retries == 2


def test_reauth_budget_does_not_consume_transient_budget(monkeypatch) -> None:
    transport = transport_mod.BroadlinkBL3372Transport(
        "192.0.2.1", transient_delays=(0.0, 0.0)
    )
    sequence = [-1, -5, -5, 0]

    async def sequence_reply(frame: bytes) -> bytes:
        code = sequence.pop(0)
        if code:
            raise transport_mod.BroadlinkOuterError(code)
        return b"ok"

    monkeypatch.setattr(transport, "_transact_once", sequence_reply)
    monkeypatch.setattr(transport, "_drop_session", _noop_session)
    monkeypatch.setattr(transport_mod.random, "uniform", lambda _a, _b: 0.0)
    assert asyncio.run(transport.transact(b"frame")) == b"ok"
    assert transport.reauth_count == 1
    assert transport.transient_retries == 2


def test_read_retries_once_after_endpoint_closed(monkeypatch) -> None:
    """A closed endpoint is recoverable on a read, from the session budget.

    `python-broadlink` 1.0 keeps one persistent UDP endpoint per device and
    raises EndpointClosedError (new in 1.0.2) when it is closed mid-request.
    Without this the first occurrence would surface as a hard transport error.
    """
    transport = transport_mod.BroadlinkBL3372Transport(
        "192.0.2.1", transient_delays=(0.0, 0.0)
    )
    calls = 0

    async def closed_once(frame: bytes) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise broadlink.exceptions.EndpointClosedError
        return b"ok"

    monkeypatch.setattr(transport, "_transact_once", closed_once)
    monkeypatch.setattr(transport, "_drop_session", _noop_session)
    assert asyncio.run(transport.transact(b"frame")) == b"ok"
    assert calls == 2
    assert transport.reauth_count == 1
    # The transient budget must be untouched by a session refresh.
    assert transport.transient_retries == 0


def test_write_path_does_not_retry_endpoint_closed(monkeypatch) -> None:
    """The read-path recovery must NOT leak into writes.

    A closed endpoint after submission is precisely the ambiguous case: the
    controller may already have acted on the frame.
    """
    transport = transport_mod.BroadlinkBL3372Transport("192.0.2.1")
    calls = 0

    async def always_closed(frame: bytes) -> bytes:
        nonlocal calls
        calls += 1
        raise broadlink.exceptions.EndpointClosedError

    monkeypatch.setattr(transport, "_transact_once", always_closed)
    monkeypatch.setattr(transport, "_drop_session", _noop_session)
    with pytest.raises(transport_mod.RunxinTransportError):
        asyncio.run(transport.transact_write(b"frame"))
    assert calls == 1

