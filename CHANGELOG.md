# Changelog

All notable changes to this project are documented here.

## [2.10.0] - 2026-10-11

### Changed
- **Moved to the `python-broadlink` distribution, pinned at `1.0.6`.** Home Assistant Core 2026.10 moved its own BroadLink integration to the same distribution. Both `broadlink` and `python-broadlink` unpack into the same `site-packages/broadlink/` module directory, so the previous `broadlink==0.19.0` requirement was installed over the top of core's copy and replaced `exceptions.py` with a version lacking `EndpointClosedError`. Core's BroadLink integration then failed to import and every BroadLink device in the installation lost its entities, including unrelated Hysen thermostats. Home Assistant compares only distribution names when checking requirements, so `python-broadlink==1.0.6` still counted as satisfied and was never reinstalled; recovery needs `ha core rebuild` or a core image replacement, not a restart. See home-assistant/core#184800.
- The transport, the F79D client, `YpsilonLocalClient` and the compatibility collector are now **asynchronous**. `python-broadlink` 1.0 made `hello`, `auth`, `get_fwversion` and `send_packet` coroutines with no synchronous compatibility layer; `decrypt` stayed synchronous. The eleven `async_add_executor_job` hops in `__init__.py`, `coordinator.py` and `config_flow.py` are gone and the integration awaits the library directly. `threading.Lock` became `asyncio.Lock` in the transport, the client and the adapter.
- Session teardown uses `await device.aclose()`. 1.0 owns the UDP endpoint and no longer exposes a `sock` attribute, in the transport and in the collector's teardown.
- `broadlink.hello()` raises `NetworkTimeoutError` instead of returning `None`, so the unreachable-device case is translated from that exception and the unreachable `if device is None` guards are removed.
- The compatibility collector's dependency gate now requires the `python-broadlink` 1.x line instead of exactly `broadlink==0.19.0`; its probe-error reason changed from `broadlink_0_19_0_required` to `python_broadlink_1_x_required`. The collector keeps its instance override of `send_packet` and its header, counter, device-type and MAC validation: `Device.count`, `Device.devtype` and `Device.mac` are unchanged in 1.0 and `send_packet` is still overridable.
- `requirements-test-offline.txt` and the documented dependency in `docs/broadlink-bl3372.md` and `docs/troubleshooting.md` follow the new pin in all three languages.

### Added
- A read transaction failing with `ConnectionClosedError` - including `EndpointClosedError`, new in `python-broadlink` 1.0.2 - now spends the existing session budget on one fresh session instead of failing outright. 1.0 keeps one persistent UDP endpoint per device, so a mid-request close is a new and recoverable failure mode. The write path deliberately does **not** retry it: a closed endpoint after submission is exactly the ambiguous case the write-once rule exists for.

### Notes
- `python-broadlink` 1.0 requires **Python 3.13 or newer**. The offline CI job already pinned 3.13 and the Home Assistant jobs 3.14.
- `python-broadlink` is `DAB-LABS/python-broadlink`, a maintained fork of `mjg59/python-broadlink`; the import name remains `broadlink`.
- The `runxin/` codec is unchanged and still imports neither `homeassistant` nor `broadlink`. Only the transport contract became awaitable.
- No wire-format change. Field encodings, per-model write permissions, the write-once rule and strict post-write read-back reconciliation all behave as in 2.9.3.
- The `ValueError` guard around authentication was written for a 0.19.0 defect and is retained unverified against 1.0.x, where it may no longer be reachable.

## [2.9.3] - 2026-10-10

- Correct only physically confirmed field-2 language labels: model 1/code 7 is Dutch and reference G6 model 9/code 3 is Spanish. Retain the reference enum for other model/code pairs, raw codes, disabled-by-default diagnostic entities and existing unique IDs. Add Dutch translations and model-aware enum options.
- Enable model-1 Device clock and manual Sync clock as ordinary validated controls, without experimental settings. Keep all reference sensor identities, default-off experimental fields 6/10/43/47, separate regeneration opt-in and blocked automatic correction. Update setup/options explanations and cached permission diagnostics.
- Record issue #17's two manual clock writes and restoration through manual clock sync as contributor-verified field-4 evidence for model 1. Other optional settings and regeneration start remain pending; only manual field-4 clock controls are enabled by default, with explicit opt-ins for the remaining tests and blocked automatic correction.
- Clarify the distinction between field-26 resin and fields 41–42 treatment capacity. Model-1 raw resin 240 and treatment-capacity reference 15 remain unscaled without assumed units; the nominal 24 L unit alone does not confirm the configured resin conversion. Update English/Catalan/Spanish evidence and comparison guides.
- Add per-model language and partial-write-evidence regressions. Preserve all wire codecs, queries, G6/Midnight controls, resin conversions, domain/config entries and model support levels (1/12 Alpha, 14 Beta).

## [2.9.2] - 2026-10-09

- Fix model-14/F136 resin volume by reading both field-26 bytes as U16 little-endian tenths of a litre. Issue #22's `[44, 1]` now displays 30.0 L instead of 4.4 L, matching the controller photo. Preserve original byte pairs and reference G6/model-12 decoding.
- Promote model 14 from Alpha to Beta and mark its resin conversion confirmed on the reported BL3372 0x520F / firmware 62016 unit. Record app-matched readings for 4/6/7/10/43/47 separately from contributor-verified writes to 4/6/10/43; writes to 7/47 and mechanical actions on 34 remain pending.
- Apply the model-specific read override to partial reads after identity discovery without adding device queries, writes or controls. Add regression coverage for the reported bytes, Home Assistant sensor/diagnostics and existing model behavior.
- Update English/Catalan/Spanish support, protocol and hardware-evidence documentation. Domain, config entries, entity IDs, write permissions and model-1/model-12 Alpha status remain unchanged.

## [2.9.1] - 2026-10-08

- Add explicit, default-off model-1 Alpha options for manual tests of clock (4), continuous-flow time (6), regeneration schedule (10), added salt (43) and hardness (47). All model-1 writes remain hardware-unverified; existing readings, raw bytes, unconfirmed units and disabled provisional statistics are retained.
- Add a separate default-off regeneration-start opt-in requiring the settings test mode. Keep the fresh service/vacation checks, single command and phase confirmation; block direct phase advancement, field 7, vacation writes and automatic clock correction.
- Apply opted-in permissions to entities, coordinator, administrator services and adapter. Revoke and replace sessions when test permissions change, preserving the field-52 cache and entity identities. Diagnostics distinguish default model policy from effective test permissions.
- Add EN/CA/ES options and validation instructions. G6 and Midnight control sets, codecs, conversions and identities are retained.

## [2.9.0] - 2026-10-08

- Publish a normal stable integration version; Alpha status remains scoped to models 1, 12 and 14.
- Add Euro-Clear Midnight 25 Runxin F136 / controller model 14 based on issue #22: reported working F79D reads and verified local writes to 4/6/10/43, with 7/34/47 pending. Reuse Midnight controls and strict fresh read-back without enabling vacation writes.
- Adopt Midnight resin scale 0.1 for model 14 from the reported shared map; expose its pending direct comparison in diagnostics and resin-sensor attributes. Preserve raw resin bytes.
- Identify model 12 as F105 in device metadata while retaining its entry title, unique IDs, conversions and controls.

- Add cached effective write-policy diagnostics that distinguish controller evidence, configured read-only restrictions and adapter session restrictions, without device I/O.
- Enforce recursive protocol/transport import boundaries and immutable action references in the offline audit.
- Pin workflow action source revisions, pin offline test tools and run the full suite against HA 2026.9.3 and 2026.9.4. Validator container images still follow upstream tags.
- Clarify shared protocol profiles, per-model permissions and standalone transport examples; align contribution/publishing guidance in English, Catalan and Spanish. No new write commands, conversions or domain migration.

## [2.9.0-alpha.1] - 2026-10-07

- Add controller model 1 (F150 API name) as read-only Alpha, based on issue #17's published 52-field report; app conversions remain provisional.
- Add explicit per-model write permissions, defaulting to no writes. Enforce read-only policy in setup, coordinator, services and composition adapter, including automatic clock correction. Preserve G6/model-12 control fields and conversions.
- Add read-only equivalents for normally writable settings, raw field-pair diagnostics, unscaled resin/per-cycle readings without assumed units and no provisional long-term statistics.
- Add English/Catalan/Spanish pilot guides and multi-model architecture/policy documentation; document issue #17's app-pairing workaround as one reported case.
- Close discovery sockets on failed authentication, reject too-short inner frames as protocol errors and require matching query/write response opcodes.
- Mark hyphenated release versions as prereleases without replacing stable latest. The ypsilon_local domain and existing identities stay unchanged; PR #24 migration remains separate.

## [2.8.0] - 2026-10-07

- Rename the public project and visible integration to **Runxin Local**, with repository `Danirv/runxin-local`. Keep the `ypsilon_local` domain, folder, services and existing unique IDs.
- Offer an opt-in, bounded read-only compatibility report inside Home Assistant for unlisted controllers and setup failures. No external Python environment or model-registry edit is required.
- Preserve raw bytes, unmapped numeric codes, missing fields and timestamps; identify controller enum names without extending supported models. No model-specific resin scale is applied to research reports.
- Store reports locally in diagnostic-only entries with no entities, polling, clock correction or write methods. Reload/download performs no new scan; deletion removes the saved report. Advanced write services reject these entries.
- Add prepared issue summaries, instructions and compatibility-report template fields. Existing G6/model-12 polling, control encodings and per-model scaling are retained.

## [2.7.2] - 2026-10-05

### Fixed
- Show unmapped enum codes as their decimal device value (for example relay `2` and work pattern `255`), with valid Home Assistant enum options and the existing `raw_code` attribute. Known state keys/translations are unchanged; missing readings still report unknown.
- Guard the regeneration button with a fresh service/vacation read under the write lock, and reject overlapping regeneration requests. The existing field-34 value-1 command and single-write/read-back reconciliation are retained. Explicit advanced phase control keeps its existing policy.
- Confirm the ticking device clock across a one-minute rollover, including midnight, only within 60 seconds of sending the write and with fresh pre-write evidence that the next-minute value changed. An unchanged next-minute value never confirms an ignored or ambiguously delivered write. Regeneration schedules and other settings still require exact read-back. Automatic sync samples the target clock after acquiring the write lock.

### Added
- Real Home Assistant regressions for enum state/options transitions, G6 and model-12 regeneration guards, ambiguous/ignored writes and clock reconciliation.
- Model-12 documentation of the manufacturer hardness convention and the limits of the enum investigation. No reliable field-9/24 mapping for codes 255/2 was found in the consulted manuals; WaterCare shares this project's mapping and is not independent evidence.

### Notes
- Model 12 remains Alpha with the same pending hardware validations. G6 codecs, units, numeric ranges, command bytes and known enum labels are unchanged. Software tests do not certify physical valve actions.

## [2.7.1] - 2026-10-05

### Added
- Connection troubleshooting in English, Catalan and Spanish, plus `scripts/debug_connection.py`: one discovery/authentication attempt and an optional firmware read, with a sanitized JSON report and no configuration/mechanical writes.
- Non-identifying connection debug logs and transport diagnostics for stage, discovered device type, advertised lock and latest error type/code. Failed setup emits a useful warning before a config entry exists.
- Regression tests for rejected/false authentication, timeouts, successful authentication despite an advertised lock, all setup paths and report/log privacy.

### Fixed
- Distinguish a rejected local BroadLink handshake from generic connection failures in setup, DHCP confirmation and reconfiguration. Show a separate message when the rejected device also advertises a local-control lock.
- Handle malformed authentication replies that make BroadLink's AES setup raise `ValueError` as transport failures, without mislabelling them as lock/rejection. The standalone report also captures unexpected library errors without emitting private exception text or a traceback.

### Notes
- Improves diagnosis of issue #17; it does not claim to fix the physical device's authentication rejection or prove that cloud pairing caused it.
- Authentication keys/handshake, retry budgets, F79D encodings, commands and model-12 Alpha support remain unchanged. No automatic unlock, reset, provisioning or alternative key path is introduced.

## [2.7.0] - 2026-10-04

### Added
- Experimental / Alpha support for the **Euro-Clear Midnight** (ECOPRO+ head), which reports Runxin controller model **12** behind the same BroadLink BL3372 (`0x520F`). A full read of fields 1–52 from a real Midnight 25 decodes consistently with the F79D map: clock, hardness, salt, programme times, capacity and volumes all match the controller. The captured frames are kept as regression tests.
- `models.py`: the accepted controller models with their entry title, device-registry model and manufacturer, kept free of Home Assistant imports so they can be unit-tested.
- Per-model support and hardware-write evidence in diagnostics, without changing control availability or write policy.
- Both raw field-26 resin bytes retained in state and the resin sensor's attributes, preserving the original decoding/scaling.
- Home Assistant 2026.9.4 regressions for config flow, entity states/identity, controls and redacted diagnostics, in a separate CI job.

### Changed
- Setup and DHCP discovery accept models 9 and 12. The config entry and device are named after the reported model.
- Resin volume is scaled per model. Model 12 reports tenths of a litre (raw 250 on a 25 L Midnight 25).
- Enum sensors report an unrecognised controller code as unknown rather than raising, keeping the code in `raw_code`. Model 12 reports output relay mode 2.

### Notes
- Alpha is scoped to model 12; existing G6 support is unchanged. No new codec, command sequence, range or device write is introduced by the review follow-up.
- The observed resin capture `FA 00` validates 25 L on Midnight 25, not the meaning of the second byte or resin values above 25.5 L. Raw bytes remain available for follow-up investigation.
- Model 12 controls use the same field encodings as model 9. On the Midnight 25, local writes to fields 4 (clock), 6 (continuous-flow limit), 10 (regeneration time) and 43 (salt added) were hardware-verified with the documented baseline → set → fresh read → restore → fresh read sequence, with no side effects on other fields. Fields 7 and 47 and forced regeneration use the same encodings and the existing read-back reconciliation, but are not yet hardware-verified on model 12.

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
