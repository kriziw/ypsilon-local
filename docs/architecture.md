# Architecture

[English](architecture.md) | [Català](architecture.ca.md) | [Español](architecture.es.md)

Runxin Local separates transport, wire profile, controller policy and Home Assistant presentation. **Controller model is not protocol profile**: multiple models can share a proven codec with different units, permissions or applicability; an unrelated family needs a different profile.

## Responsibilities

| Layer | Responsibility | Boundary |
|---|---|---|
| `transport/` | BroadLink discovery/authentication, encryption, TFB envelope, sockets and bounded retries | Carries raw Runxin frames; does not decode fields or choose units |
| `runxin/framing.py` | Observed envelope, length/checksum validation and opcodes | No HA/BroadLink dependency |
| `runxin/fields.py`, `f79d.py`, `semantics.py` | Current F79D catalogue, byte codecs and reference semantic labels | 52 fields are not a universal Runxin limit; G6 evidence is not every model's evidence |
| `runxin/client.py` | Serialized protocol transactions, optional raw field-pair capture and matching response opcodes | Transport-neutral; does not grant HA model compatibility or controls |
| `models.py` | Accepted identities, profile association, model conversions, uncertainty, effective permissions and evidence | New models default to no writes; API names are descriptive only |
| `api.py` | Composition adapter for the currently proven F79D-compatible models on BL3372; field-52 cache and settle timing | Blocks writes before transport when model permission is absent; no packet/crypto implementation |
| `coordinator.py` | HA polling, stale state, adaptive cadence and serialized write reconciliation | Enforces model policy for every mutation, including automatic clock sync |
| Entity platforms / `services.py` | Presentation, applicable controls and administrator services | Do not construct packets; hiding a control is not the only write guard |
| `compatibility.py` / `diagnostic_report.py` | Explicit bounded one-time read-only investigation and cached report storage | Separate from continuous polling; saved diagnostic entries never create a normal client |

## Current extension strategy

The existing split is suitable for the models now observed. Reuse the shared F79D catalogue for a compatible controller and put proven model differences in the registry/presentation policy. Avoid copied `model_1.py`, `model_12.py`, etc. with duplicate packet tables.

`protocol_profile` records the currently shared `f79d` path; it is **not yet a runtime factory for arbitrary codecs**. Setup still probes the observed F79D identity fields, and the composition adapter remains F79D/BL3372-specific. If a second genuinely different local profile is captured, add an explicit profile descriptor/selector (identity/read sets/catalogue/decoder/encoder), preserve `F79DClient`/`protocol.py` as compatibility facades and route the adapter through that proven profile. Do not create speculative RO/F104 codecs from cloud DTO names.

The same rule applies to another transport: implement the raw-frame contract independently, then explicitly select it only for demonstrated hardware. BroadLink `0x520F` alone does not identify the Runxin field map.

## Invariants

- Protocol modules do not import HA/BroadLink; transport base does not import model field definitions.
- Field receipt, physical meaning, unit calibration, theoretical encoding and effective write permission are separate evidence levels.
- `allowed_write_fields` defaults empty. Model 1 explicitly allows verified manual field 4; opted-in tests of remaining settings use a separate field policy enforced by the coordinator and adapter. Automatic clock correction and field 7 remain blocked. Regeneration start has a separate opt-in; direct phase advancement is blocked.
- Models 9/12 retain their original write surface and conversions, including explicitly documented pending actions.
- Model 14 has Beta support and reuses the Midnight write surface based on issue #22; reported reads, verified writes and pending writes are recorded separately. Its field-26 U16 LE read override lives in `runxin/fields.py`; the client reuses a validated identity for partial reads, without extra I/O. G6/model-12 defaults remain unchanged.
- Per-model byte-order/unit/enum changes require independent fixtures and regression coverage for all existing models.
- An ACK alone never confirms physical state. Writes are not blindly retried after ambiguous delivery.
- Unknown enum codes remain visible; missing fields are not invented as zero/false.
- Provisional readings do not create long-term statistics; raw field pairs support later calibration.
- The normal 1..51 read and separately cached field 52 stay unchanged. Cached field-52 bytes are not a simultaneous full snapshot.
- Domain `ypsilon_local`, config-entry version 2, MAC identities, existing unique IDs and compatibility facades are retained. PR #24's domain migration is a separate pilot.

The pure protocol layer remains extractable inside this repository. A separate PyPI package is deferred until another real consumer justifies release/dependency overhead. Do not make another custom integration depend on an installed `custom_components.ypsilon_local` at runtime.

See the [support matrix](model-support.md), [profile guide](adding-a-device-profile.md) and [compatibility reports](compatibility-report.md).

The offline audit checks nested relative imports and transport dependencies. Exported `write_policy` distinguishes model evidence from configured/coordinator/adapter restrictions using cached metadata. For test environments and CI coverage, see [CONTRIBUTING](../CONTRIBUTING.md).
