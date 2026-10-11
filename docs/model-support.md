# Controller support and evidence

This is the current model policy for **2.9.3**. A commercial brand, valve reference, BroadLink device type and Runxin `deviceModel` code are different identifiers.

| Controller code | Manufacturer enum name | Integration policy | Field evidence | Writes |
|---|---|---|---|---|
| 9 | F79D | Reference ATH/BWT Ypsilon G6 | Reference hardware and per-field checks | Existing fields 4/6/7/10/34/43/47; field 34 remains pending physical verification |
| 12 | F105 | Alpha Euro-Clear Midnight 25 | Captured state/app comparison; resin scale 0.1 | Existing fields 4/6/7/10/34/43/47; 4/6/10/43 hardware-verified, 7/34/47 pending |
| 1 | F150 | Alpha readings, validated manual clock, issue #17 | All 52 requested field IDs received; v2.9.3 polling/restart recovery and one phase/display comparison confirmed; remaining semantics/applicability pending | Manual clock/sync (4) verified and available by default; opt-in tests 6/10/43/47 and separate start 34; 6/10/34/43/47 pending. Field 7, auto clock, phase advancement and vacation blocked |
| 14 | F136 | Beta Euro-Clear Midnight 25 | Working v2.9.1; app comparisons for 4/6/7/10/43/47; field 26 U16 LE tenths matches controller 30.0 L | Existing fields 4/6/7/10/34/43/47; contributor reports writes 4/6/10/43 verified, writes 7/34/47 pending |
| Other codes | Descriptive API names, where known | One-time diagnostic report only | No automatic support from the name table | None through a diagnostic entry |

`models.py` is the authoritative registry and records default `allowed_write_fields`; `write_policy` diagnostics report effective opted-in permission; `hardware_verified_write_fields`/`pending_write_fields` document evidence. They serve different purposes: legacy pending controls for 9/12 are preserved, while a new model defaults to an empty permission set. A support-status label alone does not grant or withdraw write permission. For model 1, `experimental_writes_verified` is an aggregate for all optional settings; it remains false while fields 6/10/43/47 are pending even though `hardware_verified_write_fields` includes field 4.

A periodic Alpha with scoped controls is distinct from a saved diagnostic-only entry. The Alpha authenticates/polls and creates reference sensors; a diagnostic-only entry loads a saved one-time report without polling or entities. Diagnostic-only entries never permit writes. Model 1 permits only manual field-4 clock writes by default. Other settings and regeneration require explicit test options; automatic clock correction remains blocked.

The integration release is stable; Alpha and Beta status apply to individual models. Model 14 is Beta on the reported F136 / BL3372 0x520F / firmware 62016 unit; this does not certify other hardware variants or pending writes. Reported model-14 write evidence is attributed to [issue #22](https://github.com/Danirv/runxin-local/issues/22), not to a new maintainer hardware test.

## Shared maps and model-specific behavior

Models 1/9/12/14 currently use the F79D-compatible frame and field-map path. That does not mean their full physical semantics are identical. Model 12 retains U8 resin decoding and the observed scale 0.1 (`FA 00` → 25 L); its high byte remains unverified. Model 14 has an explicit field-26 U16 little-endian read override followed by scale 0.1: `[44, 1]` → 300 → 30.0 L, confirmed by the controller photo in issue #22. Both have `resin_volume_scale_confirmed=true`, scoped to their evidence. The configured 30 L is distinct from nominal physical capacity 25 L; the integration does not change the setting. Model 1 keeps resin/per-cycle values without confirmed units and all readings marked provisional, with long-term statistics disabled. Original bytes are retained for comparison.

The catalogue's hardware-write evidence is reference G6 evidence, not a blanket claim for every model. Future differences in byte order, enums, units or applicability require model/profile-specific evidence and regression fixtures; do not change the shared G6 definition to fit another controller.

Field-2 labels have two physical-display exceptions: model 1/code 7 → Dutch and reference G6 model 9/code 3 → Spanish. Every other pair retains the reference DeviceLanguage table, including models 12/14. This table is distinct from app/account language preferences; no complete local/cloud enum equivalence is inferred. BroadLink firmware 62016 identifies the Wi-Fi module, not the valve firmware. See [language evidence](f79d-settings.md#controller-language-evidence-293).

The [model-1 operation report on 2.9.3](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6101162421) confirms polling, recovery after HA restarts and the brine draw / slow up-flow rinse reading against the controller. It does not validate the HA regeneration-start command, all phases/durations or resin/capacity conversions. Remaining model calibration is independent of closing the resolved connection/setup issue; no further tests or reports are requested from this contributor. See [the detailed operation record](model-1-alpha.md#operation-reported-after-regeneration-on-293).

## Beyond field 52

52 is the current **F79D catalogue**, not a proven universal Runxin limit. The public API lists additional pressure, RO-filter, TDS and immersion-detector properties for other families. Cloud object properties are not local numeric field IDs. No automatic scan beyond 52, alternate profile, unknown-model control or cloud dependency is added here.

## Promotion

- Diagnostic evidence → read-only Alpha: coherent identity, readable frame/map, minimal read set and tests that block all mutation routes.
- Read-only Alpha → calibrated readings: app/controller comparisons with units, representative nonzero values and per-model fixtures. Field receipt/zero defaults alone do not prove applicability.
- Controls: per-field write encoding, range and baseline/set/fresh-read/restore evidence. Metadata must distinguish verified and pending actions.
- Beta/release: sustained real HA operation, reload/restart checks, missing-field/unknown-enum handling and documented hardware/firmware scope. Software tests do not replace those hardware checks.

See [model 1 comparison](model-1-alpha.md), [hardware evidence](hardware-verification.md) and [adding a profile](adding-a-device-profile.md).
