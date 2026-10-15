"""Unit and integration tests for visual observations and artifact management."""

from __future__ import annotations

from pathlib import Path
import pytest
from playwright.async_api import Page

from sightline.browser.manager import BrowserManager
from sightline.config import Settings
from sightline.observation.artifacts import ArtifactManager
from sightline.observation.models import (
    BoundingBox,
    ObservationResult,
    ObservationStatus,
    ObservedTarget,
)
from sightline.observation.observer import VisualObserver


def test_bounding_box_validation():
    """Verify BoundingBox enforces strictly positive dimensions."""
    # Valid box
    box = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0)
    assert box.x == 10.0
    assert box.center == (60.0, 45.0)
    assert box.is_within_viewport(1280, 800) is True

    # Zero or negative width/height must raise ValueError
    with pytest.raises(ValueError, match="strictly positive"):
        BoundingBox(x=0.0, y=0.0, width=0.0, height=10.0)

    with pytest.raises(ValueError, match="strictly positive"):
        BoundingBox(x=0.0, y=0.0, width=10.0, height=-5.0)


def test_bounding_box_viewport_containment():
    """Verify bounding box containment calculation against viewport boundaries."""
    box = BoundingBox(x=100.0, y=100.0, width=200.0, height=100.0)
    # Fits inside 1280x800
    assert box.is_within_viewport(1280, 800) is True

    # Off left/top
    box_neg_x = BoundingBox(x=-1.0, y=10.0, width=50.0, height=50.0)
    assert box_neg_x.is_within_viewport(1280, 800) is False

    box_neg_y = BoundingBox(x=10.0, y=-5.0, width=50.0, height=50.0)
    assert box_neg_y.is_within_viewport(1280, 800) is False

    # Overflow right/bottom
    box_overflow_x = BoundingBox(x=1200.0, y=10.0, width=100.0, height=50.0)
    assert box_overflow_x.is_within_viewport(1280, 800) is False

    box_overflow_y = BoundingBox(x=10.0, y=780.0, width=50.0, height=50.0)
    assert box_overflow_y.is_within_viewport(1280, 800) is False


def test_artifact_manager_confinement(test_settings: Settings, tmp_path: Path):
    """Verify ArtifactManager prevents path traversal and confines outputs to project artifacts."""
    art_mgr = ArtifactManager(test_settings)
    
    # 1. Normal screenshot path
    screenshot_p = art_mgr.get_screenshot_path("obs_test123")
    assert screenshot_p.name == "obs_test123.png"
    assert art_mgr.validate_file_in_artifacts(screenshot_p) is True

    # 2. Path traversal attempt in ID must be sanitized
    traversal_id = "../../etc/passwd"
    sanitized_p = art_mgr.get_screenshot_path(traversal_id)
    assert ".." not in sanitized_p.name
    assert art_mgr.validate_file_in_artifacts(sanitized_p) is True

    # 3. to_safe_relative_path produces clean relative path
    rel = art_mgr.to_safe_relative_path(screenshot_p)
    assert not rel.startswith("C:") and not rel.startswith("D:")
    assert "artifacts/screenshots" in rel or "artifacts" in rel


@pytest.mark.asyncio
async def test_observer_real_chromium_observation(
    browser_mgr: BrowserManager, scenarios_file_url: str, test_settings: Settings
):
    """Verify VisualObserver captures real Chromium viewport screenshot and extracts candidates."""
    observer = VisualObserver(test_settings)

    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)

        obs = await observer.observe(page)

        # 1. Observation metadata
        assert obs.status == ObservationStatus.COMPLETE
        assert obs.viewport_width == test_settings.browser_viewport_width
        assert obs.viewport_height == test_settings.browser_viewport_height
        assert obs.screenshot_path is not None
        assert obs.screenshot_id is not None

        # Verify screenshot file exists on disk inside artifacts
        real_file = test_settings.resolved_artifacts_dir / "screenshots" / f"{obs.screenshot_id}.png"
        assert real_file.exists()
        assert real_file.stat().st_size > 0

        # 2. Candidate extraction
        assert len(obs.candidates) > 0
        actionables = obs.get_actionable_candidates()
        assert len(actionables) > 0

        # Verify specific expected actionable elements in synthetic page
        target_ids = [c.target_id for c in actionables]
        assert "btn-submit-form" in target_ids
        assert "btn-action-save" in target_ids
        assert "btn-action-discard" in target_ids

        # 3. Disabled element must NOT be in actionable candidates
        # (#btn-process-report starts disabled in scenario 4)
        assert "btn-process-report" not in target_ids

        # 4. Hidden element must NOT be in actionable candidates
        # (#btn-modal-confirm is inside hidden modal overlay initially)
        assert "btn-modal-confirm" not in target_ids

        # 5. Check evidence source is honest
        for cand in obs.candidates:
            assert cand.evidence_source == "dom_assisted_bounding_box"


@pytest.mark.asyncio
async def test_observer_handles_closed_page_gracefully(
    browser_mgr: BrowserManager, test_settings: Settings
):
    """Verify observer returns a degraded/failed status when page or screenshot fails."""
    observer = VisualObserver(test_settings)

    async with browser_mgr.session() as page:
        # Close the page prematurely
        await page.close()

        obs = await observer.observe(page)
        # Should record failure or degraded, not raise an unhandled crash
        assert obs.status in (ObservationStatus.DEGRADED, ObservationStatus.FAILED)
        assert obs.error_message is not None


@pytest.mark.asyncio
async def test_artifact_api_endpoint(
    async_client, test_settings: Settings
):
    """Verify safe artifact retrieval endpoint without host filesystem exposure."""
    art_mgr = ArtifactManager(test_settings)
    # Create a dummy screenshot file in artifacts
    dummy_path = art_mgr.get_screenshot_path("obs_api_test_01")
    dummy_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRfakeimage")

    try:
        # 1. Fetch valid artifact
        resp = await async_client.get("/api/artifacts/screenshots/obs_api_test_01")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content.startswith(b"\x89PNG")

        # 2. Fetch nonexistent artifact -> 404
        resp_404 = await async_client.get("/api/artifacts/screenshots/obs_nonexistent_xyz")
        assert resp_404.status_code == 404

        # 3. Traversal / malformed attempt -> sanitized or rejected
        resp_traversal = await async_client.get("/api/artifacts/screenshots/..%2F..%2Fetc%2Fpasswd")
        assert resp_traversal.status_code in (400, 404)
    finally:
        if dummy_path.exists():
            dummy_path.unlink()
