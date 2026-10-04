# Ypsilon for Home Assistant

Local Home Assistant integration for compatible water softeners using a **Runxin F79D** controller and **BroadLink BL3372** Wi-Fi module, including the ATH/BWT Ypsilon G6 tested by this project.

The integration communicates directly over the LAN and does not depend on the vendor cloud for normal operation.

> **Status:** community integration, independently developed for interoperability. Not affiliated with or endorsed by ATH, BWT, Runxin or BroadLink.

## Highlights

- DHCP discovery for known compatible BroadLink module prefixes.
- Local polling with adaptive fast polling while water is flowing or the valve is mechanically moving.
- Real device-state reconciliation after writes: a transport ACK is never treated as proof that the requested state was physically adopted.
- Water consumption, remaining treatment capacity and instantaneous flow entities with unit-aware F79D decoding.
- Regeneration status, work pattern, maintenance reminders and diagnostics.
- Read-only vacation status derived from the controller's field-49 flag and physical valve phase.
- Safe controls for hardness, salt-addition bookkeeping, leak-protection thresholds, regeneration schedule and clock.
- Forced regeneration with a mechanical-state confirmation window.
- Administrator-only advanced services restricted to known reversible fields.
- Catalan, Spanish and English translations.
- Transport-neutral, Home-Assistant-independent **Runxin/F79D protocol layer** separated from the BroadLink BL3372 transport.
- Declarative 52-field F79D catalogue with conservative evidence/provenance metadata.
- Offline protocol, entity, translation, branding and architecture regression checks in `scripts/audit.py`.
- Proper square icon and landscape logo assets under `custom_components/ypsilon_local/brand/`.

## Supported hardware

Supported Home Assistant targets (BroadLink BL3372 module, devtype `0x520F`):

| Product | Runxin controller model (field 1) | Evidence |
|---|---|---|
| ATH/BWT Ypsilon G6 | 9 (F79D) | Reads and writes verified on hardware |
| Euro-Clear Midnight (ECOPRO+ head) | 12 | Full state read decodes consistently with the F79D map. Writes use the same encodings and are confirmed by read-back, but are not yet hardware-verified |

Other rebranded devices using the same controller/module may work, but compatibility must be verified per model and firmware. Separating protocol and transport does **not** imply that every Runxin or non-BroadLink device is supported.

## Installation

### HACS

Until the repository is accepted into the HACS default catalog, add it as a custom repository:

1. HACS → **Integrations** → menu → **Custom repositories**.
2. Add `https://github.com/Danirv/ypsilon-local` as an **Integration**. For Euro-Clear Midnight (model 12) support before it is merged upstream, use the fork `https://github.com/kriziw/ypsilon-local` instead.
3. Install **Ypsilon** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and search for **Ypsilon**.

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

Configuration controls include raw-water hardness, **added salt amount**, continuous-flow safety time, maximum flow cutoff, regeneration trigger time and device clock.

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

Ypsilon combines recovered application knowledge with physical-controller evidence. For the tested Ypsilon G6:

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

`write_fields` only accepts known reversible configuration fields and applies range/unit validation. Field 49 vacation control is intentionally excluded from the Home Assistant write surface because it has not been physically confirmed on the tested current firmware.

## Reusing the protocol work

```text
Home Assistant -> Ypsilon policy -> F79D client/codec -> raw Runxin frame
                                                     -> transport -> device
```

`custom_components/ypsilon_local/runxin/` contains no Home Assistant or BroadLink imports. `transport/broadlink_bl3372.py` owns the BroadLink-specific envelope/session logic.

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

GitHub CI includes HACS validation, hassfest, the offline audit and release-tag/version checks.

## Branding

Home Assistant can load local brand assets shipped by custom integrations. Ypsilon provides separate assets for their actual roles rather than reusing one square PNG for everything:

- `icon.png` / `icon@2x.png`: square artwork with safe padding for circular/square crops;
- `logo.png` / `logo@2x.png`: landscape Ypsilon Local wordmark;
- matching dark variants on transparent backgrounds.

HACS presentation depends on the HACS/Home Assistant frontend version and caching; the repository itself provides correctly proportioned local assets instead of a square image masquerading as a landscape logo.

## Interoperability and legal notice

The local protocol implementation was independently developed through interoperability research and validation against observed device behavior. No vendor APK, firmware, proprietary binary, pairing/private key, credential or substantial decompiled vendor source is distributed with this project.

See [LEGAL.md](LEGAL.md), [THIRD_PARTY.md](THIRD_PARTY.md), [SECURITY.md](SECURITY.md) and [LICENSE](LICENSE).

## Sponsorship

Optional funding links are configured through `.github/FUNDING.yml`. Funding never changes functionality or support priority.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
