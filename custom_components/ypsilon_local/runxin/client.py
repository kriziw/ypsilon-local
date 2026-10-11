"""Small transport-neutral client for a Runxin F79D controller.

Only an awaitable `transact(frame) -> frame` transport is required. The
transport may be BroadLink, serial, TCP, ESPHome-backed, or a test double.

The contract became asynchronous when `python-broadlink` 1.0 turned every
device-talking method into a coroutine. Nothing about the F79D codec itself
changed: this module still only moves bytes, and the `runxin` package still
imports neither `homeassistant` nor `broadlink`.

Transports may optionally provide `transact_write(frame) -> frame` when writes
need stricter delivery semantics than reads. This lets a stateful transport
avoid blindly retransmitting a command after an ambiguous timeout while keeping
the generic F79D codec transport-neutral.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from .errors import RunxinProtocolError
from .f79d import STATE_FIELDS, build_query, build_write_fields, decode_frame


class TransactionTransport(Protocol):
    """Minimal structural contract consumed by `F79DClient`."""

    async def transact(self, frame: bytes) -> bytes:
        """Send one raw Runxin request and return one raw Runxin response."""
        ...


class F79DClient:
    """Read/write F79D fields through an arbitrary transaction transport."""

    def __init__(self, transport: TransactionTransport) -> None:
        self.transport = transport
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        """Close the transport when it provides a close hook."""
        close = getattr(self.transport, "close", None)
        if callable(close):
            await close()

    async def _invalidate_transport(self) -> None:
        invalidate = getattr(self.transport, "invalidate", None)
        if callable(invalidate):
            await invalidate()

    async def _decode_response(self, response: bytes) -> dict[str, Any]:
        try:
            return decode_frame(response)
        except RunxinProtocolError:
            # A malformed product frame can mean stale framing/session state.
            # Stateful transports may reset themselves; stateless transports
            # simply inherit the no-op behavior.
            await self._invalidate_transport()
            raise

    async def _transaction(self, request: bytes) -> dict[str, Any]:
        return await self._decode_response(await self.transport.transact(request))

    async def _write_transaction(self, request: bytes) -> dict[str, Any]:
        write_transaction = getattr(self.transport, "transact_write", None)
        if callable(write_transaction):
            return await self._decode_response(await write_transaction(request))
        return await self._transaction(request)

    async def read_fields(self, fields: list[int]) -> dict[str, Any]:
        """Read an explicit set of F79D field ids."""
        async with self._lock:
            return await self._transaction(build_query(fields))

    async def read_identity(self) -> dict[str, Any]:
        """Read the small identity/status set used during discovery."""
        return await self.read_fields([1, 34])

    async def read_state(self) -> dict[str, Any]:
        """Read the normal 1..51 F79D state block."""
        return await self.read_fields(STATE_FIELDS)

    async def write_fields(self, values: dict[int, Any]) -> None:
        """Write one or more F79D fields in a single 0x19 transaction."""
        async with self._lock:
            await self._write_transaction(build_write_fields(values))
