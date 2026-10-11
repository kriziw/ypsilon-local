"""Diagnostics for Ypsilon Local."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .models import controller_model, model_support_details
from .const import (
    CONF_AUTO_SYNC_CLOCK, CONF_CONTROLLER_MODEL, CONF_DIAGNOSTIC_ONLY,
    DEFAULT_AUTO_SYNC_CLOCK, FIELD_CURRENT_TIME,
)
from .runxin.semantics import (
    REGENERATION_PATTERN_KEYS,
    STATION_KEYS,
    SYSTEM_CLOSE_REASON_KEYS,
    VOLUME_UNIT_KEYS,
    WORK_PATTERN_KEYS,
)

TO_REDACT = {"mac", "host", "unique_id"}


def _write_policy_summary(entry: ConfigEntry, coordinator: Any) -> dict[str, Any]:
    """Separate model evidence from the permissions retained by both guards."""
    code = (coordinator.data or {}).get("deviceModel")
    model = controller_model(code)
    coordinator_blocked = bool(getattr(coordinator, "read_only", False)) or model is None
    fields = set() if coordinator_blocked else set(getattr(
        coordinator, "allowed_write_fields", model.allowed_write_fields,
    ))
    adapter = getattr(coordinator.client, "write_policy", None)
    if isinstance(adapter, dict):
        if adapter.get("read_only", True):
            fields.clear()
        else:
            fields.intersection_update(adapter.get("allowed_write_fields", []))
    else:
        adapter = None
    clock_requested = bool(getattr(
        coordinator, "auto_sync_clock",
        entry.options.get(CONF_AUTO_SYNC_CLOCK, DEFAULT_AUTO_SYNC_CLOCK),
    ))
    return {
        "configured_model": entry.data.get(CONF_CONTROLLER_MODEL),
        "observed_model": code,
        "coordinator_read_only": coordinator_blocked,
        "adapter": adapter,
        "read_only": not fields,
        "allowed_write_fields": sorted(fields),
        "model1_test_writes": bool(getattr(coordinator, "model1_test_writes", False)),
        "model1_test_regeneration": bool(getattr(coordinator, "model1_test_regeneration", False)),
        "auto_clock_sync_requested": clock_requested,
        "auto_clock_sync_permitted": clock_requested and FIELD_CURRENT_TIME in fields
        and bool(getattr(coordinator, "automatic_clock_allowed", code != 1)),
    }


def _semantic_protocol_summary(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return compact interpreted protocol metadata alongside the raw state."""
    if not data:
        return None

    regeneration_code = data.get("regenerationPattern")
    work_code = data.get("workPattern")
    volume_unit_code = data.get("waterVolumeUnit")
    station_code = data.get("station")
    close_code = data.get("systemCloseReason")

    return {
        "profile": "F79D",
        "device_model": data.get("deviceModel"),
        "model_support": model_support_details(data.get("deviceModel")),
        "volume_unit_code": volume_unit_code,
        "volume_unit": VOLUME_UNIT_KEYS.get(volume_unit_code),
        "regeneration_pattern_code": regeneration_code,
        "regeneration_pattern": REGENERATION_PATTERN_KEYS.get(regeneration_code),
        "work_pattern_code": work_code,
        "work_pattern": WORK_PATTERN_KEYS.get(work_code),
        "station_code": station_code,
        "station": STATION_KEYS.get(station_code),
        "vacation_enabled": data.get("vacationPattern"),
        "vacation_status": data.get("_vacationStatus"),
        "system_close_reason_code": close_code,
        "system_close_reason": SYSTEM_CLOSE_REASON_KEYS.get(close_code),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return everything needed to debug a report, minus identifying data."""
    if entry.data.get(CONF_DIAGNOSTIC_ONLY):
        return {"diagnostic_only": True, "compatibility_report": entry.runtime_data.report}
    coordinator = entry.runtime_data
    client = coordinator.client
    state = dict(coordinator.data) if coordinator.data else None
    if state and state.get("_lastPollError") is not None:
        # Runtime error text can originate in a third-party library and contain
        # an address or device repr. Export safe structured transport metadata
        # instead of copying arbitrary exception text into an issue attachment.
        state["_lastPollError"] = "Connection error; see connection.transport metadata"

    return {
        "entry": {
            "version": entry.version,
            "options": dict(entry.options),
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "connection": {
            "available": coordinator.last_update_success,
            "scan_interval": coordinator.scan_interval,
            "firmware": client.firmware,
            "transient_retries": client.transient_retries,
            "reauth_count": client.reauth_count,
            "transport": client.connection_diagnostics,
        },
        "protocol": _semantic_protocol_summary(coordinator.data),
        "write_policy": _write_policy_summary(entry, coordinator),
        "state": async_redact_data(state, TO_REDACT)
        if state
        else None,
    }
