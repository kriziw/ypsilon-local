"""Physical language observations, with real HA enum state validation."""
from dataclasses import replace

import pytest

pytest.importorskip("homeassistant", reason="Requires requirements-test-ha.txt")
from .helpers import load
from .test_homeassistant import hass, _entity_context, _add_sensor, TEST_MAC

sensor_mod = load("sensor")


@pytest.mark.asyncio
@pytest.mark.parametrize("model,raw,expected", [
    (1, 7, "dutch"), (1, 3, "french"),
    (9, 3, "spanish"), (9, 7, "polish"), (9, 2, "spanish"),
    (12, 3, "french"), (12, 7, "polish"),
    (14, 3, "french"), (14, 7, "polish"),
    (1, 255, "255"), (9, 255, "255"),
])
async def test_language_labels_and_unknown_codes_are_valid_ha_states(hass, model, raw, expected):
    coordinator, entry = _entity_context(hass, {"deviceModel": model, "language": raw})
    description = next(d for d in sensor_mod.SENSORS if d.key == "language_code")
    assert not description.entity_registry_enabled_default
    sensor = sensor_mod.YpsilonSensor(coordinator, entry, replace(
        description, entity_registry_enabled_default=True,
    ))
    assert sensor.unique_id == f"{TEST_MAC}_language_code"
    assert sensor.native_value == expected
    assert expected in sensor.options
    assert len(sensor.options) == len(set(sensor.options))
    assert description.options == list(sensor_mod.DEVICE_LANGUAGE_KEYS.values())
    state = await _add_sensor(hass, sensor, "sensor.test_device_language")
    assert state.state == expected
    assert state.attributes["raw_code"] == raw
    assert state.attributes["controller_model"] == model
    assert state.attributes["interpretation"] == (
        "controller_display_confirmed" if (model, raw) in ((1, 7), (9, 3))
        else "reference_device_language_enum"
    )
    assert expected in state.attributes["options"]

    # An unknown reading stays visible; absent readings become unknown without
    # removing confirmed per-model enum options or mutating shared descriptions.
    coordinator.data["language"] = 254
    sensor.async_write_ha_state()
    state = hass.states.get(sensor.entity_id)
    assert state.state == "254"
    assert state.attributes["raw_code"] == 254
    assert "254" in state.attributes["options"]
    coordinator.data.pop("language")
    sensor.async_write_ha_state()
    state = hass.states.get(sensor.entity_id)
    assert state.state == "unknown"
    assert "raw_code" not in state.attributes
    assert "254" not in state.attributes["options"]
    assert ("dutch" in state.attributes["options"]) == (model == 1)


@pytest.mark.asyncio
async def test_language_options_follow_model_identity_without_cross_entity_leaks(hass):
    coordinator, entry = _entity_context(hass, {"deviceModel": 1, "language": 7})
    description = next(d for d in sensor_mod.SENSORS if d.key == "language_code")
    sensor = sensor_mod.YpsilonSensor(coordinator, entry, description)
    assert sensor.native_value == "dutch"
    assert "polish" not in sensor.options
    coordinator.data.update(deviceModel=14)
    assert sensor.native_value == "polish"
    assert "dutch" not in sensor.options
    coordinator.data.update(deviceModel=9, language=3)
    assert sensor.native_value == "spanish"
    assert "french" not in sensor.options
    entry.data = {"controller_model": 1}
    coordinator.data = {"language": 7}
    assert sensor.native_value == "dutch"
    assert sensor.extra_state_attributes["raw_code"] == 7
