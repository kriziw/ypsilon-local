"""Base entity for Ypsilon Local."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL_NAME
from .models import controller_model
from .coordinator import YpsilonDataUpdateCoordinator


class YpsilonEntity(CoordinatorEntity[YpsilonDataUpdateCoordinator]):
    """Shared device wiring for every Ypsilon entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: YpsilonDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._pending_value: Any | None = None
        self._writes_in_flight = 0
        self._write_target: tuple[dict[int, Any], Any] | None = None
        self._write_waiters: list[asyncio.Future[None]] = []

    def _set_pending(self, value: Any) -> None:
        self._pending_value = value
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        if not self._writes_in_flight:
            self._pending_value = None
        super()._handle_coordinator_update()

    async def _async_write(self, fields: dict[int, Any], display: Any) -> None:
        """Coalesce rapid edits while every caller awaits the real outcome.

        A later edit replaces the pending target so a slow valve is not flooded
        with intermediate writes. Unlike the old implementation, callers that
        arrive while a writer is already running no longer return early: they
        all await the drain and receive the same success/failure result for the
        final physically reconciled state.
        """
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[None] = loop.create_future()
        self._write_waiters.append(waiter)

        self._set_pending(display)
        self._write_target = (fields, display)

        if self._writes_in_flight:
            await waiter
            return

        self._writes_in_flight = 1
        error: BaseException | None = None
        try:
            while self._write_target is not None:
                target_fields, _ = self._write_target
                self._write_target = None
                await self.coordinator.async_write_and_verify(target_fields)
        except BaseException as err:  # propagate the same result to all waiters
            error = err
            self._write_target = None
        finally:
            self._writes_in_flight = 0
            self._pending_value = None
            waiters, self._write_waiters = self._write_waiters, []
            for pending in waiters:
                if pending.done():
                    continue
                if error is None:
                    pending.set_result(None)
                else:
                    pending.set_exception(error)
            self.async_write_ha_state()

        await waiter

    @property
    def device_info(self) -> DeviceInfo:
        unique_id = self._entry.unique_id
        connections = set()
        if unique_id and unique_id.count(":") == 5:
            connections.add((CONNECTION_NETWORK_MAC, unique_id))

        firmware = self.coordinator.client.firmware
        model = controller_model((self.coordinator.data or {}).get("deviceModel"))
        return DeviceInfo(
            identifiers={(DOMAIN, unique_id or self._entry.entry_id)},
            connections=connections,
            manufacturer=model.manufacturer if model else MANUFACTURER,
            model=model.model_name if model else MODEL_NAME,
            name=self._entry.title,
            sw_version=str(firmware) if firmware is not None else None,
        )
