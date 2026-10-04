"""Config flow for Ypsilon Local."""

from __future__ import annotations

from typing import Any

import broadlink.exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .api import YpsilonConnectionError, YpsilonLocalClient
from .const import (
    CONF_ACTIVE_SCAN_INTERVAL,
    CONF_ADAPTIVE_POLLING,
    CONF_AUTO_SYNC_CLOCK,
    CONF_CLOCK_TOLERANCE,
    CONF_SCAN_INTERVAL,
    DEFAULT_ACTIVE_SCAN_INTERVAL,
    DEFAULT_ADAPTIVE_POLLING,
    DEFAULT_AUTO_SYNC_CLOCK,
    DEFAULT_CLOCK_TOLERANCE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_CLOCK_TOLERANCE,
    MAX_SCAN_INTERVAL,
    MIN_ACTIVE_SCAN_INTERVAL,
    MIN_CLOCK_TOLERANCE,
    MIN_SCAN_INTERVAL,
)
from .models import controller_model, is_supported_model


def _entry_title(identity: dict[str, Any]) -> str:
    model = controller_model(identity.get("deviceModel"))
    return model.title if model is not None else "Ypsilon"


PROBE_ERRORS = (
    broadlink.exceptions.BroadlinkException,
    OSError,
    TimeoutError,
    YpsilonConnectionError,
)


class YpsilonLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self.discovered_host: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return YpsilonLocalOptionsFlow()

    async def _async_probe(self, host: str) -> tuple[dict[str, Any], str | None]:
        """Probe a temporary client and always release its BroadLink socket."""
        client = YpsilonLocalClient(host)
        try:
            identity = await self.hass.async_add_executor_job(client.read_identity)
            mac = identity.get("mac") or client.mac
            return identity, mac
        finally:
            await self.hass.async_add_executor_job(client.close)

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        mac = format_mac(discovery_info.macaddress)
        self.discovered_host = discovery_info.ip
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self.discovered_host}, reload_on_update=True
        )

        try:
            identity, _ = await self._async_probe(self.discovered_host)
        except PROBE_ERRORS:
            return self.async_abort(reason="cannot_connect")
        if not is_supported_model(identity.get("deviceModel")):
            return self.async_abort(reason="unsupported_device")

        self.context["title_placeholders"] = {"host": self.discovered_host}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            assert self.discovered_host is not None
            try:
                identity, _ = await self._async_probe(self.discovered_host)
            except PROBE_ERRORS:
                errors["base"] = "cannot_connect"
            else:
                if not is_supported_model(identity.get("deviceModel")):
                    return self.async_abort(reason="unsupported_device")
                return self.async_create_entry(
                    title=_entry_title(identity), data={CONF_HOST: self.discovered_host}
                )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": self.discovered_host or ""},
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                identity, mac = await self._async_probe(host)
            except PROBE_ERRORS:
                errors["base"] = "cannot_connect"
            else:
                if not is_supported_model(identity.get("deviceModel")):
                    errors["base"] = "unsupported_device"
                elif not mac:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(format_mac(mac))
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: host}, reload_on_update=True
                    )
                    return self.async_create_entry(
                        title=_entry_title(identity), data={CONF_HOST: host}
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Point an existing entry at a new IP without changing identity."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                _, mac = await self._async_probe(host)
            except PROBE_ERRORS:
                errors["base"] = "cannot_connect"
            else:
                if mac and entry.unique_id:
                    await self.async_set_unique_id(format_mac(mac))
                    self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}
            ),
            errors=errors,
        )


class YpsilonLocalOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
                vol.Required(
                    CONF_ADAPTIVE_POLLING,
                    default=options.get(
                        CONF_ADAPTIVE_POLLING, DEFAULT_ADAPTIVE_POLLING
                    ),
                ): bool,
                vol.Required(
                    CONF_ACTIVE_SCAN_INTERVAL,
                    default=options.get(
                        CONF_ACTIVE_SCAN_INTERVAL, DEFAULT_ACTIVE_SCAN_INTERVAL
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_ACTIVE_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
                vol.Required(
                    CONF_AUTO_SYNC_CLOCK,
                    default=options.get(
                        CONF_AUTO_SYNC_CLOCK, DEFAULT_AUTO_SYNC_CLOCK
                    ),
                ): bool,
                vol.Required(
                    CONF_CLOCK_TOLERANCE,
                    default=options.get(
                        CONF_CLOCK_TOLERANCE, DEFAULT_CLOCK_TOLERANCE
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_CLOCK_TOLERANCE, max=MAX_CLOCK_TOLERANCE),
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
