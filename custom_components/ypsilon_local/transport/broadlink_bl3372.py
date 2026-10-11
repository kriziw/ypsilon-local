"""BroadLink BL3372 transport for raw Runxin transactions.

This module owns every BroadLink-specific concern: discovery/authentication,
0x6A packet transport, encryption, the two-byte TFB length envelope, outer
response errors, session refresh and the observed transient -5 retry policy.
The Runxin codec never imports this module or the `broadlink` package.

Read transactions may be retried within bounded budgets. Write transactions are
sent at most once: after a timeout/outer error the command may already have been
accepted by the physical controller, so retrying blindly could duplicate a
mechanical action. The Home Assistant layer reconciles ambiguous writes through
an independent read-back instead.

This module is asynchronous because `python-broadlink` 1.0 is: `hello`,
`auth`, `get_fwversion` and `send_packet` are all coroutines, while `decrypt`
stayed synchronous. The public method names are unchanged from the threaded
version - `transact`, `transact_write`, `invalidate`, `close` - they are simply
coroutines now, matching `RunxinTransport`.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import broadlink
import broadlink.exceptions

from ..runxin.errors import RunxinTransportError
from .base import RunxinTransport

DEFAULT_DEVTYPE = 0x520F
DEFAULT_SOCKET_TIMEOUT = 5
DEFAULT_TRANSIENT_ERROR_CODE = -5
DEFAULT_AUTH_ERROR_CODES = frozenset({-1, -7})
DEFAULT_TRANSIENT_DELAYS = (0.4, 0.8)

BROADLINK_EXCEPTIONS = (
    broadlink.exceptions.BroadlinkException,
    OSError,
    TimeoutError,
)


class BroadlinkOuterError(RunxinTransportError):
    """BroadLink outer response error read from packet offset 0x22."""

    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(f"BroadLink outer error {code}")


def pack_tfb(frame: bytes) -> bytes:
    """Wrap a raw Runxin frame in the BL3372 two-byte little-endian length."""
    return len(frame).to_bytes(2, "little") + frame


def unpack_tfb(plaintext: bytes) -> bytes:
    """Remove the BL3372 length prefix and ignore decrypted block padding."""
    if len(plaintext) < 2:
        raise RunxinTransportError("missing BL3372 TFB length prefix")
    declared = int.from_bytes(plaintext[:2], "little")
    if declared > len(plaintext) - 2:
        raise RunxinTransportError("BL3372 declared length exceeds plaintext")
    return plaintext[2:2 + declared]


class BroadlinkBL3372Transport(RunxinTransport):
    """Authenticated BroadLink transport carrying Runxin frames over 0x6A."""

    def __init__(
        self,
        host: str,
        *,
        expected_devtype: int | None = DEFAULT_DEVTYPE,
        timeout: float = DEFAULT_SOCKET_TIMEOUT,
        transient_error_code: int = DEFAULT_TRANSIENT_ERROR_CODE,
        auth_error_codes: frozenset[int] = DEFAULT_AUTH_ERROR_CODES,
        transient_delays: tuple[float, ...] = DEFAULT_TRANSIENT_DELAYS,
    ) -> None:
        self.host = host
        self.expected_devtype = expected_devtype
        self.timeout = timeout
        self.transient_error_code = transient_error_code
        self.auth_error_codes = auth_error_codes
        self.transient_delays = transient_delays

        self._device: Any = None
        self._firmware: int | None = None
        self._lock = asyncio.Lock()
        self.transient_retries = 0
        self.reauth_count = 0

    @property
    def identifier(self) -> str | None:
        """Return the BroadLink MAC as a plain 12-character hex string."""
        raw = getattr(self._device, "mac", None) if self._device else None
        if raw is None:
            return None
        if isinstance(raw, (bytes, bytearray)):
            return raw.hex()
        return str(raw).replace(":", "").replace("-", "").lower()

    @property
    def mac(self) -> str | None:
        """Compatibility alias for `identifier`."""
        return self.identifier

    @property
    def firmware(self) -> int | None:
        return self._firmware

    @property
    def diagnostics(self) -> dict[str, int]:
        return {
            "transient_retries": self.transient_retries,
            "reauth_count": self.reauth_count,
        }

    async def _drop_session(self) -> None:
        # 1.0 owns the UDP endpoint itself and exposes no `sock`; aclose() is
        # the documented teardown. It is best-effort: a session being dropped
        # because it already failed must not raise again here.
        device = self._device
        self._device = None
        if device is None:
            return
        try:
            await device.aclose()
        except BROADLINK_EXCEPTIONS:
            pass

    async def invalidate(self) -> None:
        """Drop the current authenticated BroadLink session."""
        await self._drop_session()

    async def close(self) -> None:
        """Close the BroadLink endpoint and discard the session."""
        async with self._lock:
            await self._drop_session()

    async def _connect(self) -> Any:
        # 1.0 raises NetworkTimeoutError instead of returning None, so the old
        # `if device is None` guard could never fire again.
        try:
            device = await broadlink.hello(self.host, timeout=self.timeout)
        except broadlink.exceptions.NetworkTimeoutError as err:
            raise RunxinTransportError("No BroadLink device found") from err
        if (
            self.expected_devtype is not None
            and int(device.devtype) != self.expected_devtype
        ):
            raise RunxinTransportError(
                f"Unexpected devtype 0x{int(device.devtype):04x}"
            )
        device.timeout = self.timeout
        if await device.auth() is False:
            raise RunxinTransportError("BroadLink auth failed")
        self._device = device

        if self._firmware is None:
            try:
                self._firmware = int(await device.get_fwversion())
            except Exception:  # noqa: BLE001 - cosmetic metadata only
                self._firmware = None
        return device

    async def _transact_once(self, frame: bytes) -> bytes:
        device = self._device or await self._connect()
        response = bytes(await device.send_packet(0x6A, pack_tfb(frame)))
        if len(response) < 0x38:
            raise RunxinTransportError("Short BroadLink response")

        error = int.from_bytes(response[0x22:0x24], "little", signed=True)
        if error:
            raise BroadlinkOuterError(error)

        encrypted = response[0x38:]
        if not encrypted or len(encrypted) % 16:
            raise RunxinTransportError("Invalid BroadLink encrypted length")
        try:
            # decrypt() is the one call that stayed synchronous in 1.0.
            plaintext = device.decrypt(encrypted)
        except BROADLINK_EXCEPTIONS as err:
            raise RunxinTransportError(f"BroadLink decrypt failed: {err}") from err
        return unpack_tfb(plaintext)

    async def _transact_read_resilient(self, frame: bytes) -> bytes:
        """Retry bounded, idempotent read transactions.

        Outer -5 is empirically transient on the tested BL3372/F79D. The exact
        internal cause is not known. Authentication-like outer errors get one
        fresh session. These budgets are independent so an auth refresh cannot
        accidentally consume the last transient retry slot.

        ConnectionClosedError shares the session budget. 1.0 keeps one
        persistent UDP endpoint per device and raises EndpointClosedError (a
        ConnectionClosedError subclass, new in 1.0.2) when that endpoint is
        closed mid-request. On a read that is recoverable with a fresh
        session; without this it would surface as a hard transport error.
        """
        transient_attempt = 0
        reauth_remaining = 1
        while True:
            try:
                return await self._transact_once(frame)
            except broadlink.exceptions.ConnectionClosedError:
                if not reauth_remaining:
                    raise
                reauth_remaining -= 1
                self.reauth_count += 1
                await self._drop_session()
                continue
            except BroadlinkOuterError as err:
                if err.code in self.auth_error_codes and reauth_remaining:
                    reauth_remaining -= 1
                    self.reauth_count += 1
                    await self._drop_session()
                    continue
                if (
                    err.code == self.transient_error_code
                    and transient_attempt < len(self.transient_delays)
                ):
                    base = self.transient_delays[transient_attempt]
                    transient_attempt += 1
                    self.transient_retries += 1
                    await asyncio.sleep(base + random.uniform(0, base / 2))
                    continue
                raise

    async def transact(self, frame: bytes) -> bytes:
        """Carry one read/idempotent raw Runxin request through BroadLink."""
        async with self._lock:
            try:
                return await self._transact_read_resilient(frame)
            except RunxinTransportError:
                await self._drop_session()
                raise
            except BROADLINK_EXCEPTIONS as err:
                await self._drop_session()
                raise RunxinTransportError(str(err)) from err

    async def transact_write(self, frame: bytes) -> bytes:
        """Send one Runxin write exactly once and never retry it blindly.

        Any transport failure after packet submission is ambiguous: the F79D
        may have executed the command even if the acknowledgement was lost.
        Callers must reconcile by reading physical state before deciding whether
        a retry is safe. Note the deliberate asymmetry with reads: the
        ConnectionClosedError retry above is NOT repeated here, because a
        closed endpoint after submission is exactly the ambiguous case.
        """
        async with self._lock:
            try:
                return await self._transact_once(frame)
            except RunxinTransportError:
                await self._drop_session()
                raise
            except BROADLINK_EXCEPTIONS as err:
                await self._drop_session()
                raise RunxinTransportError(str(err)) from err
