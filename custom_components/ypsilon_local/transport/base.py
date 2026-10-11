"""Transport contract for carrying raw Runxin frames.

Transports are intentionally dumb about device fields. They send one raw
Runxin request frame and return one raw Runxin response frame.

The contract is asynchronous. `python-broadlink` 1.0 made every
device-talking method a coroutine with no synchronous compatibility layer,
so the BroadLink transport cannot be driven from a worker thread any more.
Keeping the contract async also matches how Home Assistant wants I/O done,
and let the seven `async_add_executor_job` hops above this layer go away.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class RunxinTransport(ABC):
    """Optional convenience base class for stateful Runxin transports."""

    @abstractmethod
    async def transact(self, frame: bytes) -> bytes:
        """Send one raw Runxin request and return one raw Runxin response."""

    async def invalidate(self) -> None:
        """Drop stale session/framing state, if this transport has any."""

    async def close(self) -> None:
        """Release resources, if this transport owns any."""

    @property
    def identifier(self) -> str | None:
        """Stable transport/device identifier when available."""
        return None

    @property
    def firmware(self) -> int | None:
        """Transport firmware version when available."""
        return None

    @property
    def diagnostics(self) -> Mapping[str, Any]:
        """Transport-specific counters suitable for diagnostics."""
        return {}
