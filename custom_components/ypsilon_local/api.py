"""Ypsilon-specific composition of the F79D client and BroadLink transport.

Compatibility note: Home Assistant code continues importing the same
`YpsilonLocalClient` and exception names as before v2.4.0. Protocol and
transport implementation details now live in independent subpackages.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from .const import FIELD52_FAIL_BACKOFF, FIELD52_REFRESH, WRITE_SETTLE_DELAY
from .runxin.client import F79DClient
from .runxin.errors import RunxinError
from .transport.broadlink_bl3372 import (
    BroadlinkBL3372Transport,
    BroadlinkOuterError,
)

# Keep the exception surface used by the coordinator/config flow. Every codec
# and transport error derives from RunxinError, so existing catch sites retain
# exactly the same operational behavior without coupling those lower layers to
# Home Assistant/Ypsilon names.
YpsilonConnectionError = RunxinError
YpsilonOuterError = BroadlinkOuterError


class YpsilonWriteNotConfirmed(YpsilonConnectionError):
    """The control frame was ACKed but physical read-back did not confirm it."""


class YpsilonLocalClient:
    """Async local client for the tested Ypsilon G6 / BL3372 combination."""

    def __init__(self, host: str) -> None:
        self.host = host
        self._transport = BroadlinkBL3372Transport(host)
        self._f79d = F79DClient(self._transport)
        # Preserve the original whole-operation serialization: the optional
        # field-52 refresh and write-settle delay must not interleave with a
        # concurrent poll/write even though both lower layers are also safe.
        self._lock = asyncio.Lock()

    @property
    def mac(self) -> str | None:
        return self._transport.mac

    @property
    def firmware(self) -> int | None:
        return self._transport.firmware

    @property
    def transient_retries(self) -> int:
        return self._transport.transient_retries

    @property
    def reauth_count(self) -> int:
        return self._transport.reauth_count

    async def close(self) -> None:
        async with self._lock:
            await self._f79d.close()

    async def read_identity(self) -> dict[str, Any]:
        async with self._lock:
            data = await self._f79d.read_identity()
            data["mac"] = self.mac
            return data

    async def read_state(self, field52_cache: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            state = await self._f79d.read_state()

            # Field 52 is a static filter-service setting. Keeping its slower
            # refresh policy in the Ypsilon integration avoids baking an HA
            # polling optimisation into the reusable F79D client.
            now = time.monotonic()
            if now >= field52_cache.get("next_refresh", 0.0):
                try:
                    extra = await self._f79d.read_fields([52])
                except YpsilonConnectionError:
                    field52_cache["next_refresh"] = now + FIELD52_FAIL_BACKOFF
                else:
                    field52_cache["value"] = extra.get("filterMaterialWorkingDay")
                    field52_cache["next_refresh"] = now + FIELD52_REFRESH

            state["filterMaterialWorkingDay"] = field52_cache.get("value")
            state["_transientRetries"] = self.transient_retries
            state["_reauthCount"] = self.reauth_count
            return state

    async def write_fields(self, values: dict[int, Any]) -> None:
        """Send one F79D control frame; caller must verify physical read-back."""
        async with self._lock:
            await self._f79d.write_fields(values)
            # Preserve the v2.3 timing contract before coordinator verification.
            await asyncio.sleep(WRITE_SETTLE_DELAY)
