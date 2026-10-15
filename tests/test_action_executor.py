"""Unit and integration tests for bounded action execution and safety governance."""

from __future__ import annotations

import pytest

from sightline.browser.manager import BrowserManager
from sightline.config import Settings
from sightline.executor.action_runner import BoundedActionExecutor
from sightline.executor.models import (
    ActionIntent,
    ActionType,
    ExecutionStatus,
)
from sightline.observation.models import (
    BoundingBox,
    ObservationResult,
    ObservationStatus,
    ObservedTarget,
)
from sightline.observation.observer import VisualObserver
from sightline.safety.policy import ApprovalGate


def create_dummy_observation(vw: int = 1280, vh: int = 800) -> ObservationResult:
    return ObservationResult(
        observation_id="obs_exec_test",
        timestamp=1000.0,
        viewport_width=vw,
        viewport_height=vh,
        status=ObservationStatus.COMPLETE,
    )


@pytest.mark.asyncio
async def test_executor_action_budget_enforcement(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Verify BoundedActionExecutor halts execution once maximum step budget is reached."""
    executor = BoundedActionExecutor(max_budget=2)
    obs = create_dummy_observation()

    dummy_target = ObservedTarget(
        target_id="btn-global-reset",
        selector="#btn-global-reset",
        tag_name="button",
        role="button",
        text="Reset All State",
        bounding_box=BoundingBox(x=10, y=10, width=100, height=35),
    )
    intent = ActionIntent(action_type=ActionType.CLICK, target=dummy_target)

    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)

        # Step 1: OK
        res1 = await executor.execute(page, intent, obs)
        assert res1.status == ExecutionStatus.SUCCESS

        # Step 2: OK
        res2 = await executor.execute(page, intent, obs)
        assert res2.status == ExecutionStatus.SUCCESS

        # Step 3: Must be rejected due to budget limit of 2
        res3 = await executor.execute(page, intent, obs)
        assert res3.status == ExecutionStatus.BUDGET_EXCEEDED
        assert "budget exceeded" in res3.error_message.lower()


@pytest.mark.asyncio
async def test_executor_preflight_checks_disabled_target(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Verify executor rejects interactions against disabled elements at pre-flight check."""
    executor = BoundedActionExecutor()
    obs = create_dummy_observation()

    # In scenario 4, #btn-process-report is initially disabled
    disabled_target = ObservedTarget(
        target_id="btn-process-report",
        selector="#btn-process-report",
        tag_name="button",
        role="button",
        text="Process Report",
        bounding_box=BoundingBox(x=50, y=500, width=140, height=40),
    )
    intent = ActionIntent(action_type=ActionType.CLICK, target=disabled_target)

    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)

        res = await executor.execute(page, intent, obs)
        assert res.status == ExecutionStatus.TARGET_DISABLED
        assert "disabled" in res.error_message.lower()


@pytest.mark.asyncio
async def test_executor_preflight_checks_missing_or_stale_target(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Verify executor rejects targets that do not exist in the live page."""
    executor = BoundedActionExecutor()
    obs = create_dummy_observation()

    stale_target = ObservedTarget(
        target_id="btn-ghost",
        selector="#btn-nonexistent-ghost-target",
        tag_name="button",
        role="button",
        text="Ghost",
        bounding_box=BoundingBox(x=50, y=50, width=100, height=35),
    )
    intent = ActionIntent(action_type=ActionType.CLICK, target=stale_target)

    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)

        res = await executor.execute(page, intent, obs)
        assert res.status == ExecutionStatus.TARGET_NOT_FOUND
        assert "not found in live dom" in res.evidence.lower()


@pytest.mark.asyncio
async def test_executor_destructive_action_strictly_blocked_without_token(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Verify critical destructive actions (#btn-execute-purge) are blocked by ApprovalGate."""
    gate = ApprovalGate()
    executor = BoundedActionExecutor(approval_gate=gate)
    obs = create_dummy_observation()

    purge_target = ObservedTarget(
        target_id="btn-execute-purge",
        selector="#btn-execute-purge",
        tag_name="button",
        role="button",
        text="Execute Database Purge",
        bounding_box=BoundingBox(x=50, y=600, width=180, height=40),
    )

    # 1. Attempt purge with NO approval token -> BLOCKED_BY_SAFETY
    blocked_intent = ActionIntent(action_type=ActionType.CLICK, target=purge_target, approval_token=None)

    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)

        res_blocked = await executor.execute(page, blocked_intent, obs)
        assert res_blocked.status == ExecutionStatus.BLOCKED_BY_SAFETY
        assert "Explicit operator approval token is required" in res_blocked.error_message

        # 2. Attempt purge with bogus token -> BLOCKED_BY_SAFETY
        bogus_intent = ActionIntent(
            action_type=ActionType.CLICK, target=purge_target, approval_token="FAKE-TOKEN-1234"
        )
        res_bogus = await executor.execute(page, bogus_intent, obs)
        assert res_bogus.status == ExecutionStatus.BLOCKED_BY_SAFETY

        # 3. Purge with valid system token -> ALLOWED & EXECUTED
        valid_intent = ActionIntent(
            action_type=ActionType.CLICK,
            target=purge_target,
            approval_token=ApprovalGate.VALID_SYSTEM_TOKEN,
        )
        res_allowed = await executor.execute(page, valid_intent, obs)
        assert res_allowed.status == ExecutionStatus.SUCCESS
        assert "Clicked target" in res_allowed.evidence
