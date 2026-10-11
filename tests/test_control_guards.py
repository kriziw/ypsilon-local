"""Exercise real HA coordination with deterministic device I/O, never hardware."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock
from types import MappingProxyType

import pytest

pytest.importorskip("homeassistant", reason="Requires requirements-test-ha.txt")
from homeassistant import config_entries
from homeassistant.exceptions import ServiceValidationError

from .helpers import load
from .test_homeassistant import hass, _entity_context, _add_sensor

coordinator_mod = load("coordinator")
sensor_mod = load("sensor")
button_mod = load("button")
Coordinator = coordinator_mod.YpsilonDataUpdateCoordinator


def _coordinator(hass, model=9, *, data=None, options=None):
    entry = config_entries.ConfigEntry(
        domain="ypsilon_local", unique_id="02:00:00:00:00:09", title="Test softener",
        data=data or {}, options=options if options is not None else {"auto_sync_clock": False}, source=config_entries.SOURCE_USER,
        version=2, minor_version=1, discovery_keys=MappingProxyType({}), subentries_data=[],
    )
    client = Mock(read_state=AsyncMock(), read_identity=AsyncMock(), write_fields=AsyncMock(), close=AsyncMock(), revoke_writes=AsyncMock())
    coordinator = Coordinator(hass, entry, client, {})
    coordinator.data = {"deviceModel": model, "station": 0, "vacationPattern": False}
    coordinator.async_set_updated_data = Mock()
    return coordinator, client, entry


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [9, 12, 14])
async def test_regeneration_preserves_command_and_confirms_advanced_phase(hass, model):
    coordinator, client, entry = _coordinator(hass, model)
    coordinator.data["station"] = 1  # Cached state must not decide whether to send.
    coordinator._async_strict_read = AsyncMock(side_effect=[
        {"station": 0, "vacationPattern": False}, {"station": 2, "vacationPattern": False},
    ])
    await button_mod.YpsilonRegenerationButton(coordinator, entry).async_press()
    client.write_fields.assert_awaited_once_with({34: 1})
    assert coordinator._async_strict_read.await_count == 2
    assert coordinator.async_set_updated_data.call_args.args[0]["station"] == 2
    assert not coordinator._regeneration_requested


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [9, 12, 14])
@pytest.mark.parametrize("fresh", [
    {"station": 1, "vacationPattern": False},
    {"station": 5, "vacationPattern": False},
    {"station": 8, "vacationPattern": True},
    {"station": 0, "vacationPattern": True},
    {"station": 0}, {"vacationPattern": False}, {},
])
async def test_regeneration_rejects_busy_vacation_and_incomplete_fresh_state(hass, model, fresh):
    coordinator, client, _ = _coordinator(hass, model)
    coordinator._async_strict_read = AsyncMock(return_value=fresh)
    with pytest.raises(ServiceValidationError):
        await coordinator.async_start_regeneration()
    client.write_fields.assert_not_awaited()
    coordinator.async_set_updated_data.assert_called_once_with(fresh)
    assert not coordinator._regeneration_requested


@pytest.mark.asyncio
async def test_failed_precheck_does_not_write_or_fall_back_to_cached_service(hass):
    coordinator, client, _ = _coordinator(hass)
    coordinator._async_strict_read = AsyncMock(side_effect=coordinator_mod.YpsilonConnectionError("offline"))
    with pytest.raises(coordinator_mod.YpsilonConnectionError):
        await coordinator.async_start_regeneration()
    client.write_fields.assert_not_awaited()
    assert not coordinator._regeneration_requested
    coordinator._async_strict_read.side_effect = [{"station": 0, "vacationPattern": False}, {"station": 1}]
    await coordinator.async_start_regeneration()
    client.write_fields.assert_awaited_once_with({34: 1})


@pytest.mark.asyncio
async def test_overlapping_regeneration_is_rejected_without_a_second_write(hass):
    coordinator, client, _ = _coordinator(hass)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def read():
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await release.wait()
            return {"station": 0, "vacationPattern": False}
        return {"station": 1}

    coordinator._async_strict_read = read
    first = asyncio.create_task(coordinator.async_start_regeneration())
    try:
        await entered.wait()
        with pytest.raises(ServiceValidationError):
            await coordinator.async_start_regeneration()
    finally:
        release.set()
        await first
    client.write_fields.assert_awaited_once_with({34: 1})
    assert calls == 2
    assert not coordinator._regeneration_requested


@pytest.mark.asyncio
async def test_regeneration_precheck_waits_for_other_mutations(hass):
    coordinator, client, _ = _coordinator(hass)
    coordinator._async_strict_read = AsyncMock(return_value={"station": 1, "vacationPattern": False})
    async with coordinator._mutation_lock:
        task = asyncio.create_task(coordinator.async_start_regeneration())
        await asyncio.sleep(0)
        coordinator._async_strict_read.assert_not_awaited()
        client.write_fields.assert_not_awaited()
    with pytest.raises(ServiceValidationError):
        await task
    client.write_fields.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("ambiguous,active", [(True, True), (False, False)])
async def test_regeneration_reconciles_once_without_resending(hass, monkeypatch, ambiguous, active):
    coordinator, client, _ = _coordinator(hass)
    monkeypatch.setattr(coordinator_mod, "MECHANICAL_VERIFY_TIMEOUT", 0)
    if ambiguous:
        client.write_fields.side_effect = coordinator_mod.YpsilonConnectionError("lost ack")
    coordinator._async_strict_read = AsyncMock(side_effect=[
        {"station": 0, "vacationPattern": False}, {"station": 2 if active else 0},
    ])
    if active:
        await coordinator.async_start_regeneration()
    else:
        with pytest.raises(coordinator_mod.YpsilonWriteNotConfirmed):
            await coordinator.async_start_regeneration()
    client.write_fields.assert_awaited_once_with({34: 1})
    assert not coordinator._regeneration_requested


@pytest.mark.asyncio
async def test_explicit_phase_control_keeps_existing_policy(hass):
    coordinator, client, _ = _coordinator(hass)
    coordinator._async_strict_read = AsyncMock(return_value={"station": 3})
    await coordinator.async_write_and_verify({34: 3})
    client.write_fields.assert_awaited_once_with({34: 3})
    coordinator._async_strict_read.assert_awaited_once_with()


@pytest.mark.parametrize("actual,wanted,elapsed,expected", [
    ("10:20:00", "10:20:00", 0, True),
    ("10:21:00", "10:20:00", 0.01, True),
    ("00:00:00", "23:59:00", 5, True),
    ("10:21:00", "10:20:00", 60, True),
    ("10:21:00", "10:20:00", 60.01, False),
    ("10:21:00", "10:20:00", 0, False),
    ("10:21:00", "10:20:00", -1, False),
    ("10:22:00", "10:20:00", 5, False),
    ("10:19:00", "10:20:00", 5, False),
    ("23:59:00", "00:00:00", 5, False),
    (None, "10:20:00", 5, False),
    ("invalid", "10:20:00", 5, False),
    ("24:00:00", "23:59:00", 5, False),
    ("10:60:00", "10:59:00", 5, False),
    ("10:21:01", "10:20:00", 5, False),
])
def test_clock_confirmation_is_bounded_and_wraps_midnight(actual, wanted, elapsed, expected):
    assert Coordinator._clock_readback_matches(actual, wanted, elapsed, previous_clock=wanted) is expected


def test_tolerance_only_applies_to_ticking_clock_and_reports_real_mismatch():
    data = {"currentTime": "00:00:00", "regeneratingTriggerTime": "01:01:00", "saltAddition": 24}
    expected = {"currentTime": "23:59:00", "regeneratingTriggerTime": "01:00:00", "saltAddition": 24}
    assert not Coordinator._matches_expected(data, expected, accept_station_active=False, clock_elapsed=1, clock_before_write="23:59:00")
    mismatch = Coordinator._mismatch_text(data, expected, accept_station_active=False, clock_elapsed=1, clock_before_write="23:59:00")
    assert "regeneratingTriggerTime" in mismatch and "currentTime" not in mismatch
    data["regeneratingTriggerTime"] = "01:00:00"
    assert Coordinator._matches_expected(data, expected, accept_station_active=False, clock_elapsed=1, clock_before_write="23:59:00")
    data["saltAddition"] = 25
    assert not Coordinator._matches_expected(data, expected, accept_station_active=False, clock_elapsed=1, clock_before_write="23:59:00")


@pytest.mark.asyncio
@pytest.mark.parametrize("field,actual,success", [(4, "00:00:00", True), (10, "00:00:00", False)])
async def test_manual_clock_rollover_and_strict_schedule(hass, monkeypatch, field, actual, success):
    coordinator, client, _ = _coordinator(hass)
    monkeypatch.setattr(coordinator_mod, "WRITE_VERIFY_TIMEOUT", 0)
    name = "currentTime" if field == 4 else "regeneratingTriggerTime"
    coordinator._async_strict_read = AsyncMock(
        side_effect=[{"currentTime": "23:58:00"}, {name: actual}]
        if field == 4 else [{name: actual}]
    )
    if success:
        await coordinator.async_write_and_verify({field: (23, 59)})
    else:
        with pytest.raises(coordinator_mod.YpsilonWriteNotConfirmed):
            await coordinator.async_write_and_verify({field: (23, 59)})
    client.write_fields.assert_awaited_once_with({field: (23, 59)})


@pytest.mark.asyncio
async def test_auto_clock_samples_target_after_wait_and_confirms_rollover(hass, monkeypatch):
    coordinator, client, _ = _coordinator(hass)
    coordinator.auto_sync_clock = True
    monkeypatch.setattr(coordinator_mod.dt_util, "now", Mock(return_value=datetime(2026, 10, 5, 23, 58)))
    coordinator._async_strict_read = AsyncMock(side_effect=[
        {"currentTime": "22:00:00"}, {"currentTime": "00:00:00"},
    ])
    data = {"currentTime": "22:00:00"}
    async with coordinator._mutation_lock:
        task = asyncio.create_task(coordinator._async_sync_clock_if_needed(data))
        await asyncio.sleep(0)
        client.write_fields.assert_not_awaited()
        monkeypatch.setattr(coordinator_mod.dt_util, "now", Mock(return_value=datetime(2026, 10, 5, 23, 59)))
    await task
    client.write_fields.assert_awaited_once_with({4: (23, 59)})
    assert data["currentTime"] == "00:00:00"
    assert data["_clockSyncs"] == 1
    assert data["_clockDriftMinutes"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("key,field,raw,expected", [
    ("station", "station", 0, "in_service"),
    ("volume_unit", "waterVolumeUnit", 2, "cubic_meters"),
    ("regeneration_pattern", "regenerationPattern", 0, "flow"),
    ("work_pattern", "workPattern", 0, "downflow_meter_delayed"),
    ("output_relay_mode", "outRelayMode", 0, "b_01"),
    ("language_code", "language", 1, "english"),
    ("device_time_scheme", "deviceTimeScheme", 0, "12_hour"),
    ("brine_draw_mode", "absorbSaltMode", 0, "reverse"),
])
async def test_known_enum_keys_and_model_options_survive_unknown_readings(hass, key, field, raw, expected):
    from dataclasses import replace
    coordinator, entry = _entity_context(hass, {"deviceModel": 9, field: raw})
    desc = next(desc for desc in sensor_mod.SENSORS if desc.key == key)
    desc = replace(desc, entity_registry_enabled_default=True)
    sensor = sensor_mod.YpsilonSensor(coordinator, entry, desc)
    assert sensor.native_value == expected
    # Model 9/code 3 is Spanish, already present at code 2. Its effective
    # options omit French and the duplicate; the shared reference stays intact.
    expected_options = (
        [option for option in desc.options if option != "french"]
        if key == "language_code" else desc.options
    )
    assert sensor.options == expected_options
    state = await _add_sensor(hass, sensor, f"sensor.test_{key}")
    assert state.state == expected
    coordinator.data[field] = 253
    sensor.async_write_ha_state()
    assert hass.states.get(sensor.entity_id).state == "253"
    assert "253" in sensor.options
    assert "253" not in desc.options
    coordinator.data[field] = raw
    sensor.async_write_ha_state()
    assert hass.states.get(sensor.entity_id).state == expected
    assert sensor.options == expected_options
    # Device communication loss retains HA's normal unavailable semantics.
    coordinator.last_update_success = False
    sensor.async_write_ha_state()
    assert hass.states.get(sensor.entity_id).state == "unavailable"


@pytest.mark.parametrize("previous", [None, "invalid", "24:21:00", "10:21:01", "10:21:00"])
def test_clock_rollover_requires_valid_changed_prewrite_evidence(previous):
    assert not Coordinator._clock_readback_matches(
        "10:21:00", "10:20:00", 1, previous_clock=previous,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [9, 12, 14])
@pytest.mark.parametrize("ambiguous", [False, True])
@pytest.mark.parametrize("actual,confirmed", [("10:21:00", False), ("10:20:00", True)])
async def test_manual_clock_does_not_confirm_unchanged_next_minute(
    hass, monkeypatch, model, ambiguous, actual, confirmed,
):
    coordinator, client, _ = _coordinator(hass, model)
    coordinator.data["currentTime"] = "10:00:00"  # A cached baseline is insufficient.
    monkeypatch.setattr(coordinator_mod, "WRITE_VERIFY_TIMEOUT", 0)
    if ambiguous:
        client.write_fields.side_effect = coordinator_mod.YpsilonConnectionError("lost ack")
    coordinator._async_strict_read = AsyncMock(side_effect=[
        {"currentTime": "10:21:00"}, {"currentTime": actual},
    ])
    if confirmed:
        await coordinator.async_write_and_verify({4: (10, 20)})
    else:
        with pytest.raises(coordinator_mod.YpsilonWriteNotConfirmed, match="currentTime"):
            await coordinator.async_write_and_verify({4: (10, 20)})
    client.write_fields.assert_awaited_once_with({4: (10, 20)})
    assert coordinator._async_strict_read.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("ambiguous", [False, True])
async def test_auto_clock_does_not_count_an_unchanged_next_minute(hass, monkeypatch, ambiguous):
    coordinator, client, _ = _coordinator(hass)
    coordinator.auto_sync_clock = True
    coordinator.clock_tolerance = 0
    monkeypatch.setattr(coordinator_mod.dt_util, "now", Mock(return_value=datetime(2026, 10, 5, 10, 20)))
    if ambiguous:
        client.write_fields.side_effect = coordinator_mod.YpsilonConnectionError("lost ack")
    coordinator._async_strict_read = AsyncMock(side_effect=[
        {"currentTime": "10:21:00"}, {"currentTime": "10:21:00"},
    ])
    data = {"currentTime": "10:00:00"}
    await coordinator._async_sync_clock_if_needed(data)
    client.write_fields.assert_awaited_once_with({4: (10, 20)})
    assert data["_clockSyncs"] == 0
    assert coordinator._clock_syncs == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("automatic", [False, True])
async def test_clock_precheck_failure_sends_no_write(hass, monkeypatch, automatic):
    coordinator, client, _ = _coordinator(hass)
    coordinator._async_strict_read = AsyncMock(side_effect=coordinator_mod.YpsilonConnectionError("offline"))
    if automatic:
        coordinator.auto_sync_clock = True
        monkeypatch.setattr(coordinator_mod.dt_util, "now", Mock(return_value=datetime(2026, 10, 5, 10, 20)))
        await coordinator._async_sync_clock_if_needed({"currentTime": "10:00:00"})
        assert coordinator._clock_syncs == 0
    else:
        with pytest.raises(coordinator_mod.YpsilonConnectionError):
            await coordinator.async_write_and_verify({4: (10, 20)})
    client.write_fields.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("automatic", [False, True])
async def test_clock_window_includes_the_fresh_baseline_read(hass, monkeypatch, automatic):
    from types import SimpleNamespace
    coordinator, client, _ = _coordinator(hass)
    seconds = 0
    calls = 0
    monkeypatch.setattr(coordinator_mod, "time", SimpleNamespace(monotonic=lambda: seconds))
    monkeypatch.setattr(coordinator_mod, "WRITE_VERIFY_TIMEOUT", 0)
    monkeypatch.setattr(coordinator_mod.dt_util, "now", Mock(return_value=datetime(2026, 10, 5, 10, 20)))

    async def read():
        nonlocal seconds, calls
        calls += 1
        if calls == 1:
            # A delayed GET makes an ignored clock advance twice naturally.
            seconds = 61
            return {"currentTime": "10:19:00"}
        return {"currentTime": "10:21:00"}

    coordinator._async_strict_read = read
    if automatic:
        coordinator.auto_sync_clock = True
        await coordinator._async_sync_clock_if_needed({"currentTime": "10:00:00"})
        assert coordinator._clock_syncs == 0
    else:
        with pytest.raises(coordinator_mod.YpsilonWriteNotConfirmed):
            await coordinator.async_write_and_verify({4: (10, 20)})
    client.write_fields.assert_awaited_once_with({4: (10, 20)})
    assert calls == 2
