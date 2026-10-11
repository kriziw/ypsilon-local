"""Sensors exposed by Ypsilon Local."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime, UnitOfVolume, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import CONF_CONTROLLER_MODEL, FLOW_RATE_SCALE_BY_UNIT, FLOW_RATE_SCALE_DEFAULT
from .entity import YpsilonEntity
from .models import CONTROLLER_MODELS, ControllerModel, controller_model, resin_volume_litres
from .runxin.semantics import (
    BRINE_DRAW_MODE_KEYS,
    DEVICE_LANGUAGE_KEYS,
    DEVICE_LANGUAGE_OVERRIDES,
    DEVICE_TIME_SCHEME_KEYS,
    OUTPUT_RELAY_MODE_KEYS,
    REGENERATION_PATTERN_KEYS,
    STATION_KEYS,
    VACATION_STATUS_KEYS,
    VOLUME_UNIT_KEYS,
    WORK_PATTERN_KEYS,
    device_language_keys,
)

SOURCE_DEVICE = "Runxin F79D"
SOURCE_INTEGRATION = "Ypsilon Local Integration"

VOLUME_UNITS = {
    0: UnitOfVolume.GALLONS,
    1: UnitOfVolume.LITERS,
    2: UnitOfVolume.CUBIC_METERS,
}
# Legacy WaterDevice labels the three flow units as gpm, Lpm and m³/h.
# Only unit code 2 has been calibrated end-to-end on the project's hardware.
FLOW_UNITS = {
    0: UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
    1: UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
    2: UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
}
MODEL_NAMES = {code: model.model_name for code, model in CONTROLLER_MODELS.items()}


@dataclass(frozen=True, kw_only=True)
class YpsilonSensorDescription(SensorEntityDescription):
    field: str
    protocol_field: str | None = None
    source: str = SOURCE_DEVICE
    unit_kind: str | None = None
    value_map: dict[int, str] | None = None


SENSORS = (
    YpsilonSensorDescription(
        key="flow_rate", translation_key="flow_rate", field="flowRate", protocol_field="11",
        unit_kind="flow", device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
        icon="mdi:waves-arrow-right",
    ),
    YpsilonSensorDescription(
        key="daily_water", translation_key="daily_water", field="dailyWaterConsumption",
        protocol_field="37–38", unit_kind="volume", device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2,
        icon="mdi:water",
    ),
    YpsilonSensorDescription(
        key="residual_water", translation_key="residual_water", field="residualWaterProduction",
        protocol_field="35–36", unit_kind="volume", state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2, icon="mdi:water",
    ),
    YpsilonSensorDescription(
        key="weekly_average", translation_key="weekly_average", field="averageWeeklyWaterConsumption",
        protocol_field="39–40", unit_kind="volume",
        suggested_display_precision=2, icon="mdi:chart-line",
    ),
    YpsilonSensorDescription(
        key="station", translation_key="station", field="station", protocol_field="34",
        device_class=SensorDeviceClass.ENUM, options=list(STATION_KEYS.values()), icon="mdi:state-machine",
    ),
    YpsilonSensorDescription(
        key="vacation_status", translation_key="vacation_status", field="_vacationStatus",
        source=SOURCE_INTEGRATION, device_class=SensorDeviceClass.ENUM,
        options=list(VACATION_STATUS_KEYS), icon="mdi:beach",
    ),
    YpsilonSensorDescription(
        key="operation_day", translation_key="operation_day", field="operationDay", protocol_field="44",
        native_unit_of_measurement=UnitOfTime.DAYS, entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:calendar-today",
    ),
    YpsilonSensorDescription(
        key="remaining_day", translation_key="remaining_day", field="remainingDay", protocol_field="45",
        native_unit_of_measurement=UnitOfTime.DAYS, entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:calendar-clock",
    ),
    YpsilonSensorDescription(
        key="regeneration_pattern", translation_key="regeneration_pattern", field="regenerationPattern",
        protocol_field="46", device_class=SensorDeviceClass.ENUM,
        options=list(REGENERATION_PATTERN_KEYS.values()), icon="mdi:sync-circle",
    ),
    YpsilonSensorDescription(
        key="work_pattern", translation_key="work_pattern", field="workPattern",
        protocol_field="9", device_class=SensorDeviceClass.ENUM,
        options=list(WORK_PATTERN_KEYS.values()), icon="mdi:tune-variant",
    ),
    YpsilonSensorDescription(
        key="maximum_regeneration_interval", translation_key="maximum_regeneration_interval",
        field="maximumRegenerationIntervalDay", protocol_field="23",
        native_unit_of_measurement=UnitOfTime.DAYS, entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:calendar-alert",
    ),
    YpsilonSensorDescription(
        key="periodic_water", translation_key="periodic_water", field="periodicWaterProduction",
        protocol_field="41–42", unit_kind="volume",
        suggested_display_precision=2, entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:water-check",
    ),
    YpsilonSensorDescription(
        key="backwash_time", translation_key="backwash_time", field="backWashTime", protocol_field="15",
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:timer-outline",
    ),
    YpsilonSensorDescription(
        key="backwash_remaining", translation_key="backwash_remaining", field="backWashTimeRemaining",
        protocol_field="16", entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:timer-sand",
    ),
    YpsilonSensorDescription(
        key="slow_wash_time", translation_key="slow_wash_time", field="absorbSaltSlowWashTime",
        protocol_field="17", entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:timer-outline",
    ),
    YpsilonSensorDescription(
        key="slow_wash_remaining", translation_key="slow_wash_remaining", field="absorbSaltTimeRemaining",
        protocol_field="18", entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:timer-sand",
    ),
    YpsilonSensorDescription(
        key="refill_time", translation_key="refill_time", field="saltTankRefillTime", protocol_field="19",
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:timer-outline",
    ),
    YpsilonSensorDescription(
        key="refill_remaining", translation_key="refill_remaining", field="saltTankRefillTimeRemaining",
        protocol_field="20", entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:timer-sand",
    ),
    YpsilonSensorDescription(
        key="wash_time", translation_key="wash_time", field="washTime", protocol_field="21",
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:timer-outline",
    ),
    YpsilonSensorDescription(
        key="wash_remaining", translation_key="wash_remaining", field="washCountdownTime", protocol_field="22",
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:timer-sand",
    ),
    YpsilonSensorDescription(
        key="salt_dissolution_remaining", translation_key="salt_dissolution_remaining",
        field="saltDissolutionRemainingTime", protocol_field="50",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:timer-sand",
    ),
    YpsilonSensorDescription(
        key="pause_1_remaining", translation_key="pause_1_remaining",
        field="pauseRemainingTime", protocol_field="51",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:timer-sand",
    ),
    YpsilonSensorDescription(
        key="resin_volume", translation_key="resin_volume", field="resinVolume", protocol_field="26",
        native_unit_of_measurement=UnitOfVolume.LITERS, entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:barrel-outline",
    ),
    YpsilonSensorDescription(
        key="filter_work_days", translation_key="filter_work_days", field="filterMaterialWorkingDay",
        protocol_field="52", native_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:air-filter",
    ),
    YpsilonSensorDescription(
        key="device_model", translation_key="device_model", field="deviceModel", protocol_field="1",
        value_map=MODEL_NAMES, entity_category=EntityCategory.DIAGNOSTIC,
    ),
    YpsilonSensorDescription(
        key="language_code", translation_key="language_code", field="language", protocol_field="2",
        device_class=SensorDeviceClass.ENUM, options=list(DEVICE_LANGUAGE_KEYS.values()),
        value_map=DEVICE_LANGUAGE_KEYS, entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False, icon="mdi:translate",
    ),
    YpsilonSensorDescription(
        key="device_time_scheme", translation_key="device_time_scheme", field="deviceTimeScheme",
        protocol_field="3", device_class=SensorDeviceClass.ENUM,
        options=list(DEVICE_TIME_SCHEME_KEYS.values()), value_map=DEVICE_TIME_SCHEME_KEYS,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        icon="mdi:clock-cog-outline",
    ),
    YpsilonSensorDescription(
        key="washing_increase_number", translation_key="washing_increase_number",
        field="washingIncreaseNumber", protocol_field="13",
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        icon="mdi:counter",
    ),
    YpsilonSensorDescription(
        key="backwash_interval_number", translation_key="backwash_interval_number",
        field="backWashIntervalNumber", protocol_field="14",
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        icon="mdi:counter",
    ),
    YpsilonSensorDescription(
        key="output_relay_mode", translation_key="output_relay_mode", field="outRelayMode",
        protocol_field="24", device_class=SensorDeviceClass.ENUM,
        options=list(OUTPUT_RELAY_MODE_KEYS.values()), value_map=OUTPUT_RELAY_MODE_KEYS,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        icon="mdi:electric-switch",
    ),
    YpsilonSensorDescription(
        key="resin_regeneration_alarm_number", translation_key="resin_regeneration_alarm_number",
        field="regenerationAlarmNumber", protocol_field="25",
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:counter",
    ),
    YpsilonSensorDescription(
        key="brine_draw_mode", translation_key="brine_draw_mode", field="absorbSaltMode",
        protocol_field="48", device_class=SensorDeviceClass.ENUM,
        options=list(BRINE_DRAW_MODE_KEYS.values()), value_map=BRINE_DRAW_MODE_KEYS,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        icon="mdi:water-cog-outline",
    ),
    YpsilonSensorDescription(
        key="volume_unit", translation_key="volume_unit", field="waterVolumeUnit", protocol_field="8",
        device_class=SensorDeviceClass.ENUM, options=list(VOLUME_UNIT_KEYS.values()),
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
    ),
    YpsilonSensorDescription(
        key="last_sync", translation_key="last_sync", field="_lastSuccessfulUpdate",
        source=SOURCE_INTEGRATION, device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:clock-check-outline",
    ),
    YpsilonSensorDescription(
        key="poll_duration", translation_key="poll_duration", field="_pollDurationMs",
        source=SOURCE_INTEGRATION, native_unit_of_measurement="ms",
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        icon="mdi:timer-outline",
    ),
    YpsilonSensorDescription(
        key="scan_interval", translation_key="scan_interval", field="_scanIntervalSeconds",
        source=SOURCE_INTEGRATION, native_unit_of_measurement="s",
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        icon="mdi:refresh",
    ),
    YpsilonSensorDescription(
        key="polling_mode", translation_key="polling_mode", field="_pollingMode",
        source=SOURCE_INTEGRATION, device_class=SensorDeviceClass.ENUM,
        options=["idle", "active"], entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:speedometer",
    ),
    YpsilonSensorDescription(
        key="transient_retries", translation_key="transient_retries", field="_transientRetries",
        source=SOURCE_INTEGRATION, state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        icon="mdi:connection",
    ),
    YpsilonSensorDescription(
        key="reauth_count", translation_key="reauth_count", field="_reauthCount",
        source=SOURCE_INTEGRATION, state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        icon="mdi:key-change",
    ),
    YpsilonSensorDescription(
        key="consecutive_failures", translation_key="consecutive_failures", field="_consecutiveFailures",
        source=SOURCE_INTEGRATION, state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:alert-circle-outline",
    ),
    YpsilonSensorDescription(
        key="active_alerts", translation_key="active_alerts", field="_activeAlertCount",
        source=SOURCE_INTEGRATION, state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:bell-alert-outline",
    ),
    YpsilonSensorDescription(
        key="wash_initiation_time", translation_key="wash_initiation_time",
        field="washInitiationTime", protocol_field="5", entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-start",
    ),
    YpsilonSensorDescription(
        key="clock_drift", translation_key="clock_drift", field="_clockDriftMinutes",
        source=SOURCE_INTEGRATION, native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-alert-outline",
    ),
    YpsilonSensorDescription(
        key="clock_syncs", translation_key="clock_syncs", field="_clockSyncs",
        source=SOURCE_INTEGRATION, state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        icon="mdi:clock-check-outline",
    ),
    YpsilonSensorDescription(
        key="failed_polls", translation_key="failed_polls", field="_failedPolls",
        source=SOURCE_INTEGRATION, state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        icon="mdi:close-network-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(YpsilonSensor(coordinator, entry, desc) for desc in SENSORS)
    model = controller_model((coordinator.data or {}).get("deviceModel"))
    if model is not None and (model.read_only or model.provisional_readings):
        async_add_entities(YpsilonSensor(coordinator, entry, desc) for desc in READ_ONLY_SETTINGS)


# Read-only equivalents for settings normally shown by number/time controls.
# New keys cannot collide with the legacy controls' registry identities.
READ_ONLY_SETTINGS = (
    YpsilonSensorDescription(key="reference_clock", translation_key="reference_clock",
        field="currentTime", protocol_field="4", entity_category=EntityCategory.DIAGNOSTIC),
    YpsilonSensorDescription(key="reference_schedule", translation_key="reference_schedule",
        field="regeneratingTriggerTime", protocol_field="10", entity_category=EntityCategory.DIAGNOSTIC),
    YpsilonSensorDescription(key="reference_salt", translation_key="reference_salt",
        field="saltAddition", protocol_field="43", native_unit_of_measurement="kg",
        entity_category=EntityCategory.DIAGNOSTIC),
    YpsilonSensorDescription(key="reference_hardness", translation_key="reference_hardness",
        field="rawWaterHardness", protocol_field="47", native_unit_of_measurement="mg/L",
        entity_category=EntityCategory.DIAGNOSTIC),
    YpsilonSensorDescription(key="reference_continuous_flow", translation_key="reference_continuous_flow",
        field="continuousWaterTime", protocol_field="6", native_unit_of_measurement="min",
        entity_category=EntityCategory.DIAGNOSTIC),
    YpsilonSensorDescription(key="reference_flow_cutoff", translation_key="reference_flow_cutoff",
        field="flowRateOff", protocol_field="7", entity_category=EntityCategory.DIAGNOSTIC),
    YpsilonSensorDescription(key="reference_close_reason", translation_key="reference_close_reason",
        field="systemCloseReason", protocol_field="12", entity_category=EntityCategory.DIAGNOSTIC),
)


class YpsilonSensor(YpsilonEntity, SensorEntity):
    entity_description: YpsilonSensorDescription

    @property
    def _model(self) -> ControllerModel | None:
        configured = controller_model(getattr(self._entry, "data", {}).get(CONF_CONTROLLER_MODEL))
        if configured is not None and configured.provisional_readings:
            return configured
        return controller_model((self.coordinator.data or {}).get("deviceModel"))

    @property
    def state_class(self) -> SensorStateClass | None:
        # Provisional water conversions must not become long-term statistics.
        if self._model is not None and self._model.provisional_readings:
            return None
        return self.entity_description.state_class

    def __init__(self, coordinator, entry, description) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        base_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_id}_{description.key}"

    @property
    def _value_map(self) -> dict[int, str] | None:
        if self.entity_description.key == "language_code":
            model = self._model
            return device_language_keys(model.code if model is not None else None)
        return {
            "station": STATION_KEYS,
            "volume_unit": VOLUME_UNIT_KEYS,
            "regeneration_pattern": REGENERATION_PATTERN_KEYS,
            "work_pattern": WORK_PATTERN_KEYS,
        }.get(self.entity_description.key, self.entity_description.value_map)

    @property
    def options(self) -> list[str] | None:
        """Keep known enum keys and admit the current unmapped device code."""
        options = self.entity_description.options
        if self.entity_description.key == "language_code":
            options = list(dict.fromkeys(self._value_map.values()))
        if options is None:
            return None
        result = list(options)
        value = self.native_value
        if self._value_map is not None and value is not None and value not in result:
            result.append(str(value))
        return result

    @property
    def native_value(self) -> StateType:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self.entity_description.field)
        if value is None:
            return None

        if self._value_map is not None:
            return self._value_map.get(value, str(value))
        if self.entity_description.key == "resin_volume":
            if self._model is not None and self._model.resin_volume_scale is None:
                return value
            return resin_volume_litres(value, self.coordinator.data.get("deviceModel"))

        if self.entity_description.unit_kind == "flow":
            unit_code = self.coordinator.data.get("waterVolumeUnit")
            scale = FLOW_RATE_SCALE_BY_UNIT.get(unit_code, FLOW_RATE_SCALE_DEFAULT)
            try:
                return round(float(value) * scale, 4)
            except (TypeError, ValueError):
                return None

        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self._model is not None and self.entity_description.field in self._model.unconfirmed_unit_fields:
            return None
        if not self.coordinator.data or self.entity_description.unit_kind is None:
            return self.entity_description.native_unit_of_measurement
        unit_code = self.coordinator.data.get("waterVolumeUnit")
        if self.entity_description.unit_kind == "flow":
            return FLOW_UNITS.get(unit_code)
        return VOLUME_UNITS.get(unit_code)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes: dict[str, Any] = {"origin": self.entity_description.source}
        if (
            self.entity_description.key == "resin_volume"
            and self._model is not None
            and self._model.resin_volume_scale is not None
            and not self._model.resin_volume_scale_confirmed
        ):
            attributes.update(
                resin_volume_scale=self._model.resin_volume_scale,
                resin_volume_scale_confirmed=False,
                interpretation="midnight_scale_pending_direct_comparison",
            )
        if self._model is not None and self._model.provisional_readings:
            attributes.update(
                interpretation="reference_f79d_pending_app_validation",
                controller_model=self._model.code,
                read_only=bool(getattr(self.coordinator, "read_only", True)),
                reference_value=(self.coordinator.data or {}).get(self.entity_description.field),
            )
            raw = (self.coordinator.data or {}).get("_rawFieldBytes", {})
            # Paired field IDs use an en dash in the description (e.g. 35–36).
            ids = (self.entity_description.protocol_field or "").split("–")
            pairs = {field: raw.get(int(field)) for field in ids if field.isdigit()}
            if pairs:
                attributes["raw_field_bytes"] = pairs
            if self.entity_description.field in self._model.unconfirmed_unit_fields:
                attributes["unit_confirmed"] = False
            if self.entity_description.key == "reference_flow_cutoff":
                attributes["reference_display_candidate"] = (
                    self.native_value / 100 if self.native_value is not None else None
                )
        if self.entity_description.protocol_field is not None:
            attributes["f79d_protocol_field"] = self.entity_description.protocol_field
        if self.coordinator.data and (
            self.entity_description.value_map is not None
            or self.entity_description.key
            in ("station", "volume_unit", "regeneration_pattern", "work_pattern")
        ):
            raw = self.coordinator.data.get(self.entity_description.field)
            if raw is not None:
                attributes["raw_code"] = raw
                if self.entity_description.key == "language_code":
                    model = self._model
                    confirmed = model is not None and raw in DEVICE_LANGUAGE_OVERRIDES.get(model.code, {})
                    attributes["interpretation"] = (
                        "controller_display_confirmed" if confirmed
                        else "reference_device_language_enum"
                    )
                    if model is not None:
                        attributes["controller_model"] = model.code
        if self.entity_description.key == "active_alerts" and self.coordinator.data:
            attributes["alerts"] = self.coordinator.data.get("_activeAlerts", [])
        if self.entity_description.key == "flow_rate" and self.coordinator.data:
            raw = self.coordinator.data.get("_raw_flowRate")
            if raw is not None:
                attributes["raw_value"] = raw
        if self.entity_description.key == "resin_volume" and self.coordinator.data:
            raw_bytes = self.coordinator.data.get("_raw_resinVolumeBytes")
            if raw_bytes is not None:
                attributes["raw_bytes"] = list(raw_bytes)
        return attributes
