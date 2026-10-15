"""Verification tests proving automated test screenshot confinement and cleanup safety."""

from __future__ import annotations

from pathlib import Path
import pytest

from sightline.config import Settings
from sightline.observation.artifacts import ArtifactManager


def test_cleanup_artifacts_confined_to_test_directory(tmp_path: Path):
    """Verify cleanup_artifacts successfully removes screenshots in isolated test directories."""
    test_dir = tmp_path / ".test_artifacts"
    mgr = ArtifactManager(Settings(artifacts_dir=str(test_dir)))

    assert mgr.is_test_artifacts is True

    # Create dummy test screenshots
    p1 = mgr.get_screenshot_path("obs_test_clean_01")
    p2 = mgr.get_screenshot_path("obs_test_clean_02")
    p1.write_bytes(b"\x89PNG\r\n\x1a\nfake1")
    p2.write_bytes(b"\x89PNG\r\n\x1a\nfake2")

    assert p1.exists()
    assert p2.exists()

    # Clean up test artifacts
    deleted_count = mgr.cleanup_artifacts()
    assert deleted_count == 2
    assert not p1.exists()
    assert not p2.exists()


def test_cleanup_artifacts_refuses_production_directory():
    """Verify cleanup_artifacts strictly refuses to delete files in production artifacts directory."""
    prod_mgr = ArtifactManager(Settings(artifacts_dir="artifacts"))

    assert prod_mgr.is_test_artifacts is False

    # Production artifacts count before call
    existing_pngs = list(prod_mgr.screenshots_dir.glob("*.png"))
    assert len(existing_pngs) >= 496, f"Expected at least 496 historical PNGs, found {len(existing_pngs)}"

    # Calling cleanup without force_non_test must return 0 and touch nothing
    deleted = prod_mgr.cleanup_artifacts()
    assert deleted == 0

    # Ensure all historical screenshots remain intact
    after_pngs = list(prod_mgr.screenshots_dir.glob("*.png"))
    assert len(after_pngs) == len(existing_pngs)


def test_artifact_manager_is_test_artifacts_detection(tmp_path: Path):
    """Verify is_test_artifacts correctly distinguishes test folders from production."""
    prod_mgr = ArtifactManager(Settings(artifacts_dir="artifacts"))
    assert prod_mgr.is_test_artifacts is False

    isolated_mgr = ArtifactManager(Settings(artifacts_dir="artifacts/.test_artifacts"))
    assert isolated_mgr.is_test_artifacts is True

    tmp_mgr = ArtifactManager(Settings(artifacts_dir=str(tmp_path / "custom_test")))
    assert tmp_mgr.is_test_artifacts is True
