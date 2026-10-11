# Controller model 1 / F150: Alpha readings, validated manual clock

[English](model-1-alpha.md) | [Català](model-1-alpha.ca.md) | [Español](model-1-alpha.es.md)

Controller code **1** has been supported since **2.9.0** with continuous reference sensors; **2.9.3** adds validated manual clock controls without experimental options. The public manufacturer's enumeration calls this code **F150**; the commercial product and valve identity in issue #17 are unconfirmed. This does not claim support for every F150-branded product or firmware.

The integration release is stable; Alpha describes support for this particular model.

## Install and compare

1. Install version 2.9.3 or later through HACS, or download the release ZIP and copy only `custom_components/ypsilon_local` to `/config/custom_components/ypsilon_local`. Keep a backup of the previous integration folder and restart Home Assistant. Do not install `runxin_local`; the domain-migration pilot is separate.
2. If you saved a diagnostic-only entry for this device, download its report first, then delete that entry before adding the device normally. Diagnostic entries have no operational entities and are not silently converted.
3. Add **Runxin Local**, enter the local IP, and accept the **Alpha with validated manual clock controls** explanation. Default polling is once per minute, with adaptive polling off. Automatic clock correction remains blocked even if an old option is enabled. Manual clock controls are available.
4. Open the device and compare its sensors with the working vendor app. Some reference/diagnostic entities are disabled by default; enable them in the entity list if useful. No settings need to be changed to make a comparison.
5. From the integration entry menu, **Download diagnostics** and attach the JSON to the existing issue. This exports the last cached state and does not trigger another scan. Include a few app readings with their units and approximate comparison time; redact account/device identifiers in screenshots.

The domain, config-entry version and G6/Midnight entity identities stay unchanged. A normal integration setup authenticates and polls, so it is a small amount of active LAN traffic. If the app and HA interfere, pause HA polling or disable the entry temporarily while collecting app screenshots; it does not need to be unpaired.

## What is enabled

- Existing status, water, programme-duration and diagnostic sensors, using the **reference F79D interpretation**.
- Sensor equivalents for clock, regeneration schedule, hardness, added salt, continuous-flow timeout, flow-cutoff raw value and closure-reason raw code.
- The original two bytes of received fields in diagnostics (`state._rawFieldBytes`), plus raw bytes/reference markers on entities. No raw network packets, encryption keys or session IDs are included.
- Model/evidence/write-permission metadata. Zero/false readings are retained, but receipt alone does not prove a field is applicable.

From **2.9.3**, **Device clock** and the **manual Sync clock button** are validated controls available without experimental options. Their existing unique IDs and strict fresh read-back are preserved. Setup, polling and reloads do not initiate clock writes. The other settings require the optional experimental mode described below, and regeneration start has a separate opt-in. Administrator services, the coordinator and adapter enforce the same field-level permissions; granting field 4 does not allow arbitrary writes or automatic clock correction.

Numeric model-1 readings remain provisional: these entities have **no long-term statistics state class**. Ordinary recorder history can still be retained. Known enum labels use the reference table except the physically confirmed language code 7 → Dutch; unmapped values retain their numeric codes.

## Optional experimental settings

Open **Settings → Devices & services → Runxin Local → Configure** for the operational model-1 entry. Enable **experimental model-1 settings** and save. The integration reloads automatically and adds controls for:

| Field | Manual test | Reference baseline in issue #17 |
|---|---|---|
| 6 | Continuous-flow timeout | 50 (reference minutes) |
| 10 | Regeneration schedule | 00:00 |
| 43 | Added-salt bookkeeping | 25 (reference kg) |
| 47 | Hardness | 280 (reference mg/L) |

**Field 4 manual clock writes and manual sync restoration are verified on the reported unit. Fields 6/10/43/47 and regeneration start (34) remain pending.** No repeat of the completed clock test is needed. For a new test, use the actual fresh baseline, not these historical numbers. Change one setting by a small valid amount, wait for fresh read-back, compare with the app/controller where visible, restore the original value and confirm restoration. Record field, baseline, requested value, read-back, display/units and restored value. Partial results are useful; do not repeat writes if their delivery is ambiguous. The integration reconciles once without blindly resending.

**Regeneration start** has a second, separate option and also requires the settings mode enabled. Use it only for a normally planned physical cycle. The button checks a fresh in-service/vacation-off state, sends the existing field-34 value-1 command once and confirms the phase transition. Direct phase advancement remains blocked, including through administrator services; the option does not grant arbitrary field-34 commands.

**Automatic clock correction stays off**, even if an old option says otherwise. **Field 7 / flow cutoff stays blocked**, even if the unit changes: this unit reported code 1, while the established writable cutoff is calibrated for code 2. Vacation writes and resin/capacity writes are not enabled.

Turning the experimental settings option off removes only the additional test controls and also disables regeneration tests. Device clock and manual Sync clock remain available. The old write session is revoked/replaced; reference sensors, unique IDs, raw bytes, unconfirmed units and absence of provisional long-term statistics are preserved across upgrades, restarts and option changes.

Diagnostics report model-default evidence separately from the effective `write_policy` (enabled test options, permitted fields, adapter restrictions and automatic-clock permission). Download them after each completed test sequence; exporting diagnostics does not query or write the device. G6/model-12/model-14 policy and conversions are unaffected.

## Priority comparisons from issue #17

| Field | Reported reference | Compare with the app |
|---|---|---|
| 26, resin | Raw `F0 00`, first byte 240 | Resin volume/capacity and unit. HA shows 240 **without L**, with no guessed multiplier. |
| 41–42, per-cycle quantity | Reference 15 | The contributor changed 24 → 15 under Runxin Advanced → Water treatment capacity. The manufacturer distinguishes this from resin volume; confirm its unit and local-field correspondence. HA keeps 15 **without an assumed unit**. |
| 35–36, remaining quantity | Reference 1304 L | Remaining capacity and unit, close to the HA snapshot time. |
| 37–40, daily/weekly quantities | Reference 215 / 192 L | Daily consumption and the controller's weekly average, not necessarily an app history total. |
| 47, hardness | Reference 280 mg/L | Exact label, value and hardness scale. |
| 43, added salt | Reference 25 kg | Bookkeeping amount, not a measured tank level. |
| 4/5/10, clocks/schedule | 20:38 / 00:00 / 00:00 | Clock and visible regeneration schedule; values naturally change over time. |
| 6/7/15/17/19/21/23 | Raw values and programme times | Protection settings, programme durations and maximum interval, wherever visible. |

Resin and per-cycle capacity are uncalibrated. Other displayed units/scales are reference candidates, not independently validated measurements. The second resin byte is preserved without assuming a U16 codec. Field 52 remains cached separately; its raw bytes may be older than the rest of the snapshot.

## Confirmed comparisons in 2.9.3

The [2026-10-10 reply](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6096161743) records a clock baseline of 11:23, writes to 11:24 and 11:26, and restoration using manual clock sync. Both the physical controller and Water Device app agreed after each action. Only field 4 was exercised; the experimental option was disabled afterwards. This validates manual clock controls on that unit, not automatic correction or other writes.

The same reply confirms a Dutch controller display with field-2 code 7. HA now labels that model/code pair `dutch`; no language write or app-locale change is made.

The reported unit has nominal 24 L resin. Field 26 remains `F0 00` (reference 240), while fields 41–42 remain reference 15. In the examined manufacturer frontend, `resinVolume` is labelled Resin volume and `periodicWaterProduction` is Water treatment capacity; the older Runxin app's exact setting-to-local-field path is not independently confirmed. `240 / 10 = 24 L` is plausible but not yet a configured-value comparison. Keep both sensors without assumed units and do not copy model 14's U16 override.

Do not reduce a resin-volume setting to match household size: it should describe the actual resin charge. Treatment capacity is a different parameter based on resin, hardness and regeneration settings; a lower programmed capacity with unchanged cycles can cause more frequent regeneration rather than savings. Confirm the label/unit and follow the unit's instructions before suggesting an adjustment. No re-pairing, old-app access, repeated diagnostics or setting changes are needed just to clarify these readings.

## Operation reported after regeneration on 2.9.3

The [later 2026-10-10 report](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6101162421) confirms normal polling and recovery of readings after HA restarts following updates on the reported model-1 unit, with BL3372 firmware 62016 and integration 2.9.3.

At 19:41:45 local time, HA reported brine draw and slow rinse while the controller displayed **“pekel-spoel traag up-flow”**. This independently supports that specific phase label. HA had reported brine refill at 19:35:34, approximately six minutes earlier. With 60-second polling, this observation does not independently validate the configured refill duration or establish a timing error against the earlier seven-minute reading. Earlier aborted attempts are excluded from sequence and duration validation. The HA regeneration option remained off, so these observations do not validate the field-34 start command.

After the cycle, HA showed remaining capacity **3429 L**, compared with **1267 L** reported on 8 October. This records a capacity recovery after regeneration; it is not an independent calibration of its units. Reported hardness remained 280 mg/L, resin `F0 00` / reference 240 and per-cycle reference 15. Assuming hardness expressed as CaCO₃, `3.429 m³ × 28 °f ≈ 96 °f·m³`, or about `4 °f·m³/L` for nominal 24 L resin. This is a consistency check, not a configured-resin comparison or proof of the 0.1 conversion. The contributor recalls an L label beside the old setting but is unsure; its unit and exact local-field correspondence remain pending.

These observations add operational and phase-reading evidence without changing the model's Alpha status, codecs, permissions or provisional units. The remaining comparisons above are a calibration backlog; no further tests, screenshots or diagnostic reports are requested from this contributor. The original connection/setup issue can be closed independently of those pending validations.

## Evidence and next steps

[Issue #17](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6044822202) supplied BL3372 devtype `0x520F`, firmware 62016, standard authentication with the app closed, stable code 1 and all 52 requested fields in two successful queries. The fixture in `tests/fixtures/model1_fields.json` preserves published field pairs; reconstructed test frames are **synthetic**, not network captures. Software tests cannot confirm physical units or mechanical actions.

A later model-1 calibration should change only its model policy/presentation or proven codec overrides. It must not change G6/Midnight interpretation to accommodate this device. Reads beyond 52 remain disabled. Model-1 writes other than the validated manual clock remain experimental and require the explicit opt-ins above; software tests do not validate physical acceptance.
