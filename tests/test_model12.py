"""Euro-Clear Midnight (Runxin controller model 12) support.

The frames below were read from a real Euro-Clear Midnight 25 (ECOPRO+ head, BroadLink BL3372
devtype 0x520F) on 2026-10-04 with a read-only query. They contain no device identifiers.
"""

from __future__ import annotations

from .helpers import load

framing = load("runxin.framing")
f79d = load("runxin.f79d")
models = load("models")

IDENTITY_FRAME = bytes.fromhex("5a5c1f00000000000000000001c00a9f00dffd0cc9010c00220000e0dedda5")
STATE_FRAME = bytes.fromhex(
    "5a5cb200000000000000000001c00a9f00dffd9fc9010c00020000030100040b130500000600000700c808020009ff"
    "000a00000b00000c00000d01000e01000f0200100000112d0012000013081e1400001503001600001707001802001"
    "92c011afa001b00001c00001d00001e00001f000020000021000022000023000024031225000026000727000028004e"
    "2900002a03e82b17002c00002d00002e00002fa000300000310000320000330000fcdea8a5"
)


def test_identity_frame_reports_model_12() -> None:
    decoded = f79d.decode_frame(IDENTITY_FRAME)
    assert decoded["deviceModel"] == 12
    assert decoded["station"] == 0


def test_real_state_frame_decodes_with_the_f79d_map() -> None:
    state = f79d.decode_frame(STATE_FRAME)
    assert state["deviceModel"] == 12
    assert state["waterVolumeUnit"] == 2
    assert state["currentTime"] == "11:19:00"
    assert state["regeneratingTriggerTime"] == "00:00:00"
    assert state["rawWaterHardness"] == 160
    assert state["saltAddition"] == 23
    assert state["flowRateOff"] == 200  # 2.00 m³/h, big-endian like the F79D
    assert state["continuousWaterTime"] == 0
    assert state["station"] == 0
    assert state["vacationPattern"] is False
    # Regeneration programme.
    assert state["backWashTime"] == "00:02:00"
    assert state["absorbSaltSlowWashTime"] == "00:45:00"
    assert state["saltTankRefillTime"] == "00:08:30"
    assert state["washTime"] == "00:03:00"
    # Unit-2 volume pairs.
    assert state["residualWaterProduction"] == 3.18
    assert state["dailyWaterConsumption"] == 0.07
    assert state["averageWeeklyWaterConsumption"] == 0.78
    assert state["periodicWaterProduction"] == 5.32
    # Differences from the reference G6: resin in tenths of a litre, unknown enum codes.
    assert state["resinVolume"] == 250
    assert state["outRelayMode"] == 2
    assert state["workPattern"] == 255


def test_supported_models() -> None:
    assert models.SUPPORTED_DEVICE_MODELS == frozenset({1, 9, 12, 14})
    assert models.is_supported_model(9)
    assert models.is_supported_model(12)
    assert not models.is_supported_model(10)
    assert not models.is_supported_model(None)
    assert not models.is_supported_model("12")
    assert models.controller_model(9).title == "Ypsilon G6"
    assert models.controller_model(12).title == "Euro-Clear Midnight"


def test_resin_volume_scale_per_model() -> None:
    assert models.resin_volume_litres(250, 12) == 25.0
    assert models.resin_volume_litres(25, 9) == 25
    assert models.resin_volume_litres(40, None) == 40
    assert models.resin_volume_litres(None, 12) is None


def test_model_12_settings_use_the_same_write_encodings() -> None:
    # Writes for model 12 reuse the F79D codec; the integration confirms each by read-back.
    assert f79d.encode_field(47, 160) == [47, 0xA0, 0x00]
    assert f79d.encode_field(7, 200) == [7, 0x00, 0xC8]
    assert f79d.encode_field(43, 23) == [43, 23, 0]
    assert f79d.encode_field(10, (0, 0)) == [10, 0, 0]


def test_support_evidence_is_scoped_to_the_physical_model() -> None:
    g6 = models.model_support_details(9)
    midnight = models.model_support_details(12)
    assert g6["support_level"] == "reference"
    assert g6["hardware_verified_write_fields"] == [4, 6, 7, 10, 43, 47]
    assert g6["pending_write_fields"] == [34]
    assert midnight["support_level"] == "alpha"
    assert midnight["tested_hardware"] == "Euro-Clear Midnight 25 (ECOPRO+ head)"
    assert midnight["hardware_verified_write_fields"] == [4, 6, 10, 43]
    assert midnight["pending_write_fields"] == [7, 34, 47]
    assert models.model_support_details(10) is None
    assert models.model_support_details(None) is None
    # A consumer cannot mutate the declarative evidence through its JSON lists.
    midnight["hardware_verified_write_fields"].append(7)
    assert models.model_support_details(12)["hardware_verified_write_fields"] == [4, 6, 10, 43]


def test_resin_wire_bytes_are_preserved_without_guessing_a_new_codec() -> None:
    state = f79d.decode_frame(STATE_FRAME)
    assert state["_raw_resinVolumeBytes"] == (0xFA, 0x00)
    assert state["resinVolume"] == 250
    assert models.resin_volume_litres(state["resinVolume"], 12) == 25.0
    # Synthetic input only. A nonzero second byte is retained for investigation,
    # not silently reinterpreted as a physically verified uint16 resin volume.
    synthetic = f79d.decode_tlvs({1: (12, 0), 26: (0x2C, 0x01)})
    assert synthetic["_raw_resinVolumeBytes"] == (0x2C, 0x01)
    assert synthetic["resinVolume"] == 0x2C
    assert "_raw_resinVolumeBytes" not in f79d.decode_tlvs({1: (12, 0)})
