"""Bounded action executor enforcing pre-flight validation and safety approval gates."""

from __future__ import annotations

import time
from typing import Optional

from playwright.async_api import Page

from sightline.executor.models import (
    ActionIntent,
    ActionResult,
    ActionType,
    ExecutionStatus,
)
from sightline.observation.models import ObservationResult
from sightline.safety.policy import ApprovalGate, PolicyDecision, default_approval_gate


class BoundedActionExecutor:
    """Executes validated interactions against the synthetic target application.

    Guarantees:
    - Target freshness: Re-validates target presence, visibility, and bounding box immediately before execution.
    - Viewport bounds: Rejects out-of-bounds or non-positive bounding box targets.
    - Safety governance: Intercepts critical/destructive actions via ApprovalGate before invoking browser driver.
    - Budget enforcement: Strict limit on cumulative steps to prevent infinite execution loops.
    """

    def __init__(
        self,
        approval_gate: Optional[ApprovalGate] = None,
        max_budget: int = 10,
    ) -> None:
        self.approval_gate = approval_gate or default_approval_gate
        self.max_budget = max_budget
        self.step_count = 0

    def reset_budget(self) -> None:
        """Reset step counter for a fresh run."""
        self.step_count = 0

    async def execute(
        self,
        page: Page,
        intent: ActionIntent,
        observation: ObservationResult,
    ) -> ActionResult:
        """Execute a single bounded action with comprehensive pre-flight verification."""
        t_start = time.perf_counter()
        current_step = self.step_count + 1

        # 1. Enforce cumulative step budget
        if self.step_count >= self.max_budget:
            return ActionResult(
                status=ExecutionStatus.BUDGET_EXCEEDED,
                action_intent=intent,
                step_index=current_step,
                execution_time_ms=(time.perf_counter() - t_start) * 1000,
                evidence=f"Action budget exceeded: max {self.max_budget} steps permitted.",
                error_message=f"Action budget exceeded ({self.max_budget} steps).",
            )

        target = intent.target

        # 2. Verify target box within observation viewport
        vw = observation.viewport_width
        vh = observation.viewport_height
        if not target.bounding_box.is_within_viewport(vw, vh):
            return ActionResult(
                status=ExecutionStatus.OUT_OF_BOUNDS,
                action_intent=intent,
                step_index=current_step,
                execution_time_ms=(time.perf_counter() - t_start) * 1000,
                evidence=f"Target bounding box ({target.bounding_box.x}, {target.bounding_box.y}, {target.bounding_box.width}, {target.bounding_box.height}) outside viewport ({vw}x{vh}).",
                error_message="Target is out of viewport bounds.",
            )

        # 3. Pre-flight check: Re-validate live target immediately before interaction
        try:
            locator = page.locator(target.selector)
            match_count = await locator.count()
            if match_count == 0:
                return ActionResult(
                    status=ExecutionStatus.TARGET_NOT_FOUND,
                    action_intent=intent,
                    step_index=current_step,
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    evidence=f"Pre-flight check failed: target element '{target.selector}' not found in live DOM (matched 0 elements).",
                    error_message=f"Target element '{target.selector}' not found in live DOM.",
                )

            # Check visibility
            is_visible = await locator.first.is_visible()
            if not is_visible:
                return ActionResult(
                    status=ExecutionStatus.TARGET_STALE,
                    action_intent=intent,
                    step_index=current_step,
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    evidence=f"Pre-flight check failed: target '{target.selector}' has become hidden.",
                    error_message="Target element is not visible.",
                )

            # Check enabled state
            is_disabled = await locator.first.is_disabled()
            if is_disabled:
                return ActionResult(
                    status=ExecutionStatus.TARGET_DISABLED,
                    action_intent=intent,
                    step_index=current_step,
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    evidence=f"Pre-flight check failed: target '{target.selector}' has disabled attribute.",
                    error_message="Target element is disabled.",
                )

            # Re-check live bounding box
            live_box = await locator.first.bounding_box()
            if not live_box or live_box["width"] <= 0 or live_box["height"] <= 0:
                return ActionResult(
                    status=ExecutionStatus.TARGET_STALE,
                    action_intent=intent,
                    step_index=current_step,
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    evidence="Pre-flight check failed: live element bounding box is invalid or zero-dimensioned.",
                    error_message="Target bounding box is invalid or stale.",
                )

        except Exception as exc:
            return ActionResult(
                status=ExecutionStatus.FAILED,
                action_intent=intent,
                step_index=current_step,
                execution_time_ms=(time.perf_counter() - t_start) * 1000,
                evidence=f"Pre-flight check error: {str(exc)}",
                error_message=str(exc),
            )

        # 4. Enforce Safety Approval Gate
        policy_decision = self.approval_gate.evaluate_action(
            action_name=intent.action_type.value,
            target_selector=target.selector,
            approval_token=intent.approval_token,
        )
        if policy_decision.decision != PolicyDecision.ALLOW:
            return ActionResult(
                status=ExecutionStatus.BLOCKED_BY_SAFETY,
                action_intent=intent,
                step_index=current_step,
                execution_time_ms=(time.perf_counter() - t_start) * 1000,
                evidence=f"Action blocked by safety policy ({policy_decision.risk_level.value}): {policy_decision.reason}",
                error_message=policy_decision.reason,
            )

        # 5. Execute supported action
        evidence_text = ""
        try:
            elem = locator.first
            if intent.action_type == ActionType.CLICK:
                await elem.click()
                evidence_text = f"Clicked target '{target.selector}' ({target.text})"

            elif intent.action_type == ActionType.FILL:
                val = intent.value or ""
                await elem.fill(val)
                evidence_text = f"Filled input '{target.selector}' with value '{val}'"

            elif intent.action_type == ActionType.CHECK:
                await elem.check()
                evidence_text = f"Checked checkbox '{target.selector}'"

            elif intent.action_type == ActionType.UNCHECK:
                await elem.uncheck()
                evidence_text = f"Unchecked checkbox '{target.selector}'"

            elif intent.action_type == ActionType.SELECT_OPTION:
                val = intent.value or ""
                await elem.select_option(val)
                evidence_text = f"Selected option '{val}' on '{target.selector}'"

            elif intent.action_type == ActionType.READ:
                text = await elem.inner_text()
                evidence_text = f"Read text from '{target.selector}': '{text.strip()}'"

            else:
                return ActionResult(
                    status=ExecutionStatus.UNSUPPORTED_ACTION,
                    action_intent=intent,
                    step_index=current_step,
                    execution_time_ms=(time.perf_counter() - t_start) * 1000,
                    evidence=f"Unsupported action type: {intent.action_type}",
                    error_message=f"Action type '{intent.action_type}' is not supported.",
                )

            # Increment step count only upon execution attempt
            self.step_count += 1

            return ActionResult(
                status=ExecutionStatus.SUCCESS,
                action_intent=intent,
                step_index=current_step,
                execution_time_ms=(time.perf_counter() - t_start) * 1000,
                evidence=evidence_text,
            )

        except Exception as exc:
            self.step_count += 1
            return ActionResult(
                status=ExecutionStatus.FAILED,
                action_intent=intent,
                step_index=current_step,
                execution_time_ms=(time.perf_counter() - t_start) * 1000,
                evidence=f"Browser driver execution failed: {str(exc)}",
                error_message=str(exc),
            )


# Default bounded executor instance
default_action_executor = BoundedActionExecutor()
