"""Number entities for Ypsilon Local."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfMass, UnitOfTime, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import YpsilonConnectionError
from .const import DOMAIN
from .entity import YpsilonEntity

SUPPORTED_FLOW_UNIT_CODE = 2


@dataclass(frozen=True, kw_only=True)
class YpsilonNumberDescription(NumberEntityDescription):
    field_id: int
    field_name: str
    hundredths: bool = False


NUMBERS = (
    YpsilonNumberDescription(
        key="salt_addition", translation_key="salt_addition", field_id=43, field_name="saltAddition",
        native_min_value=0, native_max_value=100, native_step=1,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS, entity_category=EntityCategory.CONFIG,
        icon="mdi:shaker-outline",
    ),
    YpsilonNumberDescription(
        key="raw_water_hardness", translation_key="raw_water_hardness", field_id=47,
        field_name="rawWaterHardness", native_min_value=50, native_max_value=1500,
        native_step=10, native_unit_of_measurement="mg/L",
        entity_category=EntityCategory.CONFIG, icon="mdi:water-opacity",
    ),
    YpsilonNumberDescription(
        key="continuous_water_time", translation_key="continuous_water_time", field_id=6,
        field_name="continuousWaterTime", native_min_value=0, native_max_value=120,
        native_step=1, native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.CONFIG, icon="mdi:pipe-leak",
    ),
    YpsilonNumberDescription(
        key="flow_rate_off", translation_key="flow_rate_off", field_id=7, field_name="flowRateOff",
        hundredths=True, native_min_value=0, native_max_value=10.0, native_step=0.01,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        entity_category=EntityCategory.CONFIG, icon="mdi:valve-closed",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.read_only:
        return
    allowed = coordinator.allowed_write_fields
    async_add_entities(YpsilonNumber(coordinator, entry, desc) for desc in NUMBERS
                       if desc.field_id in allowed)


class YpsilonNumber(YpsilonEntity, NumberEntity):
    entity_description: YpsilonNumberDescription

    def __init__(self, coordinator, entry, description) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        base_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_id}_{description.key}"
        self._attr_mode = NumberMode.BOX

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self.entity_description.key != "flow_rate_off":
            return True
        # Field 7 is physically calibrated on the tested G6 as BE hundredths.
        # Unit code 2 is the only flow-unit family validated end-to-end, so keep
        # this writable control unavailable for uncalibrated unit families.
        return bool(
            self.coordinator.data
            and self.coordinator.data.get("waterVolumeUnit") == SUPPORTED_FLOW_UNIT_CODE
        )

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        if self._pending_value is not None:
            return self._pending_value
        value = self.coordinator.data.get(self.entity_description.field_name)
        if value is None:
            return None
        if self.entity_description.hundredths:
            return round(value / 100, 2)
        return value

    async def async_set_native_value(self, value: float) -> None:
        desc = self.entity_description
        if (
            desc.key == "flow_rate_off"
            and (
                not self.coordinator.data
                or self.coordinator.data.get("waterVolumeUnit") != SUPPORTED_FLOW_UNIT_CODE
            )
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_flow_unit",
                translation_placeholders={},
            )

        if desc.native_min_value is not None and value < desc.native_min_value:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="below_minimum",
                translation_placeholders={
                    "value": str(value),
                    "minimum": str(desc.native_min_value),
                },
            )
        if desc.native_max_value is not None and value > desc.native_max_value:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="above_maximum",
                translation_placeholders={
                    "value": str(value),
                    "maximum": str(desc.native_max_value),
                },
            )

        raw = round(value * 100) if desc.hundredths else int(value)
        try:
            await self._async_write({desc.field_id: raw}, value)
        except (YpsilonConnectionError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={
                    "name": desc.field_name,
                    "error": str(err),
                },
            ) from err
