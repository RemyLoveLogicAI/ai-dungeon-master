"""Fail closed when a release tag does not match verified release metadata."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def parse_version(value: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError(f"release version must be stable X.Y.Z SemVer, got {value!r}")
    return tuple(map(int, match.groups()))


def verify_release(tag: str) -> None:
    version = tag.removeprefix("v")
    current = parse_version(version)
    pyproject = (ROOT / "pyproject.toml").read_text()
    project_section = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", pyproject)
    version_match = (
        re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', project_section.group(1))
        if project_section
        else None
    )
    if not version_match:
        raise ValueError("pyproject.toml is missing [project].version")
    project_version = version_match.group(1)
    if version != project_version:
        raise ValueError(
            f"tag {tag!r} does not match pyproject.toml version {project_version!r}"
        )

    changelog = (ROOT / "CHANGELOG.md").read_text()
    if not re.search(rf"^## \[{re.escape(version)}\](?:\s|$)", changelog, re.MULTILINE):
        raise ValueError(f"CHANGELOG.md is missing a release section for {version}")

    if current == (1, 0, 0):
        checklist = (ROOT / "docs/product/MVP-1.0-CHECKLIST.md").read_text()
        boxes = re.findall(r"^- \[([ xX])\]", checklist, re.MULTILINE)
        if not boxes or any(box.lower() != "x" for box in boxes):
            raise ValueError("v1.0.0 requires every MVP verification checkbox to be checked")
        evidence = [
            line.strip().strip("|").split("|")[-1].strip()
            for line in checklist.splitlines()
            if line.lstrip().startswith("|") and "TBD" in line
        ]
        if evidence:
            raise ValueError("v1.0.0 requires every MVP evidence entry to be completed")

    if current >= (1, 1, 0):
        feature_log = (ROOT / "docs/product/FEATURE_LOG.md").read_text()
        release_row = any(
            len(cells := [cell.strip() for cell in line.strip().strip("|").split("|")]) >= 6
            and cells[3].lower() == "verified"
            and cells[4] == version
            for line in feature_log.splitlines()
            if line.lstrip().startswith("|")
        )
        if not release_row:
            raise ValueError(
                f"FEATURE_LOG.md needs a verified feature row for release {version}"
            )

    result = subprocess.run(
        ["git", "tag", "--list", "v[0-9]*"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    existing = [
        parsed
        for item in result.stdout.splitlines()
        if item != tag and (parsed := _parse_tag(item))
    ]
    if existing:
        latest = max(existing)
        if current < latest:
            raise ValueError(
                f"release {version} is older than the latest existing version "
                f"{'.'.join(map(str, latest))}"
            )
    else:
        latest = None
    if latest and current > latest:
        feature_release = current[0] == latest[0] and current[1] == latest[1] + 1 and current[2] == 0
        patch_release = current[0:2] == latest[0:2] and current[2] == latest[2] + 1
        major_release = current[0] == latest[0] + 1 and current[1:] == (0, 0)
        if not (feature_release or patch_release or major_release):
            raise ValueError(
                f"release {version} must be the next minor feature point, patch fix, "
                f"or major version after {'.'.join(map(str, latest))}"
            )


def _parse_tag(tag: str) -> tuple[int, int, int] | None:
    try:
        return parse_version(tag)
    except ValueError:
        return None


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/verify_release.py <tag>")
    try:
        verify_release(sys.argv[1])
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Release metadata rejected: {error}") from error
    print(f"Release metadata verified for {sys.argv[1]}")
