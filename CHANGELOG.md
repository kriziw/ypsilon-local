# Changelog

All notable changes to this project are documented here.

## [2.7.0] - 2026-10-04

### Added
- Support for the **Euro-Clear Midnight** (ECOPRO+ head), which reports Runxin controller model **12** behind the same BroadLink BL3372 (`0x520F`). A full read of fields 1–52 from a real Midnight 25 decodes consistently with the F79D map: clock, hardness, salt, programme times, capacity and volumes all match the controller. The captured frames are kept as regression tests.
- `models.py`: the accepted controller models with their entry title, device-registry model and manufacturer, kept free of Home Assistant imports so they can be unit-tested.

### Changed
- Setup and DHCP discovery accept models 9 and 12. The config entry and device are named after the reported model.
- Resin volume is scaled per model. Model 12 reports tenths of a litre (raw 250 on a 25 L Midnight 25).
- Enum sensors report an unrecognised controller code as unknown rather than raising, keeping the code in `raw_code`. Model 12 reports output relay mode 2.

### Notes
- Model 12 controls use the same field encodings as model 9 and are confirmed by fresh read-back, so a write the controller does not adopt is reported as not confirmed. They are not yet `HARDWARE_WRITE_VERIFIED` for model 12.

## [2.6.3] - 2026-09-13

### Fixed
- Restore F79D field 7 (`flowRateOff`) to **16-bit big-endian** read/write encoding on the tested Ypsilon G6. Physical read-back returns wire bytes `03 E8` while the vendor application displays `10.00 m³/h`; interpreting those bytes as BE gives raw 1000, while the regressed LE path produced raw 59395 / `593.95 m³/h` in Home Assistant.
- Encode a 2.00 m³/h cutoff as raw 200 / bytes `00 C8`. The 2.6.x LE regression emitted `C8 00`; the controller ACKed transport but did not adopt the requested value, and strict fresh read-back correctly rejected the write.
- Restore `HARDWARE_WRITE_VERIFIED` evidence for field 7. Earlier BE builds had already completed physical write/read-back verification, and the current hardware observations independently confirm the same wire order.

### Changed
- Keep the field-7 Home Assistant control constrained to the physically calibrated unit-code-2 range `0.00–10.00 m³/h` (raw `0–1000`).
- Document the physical-device evidence as authoritative where it conflicts with the recovered legacy-app interpretation.
- Add/restore inline codec documentation so the F79D field catalogue and codec preserve the recovered protocol knowledge next to the implementation.

### Added
- Regression coverage for `03 E8 -> 1000`, the historical LE misdecode `03 E8 -> 59395`, and `2.00 m³/h -> 00 C8` write encoding.
- Audit coverage requiring field 7 to remain BE and hardware-write verified while fields 34 and 49 remain conservatively unverified.

### Notes
- The strict `SET -> fresh GET -> reconciliation` mechanism behaved as designed during the failed LE write: a transport ACK was not accepted as proof of physical state change.
- Field 52 remains intentionally outside the normal 1..51 state block because the Ypsilon composition layer refreshes and caches that slow-changing service interval separately.
- English, Catalan and Spanish entity translations were reviewed; no translation-key or user-facing label change is required for this wire-codec correction.

## [2.6.2] - 2026-09-12

### Fixed
- Expose recovered fields 2 (`language`), 3 (`deviceTimeScheme`), 24 (`outRelayMode`) and 48 (`absorbSaltMode`) as semantic Home Assistant enums instead of raw integers.
- Align the field-6 continuous-water limit with WaterDevice's 0–120 minute range and the unit-code-2 field-7 cutoff with WaterDevice's 0–10.00 m³/h range (raw 0–1000).
- Restore release-history accuracy: changes merged after the already-published `v2.6.1` tag are recorded under 2.6.2 rather than retroactively changing the 2.6.1 release notes.

### Changed
- Preserve raw enum codes as entity attributes while exposing stable enum state keys and localized state labels.
- Strengthen the release path so the tagged source runs the same field-surface checks, unit tests and Python compilation expected by the normal offline audit before creating an asset.
- Clarify publishing documentation so the web workflow is described accurately and release/version bumps are required before publishing new code.

### Added
- Read-only diagnostic coverage for previously omitted native fields 2, 3, 13, 14, 24, 25 and 48; field 25 is enabled by default as the native resin-maintenance regeneration threshold.
- Recovered advanced-setting documentation in English, Catalan and Spanish, including exact enum maps and WaterDevice numeric ranges.
- Regression coverage that requires recovered enums to remain Home Assistant enum entities and requires complete EN/ES/CA state translations.
- Field-surface audit coverage ensuring every readable F79D field is either directly exposed or explicitly represented semantically.

### Notes
- Field 25 (`regenerationAlarmNumber`) is a maintenance reminder threshold, not the number of regenerations already performed.
- No new mechanical write capability is enabled in this release.

## [2.6.1] - 2026-09-12

### Fixed
- Withdraw the v2.6.0 writable Vacation mode switch after real Ypsilon G6 testing showed that a direct local field-49 write can be transport-ACKed while fresh read-back remains `vacationPattern=false`.
- Keep vacation information read-only and preserve the derived `off` / `preparing` / `active` status without guessing an unverified mechanical sequence.
- Replace the incorrectly reused square branding image with a properly padded 256×256 icon, exact 2× icon, landscape logo and exact 2× logo, plus matching dark variants.
- Clarify controller water statistics so field 39 is not presented as the vendor application's current-week/history total and field 41 is not treated as a cumulative meter.

### Changed
- Rename field 39 to **Controller weekly average consumption** / equivalent CA/ES wording while keeping it without a Home Assistant `state_class`.
- Rename field 41 to **Treatment capacity per cycle** / equivalent CA/ES wording; it remains without a `state_class`.
- Clarify field 43 as **Added salt amount**: a 0–100 kg controller bookkeeping/configuration value, not a physical remaining-salt level and not automatically decremented after regeneration.
- Preserve `dailyWaterConsumption` as `TOTAL_INCREASING`; real controller history confirms a within-day cumulative counter that resets at the day boundary.
- Clean the obsolete v2.6.0 vacation switch from the entity registry on reload/upgrade.
- Strengthen publication policy: a field being writable in the recovered legacy codec is no longer sufficient to expose a Home Assistant control without current-hardware physical read-back evidence.

### Added
- Comprehensive WaterDevice/F79D evidence audit in English, Catalan and Spanish.
- Regression tests for daily-counter resets, weekly/cycle quantity semantics, salt semantics, read-only vacation policy and brand image geometry.
- Offline audit checks for withdrawn vacation control, stale translation keys, proper icon/logo dimensions and distinct square/landscape artwork.

### Migration notes
- Home Assistant may offer to delete obsolete long-term statistics previously created for **Weekly average consumption** and **Periodic capacity**. This is expected after correcting their `state_class`; deleting those obsolete statistics does not remove the entities or normal recorder history.
- The v2.6.0 Vacation mode switch is intentionally removed. Vacation status remains available as a read-only sensor until a local current-firmware control sequence is physically verified.

## [2.6.0] - 2026-09-11

### Added
- Dedicated `Vacation status` enum with `off`, `preparing` and `active` states while preserving the raw valve `station` entity.
- Diagnostic sensors for F79D fields 50 and 51: salt-dissolution time remaining and Pause 1 time remaining.
- Stable semantic mapping for known `systemCloseReason` codes while retaining the raw numeric reason code.
- Home Assistant brand icon/logo assets so current Home Assistant releases can load the integration artwork locally.
- Regression coverage for unit-dependent volume decoding, vacation semantics, system-close reasons, diagnostic countdowns and Home Assistant flow units.

### Fixed
- Correct F79D field 7 (`flowRateOff`) to little-endian in both read and write paths, matching the legacy WaterDevice codec. Field 11 remains big-endian because WaterDevice explicitly reverses that field.
- Decode F79D volume pairs 35/37/39/41 according to `waterVolumeUnit` instead of applying one universal formula.
- Correct the legacy unit-code-1 instantaneous-flow unit from L/h to L/min.
- Prevent stable vacation mode (`vacationPattern=1`, `station=8`) from keeping adaptive polling permanently in the fast interval.
- Clarify field 31 as low brine concentration rather than a generic salt-shortage alarm.

### Changed
- Withdraw the previous `HARDWARE_WRITE_VERIFIED` evidence from field 7 until the corrected little-endian implementation is physically revalidated. Earlier versions could self-confirm the wrong byte order by using the same interpretation on SET and GET.
- Apply the legacy application's vacation-mode state-machine guards: enter only from station 0 and exit only from stable station 8.
- Make Vacation mode a primary operational entity rather than a configuration-category entity.
- Restrict the generic administrator `write_fields` service to reversible configuration fields; mechanical/state-machine fields 34 and 49 must use purpose-specific controls.
- Add range and unit validation to the advanced raw-write service.
- Expand diagnostics with station, vacation state and interpreted system-close reason metadata.
- Update English, Catalan and Spanish translations, protocol documentation, hardware-verification guidance, README and release information.
- Replace version-specific README wording with an evergreen compatibility statement.

## [2.5.0] - 2026-09-11

### Added
- Read-only `Work pattern` enum for F79D field 9 using the exact legacy WaterDevice code mapping.
- Centralized transport-neutral semantic mappings for F79D station, unit, regeneration-pattern and work-pattern codes.
- Semantic protocol summary in Home Assistant diagnostics while retaining the raw controller state.
- Regression tests for work-pattern mapping and Home Assistant state-class choices.
- Documentation of the evidence behind each water-related Home Assistant `state_class`: legacy WaterDevice semantics, observed device behavior and Home Assistant statistics rules.

### Changed
- Correct Home Assistant statistics semantics: `averageWeeklyWaterConsumption` and `periodicWaterProduction` no longer declare `measurement`, because the former is already a historical aggregation and the latter is a controller configuration/cycle-capacity value rather than a present-time measurement or cumulative meter.
- Keep `dailyWaterConsumption` as `total_increasing`, and keep instantaneous flow and remaining treatment capacity as `measurement`.
- Explicitly record that `dailyWaterConsumption` is strongly supported as a daily-reset cumulative total by its app/protocol semantics and observed cross-day values, while a continuous within-day monotonic/reset trace remains a useful future validation rather than a prerequisite for the current state class.
- Improve regeneration-mode translations without changing the stable `flow` / `time` entity states.
- Clarify time-mode day labels and rename the salt configuration as salt added.
- Mark field 9 as observed on real hardware while keeping it read-only; no new mechanical writes are enabled.
- Document the verified cubic-metre volume/flow interpretation and keep cloud-only `regenerationTimes` intentionally unmapped locally.

## [2.4.1] - 2026-09-07

### Added
- Explicit stale-data diagnostics with physical-data age.
- Write-specific transport hook so stateful transports can avoid blind retries after ambiguous delivery.
- Explicit F79D duration write codec, while retaining the legacy `WRITE_TIME` compatibility symbol.
- End-to-end hardware-write evidence for device clock, continuous-flow limit, flow cutoff, regeneration time, salt addition and raw-water hardness.
- Translatable administrator-service errors in English, Spanish and Catalan.

### Changed
- Serialise the full `SET -> strict GET -> reconciliation` mutation sequence so writes and automatic clock correction cannot interleave semantically.
- BroadLink read retries now use independent transient and re-authentication budgets.
- BroadLink writes are sent at most once; a lost ACK is reconciled through physical read-back instead of being resent blindly.
- Rapid coalesced entity writes now make every caller await and receive the final physical success/failure result.
- Advanced services are registered at integration setup time rather than depending on a loaded config entry.
- Field 5 remains read-only in Home Assistant and was removed from the advanced safe-write whitelist.
- Flow-cutoff configuration is only enabled for the verified cubic-metre unit mode.
- State attributes are data-only; static Catalan descriptions were removed from recorder-facing attributes.
- Filter-media field 52 is named as a service interval rather than elapsed working days.
- Publication/audit version checks are version-agnostic instead of hardcoding 2.4.0.
- F79D fields 34 (forced regeneration) and 49 (vacation mode) remain explicitly pending physical write verification.

## [2.4.0] - 2026-09-07

### Added
- Home-Assistant-independent `runxin/` package with raw frame codec, declarative F79D field catalogue and transport-neutral `F79DClient`.
- `transport/` abstraction and isolated `BroadlinkBL3372Transport` implementation.
- Conservative per-field evidence/provenance metadata for interoperability research.
- Internal architecture, protocol, F79D, BroadLink transport, new-transport and new-device-profile documentation.
- Offline architecture regressions to ensure the reusable Runxin layer stays free of Home Assistant/BroadLink dependencies.

### Changed
- Split BL3372 TFB/session/encryption/retry concerns from F79D field/framing concerns without changing Home Assistant entities, config-entry identity or write verification behavior.
- Kept `api.py` and `protocol.py` as compatibility facades so existing integration imports/research helpers continue to work.
- Moved field-52 caching and write-settle policy to the Ypsilon composition layer instead of the reusable F79D client.
- Clarified that BroadLink outer error `-5` is empirically transient on the tested device; the exact internal MCU/UART cause is not proven.
- Expanded README/contribution guidance around protocol reuse and future extraction to a standalone Python package.

## [2.3.0] - 2026-09-07

### Added
- Apache-2.0 licensing, NOTICE, legal/interoperability and third-party documentation.
- Local custom-integration brand icon (light and dark variants).
- HACS validation, hassfest, offline-audit and automated GitHub Release workflows.
- GitHub issue forms, PR template, CODEOWNERS scaffold, Dependabot, contributing/security/code-of-conduct files.
- `scripts/configure_repository.py` and `scripts/publication_check.py` for safe first publication without guessing the maintainer's GitHub account.
- Public publishing checklist and release procedure.

### Changed
- Public display name standardized from `Ypsilon Local` to `Ypsilon`; domain remains `ypsilon_local` for compatibility.
- `hacs.json` reduced to the currently supported minimal metadata.
- README rewritten for public interoperability/HACS distribution and vendor-artifact hygiene.

## [2.2.1] - 2026-09-06
- Unified protocol regression tests into `scripts/audit.py`; removed the duplicated test path.

## [2.2.0] - 2026-09-06
- Added strict read-back verification after writes; stale coordinator data cannot confirm a SET.
- Added longer verification for mechanical regeneration transitions.
- Added regeneration mode and maximum regeneration interval.
- Moved maintenance flags, timing fields, operation/remaining days, model, polling mode, resin volume and filter working days to Diagnostics.
- Corrected residual-water semantics to remaining treatment capacity rather than physical storage.
- Fixed v1→v2 MAC migration and preserved registry identities where possible.
- Closed temporary config-flow clients and made advanced services administrator-only.
- Prevented stationary `valve closed` state from forcing permanent fast polling.
- Removed custom-component `strings.json`; added Spanish translation.
- Cleaned legacy Device Time / Wash start time registry entries.

## [2.1.0]
- Rejected incomplete multi-field volume values instead of publishing false zeroes.
- Rejected invalid time values before they could reach entities or clock calculations.
- Expanded protocol and consistency auditing.

## [2.0.0]
- Preserved the BroadLink client/session and field-52 cache across option reloads.
- Added explicit session close on entry removal and correct advanced-service lifecycle.
- Hardened device-clock correction so an optional clock check cannot invalidate a good poll.

## [1.9.0]
- Coalesced rapid repeated edits to reduce unnecessary writes to the slow valve link.
- Added the Active alerts aggregate sensor.
- Removed a non-existent leakage field from the alert model and added audit coverage.

## [1.8.0]
- Separated writable Device Time from read-only Wash start time semantics.

## [1.7.0]
- Continued entity/diagnostic cleanup and protocol hardening.

## [1.6.0]
- Improved adaptive polling and state handling.

## [1.5.0]
- Expanded controls and diagnostics while keeping writes restricted to verified field encodings.

## [1.4.0]
- Improved protocol/entity mapping and safety checks.

## [1.3.0]
- Improved coordinator behavior and integration diagnostics.

## [1.2.0]
- Added further local control and state decoding improvements.

## [1.1.0]
- Corrected flow scaling; raw field 11 is exposed through the appropriate configured unit family.
- Added adaptive polling.

## [1.0.0]
- Completed local bidirectional read/write support for verified F79D fields.
- Added multi-field control frames and robust ACK handling.
- Added post-write reconciliation and Home Assistant errors for failed writes.
- Moved runtime state to `ConfigEntry.runtime_data`, added reconfiguration, firmware information and advanced services.

## [0.8.0]
- Added bidirectional control, DHCP discovery and MAC-based identity/migration.
