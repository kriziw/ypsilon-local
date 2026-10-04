"""Controller models accepted by the integration, and their per-model presentation details.

The F79D field map, framing and BL3372 transport are shared by every model listed here.
A model is only added once its real controller state has been read through that map and
the decoded values have been checked against the controller's own display.

This module has no Home Assistant imports so it can be unit-tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ControllerModel:
    """One controller identity (F79D field 1, `deviceModel`) and how to present it."""

    code: int
    title: str
    model_name: str
    manufacturer: str
    # Multiplier from the raw field-26 value to litres.
    resin_volume_scale: float = 1.0
    evidence: str = ""


CONTROLLER_MODELS: dict[int, ControllerModel] = {
    9: ControllerModel(
        code=9,
        title="Ypsilon G6",
        model_name="F79D / Ypsilon G6",
        manufacturer="ATH / BWT / Runxin",
        evidence="Reference hardware: reads and writes verified on an ATH/BWT Ypsilon G6.",
    ),
    12: ControllerModel(
        code=12,
        title="Euro-Clear Midnight",
        model_name="Model 12 / Euro-Clear Midnight",
        manufacturer="Euro-Clear / Runxin",
        # A Midnight 25 (25 L resin) reports raw 250, i.e. tenths of a litre.
        resin_volume_scale=0.1,
        evidence=(
            "Full 1..52 state read from a Euro-Clear Midnight 25 (ECOPRO+ head, BL3372 "
            "devtype 0x520F) decodes consistently with the F79D map: clock, hardness, salt, "
            "programme times, capacity and volumes. Writes use the same field encodings and "
            "are confirmed by read-back at runtime; they are not yet hardware-verified."
        ),
    ),
}

SUPPORTED_DEVICE_MODELS: frozenset[int] = frozenset(CONTROLLER_MODELS)


def controller_model(code: object) -> ControllerModel | None:
    """Return the supported model for a field-1 value, or None."""
    return CONTROLLER_MODELS.get(code) if isinstance(code, int) else None


def is_supported_model(code: object) -> bool:
    return controller_model(code) is not None


def resin_volume_litres(raw: object, code: object) -> float | int | None:
    """Field 26 in litres, applying the per-model scale (model 12 reports tenths)."""
    if not isinstance(raw, (int, float)):
        return None
    model = controller_model(code)
    scale = model.resin_volume_scale if model is not None else 1.0
    if scale == 1.0:
        return raw
    return round(raw * scale, 1)
