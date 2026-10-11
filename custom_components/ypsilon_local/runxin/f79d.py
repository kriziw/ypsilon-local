"""Runxin F79D field codec built on the transport-neutral frame layer."""

from __future__ import annotations

from typing import Any

from .errors import F79DProtocolError
from .fields import F79D_FIELDS_BY_ID, F79D_FIELD_SPECS, F79D_READ_CODEC_OVERRIDES, FieldCodec
from .framing import (
    QUERY_CODE,
    WRITE_CODE,
    build_control_frame,
    build_query_frame,
    extract_tlvs,
    inner_frame,
    validate_frame,
)

DEVICE_MODEL = 9
# Field 52 intentionally remains outside the normal state block. The Ypsilon
# integration refreshes it separately because it is a slow-changing service
# interval; keeping that policy outside this reusable protocol layer avoids
# coupling F79DClient to Home Assistant polling decisions.
STATE_FIELDS = list(range(1, 52))

FIELD_NAMES = {spec.id: spec.name for spec in F79D_FIELD_SPECS}
CLOCK_FIELDS = {spec.id for spec in F79D_FIELD_SPECS if spec.read_codec is FieldCodec.TIME_HM}
DURATION_FIELDS = {spec.id for spec in F79D_FIELD_SPECS if spec.read_codec is FieldCodec.DURATION_MIN_SEC}
LE16_FIELDS = {spec.id for spec in F79D_FIELD_SPECS if spec.read_codec is FieldCodec.U16_LE}
BE16_FIELDS = {spec.id for spec in F79D_FIELD_SPECS if spec.read_codec is FieldCodec.U16_BE}
HUNDREDTHS_FIELDS = {7, 11}
BOOL_FIELDS = {spec.id for spec in F79D_FIELD_SPECS if spec.read_codec is FieldCodec.BOOL}
VOLUME_FIELDS = {
    spec.id: spec.name for spec in F79D_FIELD_SPECS if spec.read_codec is FieldCodec.VOLUME_PAIR
}

WRITE_SIMPLE = {spec.id for spec in F79D_FIELD_SPECS if spec.write_codec is FieldCodec.U8}
WRITE_U16 = {spec.id for spec in F79D_FIELD_SPECS if spec.write_codec is FieldCodec.U16_LE}
WRITE_U16_BE = {spec.id for spec in F79D_FIELD_SPECS if spec.write_codec is FieldCodec.U16_BE}
WRITE_CLOCK = {spec.id for spec in F79D_FIELD_SPECS if spec.write_codec is FieldCodec.TIME_HM}
WRITE_DURATION = {
    spec.id for spec in F79D_FIELD_SPECS if spec.write_codec is FieldCodec.DURATION_MIN_SEC
}
WRITE_TIME = WRITE_CLOCK | WRITE_DURATION


def build_query(fields: list[int]) -> bytes:
    """Build a read-only F79D query frame for the requested field ids."""
    return build_query_frame(fields)


def build_write(field: int, low: int, high: int = 0) -> bytes:
    """Build a one-field F79D control frame from already encoded wire bytes."""
    if not 0 <= field <= 0xFF or not 0 <= low <= 0xFF or not 0 <= high <= 0xFF:
        raise ValueError("values must fit in one byte")
    return build_control_frame([field, low, high])


def _pair(value: Any, field: int, label: str) -> tuple[int, int]:
    """Coerce a two-component semantic value and raise a field-specific error."""
    try:
        first, second = value
    except (TypeError, ValueError) as err:
        raise ValueError(f"field {field} requires ({label})") from err
    return int(first), int(second)


def encode_field(field: int, value: Any) -> list[int]:
    """Encode one semantic field value as an F79D ``[id, byte1, byte2]`` triple."""
    spec = F79D_FIELDS_BY_ID.get(field)
    codec = spec.write_codec if spec is not None else None
    if codec is None:
        codec = FieldCodec.U8

    if codec is FieldCodec.TIME_HM:
        hour, minute = _pair(value, field, "hour, minute")
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError(f"invalid time {hour}:{minute} for field {field}")
        return [field, hour, minute]

    if codec is FieldCodec.DURATION_MIN_SEC:
        minute, second = _pair(value, field, "minute, second")
        if not 0 <= minute <= 0xFF or not 0 <= second <= 59:
            raise ValueError(f"invalid duration {minute}m {second}s for field {field}")
        return [field, minute, second]

    number = int(value)
    if codec is FieldCodec.U16_BE:
        if not 0 <= number <= 0xFFFF:
            raise ValueError(f"value {number} out of u16 range for field {field}")
        return [field, (number >> 8) & 0xFF, number & 0xFF]
    if codec is FieldCodec.U16_LE:
        if not 0 <= number <= 0xFFFF:
            raise ValueError(f"value {number} out of u16 range for field {field}")
        return [field, number & 0xFF, (number >> 8) & 0xFF]
    if codec is FieldCodec.U8:
        if not 0 <= number <= 0xFF:
            raise ValueError(f"value {number} out of byte range for field {field}")
        return [field, number, 0]
    raise ValueError(f"field {field} has unsupported write codec {codec.value}")


def build_control(payload: list[int]) -> bytes:
    """Wrap an already encoded control payload in an F79D write frame."""
    return build_control_frame(payload)


def build_write_fields(values: dict[int, Any]) -> bytes:
    """Encode several semantic field writes into one deterministic F79D frame."""
    payload: list[int] = []
    for field in sorted(values):
        payload += encode_field(field, values[field])
    return build_control(payload)


def _clock(low: int, high: int) -> str | None:
    """Decode hour/minute wire bytes as a Home Assistant-compatible time string."""
    if not (0 <= low <= 23 and 0 <= high <= 59):
        return None
    return f"{low:02d}:{high:02d}:00"


def _duration(low: int, high: int) -> str:
    """Decode minute/second wire bytes into an ``HH:MM:SS`` duration string."""
    total = low * 60 + high
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _decode_volume_pair(
    tlvs: dict[int, tuple[int, int]], field: int, unit_code: int | None
) -> int | float | None:
    """Mirror the legacy WaterDevice unit-dependent three-byte volume codec."""
    if field + 1 not in tlvs or unit_code not in (0, 1, 2):
        return None
    _base_low, base_high = tlvs[field]
    next_low, next_high = tlvs[field + 1]
    # Legacy app builds [base_high, next_low, next_high], reverses it, then:
    # unit 0/1 -> generic LE integer; unit 2 -> base-100 decimal packing.
    if unit_code in (0, 1):
        return next_high | (next_low << 8) | (base_high << 16)
    return (next_high + next_low * 100 + base_high * 10_000) / 100


def decode_tlvs(
    tlvs: dict[int, tuple[int, int]], *, device_model: int | None = None
) -> dict[str, Any]:
    """Decode raw F79D TLV byte pairs into named semantic controller values."""
    decoded: dict[str, Any] = {}
    unit_code = tlvs.get(8, (None, None))[0]
    # A received identity takes precedence over context from a previous read.
    model_code = tlvs.get(1, (device_model, None))[0]
    for field, (low, high) in tlvs.items():
        if field == 26:
            # Preserve original bytes regardless of the model's read codec.
            decoded["_raw_resinVolumeBytes"] = (low, high)
        spec = F79D_FIELDS_BY_ID.get(field)
        name = spec.name if spec is not None else f"field_{field}"
        codec = spec.read_codec if spec is not None else FieldCodec.U8
        codec = F79D_READ_CODEC_OVERRIDES.get((model_code, field), codec)

        if codec is FieldCodec.CONTINUATION:
            continue
        if codec is FieldCodec.TIME_HM:
            value: Any = _clock(low, high)
        elif codec is FieldCodec.DURATION_MIN_SEC:
            value = _duration(low, high)
        elif codec is FieldCodec.U16_LE:
            value = low | high << 8
            if field in HUNDREDTHS_FIELDS:
                decoded[f"_raw_{name}"] = value
        elif codec is FieldCodec.U16_BE:
            value = low << 8 | high
            if field in HUNDREDTHS_FIELDS:
                decoded[f"_raw_{name}"] = value
        elif codec is FieldCodec.BOOL:
            value = bool(low)
        elif codec is FieldCodec.VOLUME_PAIR:
            value = _decode_volume_pair(tlvs, field, unit_code)
        elif codec is FieldCodec.REMINDER_FLAGS:
            decoded["saltShortageReminder"] = bool(low)
            decoded["filterMaterialReminder"] = bool(high)
            continue
        else:
            value = low
        decoded[name] = value
    return decoded


def decode_frame(frame: bytes, *, device_model: int | None = None) -> dict[str, Any]:
    """Validate/extract a complete F79D frame and decode its semantic values."""
    return decode_tlvs(extract_tlvs(frame), device_model=device_model)


_inner_frame = inner_frame

__all__ = [
    "DEVICE_MODEL", "STATE_FIELDS", "FIELD_NAMES", "CLOCK_FIELDS", "DURATION_FIELDS",
    "LE16_FIELDS", "BE16_FIELDS", "HUNDREDTHS_FIELDS", "BOOL_FIELDS", "VOLUME_FIELDS",
    "WRITE_SIMPLE", "WRITE_U16", "WRITE_U16_BE", "WRITE_CLOCK", "WRITE_DURATION",
    "WRITE_TIME", "QUERY_CODE", "WRITE_CODE", "F79DProtocolError", "build_query",
    "build_write", "encode_field", "build_control", "build_write_fields", "validate_frame",
    "extract_tlvs", "decode_tlvs", "decode_frame", "_inner_frame",
]
