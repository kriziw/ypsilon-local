"""Observed Runxin WaterDevice frame envelope used by the F79D family.

This layer knows only how to construct and validate the 0x5A/0x5C outer frame
and the 0xDF/0xFD inner frame.  It deliberately knows nothing about BroadLink,
Home Assistant, or F79D field meanings.

The project has verified this framing with an F79D controller.  Reuse for other
Runxin models should be treated as a hypothesis until that model is captured or
tested; see docs/protocol.md.
"""

from __future__ import annotations

from collections.abc import Iterable

from .errors import RunxinProtocolError

QUERY_CODE = 0x09
WRITE_CODE = 0x19
QUERY_RESPONSE_CODE = 0xC9
WRITE_RESPONSE_CODE = 0xD9

OUTER_MAGIC = b"\x5a\x5c"
INNER_MAGIC = b"\xdf\xfd"
OUTER_END = 0xA5
INNER_END = 0xDE


def _fill_sum(frame: list[int]) -> None:
    """Fill the penultimate byte with the additive checksum."""
    frame[-2] = sum(frame[:-2]) & 0xFF


def build_frame(opcode: int, payload: Iterable[int]) -> bytes:
    """Build one observed Runxin request frame.

    `payload` is the inner payload after the opcode: field ids for a query or
    serialised three-byte field groups for a write.
    """
    if not 0 <= opcode <= 0xFF:
        raise ValueError("opcode must fit in one byte")
    data = list(payload)
    if any(not 0 <= value <= 0xFF for value in data):
        raise ValueError("payload values must fit in one byte")

    header = [0x5A, 0x5C, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0x12, 0, 0]
    inner = [0xDF, 0xFD, 0, opcode, *data, 0, 0xDE]
    header[15] = len(inner)
    inner[2] = len(inner)
    _fill_sum(inner)

    frame = header + inner + [0, 0xA5]
    frame[2] = len(frame)
    _fill_sum(frame)
    return bytes(frame)


def build_query_frame(fields: Iterable[int]) -> bytes:
    """Build a 0x09 field query."""
    field_list = list(fields)
    if not field_list or any(not 0 <= value <= 0xFF for value in field_list):
        raise ValueError("fields must contain byte-sized field identifiers")
    return build_frame(QUERY_CODE, field_list)


def build_control_frame(payload: Iterable[int]) -> bytes:
    """Build a 0x19 control frame from serialised three-byte field groups."""
    data = list(payload)
    if not data or len(data) % 3:
        raise ValueError("control payload must be whole three-byte groups")
    return build_frame(WRITE_CODE, data)


def inner_frame(frame: bytes) -> bytes:
    """Return the inner DF/FD frame without interpreting its field payload."""
    start = frame.find(INNER_MAGIC, 17)
    if start < 0 or start + 3 > len(frame):
        raise RunxinProtocolError("missing DF FD")
    length = frame[start + 2]
    if length < 6:
        raise RunxinProtocolError("inner frame too short")
    inner = frame[start:start + length]
    if len(inner) != length:
        raise RunxinProtocolError("truncated inner frame")
    return inner


def validate_frame(frame: bytes) -> None:
    """Validate lengths, delimiters and both additive checksums."""
    if len(frame) < 25:
        raise RunxinProtocolError("frame too short")
    if frame[:2] != OUTER_MAGIC:
        raise RunxinProtocolError("missing magic")
    if frame[2] != len(frame):
        raise RunxinProtocolError("outer length mismatch")
    if frame[-1] != OUTER_END:
        raise RunxinProtocolError("missing A5")
    if frame[-2] != sum(frame[:-2]) & 0xFF:
        raise RunxinProtocolError("outer checksum mismatch")

    inner = inner_frame(frame)
    if inner[2] != len(inner):
        raise RunxinProtocolError("inner length mismatch")
    if inner[-1] != INNER_END:
        raise RunxinProtocolError("missing DE")
    if inner[-2] != sum(inner[:-2]) & 0xFF:
        raise RunxinProtocolError("inner checksum mismatch")


def extract_tlvs(frame: bytes) -> dict[int, tuple[int, int]]:
    """Extract three-byte field groups from a validated query/write response."""
    validate_frame(frame)
    inner = inner_frame(frame)
    if inner[3] not in (QUERY_RESPONSE_CODE, WRITE_RESPONSE_CODE):
        raise RunxinProtocolError(
            f"unexpected response opcode 0x{inner[3]:02x}"
        )
    data = inner[4:-2]
    if len(data) % 3:
        # A 0x19 acknowledgement can carry implementation-specific payload
        # that is not a field list. The frame itself is already validated.
        if inner[3] == WRITE_RESPONSE_CODE:
            return {}
        raise RunxinProtocolError("TLV data not divisible by three")
    return {
        data[offset]: (data[offset + 1], data[offset + 2])
        for offset in range(0, len(data), 3)
    }
