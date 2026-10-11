"""Tests for transport/client contracts and bounded delivery behavior.

The transport contract is asynchronous since `python-broadlink` 1.0, so these
drive it with `asyncio.run`. They deliberately do NOT use `pytest-asyncio`:
`requirements-test-offline.txt` installs only `pytest` and the library, and
this module runs in that lightweight job as well as the Home Assistant ones.

Device doubles keep `devtype` / `is_locked` as plain attributes and make only
the awaited calls `AsyncMock`. `decrypt` stays a synchronous `Mock`, matching
the one library method that did not become a coroutine.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, Mock

import broadlink.exceptions
import pytest

from .helpers import load, run

client_mod = load("runxin.client")
framing = load("runxin.framing")
transport_mod = load("transport.broadlink_bl3372")


def _device(**attrs) -> Mock:
    """Mock BroadLink device with coroutines where 1.0 has coroutines."""
    device = Mock(**attrs)
    device.auth = AsyncMock(return_value=True)
    device.send_packet = AsyncMock()
    device.get_fwversion = AsyncMock(return_value=0)
    device.aclose = AsyncMock()
    return device


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
    run(client.write_fields({43: 50}))
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
    monkeypatch.setattr(transport, "_drop_session", AsyncMock())
    with pytest.raises(transport_mod.BroadlinkOuterError):
        run(transport.transact_write(b"frame"))
    assert calls == 1


# No asyncio.sleep patch: transient_delays=(0.0, 0.0) with random.uniform
# pinned to 0.0 makes the backoff asyncio.sleep(0.0), which returns at once.
# Patching asyncio.sleep globally would also reach asyncio.run internals.
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
    assert run(transport.transact(b"frame")) == b"ok"
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
    monkeypatch.setattr(transport, "_drop_session", AsyncMock())
    monkeypatch.setattr(transport_mod.random, "uniform", lambda _a, _b: 0.0)
    assert run(transport.transact(b"frame")) == b"ok"
    assert transport.reauth_count == 1
    assert transport.transient_retries == 2


def test_read_retries_once_after_endpoint_closed(monkeypatch) -> None:
    """A closed endpoint is recoverable on a read, from the session budget.

    1.0 keeps one persistent UDP endpoint per device and raises
    EndpointClosedError (new in 1.0.2) when it closes mid-request. Without
    this the first occurrence would surface as a hard transport error.
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
    monkeypatch.setattr(transport, "_drop_session", AsyncMock())
    assert run(transport.transact(b"frame")) == b"ok"
    assert calls == 2
    assert transport.reauth_count == 1
    # A session refresh must not spend the transient budget.
    assert transport.transient_retries == 0


def test_write_path_does_not_retry_endpoint_closed(monkeypatch) -> None:
    """The read-path recovery must not leak into writes.

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
    monkeypatch.setattr(transport, "_drop_session", AsyncMock())
    with pytest.raises(transport_mod.RunxinTransportError):
        run(transport.transact_write(b"frame"))
    assert calls == 1


@pytest.mark.parametrize("locked", [True, False, None])
@pytest.mark.parametrize("method", ["transact", "transact_write"])
def test_rejected_handshake_retains_evidence_without_sending_runxin(
    monkeypatch, caplog, locked, method
) -> None:
    secret = "192.0.2.17 02:00:00:00:00:17 private-session-key"
    device = _device(devtype=0x520F, is_locked=locked)
    device.auth.side_effect = broadlink.exceptions.AuthenticationError(-1, secret)
    hello = AsyncMock(return_value=device)
    monkeypatch.setattr(transport_mod.broadlink, "hello", hello)
    transport = transport_mod.BroadlinkBL3372Transport("192.0.2.17")
    with caplog.at_level(logging.DEBUG, logger=transport_mod.__name__):
        with pytest.raises(transport_mod.BroadlinkAuthenticationError) as caught:
            run(getattr(transport, method)(b"private-frame"))
    assert caught.value.code == -1
    assert caught.value.is_locked is locked
    assert isinstance(caught.value.__cause__, broadlink.exceptions.AuthenticationError)
    hello.assert_awaited_once_with("192.0.2.17", timeout=5)
    device.auth.assert_awaited_once_with()
    device.send_packet.assert_not_awaited()
    device.set_lock.assert_not_called()
    device.get_fwversion.assert_not_awaited()
    assert transport._device is None
    assert transport.reauth_count == 0
    details = transport.diagnostics
    assert details["stage"] == "authentication"
    assert details["devtype"] == 0x520F
    assert details["advertised_lock"] is locked
    assert details["last_error"] == {
        "stage": "authentication", "error_type": "AuthenticationError", "error_code": -1,
    }
    safe_output = json.dumps(details) + caplog.text + str(caught.value)
    for value in secret.split() + ["private-frame"]:
        assert value not in safe_output
    details["last_error"]["error_code"] = 123
    assert transport.diagnostics["last_error"]["error_code"] == -1


def test_false_auth_result_is_rejected_without_runxin(monkeypatch) -> None:
    device = _device(devtype=0x520F, is_locked=False)
    device.auth.return_value = False
    monkeypatch.setattr(transport_mod.broadlink, "hello", AsyncMock(return_value=device))
    transport = transport_mod.BroadlinkBL3372Transport("192.0.2.17")
    with pytest.raises(transport_mod.BroadlinkAuthenticationError):
        run(transport.transact(b"frame"))
    device.send_packet.assert_not_awaited()
    assert transport.diagnostics["last_error"]["error_code"] is None


def test_advertised_lock_does_not_prevent_successful_auth_or_change_packet(monkeypatch) -> None:
    device = _device(devtype=0x520F, is_locked=True)
    device.auth.return_value = True
    device.get_fwversion.return_value = 62016
    device.send_packet.return_value = bytes(0x38) + bytes(16)
    device.decrypt = Mock(return_value=transport_mod.pack_tfb(b"reply") + bytes(9))
    monkeypatch.setattr(transport_mod.broadlink, "hello", AsyncMock(return_value=device))
    transport = transport_mod.BroadlinkBL3372Transport("192.0.2.17")
    assert run(transport.transact(b"frame")) == b"reply"
    assert transport.identifier is not None
    device.send_packet.assert_awaited_once_with(0x6A, transport_mod.pack_tfb(b"frame"))
    device.set_lock.assert_not_called()
    assert transport.firmware == 62016
    assert transport.diagnostics["stage"] == "ready"
    assert transport.diagnostics["advertised_lock"] is True
    assert transport.diagnostics["last_error"] is None


@pytest.mark.parametrize("stage", ["discovery", "authentication"])
def test_timeout_is_not_classified_as_authentication_rejection(monkeypatch, stage) -> None:
    error = broadlink.exceptions.NetworkTimeoutError(-4000, "private-host")
    device = _device(devtype=0x520F, is_locked=True)
    if stage == "discovery":
        hello = AsyncMock(side_effect=error)
    else:
        hello = AsyncMock(return_value=device)
        device.auth.side_effect = error
    monkeypatch.setattr(transport_mod.broadlink, "hello", hello)
    transport = transport_mod.BroadlinkBL3372Transport("192.0.2.17")
    with pytest.raises(transport_mod.RunxinTransportError) as caught:
        run(transport.transact(b"frame"))
    assert not isinstance(caught.value, transport_mod.BroadlinkAuthenticationError)
    assert transport.diagnostics["last_error"] == {
        "stage": stage, "error_type": "NetworkTimeoutError", "error_code": -4000,
    }
    assert "private-host" not in json.dumps(transport.diagnostics)
    device.send_packet.assert_not_awaited()


def test_later_success_preserves_historical_error_but_reports_ready_stage(monkeypatch) -> None:
    device = _device(devtype=0x520F, is_locked=False)
    device.auth.side_effect = [broadlink.exceptions.AuthenticationError(-1, "rejected"), True]
    device.get_fwversion.return_value = 62016
    device.send_packet.return_value = bytes(0x38) + bytes(16)
    device.decrypt = Mock(return_value=transport_mod.pack_tfb(b"reply") + bytes(9))
    monkeypatch.setattr(transport_mod.broadlink, "hello", AsyncMock(return_value=device))
    transport = transport_mod.BroadlinkBL3372Transport("192.0.2.17")
    with pytest.raises(transport_mod.BroadlinkAuthenticationError):
        run(transport.transact(b"frame"))
    assert run(transport.transact(b"frame")) == b"reply"
    assert transport.diagnostics["stage"] == "ready"
    assert transport.diagnostics["last_error"]["stage"] == "authentication"
    assert transport.diagnostics["last_error"]["error_code"] == -1
    assert device.auth.await_count == 2
    device.send_packet.assert_awaited_once_with(0x6A, transport_mod.pack_tfb(b"frame"))


def test_short_real_auth_response_is_transport_failure_not_rejection(monkeypatch) -> None:
    """A malformed auth reply must not be classified as a rejection.

    Written for a 0.19.0 defect: its auth implementation passed a 12-byte
    session key to AES when given only 16 decrypted bytes, and
    `cryptography` raised ValueError. Ported against the real 1.0.x Device
    to check whether that path still exists. If 1.0 validates the payload
    first and raises a BroadlinkException instead, the assertion below on
    `__cause__` is what will tell us - and the ValueError guard in the
    transport becomes belt-and-braces rather than load-bearing.
    """
    device = transport_mod.broadlink.Device(("192.0.2.17", 80), bytes(6), 0x520F)
    device._exchange = AsyncMock(return_value=bytes(0x38) + bytes(16))
    device.decrypt = Mock(return_value=bytes(16))
    device.aclose = AsyncMock()
    monkeypatch.setattr(transport_mod.broadlink, "hello", AsyncMock(return_value=device))
    transport = transport_mod.BroadlinkBL3372Transport("192.0.2.17")
    with pytest.raises(transport_mod.RunxinTransportError) as caught:
        run(transport.transact(b"frame"))
    assert not isinstance(caught.value, transport_mod.BroadlinkAuthenticationError)
    assert transport._device is None
    # The command byte of each framed request: authentication only,
    # so no Runxin frame reached the wire.
    assert [call.args[0][0x26] for call in device._exchange.await_args_list] == [0x65]
    assert transport.reauth_count == 0


def test_rejected_authentication_releases_discovered_endpoint(monkeypatch):
    """Renamed from ...releases_discovered_socket.

    1.0 owns the UDP endpoint and exposes no `sock`, so the release is now
    observed through aclose() rather than sock.close().
    """
    device = _device(devtype=0x520F, is_locked=True)
    device.auth.side_effect = broadlink.exceptions.AuthenticationError(-1)
    monkeypatch.setattr(transport_mod.broadlink, "hello", AsyncMock(return_value=device))
    transport = transport_mod.BroadlinkBL3372Transport("192.0.2.1")
    with pytest.raises(transport_mod.BroadlinkAuthenticationError):
        run(transport._connect())
    device.aclose.assert_awaited_once()
    assert transport._device is None
