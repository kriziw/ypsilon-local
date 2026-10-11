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
from .models import allowed_write_fields, controller_model
from .transport.broadlink_bl3372 import (
    BroadlinkAuthenticationError,
    BroadlinkBL3372Transport,
    BroadlinkOuterError,
)

# Keep the exception surface used by the coordinator/config flow. Every codec
# and transport error derives from RunxinError, so existing catch sites retain
# exactly the same operational behavior without coupling those lower layers to
# Home Assistant/Ypsilon names.
YpsilonConnectionError = RunxinError
YpsilonOuterError = BroadlinkOuterError
YpsilonAuthenticationError = BroadlinkAuthenticationError


class YpsilonWriteNotConfirmed(YpsilonConnectionError):
    """The control frame was ACKed but physical read-back did not confirm it."""


class YpsilonLocalClient:
    """Blocking local client for the tested Ypsilon G6 / BL3372 combination."""

    def __init__(
        self, host: str, *, model1_test_writes: bool = False,
        model1_test_regeneration: bool = False,
    ) -> None:
        self.host = host
        self._transport = BroadlinkBL3372Transport(host)
        self._f79d = F79DClient(self._transport, capture_raw=True)
        # Preserve the original whole-operation serialization: the optional
        # field-52 refresh and write-settle delay must not interleave with a
        # concurrent poll/write even though both lower layers are also safe.
        self._lock = asyncio.Lock()
        self._controller_model: object = None
        self._read_only_latched = False
        self._model1_seen = False
        self._model1_test_writes = model1_test_writes
        self._model1_test_regeneration = model1_test_regeneration

    def _allowed_fields(self) -> frozenset[int]:
        fields = allowed_write_fields(
            self._controller_model, model1_test_writes=self._model1_test_writes,
            model1_test_regeneration=self._model1_test_regeneration,
        )
        if self._model1_seen:
            fields &= allowed_write_fields(
                1, model1_test_writes=self._model1_test_writes,
                model1_test_regeneration=self._model1_test_regeneration,
            )
        return fields

    def _observe_model(self, data: dict[str, Any]) -> None:
        self._controller_model = data.get("deviceModel")
        model = controller_model(self._controller_model)
        self._model1_seen |= self._controller_model == 1
        if model is not None and not self._allowed_fields():
            self._read_only_latched = True

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

    @property
    def connection_diagnostics(self) -> dict[str, Any]:
        """Non-identifying discovery/authentication/transaction metadata."""
        return self._transport.diagnostics

    @property
    def write_policy(self) -> dict[str, Any]:
        """Describe cached adapter permissions without starting device I/O."""
        code = self._controller_model
        model = controller_model(code)
        fields = self._allowed_fields()
        blocked = self._read_only_latched or model is None or not fields
        return {
            "controller_model": code if type(code) is int else None,
            "read_only": blocked,
            "allowed_write_fields": [] if blocked else sorted(fields),
        }

    async def close(self) -> None:
        async with self._lock:
            await self._f79d.close()

    async def revoke_writes(self) -> None:
        """Permanently stop queued writes before replacing this session."""
        async with self._lock:
            self._read_only_latched = True

    async def read_identity(self) -> dict[str, Any]:
        async with self._lock:
            data = await self._f79d.read_identity()
            self._observe_model(data)
            data["mac"] = self.mac
            return data

    async def read_state(self, field52_cache: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            state = await self._f79d.read_state()
            self._observe_model(state)

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
                    field52_cache["raw_bytes"] = extra.get("_rawFieldBytes", {}).get(52)
                    field52_cache["next_refresh"] = now + FIELD52_REFRESH

            state["filterMaterialWorkingDay"] = field52_cache.get("value")
            if field52_cache.get("raw_bytes") is not None:
                state.setdefault("_rawFieldBytes", {})[52] = field52_cache["raw_bytes"]
            state["_transientRetries"] = self.transient_retries
            state["_reauthCount"] = self.reauth_count
            return state

    async def write_fields(self, values: dict[int, Any]) -> None:
        """Send one F79D control frame; caller must verify physical read-back."""
        async with self._lock:
            model = controller_model(self._controller_model)
            if (
                self._read_only_latched
                or model is None
                or not set(values).issubset(self._allowed_fields())
                or (self._model1_seen and 34 in values and values != {34: 1})
            ):
                raise YpsilonConnectionError("Controller policy does not permit this write")
            await self._f79d.write_fields(values)
            # Preserve the v2.3 timing contract before coordinator verification.
            await asyncio.sleep(WRITE_SETTLE_DELAY)
