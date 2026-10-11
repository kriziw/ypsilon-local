"""Config flow for Ypsilon Local."""

from __future__ import annotations

import logging
import asyncio
import threading
from typing import Any
from uuid import uuid4

import broadlink.exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .api import YpsilonAuthenticationError, YpsilonConnectionError, YpsilonLocalClient
from .const import (
    CONF_ACTIVE_SCAN_INTERVAL,
    CONF_ADAPTIVE_POLLING,
    CONF_AUTO_SYNC_CLOCK,
    CONF_CLOCK_TOLERANCE,
    CONF_CONTROLLER_MODEL,
    CONF_MODEL1_TEST_WRITES,
    CONF_MODEL1_TEST_REGENERATION,
    CONF_DIAGNOSTIC_ONLY,
    CONF_DIAGNOSTIC_REPORT_ID,
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
from .models import controller_model, controller_protocol_name, is_supported_model
from .compatibility import probe
from .diagnostic_report import prepare_report, report_store

_LOGGER = logging.getLogger(__name__)


def _probe_error(err: Exception) -> str:
    """Classify a rejected handshake, without inferring its underlying cause."""
    if isinstance(
        err, (YpsilonAuthenticationError, broadlink.exceptions.AuthenticationError)
    ):
        if getattr(err, "is_locked", None) is True:
            return "device_locked"
        return "invalid_auth"
    return "cannot_connect"


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
        self._diagnostic_host: str | None = None
        self._diagnostic_model: object = None
        self._diagnostic_reason = "unsupported_device"
        self._diagnostic_report: dict[str, Any] | None = None
        self._diagnostic_task: asyncio.Task | None = None
        self._diagnostic_cancel = threading.Event()
        self._diagnostic_identifiers: list[str] = []
        self._alpha_host: str | None = None
        self._alpha_identity: dict[str, Any] = {}

    async def _async_controller_entry(
        self, host: str, identity: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        model = controller_model(identity.get("deviceModel"))
        if model is not None and (model.read_only or model.provisional_readings):
            self._alpha_host = host
            self._alpha_identity = identity
            return await self.async_step_readonly_alpha()
        return self.async_create_entry(title=_entry_title(identity), data={CONF_HOST: host})

    async def async_step_readonly_alpha(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Explain provisional readings and the scoped manual-clock permission."""
        if user_input is not None:
            return self.async_create_entry(
                title=_entry_title(self._alpha_identity),
                data={CONF_HOST: self._alpha_host,
                      CONF_CONTROLLER_MODEL: self._alpha_identity["deviceModel"]},
                options={CONF_AUTO_SYNC_CLOCK: False, CONF_ADAPTIVE_POLLING: False},
            )
        return self.async_show_form(step_id="readonly_alpha", data_schema=vol.Schema({}))

    @callback
    def async_remove(self) -> None:
        """Cancelling a flow stops its executor worker at the next boundary."""
        self._diagnostic_cancel.set()
        if self._diagnostic_task is not None and not self._diagnostic_task.done():
            self._diagnostic_task.cancel()
        super().async_remove()

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
            _LOGGER.debug("Starting local setup probe")
            identity = await client.read_identity()
            mac = identity.get("mac") or client.mac
            return identity, mac
        except PROBE_ERRORS as err:
            details = client.connection_diagnostics
            last_error = details.get("last_error") or {}
            devtype = details.get("devtype")
            _LOGGER.warning(
                "Local setup probe failed (result=%s, transport_stage=%s, "
                "error_type=%s, error_code=%s, devtype=%s, advertised_lock=%s). "
                "See the Ypsilon connection troubleshooting guide.",
                _probe_error(err), details.get("stage"),
                last_error.get("error_type", type(err).__name__),
                last_error.get("error_code"),
                f"0x{devtype:04x}" if isinstance(devtype, int) else None,
                details.get("advertised_lock"),
            )
            raise
        finally:
            await client.close()

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
        except PROBE_ERRORS as err:
            return await self._diagnostic_offer(self.discovered_host, _probe_error(err))
        if not is_supported_model(identity.get("deviceModel")):
            return await self._diagnostic_offer(self.discovered_host, "unsupported_device", identity)

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
            except PROBE_ERRORS as err:
                return await self._diagnostic_offer(self.discovered_host, _probe_error(err))
            else:
                if not is_supported_model(identity.get("deviceModel")):
                    return await self._diagnostic_offer(self.discovered_host, "unsupported_device", identity)
                return await self._async_controller_entry(self.discovered_host, identity)

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
            if user_input.get(CONF_DIAGNOSTIC_ONLY):
                self._diagnostic_host = host
                return await self.async_step_diagnostic_scan()
            try:
                identity, mac = await self._async_probe(host)
            except PROBE_ERRORS as err:
                return await self._diagnostic_offer(host, _probe_error(err))
            else:
                if not is_supported_model(identity.get("deviceModel")):
                    return await self._diagnostic_offer(host, "unsupported_device", identity)
                elif not mac:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(format_mac(mac))
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: host}, reload_on_update=True
                    )
                    return await self._async_controller_entry(host, identity)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_DIAGNOSTIC_ONLY, default=False): bool,
            }),
            errors=errors,
        )

    async def _diagnostic_offer(
        self, host: str, reason: str, identity: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        self._diagnostic_host = host
        self._diagnostic_model = (identity or {}).get("deviceModel")
        self._diagnostic_reason = reason
        return await self.async_step_diagnostic_offer()

    async def async_step_diagnostic_offer(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            if not user_input.get("generate_report"):
                return self.async_abort(reason="diagnostic_declined")
            return await self.async_step_diagnostic_scan()
        code = self._diagnostic_model
        name = controller_protocol_name(code)
        model = f"{name} ({code})" if name else str(code) if code is not None else "—"
        return self.async_show_form(
            step_id="diagnostic_offer",
            data_schema=vol.Schema({vol.Required("generate_report", default=True): bool}),
            description_placeholders={"controller": model},
            errors={"base": self._diagnostic_reason},
        )

    async def _async_collect_report(self) -> None:
        assert self._diagnostic_host is not None
        try:
            report = await probe(
                self._diagnostic_host,
                cancel=self._diagnostic_cancel,
                identifier_sink=self._diagnostic_identifiers,
            )
            self._diagnostic_report = await self.hass.async_add_executor_job(prepare_report, report)
        except asyncio.CancelledError:
            self._diagnostic_cancel.set()
            raise

    async def async_step_diagnostic_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        assert self._diagnostic_host is not None
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == self._diagnostic_host:
                return self.async_abort(reason="already_configured")
        for progress in self._async_in_progress():
            if (progress["flow_id"] != self.flow_id and
                progress.get("context", {}).get("diagnostic_host") == self._diagnostic_host):
                return self.async_abort(reason="diagnostic_in_progress")
        self.context["diagnostic_host"] = self._diagnostic_host
        if self._diagnostic_task is None:
            self._diagnostic_task = self.hass.async_create_task(
                self._async_collect_report(), "Runxin read-only compatibility report",
                eager_start=False,
            )
        if not self._diagnostic_task.done():
            return self.async_show_progress(
                step_id="diagnostic_scan", progress_action="collecting_report",
                progress_task=self._diagnostic_task,
            )
        try:
            self._diagnostic_task.result()
        except (Exception, asyncio.CancelledError):
            return self.async_abort(reason="diagnostic_failed")
        return self.async_show_progress_done(next_step_id="diagnostic_ready")

    async def async_step_diagnostic_ready(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        assert self._diagnostic_report is not None
        if user_input is not None:
            if self._diagnostic_identifiers:
                await self.async_set_unique_id(format_mac(self._diagnostic_identifiers[0]))
                self._abort_if_unique_id_configured()
            report_id = uuid4().hex
            await report_store(self.hass, report_id).async_save(self._diagnostic_report)
            controller = self._diagnostic_report.get("controller") or {}
            code = controller.get("code")
            name = controller.get("manufacturer_protocol_name")
            detail = f"{name} ({code})" if name else str(code) if code is not None else "Runxin"
            return self.async_create_entry(
                title=f"{detail} · Diagnostic",
                data={CONF_HOST: self._diagnostic_host, CONF_DIAGNOSTIC_ONLY: True,
                      CONF_DIAGNOSTIC_REPORT_ID: report_id},
            )
        report = self._diagnostic_report
        return self.async_show_form(
            step_id="diagnostic_ready", data_schema=vol.Schema({}),
            description_placeholders={
                "fields": str(report.get("summary", {}).get("fields_observed_count", 0)),
                "issue_url": report["issue_url"],
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Point an existing entry at a new IP without changing identity."""
        entry = self._get_reconfigure_entry()
        if entry.data.get(CONF_DIAGNOSTIC_ONLY):
            return self.async_abort(reason="diagnostic_only")
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                _, mac = await self._async_probe(host)
            except PROBE_ERRORS as err:
                errors["base"] = _probe_error(err)
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
        if self.config_entry.data.get(CONF_DIAGNOSTIC_ONLY):
            return self.async_abort(reason="diagnostic_only")
        runtime = getattr(self.config_entry, "runtime_data", None)
        observed = (getattr(runtime, "data", None) or {}).get("deviceModel")
        model = controller_model(self.config_entry.data.get(CONF_CONTROLLER_MODEL, observed))
        read_only = bool(model and model.read_only)
        model1 = bool(model and model.code == 1)
        if user_input is not None:
            if read_only or model1:
                user_input = {**user_input, CONF_AUTO_SYNC_CLOCK: False}
            if model1:
                # A separate mechanical opt-in cannot grant configuration writes.
                user_input = {
                    **user_input,
                    CONF_MODEL1_TEST_WRITES: user_input.get(CONF_MODEL1_TEST_WRITES) is True,
                    CONF_MODEL1_TEST_REGENERATION:
                        user_input.get(CONF_MODEL1_TEST_WRITES) is True
                        and user_input.get(CONF_MODEL1_TEST_REGENERATION) is True,
                }
            else:
                user_input = {key: value for key, value in user_input.items()
                              if key not in (CONF_MODEL1_TEST_WRITES, CONF_MODEL1_TEST_REGENERATION)}
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
        if read_only or model1:
            schema = vol.Schema({key: value for key, value in schema.schema.items()
                                 if key.schema not in (CONF_AUTO_SYNC_CLOCK, CONF_CLOCK_TOLERANCE)})
        if model1:
            schema = schema.extend({
                vol.Required(CONF_MODEL1_TEST_WRITES,
                             default=options.get(CONF_MODEL1_TEST_WRITES, False)): bool,
                vol.Required(CONF_MODEL1_TEST_REGENERATION,
                             default=options.get(CONF_MODEL1_TEST_REGENERATION, False)): bool,
            })
        return self.async_show_form(step_id="init", data_schema=schema)
