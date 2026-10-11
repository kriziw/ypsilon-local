# Adding another Runxin device profile

Do not copy the F79D table and rename it. Treat another controller as unverified until read-only evidence establishes what is shared. A compatible controller may reuse the existing wire profile with model-specific policy; shared framing does not establish identical physical semantics.

## Controller policy versus wire profile

First check whether the new controller shares a demonstrated existing map. If it does, reuse the codec and add a `ControllerModel` entry with evidence, explicit `allowed_write_fields`, conversion uncertainty and applicable entities. The default write set is empty. A read-only Alpha can expose provisional readings before unit calibration, but must block clock correction, services and direct adapter writes and suppress provisional statistics. Do not inherit G6 write evidence.

If bytes/enums/scales differ, add proven model-specific overrides and fixtures without changing G6/Midnight defaults. If the frame/map is different, add a separate profile and explicit selector; `protocol_profile` currently documents the shared path and is not a general codec factory. Tests must cover missing fields, unmapped values, permission bypasses, restarts and legacy identities.

See [support policy](model-support.md) and [model 1](model-1-alpha.md).


## Suggested workflow

1. Identify the controller/model and transport independently.
2. Capture read-only traffic first.
3. Confirm whether the raw frame format matches `runxin/framing.py`.
4. Establish the model/identity field and a minimal safe read set.
5. Build a declarative field catalogue with explicit codecs and evidence.
6. Add offline golden-frame/regression tests.
7. Only then investigate writes, one field at a time, with physical read-back.
8. Keep Home Assistant controls narrower than the protocol's theoretical write
   capability until ranges and consequences are understood.

## Reusing the shared framing

If the new device uses the same `5A 5C` / `DF FD` envelope and request/response
opcodes, reuse `runxin/framing.py`. If not, add a separate framing implementation
rather than weakening validation to accept unrelated packet formats.

## Field catalogue

Use `FieldSpec` / `FieldCodec` from `runxin/fields.py` as the pattern. Keep:

- field id;
- stable semantic name;
- read codec;
- known write codec, if any;
- unit/scaling notes;
- provenance/evidence.

Avoid hiding uncertainty. `inferred` is preferable to presenting a guess as a
verified protocol fact.

## Home Assistant support is a separate decision

A reusable profile can exist in the repository before the Runxin Local integration
supports it. Adding it to automatic discovery/config flow requires additional
work: model naming, device identity, entity applicability, safe-write policy,
translations, diagnostics and real-device testing.

This separation lets reverse-engineering work be useful without pretending a
new model is production-ready.

## Evidence hygiene

Submit sanitised captures, decoded field tables and independently written test
fixtures. Do not commit vendor APKs, firmware, decompiled source dumps, private
keys, credentials or secrets.
