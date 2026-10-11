"""Advanced administrator-only services for Ypsilon Local."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .api import YpsilonConnectionError
from .const import (
    CONF_DIAGNOSTIC_ONLY,
    DOMAIN,
    FIELD_FLOW_RATE_OFF,
    FIELD_SYSTEM_MODE,
    SAFE_RAW_WRITE_RANGES,
    SERVICE_ADVANCE_PHASE,
    SERVICE_WRITE_FIELDS,
    WRITABLE_FIELDS,
)

ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_FIELDS = "fields"
ATTR_PHASE = "phase"

WRITE_FIELDS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): cv.string,
        vol.Required(ATTR_FIELDS): vol.All(
            {vol.Coerce(int): vol.Any(int, [int])},
            vol.Length(min=1),
        ),
    }
)

ADVANCE_PHASE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): cv.string,
        vol.Required(ATTR_PHASE): vol.All(vol.Coerce(int), vol.Range(min=0, max=4)),
    }
)


def _coordinator(hass: HomeAssistant, entry_id: str):
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="service_entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="service_entry_not_loaded",
        )
    if entry.data.get(CONF_DIAGNOSTIC_ONLY):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="diagnostic_read_only",
        )
    if entry.runtime_data.read_only:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="model_write_not_allowed",
        )
    return entry.runtime_data


def _validate_raw_fields(coordinator, values: dict[int, object]) -> None:
    """Apply the same safety contract to the raw service as normal entities."""
    for field, value in values.items():
        if field in SAFE_RAW_WRITE_RANGES:
            if isinstance(value, list):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="service_field_invalid_value",
                    translation_placeholders={"field": str(field), "value": str(value)},
                )
            low, high = SAFE_RAW_WRITE_RANGES[field]
            try:
                number = int(value)
            except (TypeError, ValueError) as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="service_field_invalid_value",
                    translation_placeholders={"field": str(field), "value": str(value)},
                ) from err
            if not low <= number <= high:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="service_field_out_of_range",
                    translation_placeholders={
                        "field": str(field), "value": str(value),
                        "minimum": str(low), "maximum": str(high),
                    },
                )

    if FIELD_FLOW_RATE_OFF in values and (
        not coordinator.data or coordinator.data.get("waterVolumeUnit") != 2
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unsupported_flow_unit",
            translation_placeholders={},
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services once at integration setup time."""
    if hass.services.has_service(DOMAIN, SERVICE_WRITE_FIELDS):
        return

    async def _write_fields(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data[ATTR_CONFIG_ENTRY])
        raw = call.data[ATTR_FIELDS]

        unknown = sorted(set(raw) - WRITABLE_FIELDS)
        if unknown:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_fields_not_writable",
                translation_placeholders={
                    "fields": ", ".join(str(field) for field in unknown)
                },
            )

        _validate_raw_fields(coordinator, raw)
        values = {
            field: tuple(value) if isinstance(value, list) else value
            for field, value in raw.items()
        }
        try:
            await coordinator.async_write_and_verify(values)
        except (YpsilonConnectionError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_write_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def _advance_phase(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data[ATTR_CONFIG_ENTRY])
        try:
            await coordinator.async_write_and_verify(
                {FIELD_SYSTEM_MODE: call.data[ATTR_PHASE]}
            )
        except (YpsilonConnectionError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_phase_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async_register_admin_service(
        hass, DOMAIN, SERVICE_WRITE_FIELDS, _write_fields, schema=WRITE_FIELDS_SCHEMA
    )
    async_register_admin_service(
        hass, DOMAIN, SERVICE_ADVANCE_PHASE, _advance_phase, schema=ADVANCE_PHASE_SCHEMA
    )
