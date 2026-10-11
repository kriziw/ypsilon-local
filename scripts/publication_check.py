#!/usr/bin/env python3
"""Fail CI when publication placeholders or release metadata are inconsistent."""

from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "custom_components" / "ypsilon_local" / "manifest.json"
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
CHANGELOG_VERSION = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)
INFO_VERSION = re.compile(r"^# Runxin Local ([^\s]+)\s*$", re.MULTILINE)


def main() -> int:
    errors: list[str] = []
    manifest = json.loads(MANIFEST.read_text())
    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        errors.append(f"manifest version is not a valid semantic version: {version!r}")
    else:
        info = (ROOT / "info.md").read_text()
        changelog = (ROOT / "CHANGELOG.md").read_text()

        info_match = INFO_VERSION.search(info)
        info_version = info_match.group(1) if info_match else None
        if info_version != version:
            errors.append(
                f"info.md current version is {info_version!r}, expected manifest {version}"
            )

        changelog_match = CHANGELOG_VERSION.search(changelog)
        changelog_version = changelog_match.group(1) if changelog_match else None
        if changelog_version != version:
            errors.append(
                "CHANGELOG.md first release section is "
                f"{changelog_version!r}, expected manifest {version}"
            )

    for field in ("documentation", "issue_tracker"):
        if "__GITHUB_USER__" in str(manifest.get(field, "")):
            errors.append(f"manifest {field} still contains __GITHUB_USER__")
    owners = manifest.get("codeowners") or []
    if not owners or any("__GITHUB_USER__" in owner for owner in owners):
        errors.append("manifest codeowners has not been configured")
    codeowners = (ROOT / ".github" / "CODEOWNERS").read_text()
    if "__GITHUB_USER__" in codeowners:
        errors.append(".github/CODEOWNERS has not been configured")
    for relative in ("README.md", "PUBLISHING.md", "docs/README.ca.md", "docs/README.es.md"):
        content = (ROOT / relative).read_text()
        if "__GITHUB_USER__" in content or "__GITHUB_REPO__" in content:
            errors.append(f"{relative} still contains repository placeholders")
    if not (ROOT / "custom_components" / "ypsilon_local" / "brand" / "icon.png").exists():
        errors.append("brand/icon.png is missing")
    if not (ROOT / "LICENSE").exists():
        errors.append("LICENSE is missing")
    if errors:
        print("PUBLICATION CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PUBLICATION CHECK CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
