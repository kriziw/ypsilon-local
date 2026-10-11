"""Data coordinator for Ypsilon Local."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
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
    CONF_CONTROLLER_MODEL,
    CONF_MODEL1_TEST_WRITES,
    CONF_MODEL1_TEST_REGENERATION,
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
from .models import allowed_write_fields, controller_model

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
        self._configured_model = entry.data.get(CONF_CONTROLLER_MODEL)
        self._read_only_latched = False
        self._field52_cache = field52_cache
        options = entry.options
        self.model1_test_writes = options.get(CONF_MODEL1_TEST_WRITES) is True
        self.model1_test_regeneration = (
            self.model1_test_writes and options.get(CONF_MODEL1_TEST_REGENERATION) is True
        )
        self._model1_seen = self._configured_model == 1
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
        self._regeneration_requested = False

        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.scan_interval),
            always_update=True,
        )

    @property
    def read_only(self) -> bool:
        for code in (self._configured_model, (self.data or {}).get("deviceModel")):
            self._model1_seen |= code == 1
            model = controller_model(code)
            if model is not None and not self._policy_fields(code):
                self._read_only_latched = True
        return self._read_only_latched

    def _policy_fields(self, code: object) -> frozenset[int]:
        fields = allowed_write_fields(
            code, model1_test_writes=self.model1_test_writes,
            model1_test_regeneration=self.model1_test_regeneration,
        )
        if self._model1_seen:
            fields &= allowed_write_fields(
                1, model1_test_writes=self.model1_test_writes,
                model1_test_regeneration=self.model1_test_regeneration,
            )
        configured = controller_model(self._configured_model)
        if configured is not None:
            fields &= allowed_write_fields(
                configured.code, model1_test_writes=self.model1_test_writes,
                model1_test_regeneration=self.model1_test_regeneration,
            )
        return fields

    @property
    def allowed_write_fields(self) -> frozenset[int]:
        if self.read_only:
            return frozenset()
        return self._policy_fields((self.data or {}).get("deviceModel"))

    @property
    def automatic_clock_allowed(self) -> bool:
        fields = self.allowed_write_fields
        return not self._model1_seen and FIELD_CURRENT_TIME in fields

    def _observe_write_policy(self, data: dict[str, Any]) -> None:
        code = data.get("deviceModel")
        self._model1_seen |= code == 1
        if controller_model(code) is not None and not self._policy_fields(code):
            self._read_only_latched = True

    def _require_write_permission(
        self, fields: dict[int, Any], observed: dict[str, Any] | None = None,
        *, regeneration_start: bool = False,
    ) -> None:
        code = (observed or {}).get("deviceModel", (self.data or {}).get("deviceModel"))
        self._observe_write_policy({"deviceModel": code})
        if (
            self.read_only or controller_model(code) is None
            or not set(fields).issubset(self._policy_fields(code))
            or (self._model1_seen and FIELD_SYSTEM_MODE in fields
                and (not regeneration_start or fields != {FIELD_SYSTEM_MODE: 1}))
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="model_write_not_allowed"
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
        code = data.get("deviceModel", (self.data or {}).get("deviceModel"))
        self._observe_write_policy({"deviceModel": code})
        if (
            self.read_only or self._model1_seen or FIELD_CURRENT_TIME not in self._policy_fields(code)
            or drift is None or not self.auto_sync_clock or abs(drift) <= self.clock_tolerance
        ):
            return

        now = time.monotonic()
        if (
            self._last_clock_sync_attempt is not None
            and now - self._last_clock_sync_attempt < CLOCK_SYNC_RETRY_SECONDS
        ):
            return
        self._last_clock_sync_attempt = now

        async with self._mutation_lock:
            clock_check_started = time.monotonic()
            try:
                before_write = await self._async_strict_read()
            except YpsilonConnectionError as err:
                _LOGGER.warning("Could not read valve clock before correction: %s", err)
                return
            # Sample the clock after waiting for other writes, not before.
            try:
                self._require_write_permission({FIELD_CURRENT_TIME: (0, 0)}, before_write)
            except ServiceValidationError:
                return
            if self._model1_seen:
                return
            local = dt_util.now()
            expected_time = f"{local.hour:02d}:{local.minute:02d}:00"
            _LOGGER.info("Valve clock is %+d min out; correcting", drift)
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

            if not self._clock_readback_matches(
                confirmed.get("currentTime"),
                expected_time,
                time.monotonic() - clock_check_started,
                previous_clock=before_write.get("currentTime"),
            ):
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
        confirmed["_clockDriftMinutes"] = self._clock_drift(confirmed.get("currentTime"))
        data.clear()
        data.update(confirmed)

    def _decorate_successful_read(
        self, data: dict[str, Any], started: float
    ) -> dict[str, Any]:
        self._consecutive_failures = 0
        self._observe_write_policy(data)
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
    def _clock_readback_matches(
        actual: Any, wanted: str, elapsed: float, *, previous_clock: Any = None
    ) -> bool:
        """Allow one ticking minute during a read/write window of at most 60s.

        The wire clock has no seconds, so even a short read can cross a minute
        boundary. Require a fresh pre-write clock different from the next-minute
        value, so an ignored write cannot confirm an unchanged clock. This
        tolerance is for currentTime only, never a schedule.
        """
        if actual == wanted:
            return True
        if not 0 < elapsed <= 60:
            return False
        try:
            actual_h, actual_m, actual_s = (int(part) for part in actual.split(":"))
            wanted_h, wanted_m, wanted_s = (int(part) for part in wanted.split(":"))
            previous_h, previous_m, previous_s = (
                int(part) for part in previous_clock.split(":")
            )
        except (AttributeError, TypeError, ValueError):
            return False
        if not (
            0 <= actual_h < 24
            and 0 <= actual_m < 60
            and actual_s == 0
            and 0 <= wanted_h < 24
            and 0 <= wanted_m < 60
            and wanted_s == 0
            and 0 <= previous_h < 24
            and 0 <= previous_m < 60
            and previous_s == 0
        ):
            return False
        actual_minutes = actual_h * 60 + actual_m
        return (
            (actual_minutes - (wanted_h * 60 + wanted_m)) % 1440 == 1
            and actual_minutes != previous_h * 60 + previous_m
        )

    @staticmethod
    def _matches_expected(
        data: dict[str, Any],
        expected: dict[str, Any],
        *,
        accept_station_active: bool,
        clock_elapsed: float = 0,
        clock_before_write: Any = None,
    ) -> bool:
        for field_name, wanted in expected.items():
            actual = data.get(field_name)
            if field_name == "currentTime":
                if not YpsilonDataUpdateCoordinator._clock_readback_matches(
                    actual, wanted, clock_elapsed, previous_clock=clock_before_write
                ):
                    return False
                continue
            if field_name == "station" and accept_station_active:
                if actual in (None, 0, 5):
                    return False
                continue
            if actual != wanted:
                return False
        return True

    @staticmethod
    def _mismatch_text(
        data: dict[str, Any],
        expected: dict[str, Any],
        *,
        accept_station_active: bool,
        clock_elapsed: float = 0,
        clock_before_write: Any = None,
    ) -> str:
        parts: list[str] = []
        for field_name, wanted in expected.items():
            actual = data.get(field_name)
            if (
                field_name == "currentTime"
                and YpsilonDataUpdateCoordinator._clock_readback_matches(
                    actual, wanted, clock_elapsed, previous_clock=clock_before_write
                )
            ):
                continue
            if field_name == "station" and accept_station_active:
                if actual in (None, 0, 5):
                    parts.append(f"station active (got {actual!r})")
            elif actual != wanted:
                parts.append(f"{field_name}: expected {wanted!r}, got {actual!r}")
        return "; ".join(parts) or "read-back did not match"

    async def async_start_regeneration(self) -> None:
        """Start once from freshly verified service state, without overlapping requests."""
        if self._regeneration_requested:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="regeneration_busy"
            )
        self._regeneration_requested = True
        try:
            await self.async_write_and_verify(
                {FIELD_SYSTEM_MODE: 1},
                accept_station_active=True,
                require_in_service=True,
            )
        finally:
            self._regeneration_requested = False

    async def async_write_and_verify(
        self,
        values: dict[int, Any],
        *,
        accept_station_active: bool = False,
        require_in_service: bool = False,
    ) -> None:
        """Write once, then reconcile the controller through strict read-back."""
        regeneration_start = (
            values == {FIELD_SYSTEM_MODE: 1} and require_in_service and accept_station_active
        )
        self._require_write_permission(values, regeneration_start=regeneration_start)
        expected = self._expected_readback(values)

        async with self._mutation_lock:
            self._require_write_permission(values, regeneration_start=regeneration_start)
            # Include the baseline GET in the clock window: an ignored write
            # must not look applied merely because two natural minutes passed.
            clock_check_started = time.monotonic()
            clock_before_write: Any = None
            if require_in_service or "currentTime" in expected:
                fresh = await self._async_strict_read()
                self.async_set_updated_data(fresh)
                self._require_write_permission(values, fresh, regeneration_start=regeneration_start)
                clock_before_write = fresh.get("currentTime")
                if require_in_service and (
                    fresh.get("station") != 0
                    or fresh.get("vacationPattern") is not False
                ):
                    raise ServiceValidationError(
                        translation_domain=DOMAIN, translation_key="regeneration_not_ready"
                    )

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
                        clock_elapsed=time.monotonic() - clock_check_started,
                        clock_before_write=clock_before_write,
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
                            clock_elapsed=time.monotonic() - clock_check_started,
                            clock_before_write=clock_before_write,
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
