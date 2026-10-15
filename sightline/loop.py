"""Visual interaction loop orchestrator: Observe -> Ground -> Validate -> Act -> Observe -> Verify."""

from __future__ import annotations

import time
import uuid
from typing import List, Optional
from pydantic import BaseModel, Field

from playwright.async_api import Page

from sightline.config import Settings, get_settings
from sightline.executor.action_runner import BoundedActionExecutor, default_action_executor
from sightline.executor.models import ActionIntent, ActionResult, ActionType, ExecutionStatus
from sightline.grounding.grounder import DeterministicGrounder, default_grounder
from sightline.grounding.models import GroundingMatchStatus, GroundingRequest, GroundingResult
from sightline.observation.models import ObservationResult
from sightline.observation.observer import VisualObserver, default_visual_observer
from sightline.verification.models import VerificationResult, VerificationStatus, VisiblePostcondition
from sightline.verification.verifier import ClosedLoopVerifier, default_verifier


class InteractionStep(BaseModel):
    """Specification of a single step in a goal-oriented interaction plan."""

    intent_type: ActionType
    target_query: str = Field(description="Label, element ID, or attribute to uniquely ground")
    target_role: Optional[str] = Field(default=None, description="Optional role constraint")
    value: Optional[str] = Field(default=None, description="Value for text fields or select options")
    approval_token: Optional[str] = Field(default=None, description="Approval token for protected actions")
    expected_postcondition: Optional[VisiblePostcondition] = Field(
        default=None, description="Visible postcondition asserted after action"
    )
    description: Optional[str] = Field(default=None, description="Human-readable step intent")
    wait_for_selector: Optional[str] = Field(
        default=None, description="Optional CSS selector to wait for before observation (e.g. delayed enablement)"
    )


class StepExecutionTrace(BaseModel):
    """Auditable trace for a single executed step in the loop."""

    step_index: int
    intent: InteractionStep
    pre_observation: ObservationResult
    grounding_result: GroundingResult
    action_result: Optional[ActionResult] = None
    post_observation: Optional[ObservationResult] = None
    verification_result: Optional[VerificationResult] = None
    success: bool
    error_message: Optional[str] = None


class RunTrace(BaseModel):
    """Complete auditable trace of an evaluation run across all steps."""

    run_id: str
    scenario_id: Optional[str] = None
    status: str = Field(description="success | failed | blocked_safety | stopped_ambiguity | budget_exceeded")
    total_steps: int
    step_traces: List[StepExecutionTrace] = Field(default_factory=list)
    started_at: float
    completed_at: float
    summary: str = ""


class VisualInteractionLoop:
    """Deterministic visual interaction loop for evaluating agent reliability.

    Implements:
    Observe -> Ground target -> Validate action -> Act -> Observe again -> Verify result.
    """

    def __init__(
        self,
        observer: Optional[VisualObserver] = None,
        grounder: Optional[DeterministicGrounder] = None,
        executor: Optional[BoundedActionExecutor] = None,
        verifier: Optional[ClosedLoopVerifier] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.observer = observer or (
            default_visual_observer
            if self.settings.artifacts_dir == default_visual_observer.settings.artifacts_dir
            else VisualObserver(settings=self.settings)
        )
        self.grounder = grounder or default_grounder
        self.executor = executor if executor is not None else BoundedActionExecutor()
        self.verifier = verifier or default_verifier

    def reset_budget(self) -> None:
        """Reset step budget on the executor."""
        self.executor.reset_budget()

    async def execute_step(
        self,
        page: Page,
        step: InteractionStep,
        step_index: int = 1,
    ) -> StepExecutionTrace:
        """Execute one complete cycle of observe-ground-validate-act-observe-verify."""
        # Optional prerequisite synchronization
        if step.wait_for_selector:
            try:
                await page.wait_for_selector(step.wait_for_selector, timeout=3000)
            except Exception:
                pass

        # 1. Observe pre-action state
        pre_obs = await self.observer.observe(page)

        # 2. Ground target deterministically
        ground_req = GroundingRequest(
            query=step.target_query,
            role=step.target_role,
        )
        ground_res = self.grounder.ground(pre_obs, ground_req)

        # Ambiguous, missing, or out-of-bounds targets abort the step safely
        if ground_res.status != GroundingMatchStatus.MATCH_UNIQUE or not ground_res.matched_target:
            return StepExecutionTrace(
                step_index=step_index,
                intent=step,
                pre_observation=pre_obs,
                grounding_result=ground_res,
                action_result=None,
                post_observation=None,
                verification_result=None,
                success=False,
                error_message=f"Grounding failed with status '{ground_res.status.value}': {ground_res.error_message}",
            )

        # 3. Formulate bounded ActionIntent
        target = ground_res.matched_target
        intent = ActionIntent(
            action_type=step.intent_type,
            target=target,
            value=step.value,
            approval_token=step.approval_token,
            description=step.description or f"{step.intent_type.value} on {target.target_id}",
        )

        # 4. Act with bounded safety checks
        action_res = await self.executor.execute(page, intent, pre_obs)

        # If action failed or was blocked by safety policy, record and stop
        if action_res.status != ExecutionStatus.SUCCESS:
            return StepExecutionTrace(
                step_index=step_index,
                intent=step,
                pre_observation=pre_obs,
                grounding_result=ground_res,
                action_result=action_res,
                post_observation=None,
                verification_result=None,
                success=False,
                error_message=f"Action failed with status '{action_res.status.value}': {action_res.error_message}",
            )

        # 5. Observe post-action state
        post_obs = await self.observer.observe(page)

        # 6. Verify postcondition if specified
        verification_res: Optional[VerificationResult] = None
        step_success = True
        err_msg: Optional[str] = None

        if step.expected_postcondition:
            is_destructive = "purge" in target.selector.lower()
            verification_res = await self.verifier.verify(
                page=page,
                pre_observation=pre_obs,
                post_observation=post_obs,
                postcondition=step.expected_postcondition,
                allow_recovery=True,
                is_destructive_action=is_destructive,
            )
            step_success = verification_res.status == VerificationStatus.VERIFIED
            if not step_success:
                err_msg = f"Postcondition verification failed: {verification_res.evidence}"

        return StepExecutionTrace(
            step_index=step_index,
            intent=step,
            pre_observation=pre_obs,
            grounding_result=ground_res,
            action_result=action_res,
            post_observation=post_obs,
            verification_result=verification_res,
            success=step_success,
            error_message=err_msg,
        )

    async def run_scenario(
        self,
        page: Page,
        scenario_id: str,
        steps: List[InteractionStep],
        max_budget: int = 10,
    ) -> RunTrace:
        """Run a sequential list of interaction steps through the complete visual loop."""
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        t_start = time.time()
        self.executor.reset_budget()
        self.executor.max_budget = max_budget

        traces: List[StepExecutionTrace] = []
        overall_status = "success"
        summary_msg = f"Successfully completed {len(steps)} steps."

        for idx, step in enumerate(steps, start=1):
            trace = await self.execute_step(page, step, step_index=idx)
            traces.append(trace)

            if not trace.success:
                if trace.grounding_result.status == GroundingMatchStatus.AMBIGUOUS:
                    overall_status = "stopped_ambiguity"
                elif trace.action_result and trace.action_result.status == ExecutionStatus.BLOCKED_BY_SAFETY:
                    overall_status = "blocked_safety"
                elif trace.action_result and trace.action_result.status == ExecutionStatus.BUDGET_EXCEEDED:
                    overall_status = "budget_exceeded"
                else:
                    overall_status = "failed"
                summary_msg = f"Run stopped at step {idx}: {trace.error_message}"
                break

        t_end = time.time()
        return RunTrace(
            run_id=run_id,
            scenario_id=scenario_id,
            status=overall_status,
            total_steps=len(traces),
            step_traces=traces,
            started_at=t_start,
            completed_at=t_end,
            summary=summary_msg,
        )


# Global default visual interaction loop instance
default_visual_loop = VisualInteractionLoop()
