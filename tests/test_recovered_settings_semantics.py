"""Regression tests for settings recovered from the legacy WaterDevice UI."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "custom_components" / "ypsilon_local"
PKG = "_ypsilon_recovered_settings_test"


def _load(module: str):
    if PKG not in sys.modules:
        root = types.ModuleType(PKG)
        root.__path__ = [str(HERE)]
        sys.modules[PKG] = root
    runxin_pkg = f"{PKG}.runxin"
    if runxin_pkg not in sys.modules:
        pkg = types.ModuleType(runxin_pkg)
        pkg.__path__ = [str(HERE / "runxin")]
        sys.modules[runxin_pkg] = pkg
    full = f"{runxin_pkg}.{module}"
    spec = importlib.util.spec_from_file_location(full, HERE / "runxin" / f"{module}.py")
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[full] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def _sensor_block(key: str) -> str:
    source = (HERE / "sensor.py").read_text(encoding="utf-8")
    match = re.search(
        rf'YpsilonSensorDescription\((?:(?!YpsilonSensorDescription).)*?key="{re.escape(key)}"(?P<body>.*?)\n    \),',
        source,
        re.S,
    )
    assert match, key
    return match.group(0)


def test_recovered_enum_maps_are_exact() -> None:
    s = _load("semantics")
    assert s.DEVICE_LANGUAGE_KEYS == {
        0: "chinese", 1: "english", 2: "spanish", 3: "french",
        4: "russian", 5: "italian", 6: "german", 7: "polish",
    }
    assert s.DEVICE_TIME_SCHEME_KEYS == {0: "12_hour", 1: "24_hour"}
    assert s.OUTPUT_RELAY_MODE_KEYS == {0: "b_01", 1: "b_02"}
    assert s.BRINE_DRAW_MODE_KEYS == {0: "reverse", 1: "forward"}


def test_recovered_enum_fields_are_ha_enums() -> None:
    for key, field in {
        "language_code": 2,
        "device_time_scheme": 3,
        "output_relay_mode": 24,
        "brine_draw_mode": 48,
    }.items():
        block = _sensor_block(key)
        assert f'protocol_field="{field}"' in block
        assert "SensorDeviceClass.ENUM" in block
        assert "value_map=" in block
        assert "entity_registry_enabled_default=False" in block


def test_confirmed_language_pairs_do_not_replace_other_model_reference_labels() -> None:
    s = _load("semantics")
    assert s.device_language_keys(1)[7] == "dutch"
    assert s.device_language_keys(1)[3] == "french"
    assert s.device_language_keys(9)[3] == "spanish"
    assert s.device_language_keys(9)[7] == "polish"
    for model in (12, 14, None, 99, True):
        assert s.device_language_keys(model) == s.DEVICE_LANGUAGE_KEYS
    # Callers cannot contaminate the reference table or subsequent entities.
    keys = s.device_language_keys(1)
    keys[3] = "dutch"
    assert s.device_language_keys(1)[3] == "french"
    assert s.DEVICE_LANGUAGE_KEYS[7] == "polish"


def test_numeric_recovered_fields_stay_numeric() -> None:
    for key, field in {
        "washing_increase_number": 13,
        "backwash_interval_number": 14,
        "resin_regeneration_alarm_number": 25,
    }.items():
        block = _sensor_block(key)
        assert f'protocol_field="{field}"' in block
        assert "SensorDeviceClass.ENUM" not in block
    assert "entity_registry_enabled_default=False" not in _sensor_block(
        "resin_regeneration_alarm_number"
    )


def test_recovered_waterdevice_ranges() -> None:
    numbers = (HERE / "number.py").read_text(encoding="utf-8")
    const = (HERE / "const.py").read_text(encoding="utf-8")
    continuous = re.search(
        r'key="continuous_water_time".*?native_max_value=([0-9.]+)', numbers, re.S
    )
    cutoff = re.search(
        r'key="flow_rate_off".*?native_max_value=([0-9.]+)', numbers, re.S
    )
    assert continuous and float(continuous.group(1)) == 120
    assert cutoff and float(cutoff.group(1)) == 10.0
    assert "FIELD_CONTINUOUS_WATER_TIME: (0, 120)" in const
    assert "FIELD_FLOW_RATE_OFF: (0, 1000)" in const


def test_all_enum_states_are_translated_in_all_languages() -> None:
    expected = {
        "language_code": {
            "chinese", "english", "spanish", "french",
            "russian", "italian", "german", "polish",
            "dutch",
        },
        "device_time_scheme": {"12_hour", "24_hour"},
        "output_relay_mode": {"b_01", "b_02"},
        "brine_draw_mode": {"reverse", "forward"},
    }
    for lang in ("en", "es", "ca"):
        data = json.loads((HERE / "translations" / f"{lang}.json").read_text(encoding="utf-8"))
        sensors = data["entity"]["sensor"]
        for key, states in expected.items():
            assert set(sensors[key]["state"]) == states, (lang, key)
