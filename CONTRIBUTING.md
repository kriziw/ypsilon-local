# Contributing

Contributions are welcome. The project prioritizes reliable local control,
explicit state reconciliation, conservative mechanical writes, and reusable
interoperability knowledge.

## Before opening a pull request

1. Install `requirements-test-offline.txt` in an isolated Python environment and run `python -m pytest -q`. Then run `python scripts/audit.py` and `python scripts/field_surface_audit.py`.
2. Run `python scripts/publication_check.py` in a configured public clone.
3. Run `python -m compileall -q custom_components/ypsilon_local scripts tests`.
4. Keep user-facing strings in the translation files (`en`, `ca`, `es`).
5. Prefer small, reviewable changes and preserve entity/config-entry unique ids
   unless a migration is provided.
6. For writes, distinguish command transport, protocol ACK and confirmed
   physical device state.

## Commit messages

Releases are produced by release-please, which reads **Conventional Commit**
subjects on `main`. A commit that does not parse is simply not mentioned in
the changelog, and a run of such commits means no release is proposed at all.

Use the type that matches the change:

| Type | Changelog section | Version bump |
|---|---|---|
| `feat:` | Added | minor |
| `fix:` | Fixed | patch |
| `perf:` / `refactor:` | Changed | patch |
| `docs:` | Notes | patch |
| `chore:` / `test:` / `ci:` / `build:` | hidden | none |

A `!` after the type, or a `BREAKING CHANGE:` footer, forces a major bump.

**Squash-merge pull requests.** The PR title then becomes the commit subject
on `main`, which is what release-please reads. A merge commit puts the
*branch's* subjects on `main` instead, and if those do not conform there is no
release - release-please succeeds and simply opens no pull request, so nothing
tells you. That is what happened with #4, which shipped as a merge commit
titled "Sync to upstream 2.9.3 and re-apply the python-broadlink migration"
and produced no release until one was cut by hand.

`.github/workflows/pr-title.yml` now fails a pull request whose title is not a
Conventional Commit, so the two halves cannot drift apart again.

Hand-written detail still matters here. The changelog for this project records
physical evidence - wire bytes, raw values, what the vendor application showed
- and release-please cannot invent that. Put it in the commit body, or edit
`CHANGELOG.md` directly in the release pull request before merging it.

## Architecture boundaries

The default CI keeps protocol tests lightweight. For config-flow/entity/control
regressions with real Home Assistant classes, use Python 3.14, install
`requirements-test-ha.txt`, and run `python -m pytest -q`.
That job uses mocked device I/O and does not establish hardware-write evidence.

Read [`docs/architecture.md`](docs/architecture.md) before protocol work.

- `runxin/` must remain independent of Home Assistant and BroadLink.
- transports carry raw Runxin frames and must not decode F79D fields;
- packet/encryption/session logic belongs in a transport implementation;
- field ids, codecs and evidence belong in the device profile;
- Home Assistant decides which known writes are safe to expose;
- keep `protocol.py` as a compatibility facade, not as a place for new logic.

These boundaries are enforced by the offline audit where practical.

The native job runs the complete suite on HA 2026.9.4; a separate baseline job uses `requirements-test-ha-baseline.txt` for HA 2026.9.3. Both use mocked device I/O. These are tested releases, not a declared minimum HA version.

Workflow action source revisions are pinned, but the upstream HACS/hassfest actions still use floating container tags. This does not pin the entire toolchain. Import checks are static architecture checks, not a runtime sandbox.

For a compatible new model, reuse the shared map, document unit/applicability uncertainty and start with empty write permissions. Read-only Alpha tests must cover clock/admin/adapter bypasses and existing G6/model-12 identities and conversions. A different wire family needs its own evidence and profile, not a copy of the existing catalogue. See the [support matrix](docs/model-support.md) and [hardware verification guide](docs/hardware-verification.md).

## Protocol research and test data

Interoperability research is welcome, but this repository must not contain
vendor APKs, firmware images, proprietary scripts/binaries, credentials, private
or pairing keys, account tokens, or unredacted captures containing user/device
identifiers.

Small sanitized protocol fixtures necessary to test independently written code
are acceptable when they contain no secrets and no substantial vendor
code/content.

When documenting a reverse-engineered fact, distinguish evidence recovered from
the legacy app, behavior observed on a real device, a physically verified write,
and an inference. Prefer an explicit `inferred` note to false certainty.

## New transports

See [`docs/adding-a-transport.md`](docs/adding-a-transport.md). A transport should
implement the raw `transact(frame: bytes) -> bytes` contract and remove only its
own envelope before returning the response.

The existence of a transport implementation does not automatically make that
hardware discoverable/supported by the Home Assistant integration.

## New Runxin devices

See [`docs/adding-a-device-profile.md`](docs/adding-a-device-profile.md). Include
the brand/model, valve/controller model, transport/module identity if known, and
which fields/commands were actually verified. Do not copy the F79D table or mark
an untested field writable merely because its numeric id looks plausible.

## Standalone-library direction

The pure protocol layer is intentionally structured so it can later be moved to
a public PyPI library if there are multiple real consumers. Until that happens,
do not introduce runtime dependencies between unrelated HACS integrations by
importing an installed `custom_components.ypsilon_local` package.

## License

By contributing, you agree that your contribution is licensed under the
repository's Apache License 2.0.
