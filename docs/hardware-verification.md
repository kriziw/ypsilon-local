[English](hardware-verification.md) | [Español](hardware-verification.es.md) | [Català](hardware-verification.ca.md)

# Hardware write verification

A field is marked `HARDWARE_WRITE_VERIFIED` only after the local integration has proved the complete write/read-back path against a physical controller. A protocol ACK or a self-consistent codec is not enough.

The v2.6.1 vacation-mode correction remains an intentional example of this rule: field 49 is writable in the recovered legacy codec, but the tested current Ypsilon G6 ACKed the direct local write without changing fresh read-back state. Therefore Home Assistant exposes vacation state read-only.

## Required sequence

For a reversible configuration field:

1. **Baseline GET** — read the current value locally.
2. **SET candidate** — send one local write with the codec under test.
3. **Independent GET** — read the controller again through a fresh local query.
4. **Physical/semantic check** — confirm that the observed state means what the field is expected to mean.
5. **Restore** — write the original baseline value back.
6. **Independent restore GET** — verify restoration.

Do not use cached coordinator state as evidence.

For a mechanical action, add the expected phase/state transition to steps 3–4. A matching configuration bit without the expected physical transition is insufficient.

## Ambiguous delivery

If a SET is sent and the transport response is lost or times out, do **not** blindly resend it. The controller may already have executed the command. Perform a fresh GET and reconcile the physical state first.

This rule is mandatory for mechanical actions such as regeneration or vacation-state transitions.

## Evidence levels

- app codec only → `LEGACY_APP_CODEC`;
- value observed in real state → `DEVICE_STATE_OBSERVED`;
- cloud-side change observed → `CLOUD_WRITE_OBSERVED`;
- complete local SET/read-back procedure → `HARDWARE_WRITE_VERIFIED`.

Codec knowledge and hardware acceptance are deliberately independent. A field may retain a write codec in `runxin/fields.py` for interoperability research while being absent from the Home Assistant write surface.

## Current Ypsilon G6 / F79D status

Verified locally end-to-end:

- field 4 — device clock / clock sync;
- field 6 — continuous-flow limit;
- **field 7 — flow shutoff threshold, 16-bit big-endian**;
- field 10 — regeneration trigger time;
- field 43 — added-salt bookkeeping value;
- field 47 — raw-water hardness.

Pending or deliberately unverified:

- **field 34 — mechanical regeneration/state-machine writes:** only specifically observed/tested actions should be exposed; codec support alone is not sufficient to generalise all values;
- **field 49 — vacation mode:** direct local `1/0` control is explicitly **not verified** on the tested current G6 and remains absent from Home Assistant.

## Field 7 / flow cutoff evidence

The physical G6 resolves the field-7 byte order independently of the recovered legacy-app interpretation:

```text
wire bytes: 03 E8
big-endian:    0x03E8 = 1000 -> 10.00 m³/h
little-endian: 0xE803 = 59395 -> 593.95 m³/h
```

The vendor application showed 10.00 m³/h while Ypsilon 2.6.2, using the LE regression, displayed 593.95 m³/h. The same controller therefore proves that the actual field-7 wire value is BE.

The write path provides a second independent check. A requested 2.00 m³/h corresponds to raw 200 (`0x00C8`) and therefore bytes `00 C8`. The regressed LE path sent `C8 00`; the transport/protocol layer ACKed the request, but repeated fresh reads did not adopt the requested value and the coordinator raised `Write ACKed but not confirmed`. That is the intended safety behavior.

Earlier project builds using BE had already completed successful physical SET/read-back verification for field 7. Combined with the current independent wire/read-back observation, this restores `HARDWARE_WRITE_VERIFIED` for field 7. The recovered WaterDevice path that appeared LE is retained as conflicting interoperability evidence rather than being allowed to override the tested controller.

## Field 49 / vacation-mode failure evidence

The recovered legacy WaterDevice UI indicates this semantic model:

- enter only from station/system mode 0;
- set the vacation flag;
- legacy preparation progresses through `0 -> 3 -> 7 -> 2 -> 8`;
- stable vacation is represented by field 49 true + station 8;
- the legacy UI uses 25% of the normal slow-wash duration for the vacation brine-draw progress display;
- exit is initiated from station 8.

On the project's current physical G6, v2.6.0 performed the critical hardware check: baseline read showed `vacationPattern=false`, a direct local field-49 SET was sent, transport/protocol returned ACK, repeated independent local reads continued returning `false`, and verification timed out without physical confirmation.

This disproves the specific direct-write method as a user-facing control on that firmware. The current vendor application also contains dedicated vacation enter/exit operations rather than relying only on the generic control path, so Ypsilon must not guess a multi-field or mechanical replacement sequence.

Consequently Ypsilon keeps field-49 read/decode support, legacy encode support for research/interoperability, and the read-only Vacation status sensor, while omitting a writable Vacation switch.

## Water-counter/statistics evidence

A real history export from the tested G6 confirms `dailyWaterConsumption` rises within the day and resets around the day boundary. This supports the Home Assistant `TOTAL_INCREASING` state class for field 37.

The same evidence, together with vendor-app screenshots, confirms that field 39's live controller value is not the same quantity as the app's week-by-week historical total bars. Fields 39 and 41 therefore intentionally have no Home Assistant `state_class`.

## Salt evidence

Field 43 has full local SET/read-back verification and a cloud-side observed change. Its legacy label/behavior is “salt added” in kilograms. This verifies the configuration/bookkeeping field, not a physical salt-level sensor. The integration must not infer or decrement “salt remaining” from this field.

## Euro-Clear Midnight / controller model 12

**Support level: experimental / Alpha, scoped to model 12 and initially tested on Midnight 25.** Existing controls remain available for validation and retain strict fresh read-back; this status does not certify pending commands. G6 evidence is not automatically model-12 evidence. The shared `FieldSpec` evidence records the reference G6; per-model evidence is in `models.py` and diagnostics.

Hardware: Euro-Clear Midnight 25 (ECOPRO+ head) with a BroadLink BL3372 module (devtype `0x520F`), which reports `deviceModel` 12. Tested 2026-10-04 over the existing transport, with the valve in service and vacation off.

A full fields 1–52 read decodes consistently with the F79D map and the controller display: clock, hardness 160 mg/l, salt added 23 kg, regeneration time 00:00, programme times, and unit-2 volumes. Differences: field 26 reports tenths of a litre (raw 250 on a 25 L unit), field 24 reports 2 and field 9 reports 255. Neither code is in the recovered enums.

Verified locally end-to-end (baseline GET → one SET → fresh GET → restore → fresh GET, with no side effects on other fields):

| Field | Baseline | SET → fresh read | Restore → fresh read |
|---|---|---|---|
| 43 `saltAddition` | `17 00` (23) | `18 00` (24) | `17 00` |
| 10 `regeneratingTriggerTime` | `00 00` | `00 01` | `00 00` |
| 6 `continuousWaterTime` | `00 00` (0) | `78 00` (120) | `00 00` |
| 4 `currentTime` | `10 1F` (16:31) | `10 20` (16:32, clock sync) | — |

Not yet hardware-verified on model 12: field 7 (`flowRateOff`, reads `00 C8` = 2.00 m³/h big-endian as on the G6), field 47 (`rawWaterHardness`) and field 34 forced regeneration.

The field-26 observation `FA 00` confirms the current Midnight 25 display of 25 L. It does not establish the second byte's meaning or the encoding of larger resin volumes. The existing U8 decode and 0.1 scale are retained; `_raw_resinVolumeBytes` preserves both bytes for investigation. Do not infer a model-12 U16 codec from this one capture.

### Model-12 enum and hardness investigation (2026-10-05)

The [Euro-Clear Midnight manufacturer manual (2025)](https://euro-clear.eu/shop/wp-content/uploads/2025/11/2025_Midnight_gepkonyv_HU.pdf) and [Runxin F105/F136 manual](https://manufacturervalve.com/pdf/download-center_22.pdf) were consulted. They do not establish a protocol mapping from field 9 value 255 or field 24 value 2 to a named setting. A physical valve model/menu label is not automatically a BroadLink controller-model code or a wire enum. Display the decimal codes `255` and `2`, retaining `raw_code`, until model-specific evidence supports a translation. Missing data remains `unknown`; existing known keys are unchanged.

[WaterCare 0.6.0](https://github.com/kriziw/Euroclear-broadlink/tree/2b5b5076e6131d96d98b2263e1f7ee47ce388db7) reuses this project's protocol mapping and also exposes those codes raw. Its agreement is useful interoperability evidence, not independent proof of their meaning. The contributor reports that WaterDevice cannot connect to this unit; a physical display comparison plus a fresh independent HA read is useful, without requiring an unavailable vendor-app comparison.

The Midnight manual, printed page 16, instructs users to multiply measured German hardness (nk°) by 10 (15 → 150 mg/L); elsewhere (page 7) it expresses water hardness as CaO mg/L. Record this model-specific convention when comparing readings. Preserve the reported setting, HA mg/L unit and write range; do not silently convert it to another hardness scale or generalise the convention to the G6.

### Follow-up validation

- Fields 7 and 47: baseline GET → one suitable SET → fresh GET → controller/app comparison → restore → fresh GET. Include both wire bytes, requested values and any write-confirmation errors.
- Field 26: report both raw bytes and the resin volume shown by the controller/app. No second unit is required; larger-volume compatibility remains unverified until evidence becomes available.
- During a normally planned regeneration, verify that the HA button starts the physical cycle and the read phases match. Phase advancement is a separate pending action; do not skip phases merely to complete this checklist.
- Confirm 25 L in HA, decimal `2`/`255` plus `raw_code` for unmapped enums, and whether normal use produces recurring errors.

Partial results are useful. Include the model, firmware, date, baseline/restore results and sanitized diagnostics; omit MAC addresses, IP addresses and credentials. None of these follow-up checks should be described as completed until a contributor reports them.

## Unbranded controller model 1 / F150: confirmed clock tests

The [2026-10-10 issue #17 reply](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6096161743) reports baseline 11:23, manual HA writes to 11:24 and 11:26, and restoration through manual clock sync. The physical display and Water Device app matched each step. Record **field 4 manual clock writes/sync verified** on this unit (BL3372 firmware 62016); fields 6/10/34/43/47 remain pending. Version 2.9.3 exposes only the validated manual field-4 controls by default. Other settings retain their opt-ins, reference sensors remain and automatic clock correction stays blocked.

Language code 7 is Dutch on the controller. The project's model-9 G6 reports code 3 with Spanish menus; see [the scoped language mappings](f79d-settings.md#controller-language-evidence-293). These are controller-display observations, not app/account language settings or a complete enum calibration.

Raw resin 240 and per-cycle reference 15 remain distinct, uncalibrated readings. The contributor changed 24 → 15 under the old Runxin app's Water treatment capacity label; its unit and exact local-field path are still pending. Nominal 24 L resin makes a 0.1 scale plausible but does not confirm the configured parameter. No repeated clock test, diagnostic scan or model-14 codec generalisation is required. See [the model-1 guide](model-1-alpha.md).

### Model-1 operation and phase observation on 2.9.3

The [later issue #17 report](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6101162421) confirms normal polling and reading recovery after HA restarts, plus agreement with the physical display for brine draw / slow up-flow rinse. It does not validate all regeneration phases or configured durations: earlier aborted attempts are excluded, and the approximate refill observation used 60-second polling. The HA regeneration option stayed off, so field-34 write verification remains pending.

HA reported remaining capacity 3429 L after the cycle, with resin raw 240 and per-cycle reference 15 unchanged. These are reported readings and a consistency check, not an independent confirmation of resin scaling or capacity units. The old setting's L label is recalled with uncertainty. Alpha and pending writes remain unchanged; no additional contributor tests or reports are requested. The original connection/setup issue may be closed independently. See [the detailed operation record](model-1-alpha.md#operation-reported-after-regeneration-on-293).

## Euro-Clear Midnight / controller model 14 (F136)

**Beta in 2.9.2**, scoped to Euro-Clear Midnight 25 Plug&Play / F136 / ECOPRO+, BL3372 `0x520F`, firmware **62016**. [Issue #22](https://github.com/Danirv/runxin-local/issues/22) confirms v2.9.1 works after update/restart without local model edits. App comparisons confirm readings for **4/6/7/10/43/47** (field 7: 3.5 m³/h; field 47: 260 mg/L). Contributor-verified writes are **4/6/10/43**; **writes 7/47 and mechanical field 34 remain pending**.

Field 26 `[44, 1]` appears identically in HA diagnostics and the independent read-only report. The [controller photo](https://github.com/Danirv/runxin-local/issues/22#issuecomment-6084624961) shows **30.0 L** configured. U16 little-endian gives `0x012C = 300`, scaled by 0.1 to 30.0 L. Version 2.9.2 applies this model-14-only read override and sets `resin_volume_scale_confirmed=true`; reference G6/model-12 decoding stays unchanged. Nominal physical capacity 25 L is distinct from the configured parameter; no setting is changed. This evidence is a reported byte-pair/controller comparison, not a captured full raw frame or a new maintainer write test. No further resin comparison or repeated report is needed. See the [model-14 guide](model-14-alpha.md).

## Field 52 polling note

Field 52 is intentionally not part of the normal 1..51 state block. The Ypsilon composition layer reads and caches it separately because it is a slow-changing service interval. This is a polling optimisation and does not weaken its observed-state evidence.

## Generalisation rule

Evidence from one controller/firmware must not be silently generalised to all Runxin devices. Before extending support to another transport, rebrand or firmware, verify the field codec and the physical semantics independently.

See also [`waterdevice-audit.md`](waterdevice-audit.md) for the complete legacy-app/device evidence summary.
