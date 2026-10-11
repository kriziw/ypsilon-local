"""Data coordinator for Ypsilon Local."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    YpsilonConnectionError,
    YpsilonLocalClient,
    YpsilonWriteNotConfirmed,
)
from .const import (
    ACTIVE_LINGER_SECONDS,
    ALERT_FIELDS,
    CLOCK_SYNC_RETRY_SECONDS,
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
    FIELD_CURRENT_TIME,
    FIELD_SYSTEM_MODE,
    MAX_TOLERATED_FAILURES,
    MECHANICAL_VERIFY_INTERVAL,
    MECHANICAL_VERIFY_TIMEOUT,
    WRITE_VERIFY_INTERVAL,
    WRITE_VERIFY_TIMEOUT,
)
from .protocol import BOOL_FIELDS, CLOCK_FIELDS, FIELD_NAMES
from .runxin.semantics import vacation_status

_LOGGER = logging.getLogger(__name__)


class YpsilonDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the softener and reconcile every write with a strict read-back."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: YpsilonLocalClient,
        field52_cache: dict[str, Any],
    ) -> None:
        self.client = client
        self._field52_cache = field52_cache
        options = entry.options
        self.scan_interval = int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self.active_scan_interval = int(
            options.get(CONF_ACTIVE_SCAN_INTERVAL, DEFAULT_ACTIVE_SCAN_INTERVAL)
        )
        self.adaptive_polling = bool(
            options.get(CONF_ADAPTIVE_POLLING, DEFAULT_ADAPTIVE_POLLING)
        )
        self.active_scan_interval = min(self.active_scan_interval, self.scan_interval)

        self._consecutive_failures = 0
        self._failed_polls = 0
        self.auto_sync_clock = bool(
            options.get(CONF_AUTO_SYNC_CLOCK, DEFAULT_AUTO_SYNC_CLOCK)
        )
        self.clock_tolerance = int(
            options.get(CONF_CLOCK_TOLERANCE, DEFAULT_CLOCK_TOLERANCE)
        )

        self._active_until = 0.0
        self._is_active = False
        self._last_clock_sync_attempt: float | None = None
        self._clock_syncs = 0
        self._mutation_lock = asyncio.Lock()

        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.scan_interval),
            always_update=True,
        )

    @staticmethod
    def _decorate_semantics(data: dict[str, Any]) -> None:
        # Field 49 is still authoritative read-back state. The v2.6.1 HA layer
        # intentionally exposes it read-only because the tested G6 ACKed a
        # direct local field-49 control frame without changing physical state.
        data["_vacationStatus"] = vacation_status(
            data.get("vacationPattern"), data.get("station")
        )

    def _device_is_busy(self, data: dict[str, Any]) -> bool:
        """Return true while real flow or a moving regeneration phase is active."""
        if data.get("_raw_flowRate"):
            return True

        station = data.get("station")
        # The legacy WaterDevice UI treats vacation mode as settled at station 8.
        # This remains useful read-only semantics even though local vacation
        # writes are not exposed on the tested hardware.
        if data.get("vacationPattern") and station == 8:
            return False
        return station not in (None, 0, 5)

    def _apply_interval(self, data: dict[str, Any]) -> None:
        if not self.adaptive_polling:
            return

        now = time.monotonic()
        if self._device_is_busy(data):
            self._active_until = now + ACTIVE_LINGER_SECONDS

        should_be_active = now < self._active_until
        if should_be_active == self._is_active:
            return

        self._is_active = should_be_active
        seconds = self.active_scan_interval if should_be_active else self.scan_interval
        self.update_interval = timedelta(seconds=seconds)
        _LOGGER.debug(
            "Switching to %s polling (%ss)",
            "active" if should_be_active else "idle",
            seconds,
        )

    @staticmethod
    def _annotate_alerts(data: dict[str, Any]) -> None:
        active = [key for field, key in ALERT_FIELDS if data.get(field)]
        data["_activeAlerts"] = active
        data["_activeAlertCount"] = len(active)

    @staticmethod
    def _clock_drift(device_clock: str | None) -> int | None:
        if not device_clock:
            return None
        try:
            hour, minute = (int(part) for part in str(device_clock).split(":")[:2])
        except (ValueError, TypeError):
            return None
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None

        now = dt_util.now()
        drift = (hour * 60 + minute) - (now.hour * 60 + now.minute)
        if drift > 720:
            drift -= 1440
        elif drift < -720:
            drift += 1440
        return drift

    @staticmethod
    def _data_age_seconds(data: dict[str, Any]) -> float | None:
        last_success = data.get("_lastSuccessfulUpdate")
        if last_success is None:
            return None
        try:
            return max(0.0, (dt_util.utcnow() - last_success).total_seconds())
        except (TypeError, AttributeError):
            return None

    async def _async_sync_clock_if_needed(self, data: dict[str, Any]) -> None:
        drift = self._clock_drift(data.get("currentTime"))
        data["_clockDriftMinutes"] = drift
        data["_clockSyncs"] = self._clock_syncs
        if drift is None or not self.auto_sync_clock or abs(drift) <= self.clock_tolerance:
            return

        now = time.monotonic()
        if (
            self._last_clock_sync_attempt is not None
            and now - self._last_clock_sync_attempt < CLOCK_SYNC_RETRY_SECONDS
        ):
            return
        self._last_clock_sync_attempt = now

        local = dt_util.now()
        expected_time = f"{local.hour:02d}:{local.minute:02d}:00"
        _LOGGER.info(
            "Valve clock is %+d min out (device %s, local %02d:%02d); correcting",
            drift,
            data.get("currentTime"),
            local.hour,
            local.minute,
        )

        async with self._mutation_lock:
            write_error: YpsilonConnectionError | None = None
            try:
                await self.client.write_fields(
                    {FIELD_CURRENT_TIME: (local.hour, local.minute)},
                )
            except YpsilonConnectionError as err:
                write_error = err

            try:
                confirmed = await self._async_strict_read()
            except YpsilonConnectionError as err:
                _LOGGER.warning("Could not confirm valve clock correction: %s", err)
                return

            if confirmed.get("currentTime") != expected_time:
                if write_error is not None:
                    _LOGGER.warning(
                        "Valve clock write had an ambiguous transport result and read-back did not confirm it: %s",
                        write_error,
                    )
                else:
                    _LOGGER.warning(
                        "Valve clock correction was ACKed but not confirmed (expected %s, got %s)",
                        expected_time,
                        confirmed.get("currentTime"),
                    )
                return

        self._clock_syncs += 1
        confirmed["_clockSyncs"] = self._clock_syncs
        confirmed["_clockDriftMinutes"] = 0
        data.clear()
        data.update(confirmed)

    def _decorate_successful_read(
        self, data: dict[str, Any], started: float
    ) -> dict[str, Any]:
        self._consecutive_failures = 0
        self._decorate_semantics(data)
        self._apply_interval(data)
        data.update(
            _lastSuccessfulUpdate=dt_util.utcnow(),
            _pollDurationMs=round((time.perf_counter() - started) * 1000, 1),
            _scanIntervalSeconds=int(self.update_interval.total_seconds()),
            _pollingMode="active" if self._is_active else "idle",
            _lastPollSuccessful=True,
            _lastPollError=None,
            _consecutiveFailures=0,
            _failedPolls=self._failed_polls,
            _clockDriftMinutes=self._clock_drift(data.get("currentTime")),
            _clockSyncs=self._clock_syncs,
            _stale=False,
            _dataAgeSeconds=0.0,
        )
        self._annotate_alerts(data)
        return data

    async def _async_strict_read(self) -> dict[str, Any]:
        started = time.perf_counter()
        data = await self.client.read_state(self._field52_cache)
        return self._decorate_successful_read(data, started)

    async def _async_update_data(self) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            data = await self.client.read_state(self._field52_cache)
        except YpsilonConnectionError as err:
            self._failed_polls += 1
            self._consecutive_failures += 1
            if self.data and self._consecutive_failures <= MAX_TOLERATED_FAILURES:
                stale = dict(self.data)
                stale.update(
                    _lastPollSuccessful=False,
                    _lastPollError=str(err),
                    _consecutiveFailures=self._consecutive_failures,
                    _failedPolls=self._failed_polls,
                    _transientRetries=self.client.transient_retries,
                    _reauthCount=self.client.reauth_count,
                    _pollDurationMs=round((time.perf_counter() - started) * 1000, 1),
                    _clockSyncs=self._clock_syncs,
                    _stale=True,
                    _dataAgeSeconds=self._data_age_seconds(stale),
                )
                return stale
            raise UpdateFailed(f"Connection error: {err}") from err

        data = self._decorate_successful_read(data, started)
        await self._async_sync_clock_if_needed(data)
        return data

    @staticmethod
    def _expected_readback(values: dict[int, Any]) -> dict[str, Any]:
        expected: dict[str, Any] = {}
        for field, value in values.items():
            name = FIELD_NAMES.get(field)
            if name is None:
                raise ValueError(f"No read-back mapping for field {field}")
            if field in CLOCK_FIELDS:
                hour, minute = value
                expected[name] = f"{int(hour):02d}:{int(minute):02d}:00"
            elif field in BOOL_FIELDS:
                expected[name] = bool(value)
            else:
                expected[name] = int(value)
        return expected

    @staticmethod
    def _matches_expected(
        data: dict[str, Any],
        expected: dict[str, Any],
        *,
        accept_station_active: bool,
    ) -> bool:
        for field_name, wanted in expected.items():
            actual = data.get(field_name)
            if field_name == "station" and accept_station_active:
                if actual in (None, 0, 5):
                    return False
                continue
            if actual != wanted:
                return False
        return True

    @staticmethod
    def _mismatch_text(
        data: dict[str, Any], expected: dict[str, Any], *, accept_station_active: bool
    ) -> str:
        parts: list[str] = []
        for field_name, wanted in expected.items():
            actual = data.get(field_name)
            if field_name == "station" and accept_station_active:
                if actual in (None, 0, 5):
                    parts.append(f"station active (got {actual!r})")
            elif actual != wanted:
                parts.append(f"{field_name}: expected {wanted!r}, got {actual!r}")
        return "; ".join(parts) or "read-back did not match"

    async def async_write_and_verify(
        self,
        values: dict[int, Any],
        *,
        accept_station_active: bool = False,
    ) -> None:
        """Write once, then reconcile the controller through strict read-back."""
        expected = self._expected_readback(values)

        async with self._mutation_lock:
            write_error: YpsilonConnectionError | None = None
            try:
                await self.client.write_fields(values)
            except YpsilonConnectionError as err:
                write_error = err
                _LOGGER.warning(
                    "Write transport result was ambiguous; reconciling physical state without resending: %s",
                    err,
                )

            self._active_until = time.monotonic() + ACTIVE_LINGER_SECONDS
            mechanical = FIELD_SYSTEM_MODE in values
            timeout = MECHANICAL_VERIFY_TIMEOUT if mechanical else WRITE_VERIFY_TIMEOUT
            interval = MECHANICAL_VERIFY_INTERVAL if mechanical else WRITE_VERIFY_INTERVAL
            deadline = time.monotonic() + timeout
            last_data: dict[str, Any] | None = None
            last_error: YpsilonConnectionError | None = None

            while True:
                try:
                    last_data = await self._async_strict_read()
                    last_error = None
                except YpsilonConnectionError as err:
                    last_error = err
                else:
                    if self._matches_expected(
                        last_data,
                        expected,
                        accept_station_active=accept_station_active,
                    ):
                        self.async_set_updated_data(last_data)
                        return
                    self.async_set_updated_data(last_data)

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    if last_data is not None:
                        mismatch = self._mismatch_text(
                            last_data,
                            expected,
                            accept_station_active=accept_station_active,
                        )
                    elif last_error is not None:
                        mismatch = f"confirmation reads failed: {last_error}"
                    else:
                        mismatch = "no confirmation data"

                    if write_error is not None:
                        raise YpsilonWriteNotConfirmed(
                            "Write delivery was ambiguous and physical state was "
                            f"not confirmed within {timeout:.0f}s ({mismatch})"
                        ) from write_error
                    raise YpsilonWriteNotConfirmed(
                        f"Write ACKed but not confirmed within {timeout:.0f}s ({mismatch})"
                    ) from last_error
                await asyncio.sleep(min(interval, remaining))
