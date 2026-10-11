<!-- x-release-please-start-version -->
# Runxin Local 2.10.0
<!-- x-release-please-end -->

Local Home Assistant integration for compatible Runxin F79D / BroadLink BL3372 water softeners, tested with ATH/BWT Ypsilon G6 and Euro-Clear Midnight.

## 2.10.0

Moves to the `python-broadlink` distribution (`1.0.6`), the same one Home
Assistant Core 2026.10 uses for its own BroadLink integration. The previous
`broadlink==0.19.0` requirement installed itself over the top of core's copy
of the shared `broadlink` module and broke core's BroadLink integration,
taking unrelated BroadLink devices such as thermostats down with it.

The transport and the compatibility collector are asynchronous as a result,
since `python-broadlink` 1.0 is. A read interrupted by a closed endpoint now
recovers with one fresh session; writes still never retry. No wire-format
change.

Requires Python 3.13 or newer.

## 2.9.3

Corrects the device-language labels confirmed on physical controllers: **model 1/code 7 → Dutch** and **Ypsilon G6 model 9/code 3 → Spanish**. Other model/code pairs retain the reference mapping; raw codes and entity identities are preserved.

Records model-1 manual clock writes and manual sync restoration as verified in issue #17. Device clock and manual Sync clock are available without enabling experimental settings. Other writes remain pending and require opt-ins; automatic clock correction stays blocked. Reference sensor identities are retained. Resin 240 and treatment-capacity reference 15 remain separate, uncalibrated parameters. Models 1/12 stay Alpha and model 14 stays Beta. See the [model-1 guide](docs/model-1-alpha.md) and [language evidence](docs/f79d-settings.md#controller-language-evidence-293).

## 2.9.2

Promotes **F136 / model 14 to Beta**, based on the working v2.9.1 installation, manufacturer-app comparisons and controller resin photo in issue #22. Fixes its resin reading from 4.4 L to **30.0 L**: field 26 `[44, 1]` is U16 little-endian 300, scaled by 0.1. This is the controller's configured value, distinct from the unit's nominal 25 L resin capacity.

Readings for fields 4/6/7/10/43/47 match the app. Writes to 4/6/10/43 are contributor-verified; writes to 7/47 and mechanical actions on 34 remain pending. Existing commands, fresh read-back and entity identities are retained. G6/model-12 resin decoding and model-1 policy stay unchanged. See the [model-14 guide](docs/model-14-alpha.md).

## 2.9.1

Normal stable release with **optional model-1 / F150 Alpha write tests**. Settings → Devices & services → Runxin Local → Configure enables manual tests for fields 4/6/10/43/47. A second option enables only regeneration start for a planned physical validation. Both are off by default; turning the settings mode off also disables regeneration tests.

At introduction in 2.9.1, all model-1 write evidence was pending; 2.9.3 records the subsequent field-4 confirmation. The adapter and coordinator enforce the same effective permissions, and turning tests off replaces/revokes the old session. Automatic clock correction, field 7, direct phase advancement and vacation writes stay blocked. Existing sensors, raw field bytes, unconfirmed resin/per-cycle units and entity identities are retained. See the [model-1 testing guide](docs/model-1-alpha.md).

## 2.9.0

Normal stable integration release, with **Alpha support scoped to controller models**. Adds Euro-Clear Midnight 25 **Runxin F136 / model 14** based on issue #22: working local discovery/authentication/F79D reads and contributor-reported verified writes to 4/6/10/43. Fields 7/34/47 remain pending but available with the existing Midnight controls and fresh read-back. Resin scale 0.1 follows the reported shared map and is explicitly marked pending a direct raw/app comparison.

Model 12 is identified as **F105 / Euro-Clear Midnight**, retaining its entry title, IDs, conversions and controls. Model 1 / F150 remains read-only Alpha. G6 support and the `ypsilon_local` domain are retained. Adds effective cached write-policy diagnostics, stronger architecture checks and full HA 2026.9.3/2026.9.4 coverage. See the [support matrix](docs/model-support.md) and [model-14 guide](docs/model-14-alpha.md).

## 2.9.0-alpha.1

Adds **model 1 / F150 read-only Alpha**: continuous reference sensors and read-only settings, no control entities, no automatic clock correction and no admin-service writes. Resin and per-cycle quantity have unconfirmed units and remain unscaled. Provisional readings do not create long-term statistics. Diagnostics preserve raw field pairs for app comparisons.

Explicit per-model permissions default to no writes; existing G6/model-12 commands, identities and conversions are retained. See [model-1 instructions](docs/model-1-alpha.md) and the [architecture guide](docs/architecture.md). Failed-auth sockets are closed, short malformed frames fail as protocol errors and responses must match the request opcode. Prerelease publication does not replace stable latest. Domain migration remains a separate pilot.

## 2.8.0

**Runxin Local** is the new public name of Ypsilon. The domain/folder/service namespace `ypsilon_local` and existing device/entity identifiers are retained. The repository is `Danirv/runxin-local`; previous GitHub links redirect after the rename.

Adds an opt-in **read-only compatibility report inside Home Assistant**, including for unlisted controller models and setup failures. No Python environment or model edits are needed. The diagnostic entry stores a bounded one-time scan, has no entities/controls/polling/clock writes, and supports the normal diagnostics download menu. Reload/download does not scan again, and advanced write services cannot target it. The report retains raw field bytes, numeric unmapped codes, omissions and timestamps without model-specific resin scaling or credentials. A prepared issue summary and comparison instructions help contributors.

Existing G6/model-12 controls and conversions are retained. Controller names from the manufacturer's enum (9 F79D, 12 F105, 14 F136) do not automatically establish support for additional models.

## 2.7.2

Displays unmapped enum codes directly while preserving known labels and raw diagnostics. Adds fresh-state and overlapping-request checks to the regeneration button, and bounded clock-rollover confirmation with fresh pre-write evidence that the next-minute value changed, retaining exact scheduled-time verification.

G6 wire encodings, units and ranges remain unchanged. Model 12 stays Alpha pending the contributor's physical validations; the consulted manuals and WaterCare do not establish meanings for codes 2/255.

## 2.7.1

Distinguishes rejected local authentication from other setup failures and reports an advertised local-control lock without assuming it caused the rejection. Adds sanitized connection logs, transport diagnostics, a standalone report script and troubleshooting guides in English, Catalan and Spanish.

This patch helps investigate authentication failures such as issue #17; it does not introduce a new authentication method or claim to fix an untested firmware restriction. The handshake, retries, valve commands and model-12 Alpha compatibility remain unchanged.

## 2.7.0

Adds **experimental / Alpha compatibility** for the **Euro-Clear Midnight** (Runxin controller model 12, BroadLink BL3372 `0x520F`), tested on a Midnight 25. It retains the original sensors and controls. Writes to the clock, continuous-flow limit, regeneration time and salt added were hardware-verified; fields 7 and 47 and mechanical field-34 actions remain pending on this model. Every write still uses strict fresh read-back. Alpha applies to model 12, not to existing G6 support.

Diagnostics now expose per-model hardware evidence and both original resin-volume bytes. Midnight 25's `FA 00` still displays as 25 L; the second byte and larger resin volumes require more evidence, with no guessed codec change.

## 2.6.3

This maintenance release fixes the F79D field-7 (`flowRateOff`) wire codec using physical Ypsilon G6 evidence and restores its hardware-write verification status.

Highlights:

- restores field 7 to **16-bit big-endian** for both reads and writes;
- documents the decisive hardware vector: wire bytes `03 E8` are raw `1000` in BE and correspond to the vendor application's `10.00 m³/h`; the regressed LE interpretation produced raw `59395` / `593.95 m³/h` in Home Assistant;
- writes `2.00 m³/h` as raw `200` / bytes `00 C8` instead of the incorrect LE bytes `C8 00`;
- restores `HARDWARE_WRITE_VERIFIED` for field 7 based on the earlier physically verified BE implementation plus the current independent read-back evidence;
- keeps the safe Home Assistant range at `0.00–10.00 m³/h` for the physically calibrated cubic-metre unit mode;
- preserves strict post-write reconciliation: an ACK alone is still never accepted as proof that the controller adopted a setting;
- adds protocol and audit regressions for the exact real-device byte vectors and the historical `59395` misdecode;
- keeps field 52 on its intentional slow-refresh cache rather than moving it into the normal 1..51 polling block;
- reviews English, Catalan and Spanish translations; no translation key or label change is required for this wire-codec fix.

### Upgrade note

No entity registry migration is required. The existing flow-rate cutoff number retains the same unique ID, range, unit and translations; only its raw wire encoding/decoding is corrected.

The transport-neutral `runxin/` layer remains independent from Home Assistant and BroadLink. The Home Assistant integration supports BroadLink BL3372 (`0x520F`) with Runxin controller model 9 (Ypsilon G6) and, since 2.7.0, model 12 (Euro-Clear Midnight).
