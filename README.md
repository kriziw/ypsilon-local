# Runxin Local for Home Assistant

Local Home Assistant integration for water softeners with compatible **Runxin controllers** and a **BroadLink BL3372** Wi-Fi module. Tested hardware includes **ATH/BWT Ypsilon G6 (F79D, model 9)** and **Euro-Clear Midnight 25 variants (F105 / model 12 and F136 / model 14)**.

Previously **Ypsilon / ypsilon-local**. The project and visible integration are now **Runxin Local**. The Home Assistant domain, installation folder, service names and existing unique IDs remain `ypsilon_local`; existing installations do not need to remove/re-add their devices or edit their automations because of the name change. GitHub redirects the previous repository URL after the rename; use the new URL for new installations.

**Other controller?** Version 2.8.0 adds a local **read-only compatibility report inside Home Assistant**. You do not need a Python environment or a modified model registry. See [collecting a compatibility report](docs/compatibility-report.md). Recognising a controller's name does not automatically enable its controls.

The integration communicates directly over the LAN and does not depend on the vendor cloud for normal operation.

> **Status:** community integration, independently developed for interoperability. Not affiliated with or endorsed by ATH, BWT, Runxin or BroadLink.

## Highlights

- DHCP discovery for known compatible BroadLink module prefixes.
- Local polling with adaptive fast polling while water is flowing or the valve is mechanically moving.
- Real device-state reconciliation after writes: a transport ACK is never treated as proof that the requested state was physically adopted.
- Water consumption, remaining treatment capacity and instantaneous flow entities with unit-aware F79D decoding.
- Regeneration status, work pattern, maintenance reminders and diagnostics.
- Read-only vacation status derived from the controller's field-49 flag and physical valve phase.
- On models with explicit write permission, controls for hardness, salt-addition bookkeeping, leak-protection thresholds, regeneration schedule and clock.
- On models with explicit write permission, forced regeneration with a mechanical-state confirmation window.
- Administrator-only configuration and phase-advance services with range validation and fresh read-back.
- Catalan, Spanish and English translations.
- Transport-neutral, Home-Assistant-independent **Runxin/F79D protocol layer** separated from the BroadLink BL3372 transport.
- Declarative 52-field F79D catalogue with conservative evidence/provenance metadata.
- Offline protocol, entity, translation, branding and architecture regression checks in `scripts/audit.py`.
- Proper square icon and landscape logo assets under `custom_components/ypsilon_local/brand/`.

The regeneration button starts only after a fresh reading confirms service state with vacation off, and rejects overlapping requests. It sends the same single command and verifies the resulting phase. Unmapped enum values appear as decimal codes with `raw_code`; known labels follow the reference map or confirmed per-model exceptions and absent readings remain `unknown`. Clock confirmation allows one ticking minute within 60 seconds of the write, including midnight, only when a fresh pre-write reading proves the next-minute value changed; regeneration schedules still require exact confirmation.

## Supported hardware

Supported Home Assistant targets (BroadLink BL3372 module, devtype `0x520F`):

| Product | Runxin controller model (field 1) | Support | Evidence |
|---|---|---|---|
| Unbranded device reported in issue #17 | 1 (F150 API name) | **Alpha readings; validated manual clock controls** | All 52 fields received; optional manual configuration/start tests in 2.9.1; manual clock writes/sync verified; other writes and numeric app conversions pending |
| ATH/BWT Ypsilon G6 | 9 (F79D) | Reference hardware | Per-field read/write evidence documented in the hardware verification guide |
| Euro-Clear Midnight (ECOPRO+ head) | 12 (F105 API name) | **Experimental / Alpha**, tested on Midnight 25 | Captured state matches the controller. Writes to fields 4, 6, 10 and 43 hardware-verified; fields 7 and 47 and mechanical field-34 actions remain available for testing but are not yet hardware-verified on this model |
| Euro-Clear Midnight (F136 / ECOPRO+ head) | 14 (F136) | **Beta**, tested on Midnight 25 | Working v2.9.1 installation; app-matched reads 4/6/7/10/43/47; controller-confirmed resin 30.0 L from U16 LE tenths. Writes 4/6/10/43 verified; writes 7/34/47 pending |

**2.9.3 is a normal stable integration release. Support status is per model:** model 1 has Alpha readings, validated manual clock controls and optional tests for other settings; model 12 remains Alpha; model 14 is Beta with confirmed resin decoding and documented pending writes. The Midnight controls and strict fresh read-back remain available; the label does not disable commands or imply that pending actions are verified. See the [model-12 evidence](docs/hardware-verification.md#euro-clear-midnight--controller-model-12) and [model-14 guide](docs/model-14-alpha.md).

Diagnostics include per-model support/evidence metadata and both raw field-26 resin bytes. Model 12's observed `FA 00` still displays as **25 L**, retaining its U8 decode because that capture does not establish the high byte's meaning. Model 14's `[44, 1]` now uses **U16 little-endian × 0.1 = 30.0 L**, matching its controller photo. This is the configured resin value, distinct from nominal physical capacity; the setting is not changed.

Other rebranded devices using the same controller/module may work, but compatibility must be verified per model and firmware. Separating protocol and transport does **not** imply that every Runxin or non-BroadLink device is supported.

Device-language labels follow confirmed controller observations where available: model 1/code 7 is Dutch, and G6 model 9/code 3 is Spanish. Other pairs keep the reference mapping and unknown codes remain visible. See [language evidence](docs/f79d-settings.md#controller-language-evidence-293).

For model 1, see the [Alpha comparison and write-testing guide](docs/model-1-alpha.md). Numeric readings are provisional; resin and per-cycle quantity have no assumed units, and provisional numeric readings do not generate long-term statistics. Device clock and manual Sync clock are validated and available without experimental options. Other model-1 write tests are off by default and can be enabled in the integration options; regeneration start has a separate opt-in. Automatic clock correction, flow-cutoff writes and phase advancement stay blocked. The policy preserves G6/Midnight controls and conversions.

## Installation

### HACS

Until the repository is accepted into the HACS default catalog, add it as a custom repository:

1. HACS → **Integrations** → menu → **Custom repositories**.
2. Add `https://github.com/Danirv/runxin-local` as an **Integration**.
3. Install **Runxin Local** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and search for **Runxin Local**.

The repository has been submitted to the HACS default-catalog review queue as `hacs/default#10717`.

### Manual

Copy `custom_components/ypsilon_local` into `/config/custom_components/ypsilon_local` and restart Home Assistant.

## Entity model

Primary operational entities include:

- **Flow rate**
- **Daily consumption**
- **Controller weekly average consumption**
- **Remaining treatment capacity**
- **Operating status**
- **Regeneration mode**
- **Work pattern**
- **Vacation status** (read-only)
- **Active alerts**

On models with explicit write permissions, configuration controls include raw-water hardness, **added salt amount**, continuous-flow safety time, maximum flow cutoff, regeneration trigger time and device clock.

Maintenance flags, wash-phase timings, salt-dissolution/pause countdowns, resin volume, filter-media interval, model, polling mode and communication telemetry are exposed as **diagnostic** entities so the normal device page stays focused on operational state.

### Vacation status: read-only by design in 2.6.1

The recovered legacy WaterDevice product codec can encode field 49 (`holidayMode`) as `1`/`0`, and the legacy embedded UI contains direct `holidayMode` control calls. However, a real local test on the project's Ypsilon G6 with v2.6.0 produced a transport ACK while fresh read-back remained `vacationPattern=false`.

The newer RunLucky application also exposes dedicated cloud operations for entering and leaving vacation mode rather than relying only on the generic control endpoint. Because the exact current-firmware local action has not been proven, **v2.6.1 withdraws the writable Vacation mode switch instead of guessing a mechanical sequence**.

The integration still reads field 49 and exposes a separate **Vacation status** enum:

- `off`: vacation flag is not set;
- `preparing`: vacation flag is set and the valve has not reached the stable vacation position;
- `active`: vacation flag is set and `station == 8`.

The raw **Operating status** entity remains available independently. Adaptive polling treats an observed stable vacation state as idle; transition phases continue using fast polling.

## Water quantities and statistics

The integration intentionally distinguishes controller counters from derived/history views:

For provisional model-1 readings, long-term statistics are disabled until the conversions are calibrated. The following semantics apply to the existing validated presentation.

- **Daily consumption** (fields 37–38) is the controller's within-day cumulative counter. Observed hardware history confirms it rises during the day and resets around the day boundary. It therefore uses Home Assistant `TOTAL_INCREASING` semantics so resets are treated as meter-cycle resets rather than negative consumption.
- **Controller weekly average consumption** (fields 39–40) is the current average value reported by the controller. It is **not** the same quantity as the vendor app's week-by-week history chart, which is obtained from a separate statistics service. It deliberately has no Home Assistant `state_class`.
- **Treatment capacity per cycle** (fields 41–42) is a controller treatment/cycle quantity, not a cumulative water meter. It deliberately has no `state_class`.
- **Remaining treatment capacity** (fields 35–36) is a current controller value and is exposed as a measurement.

Older Ypsilon releases briefly declared long-term statistics for the weekly-average and cycle-capacity entities. After upgrading, Home Assistant may offer to remove those obsolete historical statistics because the corrected entities no longer declare a `state_class`. Removing those obsolete statistic rows does not remove the entities or their normal recorder history.

For a true current-week total in Home Assistant, derive it from **Daily consumption** / recorder statistics rather than treating field 39 as the current-week total.

## Salt semantics

Field 43 is the value called `addSalt` by the legacy application. The vendor UI exposes it as a **0–100 kg amount of salt added** and sends it as a normal control value. The project's hardware has also confirmed field-43 write/read-back behavior.

It is **not a measured salt-tank level** and the integration does not automatically subtract salt after regeneration. Salt-related physical warnings are separate controller signals:

- field 31: low brine concentration;
- field 33: salt-box / add-salt reminder flag.

This distinction is intentional: a configured bookkeeping value must not be presented as a physical level sensor.

## Water units and F79D codec notes

Runxin Local combines recovered application knowledge with physical-controller evidence. For the tested Ypsilon G6:

- field 7 (`flowRateOff`) is **16-bit big-endian** in both read and write paths and is `HARDWARE_WRITE_VERIFIED`;
- field 11 (`flowRate`) is also **big-endian** on the wire;
- volume pairs 35/37/39/41 are decoded according to field 8 (`waterVolumeUnit`), rather than through one universal formula;
- legacy flow labels are `gpm`, `L/min`, and `m³/h` for unit codes 0, 1 and 2 respectively.

The decisive field-7 hardware vector is `03 E8`: big-endian gives raw 1000 / 10.00 m³/h, matching the vendor app; the regressed little-endian interpretation gives raw 59395 / 593.95 m³/h. A 2.00 m³/h write is raw 200 and must be sent as `00 C8`. The 2.6.x LE regression sent `C8 00`; the controller ACKed transport but fresh read-back did not adopt the requested value, and Ypsilon correctly rejected the write.

Only unit code 2 has been calibrated end-to-end against the project's physical Ypsilon G6. Field 7 remains exposed only in that unit family and is constrained to **0.00–10.00 m³/h** (raw 0–1000).

The recovered legacy WaterDevice path appeared to use little-endian for field 7. That discrepancy is retained in the research documentation, but observed controller bytes and independent physical read-back take precedence for the tested hardware.

## Water dashboard

Use **Daily consumption** as the consumed-water source. **Flow rate** is optional and represents the latest instantaneous sample; short draws that begin and end entirely between idle polls may not appear in the instantaneous entity, while the controller's cumulative daily counter remains authoritative.

## State verification and safety

The design deliberately separates:

1. command sent;
2. transport/protocol response;
3. fresh physical state returned by the controller;
4. Home Assistant entity state.

Writes are sent once and reconciled through a strict fresh read. Ambiguous delivery is never resolved by blindly sending the same mechanical command again. The field-7 LE regression is a concrete example of this mechanism working correctly: the controller ACKed the request, but the unmatched fresh read-back prevented Home Assistant from reporting a false successful write.

This software can change water-softener settings and start mechanical operations. It is not a certified safety controller and should not be the sole flood/leak protection mechanism.

## Advanced services

The integration exposes administrator-only services:

- `ypsilon_local.write_fields`
- `ypsilon_local.advance_phase`

Both services reject read-only model entries. `write_fields` only accepts known reversible configuration fields and applies range/unit validation. Field 49 vacation control is intentionally excluded from the Home Assistant write surface because it has not been physically confirmed on the tested current firmware.

## Model and protocol policy

Controller identity, protocol profile, transport and commercial product are separate. Models that share a proven field map reuse the codec with per-model permissions/conversions; an unrelated Runxin family needs its own profile. Manufacturer enum names do not grant support. See the [architecture](docs/architecture.md) and [support matrix](docs/model-support.md).

## Reusing the protocol work

The HA layer applies model policy, the F79D client builds/decodes raw Runxin frames, and the selected transport carries them to the device.

`custom_components/ypsilon_local/runxin/` contains no Home Assistant or BroadLink imports. `transport/broadlink_bl3372.py` owns the BroadLink-specific envelope/session logic.

Connection setup fails? See the [connection troubleshooting guide](docs/troubleshooting.md), including rejected authentication and a standalone sanitized probe.

Documentation is organised by use in the [documentation index](docs/index.md).

Developer/research documentation:

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/protocol.md`](docs/protocol.md)
- [`docs/f79d.md`](docs/f79d.md)
- [`docs/hardware-verification.md`](docs/hardware-verification.md)
- [`docs/waterdevice-audit.md`](docs/waterdevice-audit.md)
- [`docs/broadlink-bl3372.md`](docs/broadlink-bl3372.md)
- [`docs/adding-a-transport.md`](docs/adding-a-transport.md)
- [`docs/adding-a-device-profile.md`](docs/adding-a-device-profile.md)

## Development

Run the complete offline regression audit:

```bash
python scripts/audit.py
```

Before publishing:

```bash
python scripts/publication_check.py
```

GitHub CI includes HACS validation, hassfest, the offline audit, the complete test suite with HA 2026.9.3/2026.9.4 and release-tag/version checks. See [development instructions](CONTRIBUTING.md).

## Branding

Home Assistant can load local brand assets shipped by custom integrations. Runxin Local provides separate assets for their actual roles rather than reusing one square PNG for everything:

- `icon.png` / `icon@2x.png`: square artwork with safe padding for circular/square crops;
- `logo.png` / `logo@2x.png`: landscape Runxin Local wordmark;
- matching dark variants on transparent backgrounds.

HACS presentation depends on the HACS/Home Assistant frontend version and caching; the repository itself provides correctly proportioned local assets instead of a square image masquerading as a landscape logo.

## Interoperability and legal notice

The local protocol implementation was independently developed through interoperability research and validation against observed device behavior. No vendor APK, firmware, proprietary binary, pairing/private key, credential or substantial decompiled vendor source is distributed with this project.

See [LEGAL.md](LEGAL.md), [THIRD_PARTY.md](THIRD_PARTY.md), [SECURITY.md](SECURITY.md) and [LICENSE](LICENSE).

## Sponsorship

Optional funding links are configured through `.github/FUNDING.yml`. Funding never changes functionality or support priority.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
