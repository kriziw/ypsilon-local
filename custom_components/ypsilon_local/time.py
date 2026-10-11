"""Time entities for Ypsilon Local."""

from __future__ import annotations

from dataclasses import dataclass
import datetime

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import YpsilonConnectionError
from .const import DOMAIN
from .coordinator import YpsilonDataUpdateCoordinator
from .entity import YpsilonEntity


@dataclass(frozen=True, kw_only=True)
class YpsilonTimeDescription(TimeEntityDescription):
    """A writable time-of-day setting, sent as [field, hour, minute]."""

    field_id: int
    field_name: str


# Only fields the manufacturer's own app writes are exposed as controls. The
# legacy WaterDevice settings screen writes the device clock (4) and the
# regeneration time (10); the wash start time (5) mirrors the same value and is
# never written there, so it is published as a read-only sensor instead of a
# second, apparently duplicated, control.
TIMES: tuple[YpsilonTimeDescription, ...] = (
    YpsilonTimeDescription(
        key="device_clock",
        translation_key="device_clock",
        field_id=4,
        field_name="currentTime",
        icon="mdi:clock-edit",
        entity_category=EntityCategory.CONFIG,
    ),
    YpsilonTimeDescription(
        key="regenerating_trigger_time",
        translation_key="regenerating_trigger_time",
        field_id=10,
        field_name="regeneratingTriggerTime",
        icon="mdi:clock-alert",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.read_only:
        return
    allowed = coordinator.allowed_write_fields
    async_add_entities(YpsilonTime(coordinator, entry, desc) for desc in TIMES
                       if desc.field_id in allowed)


class YpsilonTime(YpsilonEntity, TimeEntity):
    """A time-of-day value that can be read and written."""

    entity_description: YpsilonTimeDescription

    def __init__(
        self,
        coordinator: YpsilonDataUpdateCoordinator,
        entry: ConfigEntry,
        description: YpsilonTimeDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        base_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_id}_{description.key}"

    @property
    def native_value(self) -> datetime.time | None:
        if not self.coordinator.data:
            return None
        if self._pending_value is not None:
            return self._pending_value
        raw = self.coordinator.data.get(self.entity_description.field_name)
        if not raw:
            return None
        try:
            hour, minute = (int(part) for part in str(raw).split(":")[:2])
            return datetime.time(hour=hour, minute=minute)
        except (ValueError, TypeError):
            return None

    async def async_set_value(self, value: datetime.time) -> None:
        try:
            await self._async_write(
                {self.entity_description.field_id: (value.hour, value.minute)}, value
            )
        except (YpsilonConnectionError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={
                    "name": self.entity_description.field_name,
                    "error": str(err),
                },
            ) from err
