"""Unit and integration tests for closed-loop verification."""

from __future__ import annotations

import pytest

from sightline.browser.manager import BrowserManager
from sightline.observation.models import ObservationResult, ObservationStatus
from sightline.verification.models import (
    ConditionType,
    VerificationResult,
    VerificationStatus,
    VisiblePostcondition,
)
from sightline.verification.verifier import ClosedLoopVerifier


def make_obs(obs_id: str) -> ObservationResult:
    return ObservationResult(
        observation_id=obs_id,
        timestamp=100.0,
        viewport_width=1280,
        viewport_height=800,
        status=ObservationStatus.COMPLETE,
    )


@pytest.mark.asyncio
async def test_verification_success_condition(browser_mgr: BrowserManager, scenarios_file_url: str):
    """Verify ClosedLoopVerifier returns VERIFIED when expected postcondition holds."""
    verifier = ClosedLoopVerifier()
    pre_obs = make_obs("obs_pre_1")
    post_obs = make_obs("obs_post_1")

    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)

        # Initial state check: editor badge contains 'Unsaved'
        postcond = VisiblePostcondition(
            target_selector="#editor-status-badge",
            condition_type=ConditionType.TEXT_CONTAINS,
            expected_value="Unsaved changes pending",
            description="Editor starts with unsaved pending badge",
        )

        res = await verifier.verify(page, pre_obs, post_obs, postcond)
        assert res.status == VerificationStatus.VERIFIED
        assert res.pre_observation_id == "obs_pre_1"
        assert res.post_observation_id == "obs_post_1"
        assert "Unsaved changes pending" in str(res.actual_value)


@pytest.mark.asyncio
async def test_verification_failure_condition_never_returns_false_success(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Verify ClosedLoopVerifier returns FAILED when postcondition does not hold."""
    verifier = ClosedLoopVerifier()
    pre_obs = make_obs("obs_pre_2")
    post_obs = make_obs("obs_post_2")

    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)

        # Assert an untrue condition
        wrong_postcond = VisiblePostcondition(
            target_selector="#editor-status-badge",
            condition_type=ConditionType.TEXT_CONTAINS,
            expected_value="COMPLETELY_UNTRUE_STATUS",
            description="Should fail",
        )

        res = await verifier.verify(page, pre_obs, post_obs, wrong_postcond, allow_recovery=False)
        assert res.status == VerificationStatus.FAILED
        assert res.actual_value is not None
        assert "expected to contain 'COMPLETELY_UNTRUE_STATUS'" in res.evidence


@pytest.mark.asyncio
async def test_verification_never_retries_destructive_actions(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Verify that destructive actions strictly forbid recovery retries."""
    verifier = ClosedLoopVerifier()
    pre_obs = make_obs("obs_pre_3")
    post_obs = make_obs("obs_post_3")

    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)

        postcond = VisiblePostcondition(
            target_selector="#safety-gate-indicator",
            condition_type=ConditionType.TEXT_EQUALS,
            expected_value="NONEXISTENT_STATE",
        )

        # Calling verify with allow_recovery=True BUT is_destructive_action=True
        res = await verifier.verify(
            page,
            pre_obs,
            post_obs,
            postcond,
            allow_recovery=True,
            is_destructive_action=True,
        )

        assert res.status == VerificationStatus.FAILED
        # Recovery must not have been triggered
        assert res.recovery_attempted is False


@pytest.mark.asyncio
async def test_verification_handles_closed_page_gracefully(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Verify that ClosedLoopVerifier handles a closed page cleanly without crashing or hanging."""
    verifier = ClosedLoopVerifier()
    pre_obs = make_obs("obs_pre_closed")
    post_obs = make_obs("obs_post_closed")

    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)
        # Explicitly close page to simulate browser/page detachment
        await page.close()

        postcond = VisiblePostcondition(
            target_selector="#editor-status-badge",
            condition_type=ConditionType.IS_VISIBLE,
            description="Should fail cleanly when page is closed",
        )

        res = await verifier.verify(
            page,
            pre_obs,
            post_obs,
            postcond,
            allow_recovery=True,
            is_destructive_action=False,
        )

        assert res.status == VerificationStatus.FAILED
        assert res.recovery_attempted is False
        assert "closed" in res.error_message.lower()

