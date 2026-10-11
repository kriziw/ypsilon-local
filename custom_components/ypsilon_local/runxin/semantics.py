"""Reference semantic mappings and confirmed per-model F79D labels."""

from __future__ import annotations

DEVICE_LANGUAGE_KEYS: dict[int, str] = {
    0: "chinese",
    1: "english",
    2: "spanish",
    3: "french",
    4: "russian",
    5: "italian",
    6: "german",
    7: "polish",
}

# Physical controller observations, not the app/account locale enumeration.
# Only these model/code pairs are confirmed; retain every other reference label.
DEVICE_LANGUAGE_OVERRIDES: dict[int, dict[int, str]] = {
    1: {7: "dutch"},  # Issue #17: controller display, 2026-10-10.
    9: {3: "spanish"},  # Project G6: field 2 = 3 and Spanish controller menus.
}


def device_language_keys(device_model: object) -> dict[int, str]:
    """Return an independent label map for the observed controller model."""
    result = DEVICE_LANGUAGE_KEYS.copy()
    if type(device_model) is int:
        result.update(DEVICE_LANGUAGE_OVERRIDES.get(device_model, {}))
    return result


DEVICE_TIME_SCHEME_KEYS: dict[int, str] = {
    0: "12_hour",
    1: "24_hour",
}

OUTPUT_RELAY_MODE_KEYS: dict[int, str] = {
    0: "b_01",
    1: "b_02",
}

BRINE_DRAW_MODE_KEYS: dict[int, str] = {
    0: "reverse",
    1: "forward",
}

STATION_KEYS: dict[int, str] = {
    0: "in_service",
    1: "backwash",
    2: "brine_draw",
    3: "brine_refill",
    4: "fast_rinse",
    5: "closed",
    6: "salt_dissolving",
    7: "pause_1",
    8: "pause_2",
}

VOLUME_UNIT_KEYS: dict[int, str] = {
    0: "gallons",
    1: "liters",
    2: "cubic_meters",
}

REGENERATION_PATTERN_KEYS: dict[int, str] = {
    0: "flow",
    1: "time",
}

WORK_PATTERN_KEYS: dict[int, str] = {
    0: "downflow_meter_delayed",
    1: "downflow_meter_immediate",
    2: "downflow_intelligent_meter_delayed",
    3: "upflow_meter_delayed",
    4: "upflow_meter_immediate",
    5: "upflow_intelligent_meter_delayed",
    6: "filter_type",
    7: "meter_delayed",
    8: "meter_immediate",
    9: "intelligent_meter_delayed",
}

SYSTEM_CLOSE_REASON_KEYS: dict[int, str] = {
    257: "manual_close",
    513: "leak_detected",
    769: "continuous_flow_timeout",
    1025: "flow_rate_exceeded",
}

VACATION_STATUS_KEYS = ("off", "preparing", "active")


def vacation_status(vacation_enabled: bool | None, station: int | None) -> str | None:
    """Return the semantic vacation state without hiding the raw valve phase."""
    if vacation_enabled is None:
        return None
    if not vacation_enabled:
        return "off"
    return "active" if station == 8 else "preparing"
