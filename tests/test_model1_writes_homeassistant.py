"""Real HA regressions for manual F150 write tests; all device I/O is mocked."""
from types import SimpleNamespace
from datetime import datetime, time
from unittest.mock import AsyncMock, Mock, call

import pytest
pytest.importorskip("homeassistant", reason="Requires requirements-test-ha.txt")
from homeassistant import config_entries
from homeassistant.exceptions import ServiceValidationError
from .helpers import load
from .test_homeassistant import hass
from .test_control_guards import _coordinator
from .test_model1 import reported_state

coordinator_mod = load("coordinator")
init_mod = load("__init__")
flow_mod = load("config_flow")
sensor_mod = load("sensor")
diagnostics_mod = load("diagnostics")


def context(hass, *, writes=True, regen=False):
    coordinator, client, entry = _coordinator(hass, 1, data={"controller_model": 1, "host": "192.0.2.1"}, options={
        "auto_sync_clock": True,  # An old or injected option must never send a model-1 write.
        "model1_test_writes": writes, "model1_test_regeneration": regen,
    })
    coordinator.data = reported_state()
    entry.runtime_data = coordinator
    return coordinator, client, entry


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value,key,expected", [
    (4, (20, 39), "currentTime", "20:39:00"), (6, 51, "continuousWaterTime", 51),
    (10, (1, 0), "regeneratingTriggerTime", "01:00:00"),
    (43, 26, "saltAddition", 26), (47, 290, "rawWaterHardness", 290),
])
async def test_manual_setting_sends_once_and_requires_fresh_readback(hass, field, value, key, expected):
    coordinator, client, entry = context(hass)
    confirmed = {**reported_state(), key: expected}
    coordinator._async_strict_read = AsyncMock(side_effect=
        [reported_state(), confirmed] if field == 4 else [confirmed])
    await coordinator.async_write_and_verify({field: value})
    client.write_fields.assert_awaited_once_with({field: value})
    assert coordinator.async_set_updated_data.call_args.args[0][key] == expected


@pytest.mark.asyncio
async def test_default_clock_entities_write_and_restore_without_experimental_settings(hass, monkeypatch):
    coordinator, client, entry = context(hass, writes=False)
    entities = []
    for platform in ("time", "button"):
        await load(platform).async_setup_entry(hass, entry, lambda group: entities.extend(group))
    clock, sync = entities
    assert coordinator.allowed_write_fields == {4}
    clock.async_write_ha_state = Mock()
    changed = {**reported_state(), "currentTime": "20:39:00"}
    coordinator._async_strict_read = AsyncMock(side_effect=[reported_state(), changed])
    await clock.async_set_value(time(20, 39))
    client.write_fields.assert_awaited_once_with({4: (20, 39)})
    assert coordinator.async_set_updated_data.call_args.args[0]["currentTime"] == "20:39:00"
    assert clock._pending_value is None
    client.write_fields.reset_mock()
    monkeypatch.setattr(load("button").dt_util, "now", Mock(return_value=datetime(2026, 10, 10, 20, 38)))
    coordinator._async_strict_read = AsyncMock(side_effect=[changed, reported_state()])
    await sync.async_press()
    client.write_fields.assert_awaited_once_with({4: (20, 38)})
    assert coordinator.async_set_updated_data.call_args.args[0]["currentTime"] == "20:38:00"
    assert not coordinator.automatic_clock_allowed


@pytest.mark.asyncio
async def test_default_clock_permission_rejects_ignored_ack_and_mixed_pending_settings(hass, monkeypatch):
    coordinator, client, entry = context(hass, writes=False)
    coordinator._async_strict_read = AsyncMock(return_value=reported_state())
    with pytest.raises(ServiceValidationError):
        await coordinator.async_write_and_verify({4: (20, 39), 43: 26})
    client.write_fields.assert_not_awaited()
    coordinator._async_strict_read.assert_not_awaited()
    monkeypatch.setattr(coordinator_mod, "WRITE_VERIFY_TIMEOUT", 0)
    with pytest.raises(coordinator_mod.YpsilonWriteNotConfirmed):
        await coordinator.async_write_and_verify({4: (20, 39)})
    client.write_fields.assert_awaited_once_with({4: (20, 39)})


@pytest.mark.asyncio
@pytest.mark.parametrize("regen", [False, True])
async def test_poll_and_first_refresh_never_correct_model1_clock(hass, regen):
    coordinator, client, entry = context(hass, regen=regen)
    coordinator.data = None
    client.read_state.return_value = {**reported_state(), "currentTime": "00:00:00"}
    for _ in range(2):
        result = await coordinator._async_update_data()
        assert result["_clockSyncs"] == 0
    client.write_fields.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("regen", [False, True])
async def test_test_controls_preserve_reference_sensors_and_exclude_flow_cutoff(hass, regen):
    coordinator, client, entry = context(hass, regen=regen)
    entities = []
    for platform in ("number", "time", "button"):
        await load(platform).async_setup_entry(hass, entry, lambda group: entities.extend(group))
    fields = {e.entity_description.field_id for e in entities if hasattr(e, "entity_description")}
    assert fields == {4, 6, 10, 43, 47}
    assert any(isinstance(e, load("button").YpsilonSyncClockButton) for e in entities)
    assert any(isinstance(e, load("button").YpsilonRegenerationButton) for e in entities) is regen
    references = []
    await sensor_mod.async_setup_entry(hass, entry, lambda group: references.extend(group))
    assert {e.entity_description.key for e in references} >= {"reference_clock", "reference_hardness"}
    for sensor in references:
        assert sensor.state_class is None
        assert sensor.extra_state_attributes["read_only"] is False
    assert len({e.unique_id for e in (*entities, *references)}) == len(entities) + len(references)
    client.write_fields.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [9, 12, 14])
async def test_other_models_have_no_test_options_and_keep_existing_clock_permission(hass, model):
    coordinator, client, entry = _coordinator(hass, model)
    entry.runtime_data = coordinator
    hass.config_entries._entries[entry.entry_id] = entry
    flow = flow_mod.YpsilonLocalOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    flow.flow_id = "other-model-options"
    flow.context = {"entry_id": entry.entry_id}
    form = await flow.async_step_init()
    keys = {key.schema for key in form["data_schema"].schema}
    assert "model1_test_writes" not in keys
    assert "model1_test_regeneration" not in keys
    assert "auto_sync_clock" in keys
    result = await flow.async_step_init({"model1_test_writes": True,
        "model1_test_regeneration": True, "auto_sync_clock": True})
    assert result["data"] == {"auto_sync_clock": True}
    assert coordinator.allowed_write_fields == {4, 6, 7, 10, 34, 43, 47}


@pytest.mark.asyncio
async def test_mechanical_opt_in_still_requires_service_state_and_cannot_advance_phase(hass):
    coordinator, client, entry = context(hass, regen=True)
    for value in (0, 1, 2, 3, 4):
        with pytest.raises(ServiceValidationError):
            await coordinator.async_write_and_verify({34: value})
    coordinator._async_strict_read = AsyncMock(return_value={**reported_state(), "station": 2})
    with pytest.raises(ServiceValidationError):
        await coordinator.async_start_regeneration()
    client.write_fields.assert_not_awaited()
    coordinator._async_strict_read = AsyncMock(side_effect=[reported_state(), {**reported_state(), "station": 2}])
    await coordinator.async_start_regeneration()
    client.write_fields.assert_awaited_once_with({34: 1})


@pytest.mark.asyncio
async def test_model1_options_are_explicit_and_clock_is_forced_off(hass):
    coordinator, client, entry = context(hass, writes=False)
    hass.config_entries._entries[entry.entry_id] = entry
    flow = flow_mod.YpsilonLocalOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    flow.flow_id = "model1-write-options"
    flow.context = {"entry_id": entry.entry_id}
    form = await flow.async_step_init()
    keys = {key.schema for key in form["data_schema"].schema}
    assert {"model1_test_writes", "model1_test_regeneration"} <= keys
    assert "auto_sync_clock" not in keys
    result = await flow.async_step_init({"model1_test_writes": True,
        "model1_test_regeneration": True, "auto_sync_clock": True})
    assert result["data"]["auto_sync_clock"] is False
    assert result["data"]["model1_test_regeneration"] is True
    result = await flow.async_step_init({"model1_test_writes": False, "model1_test_regeneration": True})
    assert result["data"]["model1_test_regeneration"] is False


@pytest.mark.asyncio
async def test_disabling_tests_replaces_and_revokes_old_session_without_losing_cache(hass, monkeypatch):
    coordinator, client, entry = context(hass)
    created = []
    def create(host, **kwargs):
        client = Mock(host=host)
        created.append((client, kwargs))
        return client
    monkeypatch.setattr(init_mod, "YpsilonLocalClient", create)
    store = await init_mod._get_store(hass, entry)
    store.field52_cache["value"] = 42
    assert created[0][1] == {"model1_test_writes": True, "model1_test_regeneration": False}
    old = store.client
    hass.config_entries._entries[entry.entry_id] = entry
    hass.config_entries.async_update_entry(entry, options={"model1_test_writes": False})
    updated = await init_mod._get_store(hass, entry)
    assert updated is store
    assert updated.field52_cache["value"] == 42
    assert updated.client is not old
    assert old.method_calls == [call.revoke_writes(), call.close()]
    replacement = coordinator_mod.YpsilonDataUpdateCoordinator(hass, entry, updated.client, updated.field52_cache)
    replacement.data = reported_state()
    assert replacement.allowed_write_fields == {4}
    assert not replacement.automatic_clock_allowed
    with pytest.raises(ServiceValidationError):
        await replacement.async_write_and_verify({43: 26})
    updated.client.write_fields.assert_not_awaited()


@pytest.mark.asyncio
async def test_diagnostics_distinguish_opted_permissions_from_per_field_evidence(hass):
    coordinator, client, entry = context(hass)
    client.write_policy = {"controller_model": 1, "read_only": False,
                           "allowed_write_fields": [4, 6, 10, 43, 47]}
    client.firmware = 62016
    client.connection_diagnostics = {"stage": "ready"}
    client.reauth_count = client.transient_retries = 0
    result = await diagnostics_mod.async_get_config_entry_diagnostics(hass, entry)
    assert result["write_policy"]["allowed_write_fields"] == [4, 6, 10, 43, 47]
    assert not result["write_policy"]["read_only"]
    assert not result["write_policy"]["auto_clock_sync_permitted"]
    assert result["protocol"]["model_support"]["hardware_verified_write_fields"] == [4]
    assert result["protocol"]["model_support"]["pending_write_fields"] == [6, 10, 34, 43, 47]
    assert not result["protocol"]["model_support"]["experimental_writes_verified"]
    assert result["state"]["_rawFieldBytes"][26] == [240, 0]
    assert not client.method_calls


@pytest.mark.asyncio
async def test_enabled_test_write_cannot_confirm_an_ignored_ack(hass, monkeypatch):
    coordinator, client, entry = context(hass)
    coordinator._async_strict_read = AsyncMock(return_value=reported_state())
    monkeypatch.setattr(coordinator_mod, "WRITE_VERIFY_TIMEOUT", 0)
    with pytest.raises(coordinator_mod.YpsilonWriteNotConfirmed):
        await coordinator.async_write_and_verify({43: 26})
    client.write_fields.assert_awaited_once_with({43: 26})


@pytest.mark.asyncio
async def test_fresh_model1_identity_stops_automatic_clock_even_with_manual_opt_in(hass, monkeypatch):
    coordinator, client, entry = _coordinator(hass, 9, options={
        "auto_sync_clock": True, "model1_test_writes": True,
    })
    coordinator._async_strict_read = AsyncMock(return_value=reported_state())
    monkeypatch.setattr(coordinator_mod.dt_util, "now", Mock(return_value=datetime(2026, 10, 8, 12, 0)))
    await coordinator._async_sync_clock_if_needed({"deviceModel": 9, "currentTime": "00:00:00"})
    coordinator._async_strict_read.assert_awaited_once()
    client.write_fields.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_services_cannot_bypass_flow_or_mechanical_test_policy(hass, monkeypatch):
    coordinator, client, entry = context(hass, regen=True)
    coordinator.data["waterVolumeUnit"] = 2  # Even this calibrated unit does not grant model-1 field 7.
    services = load("services")
    loaded = SimpleNamespace(domain="ypsilon_local", state=config_entries.ConfigEntryState.LOADED,
                             data={}, runtime_data=coordinator)
    monkeypatch.setattr(hass.config_entries, "async_get_entry", Mock(return_value=loaded))
    services.async_setup_services(hass)
    for name, data in [("write_fields", {"fields": {7: 100}}), ("advance_phase", {"phase": 1})]:
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call("ypsilon_local", name,
                {"config_entry_id": "test", **data}, blocking=True)
    client.write_fields.assert_not_awaited()
