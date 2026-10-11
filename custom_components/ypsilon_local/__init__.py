"""The Ypsilon Local integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import format_mac

from .api import YpsilonLocalClient
from .const import DOMAIN
from .coordinator import YpsilonDataUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.TIME,
]

type YpsilonConfigEntry = ConfigEntry[YpsilonDataUpdateCoordinator]


@dataclass
class YpsilonStore:
    """State that should survive config-entry reloads."""

    client: YpsilonLocalClient
    field52_cache: dict[str, Any] = field(default_factory=dict)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration-wide services independently of config entries."""
    async_setup_services(hass)
    return True


async def _get_store(hass: HomeAssistant, entry: ConfigEntry) -> YpsilonStore:
    domain_store: dict[str, YpsilonStore] = hass.data.setdefault(DOMAIN, {})
    store = domain_store.get(entry.entry_id)
    host = entry.data[CONF_HOST]
    if store is None:
        store = YpsilonStore(client=YpsilonLocalClient(host))
        domain_store[entry.entry_id] = store
    elif store.client.host != host:
        await store.client.close()
        store.client = YpsilonLocalClient(host)
    return store


def _migrate_registry_identity(
    hass: HomeAssistant, entry: ConfigEntry, old_bases: set[str], new_base: str
) -> None:
    """Move entity/device registry identities to the MAC without losing history."""
    old_bases = old_bases - {new_base}
    if not old_bases:
        return

    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        old_base = next(
            (
                base
                for base in old_bases
                if entity_entry.unique_id == base
                or entity_entry.unique_id.startswith(f"{base}_")
            ),
            None,
        )
        if old_base is None:
            continue

        suffix = entity_entry.unique_id.removeprefix(old_base)
        new_unique_id = f"{new_base}{suffix}"
        existing = entity_registry.async_get_entity_id(
            entity_entry.domain, entity_entry.platform, new_unique_id
        )
        if existing is not None and existing != entity_entry.entity_id:
            _LOGGER.warning(
                "Cannot migrate entity %s to unique id %s: already used by %s",
                entity_entry.entity_id,
                new_unique_id,
                existing,
            )
            continue

        if existing is None:
            _LOGGER.debug(
                "Migrating entity unique id %s -> %s",
                entity_entry.unique_id,
                new_unique_id,
            )
            entity_registry.async_update_entity(
                entity_entry.entity_id, new_unique_id=new_unique_id
            )

    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        identifiers = set(device_entry.identifiers)
        matched = {
            (DOMAIN, base) for base in old_bases if (DOMAIN, base) in identifiers
        }
        if not matched:
            continue

        existing_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, new_base), entry.entry_id
        )
        if existing_device is not None and existing_device.id != device_entry.id:
            _LOGGER.warning(
                "Cannot migrate device %s to identifier %s: already used by %s",
                device_entry.id,
                new_base,
                existing_device.id,
            )
            continue

        identifiers.difference_update(matched)
        identifiers.add((DOMAIN, new_base))
        _LOGGER.debug(
            "Migrating device identifiers %s -> %s", matched, (DOMAIN, new_base)
        )
        device_registry.async_update_device(
            device_entry.id, new_identifiers=identifiers
        )


def _cleanup_legacy_entity_registry_entries(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove orphaned entities left by earlier platform moves or withdrawn controls."""
    registry = er.async_get(hass)
    legacy_suffixes: dict[str, tuple[str, ...]] = {
        "sensor": ("device_time", "device_clock", "current_time"),
        "time": ("wash_initiation_time", "wash_start_time", "wash_start"),
        # v2.6.0 briefly exposed vacationPattern as a writable switch. Real
        # hardware read-back showed that the local field-49 write is not a
        # verified action on the tested controller, so v2.6.1 removes the
        # control and cleans its registry entry while preserving read-only state.
        "switch": ("vacation_mode",),
    }

    for registry_entry in er.async_entries_for_config_entry(
        registry, entry.entry_id
    ):
        if registry_entry.platform != DOMAIN:
            continue
        suffixes = legacy_suffixes.get(registry_entry.domain)
        if not suffixes:
            continue
        if not any(
            registry_entry.unique_id == suffix
            or registry_entry.unique_id.endswith(f"_{suffix}")
            for suffix in suffixes
        ):
            continue
        _LOGGER.info("Removing legacy orphan entity %s", registry_entry.entity_id)
        registry.async_remove(registry_entry.entity_id)


def _enable_wash_start_sensor_if_integration_disabled(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Enable Wash start time after changing its default in v2.2.0."""
    registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(
        registry, entry.entry_id
    ):
        if (
            registry_entry.domain == "sensor"
            and registry_entry.platform == DOMAIN
            and (
                registry_entry.unique_id == "wash_initiation_time"
                or registry_entry.unique_id.endswith("_wash_initiation_time")
            )
            and registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        ):
            _LOGGER.info(
                "Enabling Wash start time entity %s after v2.2 default change",
                registry_entry.entity_id,
            )
            registry.async_update_entity(
                registry_entry.entity_id, disabled_by=None
            )


async def async_setup_entry(hass: HomeAssistant, entry: YpsilonConfigEntry) -> bool:
    """Set up Ypsilon Local from a config entry."""
    store = await _get_store(hass, entry)

    coordinator = YpsilonDataUpdateCoordinator(
        hass, entry, store.client, store.field52_cache
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _cleanup_legacy_entity_registry_entries(hass, entry)
    _enable_wash_start_sensor_if_integration_disabled(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: YpsilonConfigEntry) -> bool:
    """Unload a config entry, keeping the session and cache warm."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Close the session and drop the cache when the entry is deleted."""
    store: YpsilonStore | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if store is not None:
        await store.client.close()


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a v1 entry (host-keyed) to v2 (MAC-keyed)."""
    if entry.version >= 2:
        return True

    host = entry.data.get(CONF_HOST)
    if not host:
        return False

    client = YpsilonLocalClient(host)
    try:
        identity = await client.read_identity()
        mac = identity.get("mac") or client.mac
    except Exception as err:  # noqa: BLE001 - migration is retried later
        _LOGGER.warning(
            "Could not reach %s to migrate to a MAC-based unique id; will retry "
            "on the next restart (%s)",
            host,
            err,
        )
        return True
    finally:
        await client.close()

    if not mac:
        _LOGGER.warning("Device at %s reported no MAC; keeping v1 entry", host)
        return True

    formatted_mac = format_mac(mac)
    old_bases = {entry.entry_id}
    if entry.unique_id:
        old_bases.add(entry.unique_id)
    _migrate_registry_identity(hass, entry, old_bases, formatted_mac)
    hass.config_entries.async_update_entry(
        entry, unique_id=formatted_mac, version=2
    )
    _LOGGER.info("Migrated entry to v2 with unique id %s", formatted_mac)
    return True
