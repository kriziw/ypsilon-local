"""Button entities for Ypsilon Local."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import YpsilonConnectionError
from .const import DOMAIN, FIELD_CURRENT_TIME
from .coordinator import YpsilonDataUpdateCoordinator
from .entity import YpsilonEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.read_only:
        return
    allowed = coordinator.allowed_write_fields
    buttons = []
    if 34 in allowed:
        buttons.append(YpsilonRegenerationButton(coordinator, entry))
    if FIELD_CURRENT_TIME in allowed:
        buttons.append(YpsilonSyncClockButton(coordinator, entry))
    async_add_entities(buttons)


class YpsilonRegenerationButton(YpsilonEntity, ButtonEntity):
    """Force a regeneration.

    The legacy WaterDevice APK implements its regeneration button as
    control({systemMode: 1}) for deviceModel 9, i.e. a plain write of field 34
    with value 1, so this mirrors the manufacturer's own action rather than
    guessing. It moves the valve and consumes water and salt, so it is a real
    mechanical operation and deliberately has no confirmation-free automation
    shortcut beyond the normal button press.
    """

    _attr_translation_key = "force_regeneration"
    _attr_icon = "mdi:recycle-variant"

    def __init__(
        self, coordinator: YpsilonDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        base_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_id}_force_regeneration"

    async def async_press(self) -> None:
        _LOGGER.info("Requesting forced regeneration (systemMode=1)")
        try:
            await self.coordinator.async_start_regeneration()
        except YpsilonConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"name": "regeneration", "error": str(err)},
            ) from err



class YpsilonSyncClockButton(YpsilonEntity, ButtonEntity):
    """Set the valve clock from Home Assistant's local time.

    The controller keeps its own clock and drifts; every regeneration schedule
    depends on it, so a one-press resync is more useful than a read-only
    reminder that the time is wrong.
    """

    _attr_translation_key = "sync_clock"
    _attr_icon = "mdi:clock-check"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: YpsilonDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        base_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_id}_sync_clock"

    async def async_press(self) -> None:
        now = dt_util.now()
        try:
            await self.coordinator.async_write_and_verify(
                {FIELD_CURRENT_TIME: (now.hour, now.minute)}
            )
        except (YpsilonConnectionError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"name": "clock", "error": str(err)},
            ) from err
