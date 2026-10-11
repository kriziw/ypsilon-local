# Publishing Ypsilon on GitHub and HACS

The source tree is prepared for the public `Danirv/ypsilon-local` repository and HACS distribution.

## 1. Repository metadata

If preparing a fresh clone/template, configure the repository owner once:

```bash
python scripts/configure_repository.py Danirv --repo ypsilon-local
```

Funding can be configured through GitHub Sponsors and/or Ko-fi. Then verify:

```bash
python scripts/publication_check.py
python scripts/audit.py
python scripts/field_surface_audit.py
python -m pytest -q
python -m compileall -q custom_components/ypsilon_local scripts tests
```

## 2. Repository requirements

Recommended description:

> Local Home Assistant integration for Runxin F79D / BroadLink BL3372 water softeners, including ATH/BWT Ypsilon G6.

Keep Issues enabled and useful topics such as `home-assistant`, `hacs`, `custom-component`, `water-softener`, `runxin`, `broadlink`, and `ypsilon`.

The repository includes HACS validation, hassfest, the offline protocol/architecture audit, and an automated release workflow. Do not ignore validator failures before publishing or while a HACS default-inclusion request is open.

## 3. Publish a GitHub Release from the web

### Automated path (preferred)

`release-please.yml` watches `main` and keeps a release pull request open.
That PR bumps `manifest.json` and the `info.md` title, and rewrites
`CHANGELOG.md` from the Conventional Commit subjects since the last release.

1. Review the release pull request. Edit `CHANGELOG.md` in it if the generated
   entries need the hardware detail this project usually records.
2. Merge it.
3. The same workflow then tags `v<version>`, creates the GitHub Release, runs
   the full publication/audit/field-surface/unit-test/compile suite **against
   the tagged source**, and attaches the manual-install ZIP.

Versions come from the commit types, so nothing is bumped by hand. See
`CONTRIBUTING.md` for the convention.

Note that a release created by `GITHUB_TOKEN` does not trigger other
workflows, which is why that validation and ZIP upload happen inside
`release-please.yml` rather than in the tag-triggered job below.

### Manual path (recovery)

Still fully supported, and the thing to use if the automated path is
unavailable or a release needs recovering:

The manual path does not require a local Git clone either:

1. Choose a **new, unused** semantic version. Never reuse a version that already has a GitHub Release, even if `main` contains newer code.
2. Update `manifest.json`, `CHANGELOG.md` and `info.md` to that same version.
3. Merge those release changes into `main` only after HACS, hassfest and the offline audit are green.
4. Open GitHub **Actions** → **Publish GitHub release**.
5. Select **Run workflow** and make sure the branch selector is `main`.
6. Run the workflow.

The web workflow reads the version directly from `custom_components/ypsilon_local/manifest.json`, runs the full publication/audit/field-surface/unit-test/compile checks, refuses an existing GitHub Release, creates or recovers the matching annotated `v<manifest version>` tag, checks out that exact tag, validates the tagged source again, builds the manual-install ZIP and creates the GitHub Release.

A tag pushed manually is handled by the tag-triggered job, which performs the same validation before creating the release. A tag created by the workflow's own `GITHUB_TOKEN` does not need a second workflow run; the web-release job completes the release itself after validating the tagged source.

### Git CLI alternative

If a local clone is available, the same release can still be started by tagging the exact manifest version:

```bash
VERSION="$(python -c 'import json; print(json.load(open("custom_components/ypsilon_local/manifest.json"))["version"])')"
git tag -a "v${VERSION}" -m "Ypsilon ${VERSION}"
git push origin "v${VERSION}"
```

Do not manually create a GitHub Release for the same tag; the workflow owns release creation.

## 4. Test through HACS

Before requesting default inclusion, add the repository to HACS as a custom **Integration**, install/update it, restart Home Assistant, configure the device, and verify the real hardware path.

## 5. HACS default inclusion

Current HACS requirements include a public GitHub repository, passing HACS + hassfest actions, brand assets, repository description/topics/issues, and a full GitHub Release created after successful validation actions.

The project currently has an inclusion request open at `hacs/default#10717`. Normal repository maintenance and new releases can continue while it waits in the review queue; do not open duplicate inclusion PRs or comment on the queue PR unless critical information or reviewer feedback requires it.

## Release discipline

For each release:

1. Confirm the intended version does **not** already exist as a GitHub Release.
2. Update `manifest.json`, `CHANGELOG.md` and `info.md` together.
3. Run publication check, audit, field-surface audit, pytest and compileall.
4. Merge only with HACS/hassfest/audit green.
5. Prefer **Actions → Publish GitHub release → Run workflow** on `main`; alternatively push exactly `v<manifest version>` from Git.
6. Verify the resulting release tag, asset and main-branch validation runs.
7. Never move or recreate an already-published release tag to include later code; publish a new patch version instead.

Never commit vendor APKs, firmware, proprietary binary/script dumps, credentials, private/pairing keys, or unredacted packet captures.
