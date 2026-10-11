"""Controller models accepted by the integration, and their per-model presentation details.

The F79D field map, framing and BL3372 transport are shared by every model listed here.
Read compatibility, presentation confidence and write permission are separate.
New models default to no writes; a received field is not a validated conversion.

This module has no Home Assistant imports so it can be unit-tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Public WaterDevice API enum checked 2026-10-07. Names describe controller
# codes; they do NOT extend the hardware-validated compatibility allowlist.
# Source: https://api.waterdevice.net/api/abp/api-definition?includeTypes=true
CONTROLLER_PROTOCOL_NAMES = dict(enumerate((
    "F79", "F150", "F67N", "F67D", "F71D", "F63D", "F65D", "F68D",
    "F69D", "F79D", "F82D", "F67NA", "F105", "F97", "F136", "F138",
    "F139", "F152", "C600A", "C800D", "F104HW", "F149", "F163", "F151",
)))


def controller_protocol_name(code: object) -> str | None:
    """Descriptive manufacturer enum name, independent of supported models."""
    return CONTROLLER_PROTOCOL_NAMES.get(code) if type(code) is int else None


@dataclass(frozen=True, slots=True)
class ControllerModel:
    """One controller identity (F79D field 1, `deviceModel`) and how to present it."""

    code: int
    title: str
    model_name: str
    manufacturer: str
    # Multiplier from the raw field-26 value to litres.
    resin_volume_scale: float | None = 1.0
    protocol_profile: str = "f79d"
    # An explicit integration policy, independent of theoretical codec support
    # and the evidence lists below. Empty is the conservative default.
    allowed_write_fields: frozenset[int] = frozenset()
    provisional_readings: bool = False
    unconfirmed_unit_fields: frozenset[str] = frozenset()
    evidence: str = ""
    # Evidence metadata only: these do not enable or disable any controls.
    support_level: str = "reference"
    tested_hardware: str = ""
    hardware_verified_write_fields: tuple[int, ...] = ()
    pending_write_fields: tuple[int, ...] = ()
    # False when a compatible-model scale is adopted pending a direct comparison.
    resin_volume_scale_confirmed: bool = True

    @property
    def read_only(self) -> bool:
        return not self.allowed_write_fields


# Preserve exactly the existing G6/Midnight integration write surface. These
# pending actions are not promoted to hardware-verified evidence by this policy.
EXISTING_CONTROL_FIELDS = frozenset({4, 6, 7, 10, 34, 43, 47})
MODEL1_TEST_FIELDS = frozenset({6, 10, 43, 47})


CONTROLLER_MODELS: dict[int, ControllerModel] = {
    1: ControllerModel(
        code=1,
        title="Runxin F150 · Alpha",
        model_name="F150 / model 1 (Alpha)",
        manufacturer="Runxin",
        # Manual clock controls are independently hardware-verified. Automatic
        # correction remains a separate coordinator policy and stays blocked.
        allowed_write_fields=frozenset({4}),
        resin_volume_scale=None,
        resin_volume_scale_confirmed=False,
        support_level="alpha",
        provisional_readings=True,
        unconfirmed_unit_fields=frozenset({"resinVolume", "periodicWaterProduction"}),
        tested_hardware="Unbranded softener reported in issue #17",
        hardware_verified_write_fields=(4,),
        pending_write_fields=(6, 10, 34, 43, 47),
        evidence=(
            "Issue #17: BL3372 0x520F firmware 62016, stable model code 1, all "
            "fields 1..52 received in two read-only queries with no failures. "
            "F150 is the manufacturer's API enum name, not a confirmed product "
            "identity. App comparisons and field applicability are pending; "
            "resin raw 240 and periodic-water reference 15 have no confirmed units. "
            "On 2026-10-10, the contributor confirmed two manual field-4 clock "
            "writes and restoration via manual sync against the controller and "
            "Water Device app; controller language code 7 is Dutch. The value 15 "
            "was changed under Runxin's Water treatment capacity setting; it is "
            "not a confirmed resin value. Optional tests of fields 6/10/43/47 "
            "and regeneration start remain unverified; field 7 and automatic "
            "clock correction stay blocked."
        ),
    ),
    9: ControllerModel(
        code=9,
        title="Ypsilon G6",
        model_name="F79D / Ypsilon G6",
        manufacturer="ATH / BWT / Runxin",
        allowed_write_fields=EXISTING_CONTROL_FIELDS,
        evidence="Reference hardware: reads and writes verified on an ATH/BWT Ypsilon G6.",
        tested_hardware="ATH/BWT Ypsilon G6",
        hardware_verified_write_fields=(4, 6, 7, 10, 43, 47),
        pending_write_fields=(34,),
    ),
    12: ControllerModel(
        code=12,
        title="Euro-Clear Midnight",
        model_name="F105 / Model 12 / Euro-Clear Midnight",
        manufacturer="Euro-Clear / Runxin",
        allowed_write_fields=EXISTING_CONTROL_FIELDS,
        # A Midnight 25 (25 L resin) reports raw 250, i.e. tenths of a litre.
        resin_volume_scale=0.1,
        support_level="alpha",
        tested_hardware="Euro-Clear Midnight 25 (ECOPRO+ head)",
        hardware_verified_write_fields=(4, 6, 10, 43),
        pending_write_fields=(7, 34, 47),
        evidence=(
            "Full 1..52 state read from a Euro-Clear Midnight 25 (ECOPRO+ head, BL3372 "
            "devtype 0x520F) decodes consistently with the F79D map: clock, hardness, salt, "
            "programme times, capacity and volumes. Local writes to fields 4, 6, 10 and 43 "
            "were hardware-verified (baseline, set, fresh read, restore, fresh read). Fields "
            "7 and 47 and forced regeneration use the same encodings with read-back "
            "reconciliation but are not yet hardware-verified on this model."
        ),
    ),
    14: ControllerModel(
        code=14,
        title="Euro-Clear Midnight (F136)",
        model_name="F136 / Model 14 / Euro-Clear Midnight",
        manufacturer="Euro-Clear / Runxin",
        allowed_write_fields=EXISTING_CONTROL_FIELDS,
        resin_volume_scale=0.1,
        resin_volume_scale_confirmed=True,
        support_level="beta",
        tested_hardware="Euro-Clear Midnight 25 (Runxin F136 / ECOPRO+ head; BL3372 0x520F, firmware 62016)",
        hardware_verified_write_fields=(4, 6, 10, 43),
        pending_write_fields=(7, 34, 47),
        evidence=(
            "Issue #22: contributor enabled model 14 locally and reports working "
            "BL3372 discovery/authentication, F79D reads and the model-12 field map. "
            "The contributor reports local writes verified for fields 4, 6, 10 and 43. "
            "App comparisons confirm readings for fields 4, 6, 7, 10, 43 and 47; "
            "writes to fields 7, 34 and 47 remain unverified. On v2.9.1, field 26 "
            "bytes [44, 1] and a controller photo showing 30.0 L confirm U16 "
            "little-endian tenths of a litre, despite the unit's nominal 25 L capacity."
        ),
    ),
}

SUPPORTED_DEVICE_MODELS: frozenset[int] = frozenset(CONTROLLER_MODELS)


def controller_model(code: object) -> ControllerModel | None:
    """Return the supported model for a field-1 value, or None."""
    return CONTROLLER_MODELS.get(code) if type(code) is int else None


def is_supported_model(code: object) -> bool:
    """Whether discovery accepts this controller identity."""
    return controller_model(code) is not None


def allowed_write_fields(
    code: object, *, model1_test_writes: bool = False,
    model1_test_regeneration: bool = False,
) -> frozenset[int]:
    """Resolve opted-in permissions independently from hardware evidence."""
    model = controller_model(code)
    if model is None:
        return frozenset()
    if model.code == 1 and model1_test_writes:
        return model.allowed_write_fields | MODEL1_TEST_FIELDS | ({34} if model1_test_regeneration else set())
    return model.allowed_write_fields


def model_support_details(code: object) -> dict[str, Any] | None:
    """Return per-model evidence and effective integration capabilities.

    Pending fields refer to exposed controls with incomplete hardware evidence,
    not to every field that the protocol can encode. In particular, field 49
    remains read-only in Home Assistant for both models.
    """
    model = controller_model(code)
    if model is None:
        return None
    return {
        "controller_model": model.code,
        "support_level": model.support_level,
        "tested_hardware": model.tested_hardware,
        "hardware_verified_write_fields": list(model.hardware_verified_write_fields),
        "pending_write_fields": list(model.pending_write_fields),
        "resin_volume_scale": model.resin_volume_scale,
        "resin_volume_scale_confirmed": model.resin_volume_scale_confirmed,
        "protocol_profile": model.protocol_profile,
        "read_only": model.read_only,
        "default_read_only": model.read_only,
        "allowed_write_fields": sorted(model.allowed_write_fields),
        "provisional_readings": model.provisional_readings,
        "unconfirmed_unit_fields": sorted(model.unconfirmed_unit_fields),
        **({"experimental_write_fields": sorted(MODEL1_TEST_FIELDS),
            "experimental_regeneration_field": 34,
            # Aggregate for all optional settings, not a per-field claim.
            "experimental_writes_verified": MODEL1_TEST_FIELDS.issubset(
                model.hardware_verified_write_fields)} if model.code == 1 else {}),
        "evidence": model.evidence,
    }


def resin_volume_litres(raw: object, code: object) -> float | int | None:
    """Field 26 in litres, applying the per-model scale (model 12 reports tenths)."""
    if not isinstance(raw, (int, float)):
        return None
    model = controller_model(code)
    scale = model.resin_volume_scale if model is not None else 1.0
    if scale is None:
        return None
    if scale == 1.0:
        return raw
    return round(raw * scale, 1)
