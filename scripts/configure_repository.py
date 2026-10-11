#!/usr/bin/env python3
"""Fill repository-owner placeholders before the first public push."""

from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = "__GITHUB_USER__"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("github_user", help="GitHub username without @")
    parser.add_argument("--repo", default="runxin-local", help="GitHub repository name")
    parser.add_argument("--github-sponsors", metavar="USERNAME", help="Enable GitHub Sponsors in .github/FUNDING.yml")
    parser.add_argument("--ko-fi", metavar="USERNAME", help="Enable Ko-fi in .github/FUNDING.yml")
    args = parser.parse_args()

    user = args.github_user.lstrip("@").strip()
    if not user or any(ch.isspace() for ch in user):
        parser.error("invalid GitHub username")

    manifest_path = ROOT / "custom_components" / "ypsilon_local" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["codeowners"] = [f"@{user}"]
    manifest["documentation"] = f"https://github.com/{user}/{args.repo}"
    manifest["issue_tracker"] = f"https://github.com/{user}/{args.repo}/issues"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    text_files = [
        ROOT / ".github" / "CODEOWNERS",
        ROOT / "README.md",
        ROOT / "PUBLISHING.md",
        ROOT / "docs" / "README.ca.md",
        ROOT / "docs" / "README.es.md",
    ]
    for path in text_files:
        if path.exists():
            path.write_text(
                path.read_text()
                .replace(PLACEHOLDER, user)
                .replace("__GITHUB_REPO__", args.repo)
            )

    funding = ROOT / ".github" / "FUNDING.yml"
    lines = ["# Optional project sponsorship. Sponsorship never changes functionality or support priority."]
    if args.github_sponsors:
        lines.append(f"github: {args.github_sponsors.lstrip('@')}")
    if args.ko_fi:
        lines.append(f"ko_fi: {args.ko_fi}")
    if len(lines) == 1:
        lines += ["# github: YOUR_GITHUB_SPONSORS_USERNAME", "# ko_fi: YOUR_KOFI_USERNAME"]
    funding.write_text("\n".join(lines) + "\n")

    print(f"Configured repository for https://github.com/{user}/{args.repo}")
    if not args.github_sponsors and not args.ko_fi:
        print("Funding left disabled; configure it later if desired.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
