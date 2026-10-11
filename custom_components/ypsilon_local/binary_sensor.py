"""Binary sensors for Ypsilon Local."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import YpsilonEntity
from .runxin.semantics import SYSTEM_CLOSE_REASON_KEYS
from .models import controller_model


@dataclass(frozen=True, kw_only=True)
class YpsilonBinaryDescription(BinarySensorEntityDescription):
    field: str
    protocol_field: str | None = None
    inverted: bool = False


BINARY_SENSORS = (
    YpsilonBinaryDescription(
        key="valve_closed_alarm", translation_key="valve_closed_alarm", field="systemCloseReason",
        protocol_field="12", device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    YpsilonBinaryDescription(
        key="clock_fault", translation_key="clock_fault", field="clockChipFault",
        protocol_field="27", device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    YpsilonBinaryDescription(
        key="multiple_position_fault", translation_key="multiple_position_fault", field="multiplePositionSignalFault",
        protocol_field="28", device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    YpsilonBinaryDescription(
        key="no_position_fault", translation_key="no_position_fault", field="noPositionSignalFault",
        protocol_field="29", device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    YpsilonBinaryDescription(
        key="memory_fault", translation_key="memory_fault", field="memoryErrorFault",
        protocol_field="30", device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    YpsilonBinaryDescription(
        key="salt_shortage_alarm", translation_key="salt_shortage_alarm", field="saltShortageAlarm",
        protocol_field="31", device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    YpsilonBinaryDescription(
        key="resin_replacement", translation_key="resin_replacement", field="resinReplacementReminder",
        protocol_field="32", device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    YpsilonBinaryDescription(
        key="salt_shortage_reminder", translation_key="salt_shortage_reminder", field="saltShortageReminder",
        protocol_field="33", device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    YpsilonBinaryDescription(
        key="communication_problem", translation_key="communication_problem",
        field="_lastPollSuccessful", protocol_field=None,
        inverted=True, device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    YpsilonBinaryDescription(
        key="filter_reminder", translation_key="filter_reminder", field="filterMaterialReminder",
        protocol_field="33", device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(YpsilonBinarySensor(coordinator, entry, desc) for desc in BINARY_SENSORS)


class YpsilonBinarySensor(YpsilonEntity, BinarySensorEntity):
    entity_description: YpsilonBinaryDescription

    def __init__(self, coordinator, entry, description) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        base_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self.entity_description.field)
        if value is None:
            return None
        state = bool(value)
        return not state if self.entity_description.inverted else state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes: dict[str, Any] = {}
        model = controller_model((self.coordinator.data or {}).get("deviceModel"))
        if model is not None and model.provisional_readings:
            attributes.update(interpretation="reference_f79d_pending_app_validation", read_only=True)
            raw = (self.coordinator.data or {}).get("_rawFieldBytes", {})
            field = self.entity_description.protocol_field
            if field is not None:
                attributes["raw_bytes"] = raw.get(int(field))
        if self.entity_description.protocol_field is not None:
            attributes["f79d_protocol_field"] = self.entity_description.protocol_field
        if self.entity_description.key == "communication_problem":
            data = self.coordinator.data or {}
            attributes["last_error"] = data.get("_lastPollError")
            attributes["consecutive_failures"] = data.get("_consecutiveFailures")
            attributes["stale"] = data.get("_stale", False)
            attributes["data_age_seconds"] = data.get("_dataAgeSeconds")
        if self.entity_description.key == "valve_closed_alarm":
            code = (self.coordinator.data or {}).get("systemCloseReason")
            attributes["reason_code"] = code
            attributes["reason"] = SYSTEM_CLOSE_REASON_KEYS.get(code, "unknown" if code else None)
        return attributes
