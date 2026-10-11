# Model 14 / Runxin F136: Midnight Beta support

[English](model-14-alpha.md) | [Català](model-14-alpha.ca.md) | [Español](model-14-alpha.es.md)

Runxin Local **2.9.2** promotes controller **14 / F136** to **Beta** and corrects its resin reading. Hardware scope: Euro-Clear Midnight 25 Plug&Play / ECOPRO+ head, BroadLink BL3372 (`0x520F`), firmware **62016**, reported in [issue #22](https://github.com/Danirv/runxin-local/issues/22). The integration release is stable; support status is per model. Models 1 and 12 remain Alpha.

## Confirmed evidence

The contributor confirms that **v2.9.1 works without local registry edits** after updating and restarting Home Assistant. Both the HA diagnostics and independent read-only report contain field 26 `[44, 1]`. Manufacturer-app comparisons confirm readings for **4 (clock), 6 (continuous-flow timeout), 7 (flow cutoff), 10 (regeneration time), 43 (salt added) and 47 (hardness)**. Fields 7 and 47 show **3.5 m³/h** and **260 mg/L**, respectively.

Contributor-verified local writes remain **4/6/10/43**. A matching read does not verify a write: **writes to 7/47 and mechanical actions on 34 remain pending**. Beta does not certify those actions or every F136 hardware variant.

## Resin conversion

The [controller photo and confirmation](https://github.com/Danirv/runxin-local/issues/22#issuecomment-6084624961) show **H1-1 / Set Resin Volume = 30.0 L**. Decimal bytes `[44, 1]` are `0x012C = 300` as U16 little-endian; dividing by 10 gives **30.0 L**. Version 2.9.1 used only the first byte and displayed 4.4 L; **2.9.2 fixes that model-14 error** and reports `resin_volume_scale_confirmed=true` in diagnostics. Original byte pairs remain available on the sensor and in diagnostics.

This is the **configured controller parameter**, not a measurement of resin physically inside the tank. The unit's nominal manufacturer capacity is 25 L; the integration displays the configured 30 L and does not change it. No further resin report or setting change is needed to resolve this issue.

The U16 read override applies only to model 14. Reference G6/model 9 keeps whole-litre U8 decoding; model 12 keeps its existing U8 × 0.1 conversion because its captured `FA 00` does not independently establish the high byte's meaning. Unmapped enums remain visible as decimal codes.

## Installation and controls

Install **2.9.2 or later** for the corrected resin reading, then restart HA. Existing operational entries update in place: the `ypsilon_local` domain, MAC-based unique IDs and controls are retained. No registry edit or device re-addition is required. Diagnostic-only entries remain diagnostic-only.

The existing Midnight sensors, number/time controls, automatic clock correction, regeneration button and administrator services keep the same encodings, ranges, fresh-state guards and read-back confirmation. Pending controls remain available for validation; vacation stays read-only. No extra device query or write is introduced. Partial field-26 reads reuse a previously validated model identity.

## Remaining validation

Previously completed tests need not be repeated and another diagnostic report is not required now. When convenient, an appropriate field-7 or field-47 setting test can provide: baseline read → change from HA → fresh read and app/controller comparison → restore → fresh read. Do not exceed the flow threshold or trigger regeneration just to validate a setting write. Mechanical field-34 evidence remains separate; no mechanical test is requested solely to complete the report. See [hardware verification](hardware-verification.md).
