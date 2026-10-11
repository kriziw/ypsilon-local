"""Ensure every readable F79D field has an explicit Home Assistant surface policy."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "custom_components" / "ypsilon_local"

PLATFORM_FILES = (
    "sensor.py",
    "binary_sensor.py",
    "number.py",
    "time.py",
    "button.py",
)

# Fields represented semantically rather than as a one-to-one raw entity.
# Field 49 feeds the derived vacation_status sensor together with station 34.
SEMANTICALLY_COMPOSED_FIELDS = {49}

RAW_DIAGNOSTICS_DISABLED_BY_DEFAULT = {
    "language_code": 2,
    "device_time_scheme": 3,
    "washing_increase_number": 13,
    "backwash_interval_number": 14,
    "output_relay_mode": 24,
    "brine_draw_mode": 48,
}

RECOVERED_ENUMS = {
    "language_code": {
        "field": 2,
        # Reference labels plus the confirmed model-1 controller language.
        "states": {"chinese", "english", "spanish", "french", "russian", "italian", "german", "polish", "dutch"},
    },
    "device_time_scheme": {"field": 3, "states": {"12_hour", "24_hour"}},
    "output_relay_mode": {"field": 24, "states": {"b_01", "b_02"}},
    "brine_draw_mode": {"field": 48, "states": {"reverse", "forward"}},
}


def load_fields_module():
    path = HERE / "runxin" / "fields.py"
    spec = importlib.util.spec_from_file_location("_ypsilon_field_surface_fields", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load runxin/fields.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def expand_protocol_field(value: str) -> set[int]:
    """Expand '25' or range labels such as '35–36' into field ids."""
    value = value.strip()
    if value.isdigit():
        return {int(value)}
    match = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", value)
    if match:
        start, end = (int(part) for part in match.groups())
        return set(range(start, end + 1))
    raise ValueError(f"unsupported protocol_field label: {value!r}")


def entity_protocol_fields() -> set[int]:
    fields: set[int] = set()
    protocol_pattern = re.compile(r'protocol_field="([^"]+)"')
    field_id_pattern = re.compile(r"field_id=(\d+)")
    for filename in PLATFORM_FILES:
        text = (HERE / filename).read_text(encoding="utf-8")
        for label in protocol_pattern.findall(text):
            fields |= expand_protocol_field(label)
        fields |= {int(value) for value in field_id_pattern.findall(text)}
    return fields


def description_block(sensor_source: str, key: str) -> str:
    match = re.search(
        rf'YpsilonSensorDescription\((?:(?!YpsilonSensorDescription).)*?key="{re.escape(key)}"(?P<body>.*?)\n    \),',
        sensor_source,
        re.S,
    )
    if match is None:
        raise AssertionError(f"missing sensor description: {key}")
    return match.group(0)


def main() -> int:
    fields_mod = load_fields_module()
    known = {spec.id for spec in fields_mod.F79D_FIELD_SPECS}
    surfaced = entity_protocol_fields()
    accounted = surfaced | SEMANTICALLY_COMPOSED_FIELDS

    missing = sorted(known - accounted)
    unknown = sorted(accounted - known)
    errors: list[str] = []

    if missing:
        errors.append(f"readable F79D fields without HA surface policy: {missing}")
    if unknown:
        errors.append(f"HA protocol references unknown F79D fields: {unknown}")

    sensor_source = (HERE / "sensor.py").read_text(encoding="utf-8")
    for key, field_id in RAW_DIAGNOSTICS_DISABLED_BY_DEFAULT.items():
        block = description_block(sensor_source, key)
        if f'protocol_field="{field_id}"' not in block:
            errors.append(f"{key}: expected protocol field {field_id}")
        if "entity_registry_enabled_default=False" not in block:
            errors.append(f"{key}: diagnostic must be disabled by default")

    for key, policy in RECOVERED_ENUMS.items():
        block = description_block(sensor_source, key)
        if "SensorDeviceClass.ENUM" not in block:
            errors.append(f"{key}: recovered enum is not exposed as SensorDeviceClass.ENUM")
        if "value_map=" not in block:
            errors.append(f"{key}: recovered enum has no raw-code value map")
        for lang in ("en", "es", "ca"):
            translation = json.loads((HERE / "translations" / f"{lang}.json").read_text(encoding="utf-8"))
            entity = translation.get("entity", {}).get("sensor", {}).get(key, {})
            translated = set(entity.get("state", {}))
            if translated != policy["states"]:
                errors.append(
                    f"translations/{lang}.json {key}: states {sorted(translated)} != {sorted(policy['states'])}"
                )

    resin_block = description_block(sensor_source, "resin_regeneration_alarm_number")
    if 'protocol_field="25"' not in resin_block:
        errors.append("resin_regeneration_alarm_number: expected protocol field 25")
    if "entity_registry_enabled_default=False" in resin_block:
        errors.append("field 25 resin-maintenance threshold should be enabled by default")
    if "SensorDeviceClass.ENUM" in resin_block:
        errors.append("field 25 is a numeric threshold, not an enum")

    if errors:
        print("Field-surface audit failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print(
        "Field-surface audit OK: all F79D fields are accounted for and recovered "
        "enum diagnostics preserve semantic states and translations."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
