"""Declarative field catalogue for the Runxin F79D profile.

The catalogue is intentionally data-first. Field meaning, wire encoding and
research evidence live together so future device profiles can reuse the frame
codec without copying a pile of field-id conditionals.

`LEGACY_APP_CODEC` means the field/encoding was recovered from the legacy
WaterDevice product codec. It does *not* mean every field has been exercised
on every valve firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FieldCodec(str, Enum):
    """Wire-level encoding used to read or write one F79D field."""

    U8 = "u8"
    U16_LE = "u16_le"
    U16_BE = "u16_be"
    TIME_HM = "time_hm"
    DURATION_MIN_SEC = "duration_min_sec"
    BOOL = "bool"
    VOLUME_PAIR = "volume_pair"
    CONTINUATION = "continuation"
    REMINDER_FLAGS = "reminder_flags"


class Evidence(str, Enum):
    """Origin and confidence category for a recovered field definition."""

    LEGACY_APP_CODEC = "legacy_app_codec"
    DEVICE_STATE_OBSERVED = "device_state_observed"
    HARDWARE_WRITE_VERIFIED = "hardware_write_verified"
    CLOUD_WRITE_OBSERVED = "cloud_write_observed"
    INFERRED = "inferred"


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """Describe one F79D field, its codecs, evidence, unit and research notes."""

    id: int
    name: str
    read_codec: FieldCodec = FieldCodec.U8
    write_codec: FieldCodec | None = None
    evidence: tuple[Evidence, ...] = (Evidence.LEGACY_APP_CODEC,)
    unit_hint: str | None = None
    notes: str | None = None


APP = (Evidence.LEGACY_APP_CODEC,)
OBSERVED = (Evidence.LEGACY_APP_CODEC, Evidence.DEVICE_STATE_OBSERVED)
HW_WRITE = (
    Evidence.LEGACY_APP_CODEC,
    Evidence.DEVICE_STATE_OBSERVED,
    Evidence.HARDWARE_WRITE_VERIFIED,
)
DEVICE_HW_WRITE = (
    Evidence.DEVICE_STATE_OBSERVED,
    Evidence.HARDWARE_WRITE_VERIFIED,
)
SALT_HW_CLOUD_WRITE = (
    Evidence.LEGACY_APP_CODEC,
    Evidence.DEVICE_STATE_OBSERVED,
    Evidence.HARDWARE_WRITE_VERIFIED,
    Evidence.CLOUD_WRITE_OBSERVED,
)


F79D_FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec(1, "deviceModel", evidence=OBSERVED),
    FieldSpec(2, "language", write_codec=FieldCodec.U8, evidence=OBSERVED,
              notes="Reference WaterDevice enum 0..7; confirmed language-label overrides live in semantics.py (model 1/code 7 Dutch; model 9/code 3 Spanish)."),
    FieldSpec(3, "deviceTimeScheme", evidence=OBSERVED,
              notes="WaterDevice enum: 0=12-hour, 1=24-hour."),
    FieldSpec(4, "currentTime", FieldCodec.TIME_HM, FieldCodec.TIME_HM, evidence=HW_WRITE),
    FieldSpec(5, "washInitiationTime", FieldCodec.TIME_HM, FieldCodec.TIME_HM),
    FieldSpec(6, "continuousWaterTime", write_codec=FieldCodec.U8, evidence=HW_WRITE, unit_hint="min",
              notes="WaterDevice settings range 0..120 min."),
    # Physical Ypsilon G6 evidence overrides the legacy-app interpretation for
    # field 7. The controller returns wire bytes 03 E8 while WaterDevice displays
    # 10.00 m³/h, proving BE 0x03E8 == 1000 hundredths. Earlier project builds
    # using BE also completed physical write/read-back verification successfully;
    # the later LE regression was transport-ACKed but failed fresh read-back.
    # Deliberately omit LEGACY_APP_CODEC from the evidence tuple because the
    # recovered application path disagrees specifically on this field's byte order.
    FieldSpec(7, "flowRateOff", FieldCodec.U16_BE, FieldCodec.U16_BE, evidence=DEVICE_HW_WRITE,
              notes="Hundredths of selected flow unit. Tested G6 wire bytes 03 E8 decode as BE raw 1000 = 10.00 m³/h; BE local writes were hardware-verified. WaterDevice caps unit-code-2 display at 10.00 m³/h."),
    FieldSpec(8, "waterVolumeUnit", evidence=OBSERVED),
    FieldSpec(9, "workPattern", write_codec=FieldCodec.U8, evidence=OBSERVED,
              notes="Legacy WaterDevice enum codes 0..9; exposed read-only by HA."),
    FieldSpec(10, "regeneratingTriggerTime", FieldCodec.TIME_HM, FieldCodec.TIME_HM, evidence=HW_WRITE),
    FieldSpec(11, "flowRate", FieldCodec.U16_BE, evidence=OBSERVED,
              notes="Hundredths of the selected flow unit; raw counter is preserved."),
    FieldSpec(12, "systemCloseReason", FieldCodec.U16_LE),
    FieldSpec(13, "washingIncreaseNumber", write_codec=FieldCodec.U8, evidence=OBSERVED,
              notes="WaterDevice numeric setting range 0..20; UI label 'Washing frequency'."),
    FieldSpec(14, "backWashIntervalNumber", write_codec=FieldCodec.U8, evidence=OBSERVED,
              notes="WaterDevice numeric setting range 0..20; backwash interval count."),
    FieldSpec(15, "backWashTime", FieldCodec.DURATION_MIN_SEC, FieldCodec.DURATION_MIN_SEC),
    FieldSpec(16, "backWashTimeRemaining", FieldCodec.DURATION_MIN_SEC),
    FieldSpec(17, "absorbSaltSlowWashTime", FieldCodec.DURATION_MIN_SEC, FieldCodec.DURATION_MIN_SEC),
    FieldSpec(18, "absorbSaltTimeRemaining", FieldCodec.DURATION_MIN_SEC),
    FieldSpec(19, "saltTankRefillTime", FieldCodec.DURATION_MIN_SEC, FieldCodec.DURATION_MIN_SEC),
    FieldSpec(20, "saltTankRefillTimeRemaining", FieldCodec.DURATION_MIN_SEC),
    FieldSpec(21, "washTime", FieldCodec.DURATION_MIN_SEC, FieldCodec.DURATION_MIN_SEC),
    FieldSpec(22, "washCountdownTime", FieldCodec.DURATION_MIN_SEC),
    FieldSpec(23, "maximumRegenerationIntervalDay", write_codec=FieldCodec.U8, unit_hint="day"),
    FieldSpec(24, "outRelayMode", write_codec=FieldCodec.U8, evidence=OBSERVED,
              notes="WaterDevice enum: 0=b-01, 1=b-02."),
    FieldSpec(25, "regenerationAlarmNumber", FieldCodec.U16_LE, FieldCodec.U16_LE, evidence=OBSERVED,
              notes="Regeneration-count reminder threshold; WaterDevice range 5..1200. Observed G6 value: 700."),
    FieldSpec(26, "resinVolume", unit_hint="L", evidence=OBSERVED,
              notes="Reference G6 uses U8 whole litres. Model 12 retains U8 tenths (FA 00 = 25 L). Model 14 overrides the read codec to U16 LE tenths: issue #22 pairs 2C 01 with a controller photo of 30.0 L. Both bytes are preserved."),
    FieldSpec(27, "clockChipFault", FieldCodec.BOOL),
    FieldSpec(28, "multiplePositionSignalFault", FieldCodec.BOOL),
    FieldSpec(29, "noPositionSignalFault", FieldCodec.BOOL),
    FieldSpec(30, "memoryErrorFault", FieldCodec.BOOL),
    FieldSpec(31, "saltShortageAlarm", FieldCodec.BOOL,
              notes="Legacy UI meaning: low brine concentration."),
    FieldSpec(32, "resinReplacementReminder", FieldCodec.BOOL),
    FieldSpec(33, "reminderFlags", FieldCodec.REMINDER_FLAGS),
    FieldSpec(34, "station", write_codec=FieldCodec.U8, evidence=OBSERVED),
    FieldSpec(35, "residualWaterProduction", FieldCodec.VOLUME_PAIR, evidence=OBSERVED,
              notes="Uses field 36; decoding depends on waterVolumeUnit."),
    FieldSpec(36, "residualWaterProductionContinuation", FieldCodec.CONTINUATION),
    FieldSpec(37, "dailyWaterConsumption", FieldCodec.VOLUME_PAIR, evidence=OBSERVED,
              notes="Uses field 38; controller daily cumulative counter that resets at the day boundary."),
    FieldSpec(38, "dailyWaterConsumptionContinuation", FieldCodec.CONTINUATION),
    FieldSpec(39, "averageWeeklyWaterConsumption", FieldCodec.VOLUME_PAIR, evidence=OBSERVED,
              notes="Uses field 40; controller-reported weekly average, not the vendor app's week-history total."),
    FieldSpec(40, "averageWeeklyWaterConsumptionContinuation", FieldCodec.CONTINUATION),
    FieldSpec(41, "periodicWaterProduction", FieldCodec.VOLUME_PAIR, evidence=OBSERVED,
              notes="Uses field 42; WaterDevice labels this water-treatment/cycle capacity, not a cumulative meter."),
    FieldSpec(42, "periodicWaterProductionContinuation", FieldCodec.CONTINUATION),
    FieldSpec(43, "saltAddition", write_codec=FieldCodec.U8, evidence=SALT_HW_CLOUD_WRITE, unit_hint="kg",
              notes="Amount of salt added/bookkept by the controller; not a measured remaining salt level."),
    FieldSpec(44, "operationDay", evidence=OBSERVED, unit_hint="day"),
    FieldSpec(45, "remainingDay", evidence=OBSERVED, unit_hint="day"),
    FieldSpec(46, "regenerationPattern", write_codec=FieldCodec.U8, evidence=OBSERVED),
    FieldSpec(47, "rawWaterHardness", FieldCodec.U16_LE, FieldCodec.U16_LE, evidence=HW_WRITE, unit_hint="mg/L"),
    FieldSpec(48, "absorbSaltMode", write_codec=FieldCodec.U8, evidence=OBSERVED,
              notes="WaterDevice enum: 0=reverse brine draw (逆吸), 1=forward brine draw (顺吸)."),
    FieldSpec(49, "vacationPattern", FieldCodec.BOOL, FieldCodec.U8, evidence=OBSERVED,
              notes="Readable vacation flag. Legacy codec can encode 1/0, but direct local writes are not hardware-verified and HA exposes this read-only."),
    FieldSpec(50, "saltDissolutionRemainingTime", evidence=OBSERVED, unit_hint="min"),
    FieldSpec(51, "pauseRemainingTime", evidence=OBSERVED, unit_hint="min"),
    FieldSpec(52, "filterMaterialWorkingDay", FieldCodec.U16_LE, FieldCodec.U16_LE, evidence=OBSERVED, unit_hint="day"),
)

F79D_FIELDS_BY_ID = {spec.id: spec for spec in F79D_FIELD_SPECS}
F79D_FIELDS_BY_NAME = {spec.name: spec for spec in F79D_FIELD_SPECS}

# Read-only, model-specific differences supported by hardware evidence.
# Issue #22: F136/model 14, BL3372 0x520F firmware 62016, 2C 01 = 30.0 L.
# Keep the reference G6 and model-12 catalogue unchanged.
F79D_READ_CODEC_OVERRIDES = {(14, 26): FieldCodec.U16_LE}

if len(F79D_FIELDS_BY_ID) != len(F79D_FIELD_SPECS):
    raise RuntimeError("duplicate F79D field id")
if len(F79D_FIELDS_BY_NAME) != len(F79D_FIELD_SPECS):
    raise RuntimeError("duplicate F79D field name")
