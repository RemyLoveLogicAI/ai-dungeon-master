import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts import verify_release


def prepare_repo(tmp_path: Path, version: str, checklist: str = "") -> None:
    (tmp_path / "docs/product").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "test"\nversion = "{version}"\n'
    )
    (tmp_path / "CHANGELOG.md").write_text(f"## [{version}] - 2026-10-13\n")
    (tmp_path / "docs/product/MVP-1.0-CHECKLIST.md").write_text(checklist)
    (tmp_path / "docs/product/FEATURE_LOG.md").write_text(
        "| Feature | PRD | PR | Status | Version | Release |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"| Test | #1 | #2 | Verified | {version} | v{version} |\n"
    )
    verify_release.ROOT = tmp_path


def mock_tags(*tags: str):
    return patch(
        "scripts.verify_release.subprocess.run",
        return_value=SimpleNamespace(stdout="\n".join(tags)),
    )


def test_release_requires_matching_version_and_changelog(tmp_path):
    prepare_repo(tmp_path, "0.1.0")
    with mock_tags("v0.1.0"):
        verify_release.verify_release("v0.1.0")
        with pytest.raises(ValueError, match="does not match"):
            verify_release.verify_release("v0.2.0")


def test_mvp_release_requires_all_checkboxes_and_evidence(tmp_path):
    prepare_repo(
        tmp_path,
        "1.0.0",
        "- [x] One\n| Gate | Evidence |\n| --- | --- |\n| One | PR #1 |\n",
    )
    with mock_tags("v0.1.0", "v1.0.0"):
        verify_release.verify_release("v1.0.0")

    prepare_repo(
        tmp_path,
        "1.0.0",
        "- [ ] One\n| Gate | Evidence |\n| --- | --- |\n| One | TBD |\n",
    )
    with mock_tags("v0.1.0", "v1.0.0"), pytest.raises(ValueError, match="checkbox"):
        verify_release.verify_release("v1.0.0")


def test_feature_release_requires_verified_log_and_sequential_minor(tmp_path):
    prepare_repo(tmp_path, "1.2.0")
    with mock_tags("v1.0.0", "v1.1.0", "v1.2.0"):
        verify_release.verify_release("v1.2.0")
    prepare_repo(tmp_path, "1.3.0")
    with mock_tags("v1.0.0", "v1.1.0"), pytest.raises(ValueError, match="next minor"):
        verify_release.verify_release("v1.3.0")


@pytest.mark.parametrize("value", ["1.0", "01.0.0", "1.0.0-rc.1"])
def test_parse_version_rejects_non_stable_semver(value):
    with pytest.raises(ValueError, match="stable X.Y.Z"):
        verify_release.parse_version(value)
    assert verify_release._parse_tag(value) is None


def test_release_requires_project_version_and_changelog_section(tmp_path):
    prepare_repo(tmp_path, "0.2.0")
    (tmp_path / "pyproject.toml").write_text('name = "test"\nversion = "0.2.0"\n')
    with mock_tags("v0.2.0"), pytest.raises(ValueError, match="missing \\[project\\]"):
        verify_release.verify_release("v0.2.0")

    prepare_repo(tmp_path, "0.2.0")
    (tmp_path / "CHANGELOG.md").write_text("## [0.1.0]\n")
    with mock_tags("v0.2.0"), pytest.raises(ValueError, match="CHANGELOG.md"):
        verify_release.verify_release("v0.2.0")


def test_mvp_release_requires_checklist_and_complete_evidence(tmp_path):
    prepare_repo(tmp_path, "1.0.0")
    with mock_tags("v0.1.0"), pytest.raises(ValueError, match="checkbox"):
        verify_release.verify_release("v1.0.0")

    prepare_repo(
        tmp_path,
        "1.0.0",
        "- [x] One\n| Gate | Evidence |\n| --- | --- |\n| One | TBD |\n",
    )
    with mock_tags("v0.1.0"), pytest.raises(ValueError, match="evidence"):
        verify_release.verify_release("v1.0.0")


def test_feature_release_requires_verified_feature_row(tmp_path):
    prepare_repo(tmp_path, "1.1.0")
    (tmp_path / "docs/product/FEATURE_LOG.md").write_text(
        "| Feature | PRD | PR | Status | Version | Release |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| Test | #1 | #2 | Proposed | 1.1.0 | v1.1.0 |\n"
    )
    with mock_tags("v1.0.0"), pytest.raises(ValueError, match="verified feature row"):
        verify_release.verify_release("v1.1.0")


def test_release_rejects_older_tag_and_accepts_patch_or_major(tmp_path):
    prepare_repo(tmp_path, "0.9.0")
    with mock_tags("v0.9.0", "v1.0.0"), pytest.raises(ValueError, match="older"):
        verify_release.verify_release("v0.9.0")

    prepare_repo(tmp_path, "1.1.1")
    with mock_tags("not-a-version", "v1.1.0"):
        verify_release.verify_release("v1.1.1")

    prepare_repo(tmp_path, "2.0.0")
    with mock_tags("v1.1.0"):
        verify_release.verify_release("v2.0.0")


def test_release_command_line_requires_a_tag(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["verify_release.py"])
    with pytest.raises(SystemExit, match="usage:"):
        runpy.run_path(
            str(Path(verify_release.__file__)),
            run_name="__main__",
        )


def test_release_command_line_verifies_metadata(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["verify_release.py", "v0.1.0"])
    with mock_tags("v0.1.0"):
        runpy.run_path(
            str(Path(verify_release.__file__)),
            run_name="__main__",
        )


def test_release_command_line_reports_invalid_metadata(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["verify_release.py", "v9.9"])
    with pytest.raises(SystemExit, match="Release metadata rejected"):
        runpy.run_path(
            str(Path(verify_release.__file__)),
            run_name="__main__",
        )
