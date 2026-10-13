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
    prepare_repo(tmp_path, "1.0.0", "- [x] One\n| Gate | Evidence |\n| --- | --- |\n| One | PR #1 |\n")
    with mock_tags("v0.1.0", "v1.0.0"):
        verify_release.verify_release("v1.0.0")

    prepare_repo(tmp_path, "1.0.0", "- [ ] One\n| Gate | Evidence |\n| --- | --- |\n| One | TBD |\n")
    with mock_tags("v0.1.0", "v1.0.0"), pytest.raises(ValueError, match="checkbox"):
        verify_release.verify_release("v1.0.0")


def test_feature_release_requires_verified_log_and_sequential_minor(tmp_path):
    prepare_repo(tmp_path, "1.2.0")
    with mock_tags("v1.0.0", "v1.1.0", "v1.2.0"):
        verify_release.verify_release("v1.2.0")
    prepare_repo(tmp_path, "1.3.0")
    with mock_tags("v1.0.0", "v1.1.0"), pytest.raises(ValueError, match="next minor"):
        verify_release.verify_release("v1.3.0")
