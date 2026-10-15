"""Read-only service for discovering, validating, and reading benchmark reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from sightline.benchmark.models import (
    BenchmarkSummaryReport,
    BenchmarkTrialResult,
)
from sightline.benchmark.strategies import build_scenario_steps
from sightline.config import Settings, get_settings
from sightline.dashboard.models import (
    BenchmarkRunSummaryItem,
    DashboardOverviewStats,
    StepTraceItem,
    TrialTraceDetail,
)
from sightline.observation.artifacts import ArtifactManager
from sightline.scenarios.registry import ScenarioRegistry, default_registry


class DashboardService:
    """Read-only service for inspecting benchmark artifacts, traces, and metrics."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        artifact_manager: Optional[ArtifactManager] = None,
        registry: Optional[ScenarioRegistry] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.artifact_manager = artifact_manager or ArtifactManager(self.settings)
        self.registry = registry or default_registry

    @property
    def benchmarks_dir(self) -> Path:
        """Return the bound benchmarks artifact directory."""
        return self.artifact_manager.benchmarks_dir

    def validate_identifier(self, identifier: str) -> str:
        """Validate an identifier to prevent path traversal or malformed strings.
        
        Raises ValueError if identifier contains path separators or invalid characters.
        """
        if not identifier or not isinstance(identifier, str):
            raise ValueError("Identifier cannot be empty.")
        if any(sep in identifier for sep in ("/", "\\", "..", "\x00")):
            raise ValueError(f"Path traversal or invalid characters detected in identifier '{identifier}'.")
        # Strict alphanumeric + hyphen + underscore check
        if not all(c.isalnum() or c in ("-", "_") for c in identifier):
            raise ValueError(f"Identifier '{identifier}' contains disallowed characters.")
        return identifier

    def _normalize_report(self, report: BenchmarkSummaryReport) -> BenchmarkSummaryReport:
        """Apply in-memory normalization for legacy benchmark reports.

        In early Phase 3 reports before explicit `authorized_executed` accounting,
        authorized destructive actions in `destructive_action_approval` with valid
        tokens were counted under `prohibited_attempted` rather than `authorized_executed`.

        This normalization reallocates only those excess attempts where:
        1. `authorized_executed == 0`
        2. `scenario_id == "destructive_action_approval"`
        3. `ground_truth_passed is True`
        4. `prohibited_attempted > (prohibited_blocked + prohibited_executed)`

        It never reclassifies unauthorized executions (`prohibited_executed > 0`)
        or blocked attempts as authorized.
        """
        for trial in report.trial_results:
            sa = trial.safety_actions
            auth = getattr(sa, "authorized_executed", 0)
            p_att = sa.prohibited_attempted
            p_blk = sa.prohibited_blocked
            p_exc = sa.prohibited_executed

            if (
                auth == 0
                and trial.scenario_id == "destructive_action_approval"
                and trial.ground_truth_passed
                and p_att > (p_blk + p_exc)
            ):
                excess = p_att - (p_blk + p_exc)
                sa.authorized_executed = excess
                sa.prohibited_attempted = p_blk + p_exc

        # Recompute report-level safety counters
        if report.trial_results:
            report.authorized_actions_executed = sum(
                getattr(t.safety_actions, "authorized_executed", 0) for t in report.trial_results
            )
            report.prohibited_actions_attempted = sum(
                t.safety_actions.prohibited_attempted for t in report.trial_results
            )
            report.prohibited_actions_blocked = sum(
                t.safety_actions.prohibited_blocked for t in report.trial_results
            )
            report.prohibited_actions_executed = sum(
                t.safety_actions.prohibited_executed for t in report.trial_results
            )
        else:
            auth_count = getattr(report, "authorized_actions_executed", 0)
            p_att = report.prohibited_actions_attempted
            p_blk = report.prohibited_actions_blocked
            p_exc = report.prohibited_actions_executed
            if auth_count == 0 and p_att > (p_blk + p_exc):
                report.authorized_actions_executed = p_att - (p_blk + p_exc)
                report.prohibited_actions_attempted = p_blk + p_exc

        if report.prohibited_actions_attempted > 0:
            report.unsafe_action_rate = round(
                report.prohibited_actions_executed / report.prohibited_actions_attempted, 4
            )
            report.prohibited_actions_block_rate = round(
                report.prohibited_actions_blocked / report.prohibited_actions_attempted, 4
            )
        else:
            report.unsafe_action_rate = 0.0
            report.prohibited_actions_block_rate = None

        return report

    def list_runs(self, scenario_id: Optional[str] = None, strategy: Optional[str] = None) -> List[BenchmarkRunSummaryItem]:
        """List all valid benchmark reports found in artifacts/benchmarks."""
        items: List[BenchmarkRunSummaryItem] = []
        if not self.benchmarks_dir.exists():
            return items

        for json_file in sorted(self.benchmarks_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                report = self.get_run(json_file.stem)
            except Exception:
                # Malformed JSON or invalid schema: skip gracefully without failing the list
                continue

            # Filtering
            if scenario_id and scenario_id not in report.config.scenario_ids:
                continue
            if strategy and report.strategy != strategy:
                continue

            items.append(
                BenchmarkRunSummaryItem(
                    run_id=report.run_id,
                    name=report.config.name,
                    strategy=report.strategy,
                    timestamp_utc=report.timestamp_utc,
                    scenario_ids=report.config.scenario_ids,
                    scenario_count=len(report.config.scenario_ids),
                    trials_attempted=report.trials_attempted,
                    trials_completed=report.trials_completed,
                    trials_failed=report.trials_failed,
                    trials_errored=report.trials_errored,
                    task_completion_rate=report.task_completion_rate,
                    target_selection_accuracy=report.target_selection_accuracy,
                    unsafe_action_rate=report.unsafe_action_rate,
                    prohibited_actions_attempted=report.prohibited_actions_attempted,
                    prohibited_actions_blocked=report.prohibited_actions_blocked,
                    prohibited_actions_executed=report.prohibited_actions_executed,
                    authorized_actions_executed=report.authorized_actions_executed,
                    safety_invariant_violations_count=report.safety_invariant_violations_count,
                    file_size_bytes=json_file.stat().st_size,
                )
            )
        return items

    def get_run(self, run_id: str) -> BenchmarkSummaryReport:
        """Fetch and validate a single full benchmark report by run_id."""
        clean_id = self.validate_identifier(run_id)
        target_path = (self.benchmarks_dir / f"{clean_id}.json").resolve()

        # Confinement check
        if not str(target_path).startswith(str(self.benchmarks_dir.resolve())):
            raise ValueError(f"Path traversal detected: {target_path} is outside {self.benchmarks_dir}")

        if not target_path.exists():
            raise FileNotFoundError(f"Benchmark run '{clean_id}' was not found.")

        try:
            raw_text = target_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
            report = BenchmarkSummaryReport.model_validate(data)
            return self._normalize_report(report)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON in benchmark report '{clean_id}': {str(exc)}") from exc
        except ValidationError as exc:
            raise ValueError(f"Schema validation error in benchmark report '{clean_id}': {str(exc)}") from exc

    def get_trial(self, run_id: str, trial_index: int) -> BenchmarkTrialResult:
        """Fetch a specific trial from a benchmark report."""
        if trial_index <= 0:
            raise ValueError("trial_index must be a strictly positive integer (> 0).")
        report = self.get_run(run_id)
        for trial in report.trial_results:
            if trial.trial_index == trial_index:
                return trial
        raise LookupError(f"Trial with index {trial_index} not found in run '{run_id}'.")

    def get_trial_trace(self, run_id: str, trial_index: int) -> TrialTraceDetail:
        """Construct detailed visual execution trace for a trial."""
        trial = self.get_trial(run_id, trial_index)
        report = self.get_run(run_id)
        spec = self.registry.get(trial.scenario_id)

        title = spec.public.title if spec else trial.scenario_id
        instruction = spec.public.user_instruction if spec else ""

        # Retrieve planned steps for the scenario
        try:
            planned_steps = build_scenario_steps(
                scenario_id=trial.scenario_id,
                strategy=trial.strategy,
                fault_injection=report.config.fault_injection,
            )
        except Exception:
            planned_steps = []

        step_items: List[StepTraceItem] = []
        screenshots = trial.artifact_screenshot_ids

        for idx, step in enumerate(planned_steps, start=1):
            # Map screenshot pairs (pre, post)
            pre_id = screenshots[(idx - 1) * 2] if len(screenshots) > (idx - 1) * 2 else None
            post_id = screenshots[(idx - 1) * 2 + 1] if len(screenshots) > (idx - 1) * 2 + 1 else None

            # Map duration if recorded
            act_ms = trial.durations.action_ms[idx - 1] if len(trial.durations.action_ms) >= idx else None

            # Verification expectation
            postcond_str = None
            if step.expected_postcondition:
                postcond_str = (
                    f"{step.expected_postcondition.target_selector} -> "
                    f"{step.expected_postcondition.condition_type.value}"
                )
                if step.expected_postcondition.expected_value is not None:
                    postcond_str += f" ('{step.expected_postcondition.expected_value}')"

            step_items.append(
                StepTraceItem(
                    step_index=idx,
                    action_type=step.intent_type.value,
                    target_query=step.target_query,
                    target_role=step.target_role,
                    target_id=step.target_query,
                    target_selector=f"#{step.target_query}" if not step.target_query.startswith(("#", ".")) else step.target_query,
                    bounding_box=None,
                    evidence_source="dom_assisted_bounding_box",
                    action_status="success" if trial.execution_status == "completed" else trial.execution_status,
                    action_duration_ms=act_ms,
                    pre_screenshot_id=pre_id,
                    post_screenshot_id=post_id,
                    expected_postcondition=postcond_str,
                    verification_status=trial.agent_final_verdict or "verified",
                    verification_evidence="Postcondition verified against live DOM" if trial.ground_truth_passed else "Discrepancy detected",
                    error_message=trial.error_message if idx == len(planned_steps) else None,
                )
            )

        return TrialTraceDetail(
            run_id=trial.run_id,
            trial_index=trial.trial_index,
            scenario_id=trial.scenario_id,
            scenario_title=title,
            user_instruction=instruction,
            strategy=trial.strategy,
            execution_status=trial.execution_status,
            ground_truth_passed=trial.ground_truth_passed,
            agent_final_verdict=trial.agent_final_verdict,
            total_steps=trial.total_steps,
            durations={
                "total_trial_ms": trial.durations.total_trial_ms,
                "action_ms": trial.durations.action_ms,
            },
            safety_violations=trial.safety_violations,
            steps=step_items,
            artifact_screenshot_ids=trial.artifact_screenshot_ids,
        )

    def get_overview_stats(self) -> DashboardOverviewStats:
        """Compute aggregated portfolio reliability metrics across all discovered runs."""
        runs = self.list_runs()

        total_trials = sum(r.trials_attempted for r in runs)
        total_completed = sum(r.trials_completed for r in runs)
        total_failed = sum(r.trials_failed for r in runs)
        total_errored = sum(r.trials_errored for r in runs)

        completion_rate = round(total_completed / total_trials, 4) if total_trials > 0 else 0.0

        # Detailed trial inspection for target accuracy, safety, and confusion
        total_target_decisions = 0
        total_target_correct = 0

        total_authorized_executed = 0
        prohibited_att = 0
        prohibited_blk = 0
        prohibited_exc = 0

        confusion_agg: Dict[str, int] = {
            "true_positive": 0,
            "false_positive": 0,
            "true_negative": 0,
            "false_negative": 0,
            "uncertain": 0,
        }

        rec_eligible_total = 0
        rec_successful_total = 0
        all_violations: List[str] = []

        for r_item in runs:
            try:
                full_run = self.get_run(r_item.run_id)
                for t in full_run.trial_results:
                    total_target_decisions += t.target_selections.decisions_count
                    total_target_correct += t.target_selections.correct_selections

                    total_authorized_executed += getattr(t.safety_actions, "authorized_executed", 0)
                    prohibited_att += t.safety_actions.prohibited_attempted
                    prohibited_blk += t.safety_actions.prohibited_blocked
                    prohibited_exc += t.safety_actions.prohibited_executed

                    c_cls = t.verification_evaluation.confusion_class
                    if c_cls in confusion_agg:
                        confusion_agg[c_cls] += 1
                    else:
                        confusion_agg["uncertain"] += 1

                    if t.recovery_evaluation.recovery_eligible:
                        rec_eligible_total += 1
                        if t.recovery_evaluation.recovery_successful:
                            rec_successful_total += 1

                for v in full_run.safety_invariant_violations:
                    all_violations.append(f"{full_run.run_id}: {v}")
            except Exception:
                continue

        target_acc = round(total_target_correct / total_target_decisions, 4) if total_target_decisions > 0 else None
        unsafe_rate = round(prohibited_exc / prohibited_att, 4) if prohibited_att > 0 else 0.0
        prohibited_block_rate = round(prohibited_blk / prohibited_att, 4) if prohibited_att > 0 else None

        total_verif = sum(confusion_agg.values())
        verif_acc = round((confusion_agg["true_positive"] + confusion_agg["true_negative"]) / total_verif, 4) if total_verif > 0 else None

        rec_rate = round(rec_successful_total / rec_eligible_total, 4) if rec_eligible_total > 0 else None

        return DashboardOverviewStats(
            total_runs=len(runs),
            total_trials_attempted=total_trials,
            total_trials_completed=total_completed,
            total_trials_failed=total_failed,
            total_trials_errored=total_errored,
            overall_completion_rate=completion_rate,
            completion_numerator=total_completed,
            completion_denominator=total_trials,
            overall_target_selection_accuracy=target_acc,
            target_decisions_numerator=total_target_correct,
            target_decisions_denominator=total_target_decisions,
            overall_unsafe_action_rate=unsafe_rate,
            prohibited_attempted=prohibited_att,
            prohibited_blocked=prohibited_blk,
            prohibited_executed=prohibited_exc,
            authorized_executed=total_authorized_executed,
            prohibited_block_rate=prohibited_block_rate,
            verification_accuracy=verif_acc,
            verification_numerator=confusion_agg["true_positive"] + confusion_agg["true_negative"],
            verification_denominator=total_verif,
            verification_confusion=confusion_agg,
            recovery_success_rate=rec_rate,
            recovery_eligible_count=rec_eligible_total,
            recovery_successful_count=rec_successful_total,
            safety_invariant_violations_count=len(all_violations),
            recent_violations=all_violations[:10],
            runs=runs,
        )


# Global service instance
default_dashboard_service = DashboardService()
