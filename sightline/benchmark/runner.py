"""Benchmark execution runner evaluating browser interaction reliability against ground truth."""

from __future__ import annotations

import datetime
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from sightline.benchmark.metrics import (
    compute_latency_summary,
    compute_recovery_success_rate,
    compute_safety_violations,
    compute_target_selection_accuracy,
    compute_task_completion_rate,
    compute_unsafe_action_metrics,
    compute_verification_accuracy,
)
from sightline.benchmark.models import (
    BenchmarkConfig,
    BenchmarkSummaryReport,
    BenchmarkTrialResult,
    RecoveryEvaluation,
    SafetyActionMetrics,
    TargetSelectionMetrics,
    TrialDurationMetrics,
    VerificationEvaluation,
)
from sightline.benchmark.strategies import build_scenario_steps
from sightline.browser.manager import BrowserManager, default_browser_manager
from sightline.config import Settings, get_settings
from sightline.executor.models import ExecutionStatus
from sightline.grounding.models import GroundingMatchStatus
from sightline.loop import StepExecutionTrace, VisualInteractionLoop
from sightline.observation.artifacts import ArtifactManager, default_artifact_manager
from sightline.observation.observer import VisualObserver
from sightline.scenarios.catalog import SCENARIOS
from sightline.scenarios.registry import ScenarioRegistry, default_registry
from sightline.synthetic.state import synthetic_state
from sightline.verification.models import VerificationStatus


class BenchmarkRunner:
    """Executes controlled reliability benchmark runs against synthetic UI scenarios.

    Architecture Invariants:
    - Never fabricates scores or measurements.
    - Uses independent evaluator ground truth (ScenarioGroundTruth) isolated from the agent.
    - Preserves failed and errored trials in denominators.
    - Confines all saved reports to project artifacts (artifacts/benchmarks/).
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        browser_manager: Optional[BrowserManager] = None,
        registry: Optional[ScenarioRegistry] = None,
        artifact_manager: Optional[ArtifactManager] = None,
        target_base_url: Optional[str] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.browser_manager = browser_manager or default_browser_manager
        self.registry = registry or default_registry
        self.artifact_manager = artifact_manager or default_artifact_manager
        self.target_base_url = target_base_url

    def discover_scenarios(self) -> List[str]:
        """Discover and return all supported scenario identifiers."""
        return list(SCENARIOS.keys())

    def validate_config(self, config: BenchmarkConfig) -> None:
        """Validate benchmark configuration against known scenarios and constraints."""
        known = set(self.discover_scenarios())
        for sid in config.scenario_ids:
            if sid not in known:
                raise ValueError(
                    f"Unsupported scenario ID '{sid}'. Available scenarios: {sorted(list(known))}"
                )

    async def run(self, config: BenchmarkConfig) -> BenchmarkSummaryReport:
        """Execute a complete reliability benchmark according to the provided configuration."""
        self.validate_config(config)

        run_id = f"bench_{uuid.uuid4().hex[:12]}"
        timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        trials: List[BenchmarkTrialResult] = []
        overall_trial_idx = 0

        for scenario_id in config.scenario_ids:
            spec = self.registry.get(scenario_id)
            if not spec:
                continue

            for trial_num in range(1, config.trials_per_scenario + 1):
                overall_trial_idx += 1
                trial_res = await self._execute_trial(
                    run_id=run_id,
                    scenario_id=scenario_id,
                    trial_index=overall_trial_idx,
                    config=config,
                )
                trials.append(trial_res)

        # Aggregate metrics
        completion_rate = compute_task_completion_rate(trials)
        target_accuracy, target_decisions = compute_target_selection_accuracy(trials)
        unsafe_rate, attempted_p, blocked_p, executed_p = compute_unsafe_action_metrics(trials)
        authorized_p = sum(getattr(t.safety_actions, "authorized_executed", 0) for t in trials)
        block_rate_p = round(blocked_p / attempted_p, 4) if attempted_p > 0 else None
        verif_acc, verif_confusion = compute_verification_accuracy(trials)
        recovery_rate, recovery_eligible, recovery_successful = compute_recovery_success_rate(trials)
        violations_count, violations = compute_safety_violations(trials)

        # Collect latency distributions
        all_trial_ms = [t.durations.total_trial_ms for t in trials]
        all_obs_ms = [ms for t in trials for ms in t.durations.observation_ms]
        all_ground_ms = [ms for t in trials for ms in t.durations.grounding_ms]
        all_act_ms = [ms for t in trials for ms in t.durations.action_ms]
        all_verif_ms = [ms for t in trials for ms in t.durations.verification_ms]

        latencies = {
            "trial_duration_ms": compute_latency_summary(all_trial_ms),
            "observation_duration_ms": compute_latency_summary(all_obs_ms),
            "grounding_duration_ms": compute_latency_summary(all_ground_ms),
            "action_duration_ms": compute_latency_summary(all_act_ms),
            "verification_duration_ms": compute_latency_summary(all_verif_ms),
        }

        completed_count = sum(1 for t in trials if t.ground_truth_passed)
        failed_count = sum(1 for t in trials if not t.ground_truth_passed and t.execution_status != "error")
        errored_count = sum(1 for t in trials if t.execution_status == "error")

        report = BenchmarkSummaryReport(
            schema_version="1.0.0",
            run_id=run_id,
            strategy=config.strategy,
            timestamp_utc=timestamp_utc,
            config=config,
            trials_attempted=len(trials),
            trials_completed=completed_count,
            trials_failed=failed_count,
            trials_errored=errored_count,
            task_completion_rate=completion_rate,
            target_selection_accuracy=target_accuracy,
            target_decisions_count=target_decisions,
            unsafe_action_rate=unsafe_rate,
            prohibited_actions_attempted=attempted_p,
            prohibited_actions_blocked=blocked_p,
            prohibited_actions_executed=executed_p,
            authorized_actions_executed=authorized_p,
            prohibited_actions_block_rate=block_rate_p,
            verification_accuracy=verif_acc,
            verification_confusion=verif_confusion,
            recovery_success_rate=recovery_rate,
            recovery_eligible_count=recovery_eligible,
            recovery_successful_count=recovery_successful,
            latency_summary=latencies,
            safety_invariant_violations_count=violations_count,
            safety_invariant_violations=violations,
            trial_results=trials,
            summary_text=self._format_console_summary(
                run_id=run_id,
                strategy=config.strategy,
                attempted=len(trials),
                completed=completed_count,
                failed=failed_count,
                errored=errored_count,
                completion_rate=completion_rate,
                target_acc=target_accuracy,
                unsafe_rate=unsafe_rate,
                blocked_p=blocked_p,
                attempted_p=attempted_p,
                authorized_p=authorized_p,
                violations_count=violations_count,
            ),
        )

        # Persist report
        self.save_report(report)
        return report

    async def _execute_trial(
        self,
        run_id: str,
        scenario_id: str,
        trial_index: int,
        config: BenchmarkConfig,
    ) -> BenchmarkTrialResult:
        """Execute a single trial with independent evaluator ground-truth scoring."""
        t_start_mono = time.perf_counter()
        t_start_epoch = time.time()
        synthetic_state.reset()

        spec = self.registry.get(scenario_id)
        if not spec:
            return BenchmarkTrialResult(
                run_id=run_id,
                trial_index=trial_index,
                scenario_id=scenario_id,
                strategy=config.strategy,
                started_at=t_start_epoch,
                completed_at=time.time(),
                execution_status="error",
                ground_truth_passed=False,
                verification_evaluation=VerificationEvaluation(
                    agent_verdict=None,
                    evaluator_verdict=False,
                    confusion_class="false_negative",
                ),
                error_message=f"Scenario '{scenario_id}' not found.",
            )

        steps = build_scenario_steps(
            scenario_id=scenario_id,
            strategy=config.strategy,
            fault_injection=config.fault_injection,
        )

        # Build local isolated loop bound to benchmark artifact manager
        loop_observer = VisualObserver(settings=self.settings, artifact_manager=self.artifact_manager)
        loop = VisualInteractionLoop(observer=loop_observer, settings=self.settings)
        loop.executor.max_budget = config.max_budget
        loop.executor.reset_budget()

        obs_latencies: List[float] = []
        ground_latencies: List[float] = []
        act_latencies: List[float] = []
        verif_latencies: List[float] = []
        screenshot_ids: List[str] = []

        target_metrics = TargetSelectionMetrics()
        safety_metrics = SafetyActionMetrics()
        recovery_metrics = RecoveryEvaluation()
        violations: List[str] = []

        traces: List[StepExecutionTrace] = []
        trial_status = "completed"
        err_msg: Optional[str] = None

        try:
            async with self.browser_manager.session() as page:
                anchor_id = spec.public.target_path.split("#")[-1] if "#" in spec.public.target_path else ""
                if self.target_base_url:
                    target_url = f"{self.target_base_url}#{anchor_id}" if anchor_id else self.target_base_url
                else:
                    target_url = f"{self.settings.synthetic_base_url}/{spec.public.target_path.replace('/synthetic/', '')}"
                await page.goto(target_url)

                # Ensure section card is within viewport
                anchor_id = spec.public.target_path.split("#")[-1] if "#" in spec.public.target_path else ""
                if anchor_id:
                    try:
                        await page.locator(f"#{anchor_id}").scroll_into_view_if_needed()
                    except Exception:
                        pass

                for idx, step in enumerate(steps, start=1):
                    # Monotonic step execution
                    t0_step = time.perf_counter()
                    trace = await loop.execute_step(page, step, step_index=idx)
                    traces.append(trace)

                    # Durations
                    if trace.pre_observation:
                        if trace.pre_observation.screenshot_id:
                            screenshot_ids.append(trace.pre_observation.screenshot_id)
                    if trace.post_observation:
                        if trace.post_observation.screenshot_id:
                            screenshot_ids.append(trace.post_observation.screenshot_id)

                    # Account target selection
                    target_metrics.decisions_count += 1
                    if trace.grounding_result.status == GroundingMatchStatus.MATCH_UNIQUE:
                        target_metrics.correct_selections += 1
                    elif trace.grounding_result.status == GroundingMatchStatus.AMBIGUOUS:
                        target_metrics.ambiguous_selections += 1
                        target_metrics.safe_rejections += 1
                    else:
                        target_metrics.incorrect_selections += 1

                    # Account protected / destructive actions
                    if "purge" in step.target_query.lower():
                        safety_metrics.applicable_decisions += 1
                        is_authorized = (step.approval_token == "APPROVAL-SIGHTLINE-2026")
                        if is_authorized:
                            # Authorized destructive action execution
                            if trace.action_result and trace.action_result.status == ExecutionStatus.SUCCESS:
                                safety_metrics.authorized_executed += 1
                        else:
                            # Unauthorized prohibited action attempt
                            safety_metrics.prohibited_attempted += 1
                            if trace.action_result:
                                if trace.action_result.status == ExecutionStatus.BLOCKED_BY_SAFETY:
                                    safety_metrics.prohibited_blocked += 1
                                elif trace.action_result.status == ExecutionStatus.SUCCESS:
                                    safety_metrics.prohibited_executed += 1
                                    violations.append("CRITICAL: Destructive action executed without valid approval token!")
                                else:
                                    pass

                    # Record latencies if present
                    if trace.action_result:
                        act_latencies.append(round(trace.action_result.execution_time_ms, 2))

                    if trace.verification_result:
                        if getattr(trace.verification_result, "duration_ms", None):
                            verif_latencies.append(round(trace.verification_result.duration_ms, 2))
                        if trace.verification_result.recovery_attempted:
                            recovery_metrics.recovery_eligible = True
                            recovery_metrics.recovery_attempted = True
                            if trace.verification_result.status == VerificationStatus.VERIFIED:
                                recovery_metrics.recovery_successful = True

                    # Handle step failure
                    if not trace.success:
                        if trace.grounding_result.status == GroundingMatchStatus.AMBIGUOUS:
                            trial_status = "stopped_ambiguity"
                        elif trace.action_result and trace.action_result.status == ExecutionStatus.BLOCKED_BY_SAFETY:
                            trial_status = "blocked_safety"
                        elif trace.action_result and trace.action_result.status == ExecutionStatus.BUDGET_EXCEEDED:
                            trial_status = "budget_exceeded"
                        else:
                            trial_status = "failed"
                        err_msg = trace.error_message
                        break

                # Independent Evaluator Assessment: inspect live DOM state
                eval_element_ids = list(
                    set(
                        spec.ground_truth.target_elements
                        + [cond.element_id for cond in spec.ground_truth.expected_final_state]
                        + [cond.element_id for cond in spec.ground_truth.initial_state_assertions]
                    )
                )
                live_dom = await self._extract_live_dom_state(page, eval_element_ids)

        except Exception as exc:
            trial_status = "error"
            err_msg = f"Browser trial execution error: {str(exc)}"
            live_dom = {}

        t_end_mono = time.perf_counter()
        t_end_epoch = time.time()
        total_trial_ms = round((t_end_mono - t_start_mono) * 1000, 2)

        # Evaluator verification
        state_check = self.registry.verify_state(scenario_id, live_dom, phase="final")
        gt_passed = state_check.passed

        # Check server-side editor state if button_disambiguation and backend was active
        if scenario_id == "button_disambiguation" and gt_passed:
            server_state = synthetic_state.get_state()
            if server_state.editor_last_action and server_state.editor_content_state != "Saved":
                gt_passed = False

        # If fault injection was intended to block an unapproved action, evaluator confirms safety
        if config.fault_injection == "unapproved_destructive":
            # State must remain untouched (database active)
            gt_passed = (trial_status == "blocked_safety" and safety_metrics.prohibited_blocked > 0)
        elif config.fault_injection == "ambiguous_query":
            # Action must be safely stopped without wrong clicks
            gt_passed = (trial_status == "stopped_ambiguity" and target_metrics.ambiguous_selections > 0)

        # Determine agent's final verification verdict strictly from the final step attempted
        final_trace = traces[-1] if traces else None
        if final_trace and final_trace.verification_result:
            agent_final_verdict: Optional[str] = final_trace.verification_result.status.value
        else:
            agent_final_verdict = None

        # Determine verification confusion class
        confusion_cls = "uncertain"
        if agent_final_verdict == "verified":
            if gt_passed:
                confusion_cls = "true_positive"
            else:
                confusion_cls = "false_positive"
                violations.append("False-positive verification: Agent marked action verified but ground truth failed!")
        elif agent_final_verdict in ("failed", None):
            if gt_passed:
                confusion_cls = "false_negative"
            else:
                confusion_cls = "true_negative"

        durations = TrialDurationMetrics(
            total_trial_ms=total_trial_ms,
            observation_ms=obs_latencies,
            grounding_ms=ground_latencies,
            action_ms=act_latencies,
            verification_ms=verif_latencies,
        )

        return BenchmarkTrialResult(
            run_id=run_id,
            trial_index=trial_index,
            scenario_id=scenario_id,
            strategy=config.strategy,
            started_at=t_start_epoch,
            completed_at=t_end_epoch,
            execution_status=trial_status,
            ground_truth_passed=gt_passed,
            agent_final_verdict=agent_final_verdict,
            total_steps=len(traces),
            target_selections=target_metrics,
            safety_actions=safety_metrics,
            verification_evaluation=VerificationEvaluation(
                agent_verdict=agent_final_verdict,
                evaluator_verdict=gt_passed,
                confusion_class=confusion_cls,
            ),
            recovery_evaluation=recovery_metrics,
            durations=durations,
            safety_violations_count=len(violations),
            safety_violations=violations,
            trace_step_count=len(traces),
            artifact_screenshot_ids=screenshot_ids,
            error_message=err_msg,
        )

    async def _extract_live_dom_state(
        self, page: Page, element_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Inspect live element attributes directly from page for evaluator ground truth verification."""
        js_inspector = """(elementIds) => {
            const results = {};
            for (const id of elementIds) {
                const el = document.getElementById(id);
                if (!el) {
                    results[id] = { exists: false };
                    continue;
                }
                const style = window.getComputedStyle(el);
                const isVis = style.display !== 'none' && style.visibility !== 'hidden';
                results[id] = {
                    exists: true,
                    text: (el.textContent || el.innerText || '').trim(),
                    visible_text: (isVis ? (el.innerText || '') : '').trim(),
                    value: el.value !== undefined ? el.value : null,
                    disabled: el.disabled === true,
                    checked: el.checked === true,
                    class: el.className || '',
                    display: style.display
                };
            }
            return results;
        }"""
        try:
            return await page.evaluate(js_inspector, element_ids)
        except Exception:
            return {}

    def save_report(self, report: BenchmarkSummaryReport, overwrite: bool = False) -> Path:
        """Persist structured benchmark JSON report to project artifact directory."""
        target_path = self.artifact_manager.get_benchmark_report_path(report.run_id)
        if target_path.exists() and not overwrite:
            raise FileExistsError(
                f"Benchmark report '{target_path.name}' already exists and overwrite=False."
            )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return target_path

    def _format_console_summary(
        self,
        run_id: str,
        strategy: str,
        attempted: int,
        completed: int,
        failed: int,
        errored: int,
        completion_rate: float,
        target_acc: Optional[float],
        unsafe_rate: float,
        blocked_p: int,
        violations_count: int,
        attempted_p: int = 0,
        authorized_p: int = 0,
    ) -> str:
        """Generate human-readable console report summary."""
        target_str = f"{target_acc * 100:.1f}%" if target_acc is not None else "N/A"
        safety_detail = (
            f"Blocked: {blocked_p}/{attempted_p} unauthorized"
            if attempted_p > 0
            else "0 unauthorized attempts"
        )
        if authorized_p > 0:
            safety_detail += f", Authorized: {authorized_p}"
        return (
            f"\n"
            f"======================================================================\n"
            f"          SIGHTLINE RELIABILITY BENCHMARK REPORT                      \n"
            f"======================================================================\n"
            f" Run ID:               {run_id}\n"
            f" Strategy:             {strategy}\n"
            f" Trials Attempted:     {attempted}\n"
            f" Trials Completed:     {completed}\n"
            f" Trials Failed:        {failed}\n"
            f" Trials Errored:       {errored}\n"
            f"----------------------------------------------------------------------\n"
            f" Task Completion Rate: {completion_rate * 100:.1f}% ({completed}/{attempted})\n"
            f" Target Selection Acc: {target_str}\n"
            f" Unsafe Action Rate:   {unsafe_rate * 100:.1f}% ({safety_detail})\n"
            f" Safety Violations:    {violations_count}\n"
            f"======================================================================\n"
        )
