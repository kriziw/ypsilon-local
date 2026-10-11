"""Bounded, guarded read-only compatibility collection; no Home Assistant imports.

Derived from the standalone diagnostic prepared for issues #17/#22.
Normal polling and controls never use this collector. Framing, field definitions
and reference decoding reuse the existing protocol modules. All interpretations
remain hypotheses for unverified controllers, and resin volume stays unscaled.

The collector is asynchronous because `python-broadlink` 1.0 is. `cancel`
stays a `threading.Event` deliberately: it is only ever polled with
`is_set()`, which is safe from the event loop, and keeping the type avoids
changing how the config flow signals cancellation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
import asyncio
import logging
import platform
import threading
import time
from typing import Any

from .models import controller_protocol_name, is_supported_model
from .runxin.f79d import decode_tlvs
from .runxin.fields import F79D_FIELD_SPECS
from .runxin.framing import build_query_frame, validate_frame, inner_frame
from .runxin.semantics import (
    DEVICE_LANGUAGE_KEYS, DEVICE_TIME_SCHEME_KEYS, VOLUME_UNIT_KEYS,
    WORK_PATTERN_KEYS, SYSTEM_CLOSE_REASON_KEYS, OUTPUT_RELAY_MODE_KEYS,
    STATION_KEYS, REGENERATION_PATTERN_KEYS, BRINE_DRAW_MODE_KEYS,
)

_LOGGER = logging.getLogger(__name__)
SCRIPT_VERSION = "2.0.0"
EXPECTED_DEVTYPE = 0x520F
MAX_QUERIES = 80
FIELD_SPECS = {
    spec.id: {"codec": spec.read_codec.value, "name": spec.name,
              "unit_hint": spec.unit_hint, "notes": spec.notes}
    for spec in F79D_FIELD_SPECS
}
ENUM_LABELS = {
    2: DEVICE_LANGUAGE_KEYS, 3: DEVICE_TIME_SCHEME_KEYS, 8: VOLUME_UNIT_KEYS,
    9: WORK_PATTERN_KEYS, 12: SYSTEM_CLOSE_REASON_KEYS, 24: OUTPUT_RELAY_MODE_KEYS,
    34: STATION_KEYS, 46: REGENERATION_PATTERN_KEYS, 48: BRINE_DRAW_MODE_KEYS,
}

class ProbeError(Exception):
    """Errors carry only a fixed diagnostic reason and optional numeric code."""

    def __init__(self, reason: str, code: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.code = code


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def safe_error(err: Exception) -> dict[str, Any]:
    result: dict[str, Any] = {"error_type": type(err).__name__}
    code = getattr(err, "code", getattr(err, "errno", None))
    if isinstance(code, int):
        result["error_code"] = code
    if isinstance(err, ProbeError):
        result["reason"] = err.reason
    # Never serialize exception text, args, causes, device reprs or packets.
    return result


def frame_inner(frame: bytes) -> bytes:
    try:
        validate_frame(frame)
        inner = inner_frame(frame)
        if len(inner) < 6 or frame.find(b"\xdf\xfd", 17) + len(inner) != len(frame) - 2:
            raise ValueError("inner boundary")
    except Exception as err:
        raise ProbeError("invalid_runxin_frame") from err
    return inner


def build_read(fields: list[int]) -> bytes:
    if not fields or len(set(fields)) != len(fields):
        raise ProbeError("invalid_read_field_list")
    if any(type(field) is not int or not 1 <= field <= 52 for field in fields):
        raise ProbeError("read_field_out_of_scope")
    return build_query_frame(fields)


def guard_outbound(packet_type: int, payload: bytes) -> None:
    """Fail closed before sending any command outside this probe's scope."""
    if packet_type == 0x65 and len(payload) == 0x50:
        return  # The standard library authentication request.
    if packet_type == 0x6A and payload == b"\x68":
        return  # The standard library firmware query.
    if packet_type != 0x6A or len(payload) < 2:
        raise ProbeError("outbound_command_not_allowed")
    length = int.from_bytes(payload[:2], "little")
    if length != len(payload) - 2:
        raise ProbeError("outbound_length_not_allowed")
    inner = frame_inner(payload[2:])
    fields = list(inner[4:-2])
    if inner[3] != 0x09 or payload[2:] != build_read(fields):
        raise ProbeError("outbound_command_not_allowed")


def parse_read(frame: bytes) -> tuple[dict[int, tuple[int, int]], list[int]]:
    inner = frame_inner(frame)
    if inner[3] != 0xC9:
        raise ProbeError("unexpected_runxin_response_opcode")
    data = inner[4:-2]
    if len(data) % 3:
        raise ProbeError("invalid_runxin_field_payload_length")
    result: dict[int, tuple[int, int]] = {}
    duplicates = []
    for offset in range(0, len(data), 3):
        field = data[offset]
        pair = (data[offset + 1], data[offset + 2])
        if field in result:
            duplicates.append(field)
            if result[field] != pair:
                raise ProbeError("conflicting_duplicate_field")
        result[field] = pair
    return result, sorted(set(duplicates))


def describe_field(field: int, pair: tuple[int, int], tlvs: dict[int, tuple[int, int]]) -> dict[str, Any]:
    """Adapted reference decoder; keeps ambiguous encodings visible for research."""
    spec = FIELD_SPECS[field]
    first, second = pair
    codec = spec["codec"]
    decoded = decode_tlvs(tlvs)
    value = decoded.get(spec["name"])
    warnings: list[str] = []
    if codec == "reminder_flags":
        value = {"saltShortageReminder": bool(first), "filterMaterialReminder": bool(second)}
    if codec == "time_hm" and value is None:
        warnings.append("bytes_outside_reference_clock_range")
    if codec == "duration_min_sec" and second > 59:
        warnings.append("second_byte_outside_reference_seconds_range")
    if codec == "bool" and first not in (0, 1):
        warnings.append("noncanonical_boolean_byte")
    if codec == "reminder_flags" and (first not in (0, 1) or second not in (0, 1)):
        warnings.append("noncanonical_boolean_byte")
    if codec == "volume_pair" and (field + 1 not in tlvs or tlvs.get(8, (None, None))[0] not in (0, 1, 2)):
        warnings.append("unit_or_continuation_missing_in_same_response")
    if codec == "u8" and second:
        warnings.append("reference_u8_decoder_ignores_nonzero_second_byte")
    record: dict[str, Any] = {
        "field_id": field, "name": spec["name"], "reference_codec": codec,
        "raw_byte_pair": [first, second], "raw_hex": f"{first:02x} {second:02x}",
        "u16_le_candidate": first | second << 8,
        "u16_be_candidate": first << 8 | second,
        "reference_value": value,
    }
    if spec["unit_hint"]:
        record["reference_unit_hint"] = spec["unit_hint"]
    if field in ENUM_LABELS:
        record["reference_label"] = ENUM_LABELS[field].get(value)
        record["enum_code_is_mapped"] = value in ENUM_LABELS[field]
    unit = tlvs.get(8, (None, None))[0]
    if codec == "volume_pair":
        record["unit_code_same_response"] = unit
        record["reference_unit_hint"] = {0: "gal", 1: "L", 2: "m3"}.get(unit)
        record["continuation_same_response"] = list(tlvs[field + 1]) if field + 1 in tlvs else None
        record["reference_note"] = "Volume interpretation needs confirmation against the app."
    if field in (7, 11):
        record["unit_code_same_response"] = unit
        record["reference_unit_hint"] = {0: "gal/min", 1: "L/min", 2: "m3/h"}.get(unit)
        record["reference_display_candidate"] = value / 100 if unit in (0, 1, 2) else None
        record["reference_note"] = "BE and /100 are reference interpretations; compare app and raw bytes."
    if field == 26:
        record["reference_unit_hint"] = None
        record["reference_note"] = "Raw resin value only. No model multiplier or litre conversion applied."
    if spec["notes"]:
        record["catalogue_note"] = spec["notes"]
    if warnings:
        record["interpretation_warnings"] = warnings
    return record


class ReadSession:
    """Single standard auth session with bounded reads and an outbound guard."""

    def __init__(self, device: Any, timeout: float, deadline: float, cancel: threading.Event | None = None):
        self.device = device
        self.timeout = timeout
        self.deadline = deadline
        self.query_count = 0
        self.transient_retries = 0
        self.cancel = cancel
        original_send = device.send_packet

        # Still an instance-attribute override of send_packet, which 1.0 keeps
        # overridable - but the wrapper and the wrapped call are coroutines
        # now. device.count, device.devtype and device.mac are unchanged in
        # 1.0, so the header/counter/MAC validation below still applies.
        async def checked_send(packet_type: int, payload: bytes) -> bytes:
            if self.cancel is not None and self.cancel.is_set():
                raise ProbeError("cancelled")
            guard_outbound(packet_type, bytes(payload))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProbeError("time_budget_exhausted")
            device.timeout = min(timeout, remaining)
            response = bytes(await original_send(packet_type, payload))
            if len(response) < 0x38 or response[:8] != bytes.fromhex("5aa5aa555aa5aa55"):
                raise ProbeError("invalid_broadlink_header")
            nominal = int.from_bytes(response[0x20:0x22], "little")
            actual = (sum(response, 0xBEAF) - sum(response[0x20:0x22])) & 0xFFFF
            if nominal != actual:
                raise ProbeError("invalid_broadlink_packet_checksum")
            if int.from_bytes(response[0x28:0x2A], "little") != device.count:
                raise ProbeError("broadlink_counter_mismatch")
            if int.from_bytes(response[0x24:0x26], "little") != device.devtype:
                raise ProbeError("broadlink_device_type_mismatch")
            if response[0x2A:0x30] != bytes(device.mac)[::-1]:
                raise ProbeError("broadlink_mac_mismatch")
            return response

        device.send_packet = checked_send

    async def read(self, fields: list[int]) -> tuple[dict[int, tuple[int, int]], list[int]]:
        request = build_read(fields)
        for attempt in range(2):
            if self.query_count >= MAX_QUERIES:
                raise ProbeError("query_budget_exhausted")
            if time.monotonic() >= self.deadline:
                raise ProbeError("time_budget_exhausted")
            self.query_count += 1
            response = await self.device.send_packet(
                0x6A, len(request).to_bytes(2, "little") + request
            )
            code = int.from_bytes(response[0x22:0x24], "little", signed=True)
            if code == -5 and attempt == 0:
                self.transient_retries += 1
                await asyncio.sleep(min(0.3, max(0, self.deadline - time.monotonic())))
                continue
            if code:
                raise ProbeError("broadlink_query_rejected", code)
            encrypted = response[0x38:]
            if not encrypted or len(encrypted) % 16:
                raise ProbeError("invalid_broadlink_encrypted_body")
            plaintext = self.device.decrypt(encrypted)
            if len(plaintext) < 2:
                raise ProbeError("missing_tfb_length")
            declared = int.from_bytes(plaintext[:2], "little")
            if declared > len(plaintext) - 2:
                raise ProbeError("invalid_tfb_length")
            return parse_read(bytes(plaintext[2:2 + declared]))
        raise ProbeError("read_retry_budget_exhausted")


def with_dependencies(fields: list[int]) -> list[int]:
    """Collect units and both volume components in the same response."""
    result = set(fields)
    if result.intersection({7, 11, *range(35, 43)}):
        result.add(8)
    for base in (35, 37, 39, 41):
        if base in result or base + 1 in result:
            result.update((base, base + 1))
    return sorted(result)


async def scan_fields(session: Any, report: dict[str, Any]) -> None:
    observations = report["queries"]
    latest: dict[int, dict[str, Any]] = {}
    stopped = False

    async def query(fields: list[int], phase: str) -> None:
        nonlocal stopped
        if stopped:
            return
        started = utc_now()
        tick = time.monotonic()
        item: dict[str, Any] = {
            "query_id": len(observations) + 1, "phase": phase,
            "started_at_utc": started, "requested_fields": fields,
        }
        try:
            tlvs, duplicates = await session.read(fields)
            item.update(ok=True, returned_fields=sorted(tlvs),
                        missing_requested_fields=sorted(set(fields) - set(tlvs)))
            scoped = {field: pair for field, pair in tlvs.items() if 1 <= field <= 52}
            item["out_of_scope_field_ids"] = sorted(set(tlvs) - set(scoped))
            item["duplicate_field_ids"] = duplicates
            item["fields"] = [describe_field(f, scoped[f], scoped) for f in sorted(scoped)]
            for record in item["fields"]:
                latest[record["field_id"]] = {
                    **record, "query_id": item["query_id"], "observed_at_utc": started,
                }
        except KeyboardInterrupt:
            item.update(ok=False, error={"reason": "interrupted"})
            report["interrupted"] = True
            report["scan_stop_reason"] = "interrupted"
            stopped = True
        except Exception as err:
            item.update(ok=False, error=safe_error(err))
            if phase == "identity" or (isinstance(err, ProbeError) and (
                err.reason in ("time_budget_exhausted", "query_budget_exhausted", "cancelled")
                or err.code in (-1, -7)
            )):
                report["scan_stop_reason"] = err.reason if isinstance(err, ProbeError) else "identity_query_failed"
                stopped = True
        item["elapsed_ms"] = round((time.monotonic() - tick) * 1000, 2)
        observations.append(item)

    _LOGGER.debug("Reading controller identity...")
    await query([1, 34], "identity")
    if 1 not in latest:
        await query([1], "identity_single_field")
    if 34 not in latest:
        await query([34], "station_single_field")
    _LOGGER.debug("Reading fields 1-52...")
    await query(list(range(1, 53)), "full_read")
    missing = sorted(set(range(1, 53)) - set(latest))
    if missing and not stopped:
        _LOGGER.debug("Recovering missing fields in smaller read-only groups...")
        for start in range(0, len(missing), 8):
            fields = [f for f in missing[start:start + 8] if f not in latest]
            if fields:
                await query(with_dependencies(fields), "fallback_group")
    missing = sorted(set(range(1, 53)) - set(latest))
    if missing and not stopped:
        _LOGGER.debug("Trying remaining fields individually (with required unit/volume context)...")
        for field in missing:
            if field not in latest:
                await query(with_dependencies([field]), "fallback_single_field")
    report["fields"] = [latest[f] for f in sorted(latest)]
    codes = sorted({r["reference_value"] for q in observations for r in q.get("fields", [])
                    if r["field_id"] == 1})
    report["identity"] = {
        "device_model_present": 1 in latest,
        "device_model_code": latest.get(1, {}).get("reference_value"),
        "device_model_codes_observed": codes,
        "model_code_changed_during_scan": len(codes) > 1,
        "station_present": 34 in latest,
        "station_code": latest.get(34, {}).get("reference_value"),
    }
    report["summary"] = {
        "status": "complete" if len(latest) == 52 else "partial" if latest else "no_fields",
        "fields_observed_count": len(latest),
        "fields_not_returned": sorted(set(range(1, 53)) - set(latest)),
        "read_packet_calls": session.query_count,
        "transient_retries": session.transient_retries,
        "query_failures": sum(not q["ok"] for q in observations),
    }
    report["comparison"] = {
        "unit_codes_observed": sorted({r["reference_value"] for q in observations
                                       for r in q.get("fields", []) if r["field_id"] == 8}),
        "unmapped_enum_field_ids": sorted({r["field_id"] for q in observations
                                           for r in q.get("fields", [])
                                           if r.get("enum_code_is_mapped") is False}),
        "fields_with_interpretation_warnings": sorted({r["field_id"] for q in observations
                                                       for r in q.get("fields", [])
                                                       if r.get("interpretation_warnings")}),
    }


async def probe(host: str, *, timeout: float = 5, max_seconds: float = 180,
                cancel: threading.Event | None = None,
                identifier_sink: list[str] | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "script_version": SCRIPT_VERSION, "started_at_utc": utc_now(),
        "python_version": platform.python_version(), "timeout_seconds": timeout,
        "time_budget_seconds": max_seconds, "max_read_packet_calls": MAX_QUERIES,
        "read_only_scope": "discovery, standard auth, firmware, F79D query opcode 0x09; fields 1-52",
        "interpretation": "Reference F79D codec, not verified semantics for this controller. No per-model scaling.",
        "snapshot_note": "Latest successful observations; fields can originate from different queries/times.",
        "omitted": ["IP", "MAC", "device_name", "serial_numbers", "session_id", "keys", "raw_packets"],
        "discovery": {"ok": False}, "authentication": {"attempted": False},
        "firmware": {"attempted": False}, "queries": [], "fields": [],
        "summary": {"status": "not_started"},
    }
    device = None
    try:
        # The module is still imported as `broadlink`, but since core
        # 2026.10 the distribution providing it is `python-broadlink`. The
        # old `broadlink` distribution unpacks over the top of it, which is
        # what broke core's own BroadLink integration, so this gate now
        # requires the 1.x line rather than exactly 0.19.0.
        try:
            report["broadlink_version"] = version("python-broadlink")
        except PackageNotFoundError:
            raise ProbeError("python_broadlink_1_x_required") from None
        if report["broadlink_version"].split(".")[0] != "1":
            raise ProbeError("python_broadlink_1_x_required")
        import broadlink
        if cancel is not None and cancel.is_set():
            raise ProbeError("cancelled")
        deadline = time.monotonic() + max_seconds
        _LOGGER.debug("Discovering BroadLink device...")
        # 1.0 raises NetworkTimeoutError rather than returning None.
        try:
            device = await broadlink.hello(host, timeout=min(timeout, max_seconds))
        except broadlink.exceptions.NetworkTimeoutError:
            raise ProbeError("no_device_found") from None
        locked = getattr(device, "is_locked", None)
        report["discovery"] = {"ok": True, "devtype": f"0x{int(device.devtype):04x}",
                               "advertised_lock": locked if isinstance(locked, bool) else None}
        if device.devtype != EXPECTED_DEVTYPE:
            raise ProbeError("unexpected_broadlink_device_type")
        if identifier_sink is not None and isinstance(device.mac, (bytes, bytearray)) and len(device.mac) == 6:
            identifier_sink.append(bytes(device.mac).hex())
        session = ReadSession(device, timeout, deadline, cancel)
        report["authentication"] = {"attempted": True, "ok": False}
        _LOGGER.debug("Performing standard authentication...")
        try:
            if await device.auth() is False:
                raise ProbeError("authentication_rejected")
        except Exception as err:
            report["authentication"].update(error=safe_error(err))
            report["summary"]["status"] = "authentication_failed"
            return report
        report["authentication"]["ok"] = True
        report["firmware"] = {"attempted": True, "ok": False}
        try:
            report["firmware"].update(ok=True, version=int(await device.get_fwversion()))
        except Exception as err:
            report["firmware"]["error"] = safe_error(err)
        await scan_fields(session, report)
    except KeyboardInterrupt:
        report["interrupted"] = True
        report["summary"]["status"] = "interrupted"
    except Exception as err:
        report["fatal_error"] = safe_error(err)
        report["summary"]["status"] = "cancelled" if isinstance(err, ProbeError) and err.reason == "cancelled" else "failed"
    finally:
        report["finished_at_utc"] = utc_now()
        # 1.0 owns the endpoint; aclose() replaces closing a `sock`.
        if device is not None:
            try:
                await device.aclose()
            except Exception:  # noqa: BLE001 - teardown must not mask the report
                pass
    code = report.get("identity", {}).get("device_model_code")
    report["controller"] = {
        "code": code, "manufacturer_protocol_name": controller_protocol_name(code),
        "supported_for_normal_use": is_supported_model(code),
        "name_source": "WaterDevice DeviceProtocolModel enumeration, checked 2026-10-07; descriptive only",
    }
    return report

