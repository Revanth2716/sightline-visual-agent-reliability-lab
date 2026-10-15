"""Unit and integration tests for deterministic target grounding."""

from __future__ import annotations

import pytest

from sightline.browser.manager import BrowserManager
from sightline.config import Settings
from sightline.grounding.grounder import DeterministicGrounder, default_grounder
from sightline.grounding.models import (
    GroundingMatchStatus,
    GroundingRequest,
    GroundingResult,
)
from sightline.observation.models import (
    BoundingBox,
    ObservationResult,
    ObservationStatus,
    ObservedTarget,
)
from sightline.observation.observer import VisualObserver


def create_synthetic_observation(candidates: list[ObservedTarget], vw: int = 1280, vh: int = 800) -> ObservationResult:
    """Helper creating an in-memory ObservationResult for fast unit testing."""
    return ObservationResult(
        observation_id="obs_unit_test",
        timestamp=1000.0,
        viewport_width=vw,
        viewport_height=vh,
        screenshot_path="artifacts/screenshots/test.png",
        screenshot_id="test",
        candidates=candidates,
        status=ObservationStatus.COMPLETE,
    )


def test_grounding_exact_target_id_resolution():
    """Verify unique resolution when an explicit target_id is requested."""
    cand = ObservedTarget(
        target_id="btn-submit-form",
        selector="#btn-submit-form",
        tag_name="button",
        role="button",
        text="Submit Intake Record",
        bounding_box=BoundingBox(x=50, y=50, width=150, height=40),
        is_visible=True,
        is_enabled=True,
        is_actionable=True,
    )
    obs = create_synthetic_observation([cand])
    grounder = DeterministicGrounder()

    req = GroundingRequest(query="irrelevant", target_id="btn-submit-form")
    res = grounder.ground(obs, req)

    assert res.status == GroundingMatchStatus.MATCH_UNIQUE
    assert res.matched_target is not None
    assert res.matched_target.target_id == "btn-submit-form"
    assert res.confidence == 1.0


def test_grounding_missing_target_rejection():
    """Verify clean NO_MATCH result when target does not exist."""
    cand = ObservedTarget(
        target_id="btn-action-save",
        selector="#btn-action-save",
        tag_name="button",
        role="button",
        text="Save Draft",
        bounding_box=BoundingBox(x=10, y=10, width=100, height=35),
    )
    obs = create_synthetic_observation([cand])
    grounder = DeterministicGrounder()

    req = GroundingRequest(query="Nonexistent Delete Button")
    res = grounder.ground(obs, req)

    assert res.status == GroundingMatchStatus.NO_MATCH
    assert res.matched_target is None
    assert res.candidate_count == 0


def test_grounding_ambiguous_target_rejection():
    """Verify that multiple matching candidates return AMBIGUOUS instead of guessing arbitrarily."""
    c1 = ObservedTarget(
        target_id="btn-action-primary",
        selector="#btn-action-primary",
        tag_name="button",
        role="button",
        text="Submit",
        bounding_box=BoundingBox(x=10, y=10, width=100, height=35),
    )
    c2 = ObservedTarget(
        target_id="btn-action-secondary",
        selector="#btn-action-secondary",
        tag_name="button",
        role="button",
        text="Submit",
        bounding_box=BoundingBox(x=10, y=60, width=100, height=35),
    )
    obs = create_synthetic_observation([c1, c2])
    grounder = DeterministicGrounder()

    req = GroundingRequest(query="Submit")
    res = grounder.ground(obs, req)

    assert res.status == GroundingMatchStatus.AMBIGUOUS
    assert res.matched_target is None
    assert res.candidate_count == 2
    assert len(res.ambiguous_candidates) == 2


def test_grounding_save_vs_discard_disambiguation():
    """Verify strict disambiguation between visually similar 'Save Draft' and 'Discard Changes' buttons."""
    save_btn = ObservedTarget(
        target_id="btn-action-save",
        selector="#btn-action-save",
        tag_name="button",
        role="button",
        text="Save Draft",
        bounding_box=BoundingBox(x=100, y=200, width=110, height=38),
    )
    discard_btn = ObservedTarget(
        target_id="btn-action-discard",
        selector="#btn-action-discard",
        tag_name="button",
        role="button",
        text="Discard Changes",
        bounding_box=BoundingBox(x=220, y=200, width=130, height=38),
    )
    obs = create_synthetic_observation([save_btn, discard_btn])
    grounder = DeterministicGrounder()

    # Query for Save Draft must match ONLY Save Draft
    save_res = grounder.ground(obs, GroundingRequest(query="Save Draft"))
    assert save_res.status == GroundingMatchStatus.MATCH_UNIQUE
    assert save_res.matched_target is not None
    assert save_res.matched_target.target_id == "btn-action-save"

    # Query for Discard Changes must match ONLY Discard Changes
    discard_res = grounder.ground(obs, GroundingRequest(query="Discard Changes"))
    assert discard_res.status == GroundingMatchStatus.MATCH_UNIQUE
    assert discard_res.matched_target is not None
    assert discard_res.matched_target.target_id == "btn-action-discard"

    # Querying a generic ambiguous substring present on both or matching generic 'btn' role
    ambig_res = grounder.ground(obs, GroundingRequest(query="btn", role="button"))
    assert ambig_res.status == GroundingMatchStatus.AMBIGUOUS
    assert ambig_res.candidate_count == 2


def test_grounding_out_of_bounds_rejection():
    """Verify targets outside viewport boundaries are rejected with OUT_OF_BOUNDS."""
    offscreen_btn = ObservedTarget(
        target_id="btn-offscreen",
        selector="#btn-offscreen",
        tag_name="button",
        role="button",
        text="Hidden Offscreen",
        bounding_box=BoundingBox(x=1400, y=200, width=100, height=40),  # x=1400 > vw=1280
    )
    obs = create_synthetic_observation([offscreen_btn], vw=1280, vh=800)
    grounder = DeterministicGrounder()

    res = grounder.ground(obs, GroundingRequest(query="Hidden Offscreen"))
    assert res.status == GroundingMatchStatus.OUT_OF_BOUNDS
    assert res.matched_target is not None
    assert "outside current viewport" in res.error_message


@pytest.mark.asyncio
async def test_grounding_against_real_synthetic_page(
    browser_mgr: BrowserManager, scenarios_file_url: str, test_settings: Settings
):
    """Integration test: Observe real Chromium page and ground buttons deterministically."""
    observer = VisualObserver(test_settings)
    grounder = DeterministicGrounder()

    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)

        obs = await observer.observe(page)

        # Ground Save Draft
        save_match = grounder.ground(obs, GroundingRequest(query="Save Draft"))
        assert save_match.status == GroundingMatchStatus.MATCH_UNIQUE
        assert save_match.matched_target.target_id == "btn-action-save"

        # Ground Discard Changes
        discard_match = grounder.ground(obs, GroundingRequest(query="Discard Changes"))
        assert discard_match.status == GroundingMatchStatus.MATCH_UNIQUE
        assert discard_match.matched_target.target_id == "btn-action-discard"

        # Ground Submit Intake Record
        submit_match = grounder.ground(obs, GroundingRequest(query="Submit Intake Record"))
        assert submit_match.status == GroundingMatchStatus.MATCH_UNIQUE
        assert submit_match.matched_target.target_id == "btn-submit-form"
