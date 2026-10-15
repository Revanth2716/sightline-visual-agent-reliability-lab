"""Domain models for the Sightline inspection dashboard."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from sightline.benchmark.models import (
    BenchmarkConfig,
    BenchmarkSummaryReport,
    BenchmarkTrialResult,
    LatencyMetric,
)


class BenchmarkRunSummaryItem(BaseModel):
    """Compact summary of a benchmark run for list views."""

    run_id: str
    name: str
    strategy: str
    timestamp_utc: str
    scenario_ids: List[str]
    scenario_count: int
    trials_attempted: int
    trials_completed: int
    trials_failed: int
    trials_errored: int
    task_completion_rate: float
    target_selection_accuracy: Optional[float] = None
    unsafe_action_rate: float = 0.0
    prohibited_actions_attempted: int = 0
    prohibited_actions_blocked: int = 0
    prohibited_actions_executed: int = 0
    authorized_actions_executed: int = 0
    safety_invariant_violations_count: int = 0
    file_size_bytes: int


class StepTraceItem(BaseModel):
    """Detailed visual trace for a single step in a trial."""

    step_index: int
    action_type: str
    target_query: str
    target_role: Optional[str] = None
    target_id: Optional[str] = None
    target_selector: Optional[str] = None
    bounding_box: Optional[Dict[str, float]] = None
    evidence_source: str = "dom_assisted_bounding_box"
    action_status: str
    action_duration_ms: Optional[float] = None
    pre_screenshot_id: Optional[str] = None
    post_screenshot_id: Optional[str] = None
    expected_postcondition: Optional[str] = None
    verification_status: Optional[str] = None
    verification_evidence: Optional[str] = None
    error_message: Optional[str] = None


class TrialTraceDetail(BaseModel):
    """Full execution trace of a trial for the trace and screenshot inspector."""

    run_id: str
    trial_index: int
    scenario_id: str
    scenario_title: str
    user_instruction: str
    strategy: str
    execution_status: str
    ground_truth_passed: bool
    agent_final_verdict: Optional[str] = None
    total_steps: int
    durations: Dict[str, Any]
    safety_violations: List[str]
    steps: List[StepTraceItem]
    artifact_screenshot_ids: List[str]


class DashboardOverviewStats(BaseModel):
    """Aggregated portfolio metrics across all saved benchmark runs."""

    total_runs: int
    total_trials_attempted: int
    total_trials_completed: int
    total_trials_failed: int
    total_trials_errored: int
    overall_completion_rate: float
    completion_numerator: int
    completion_denominator: int
    overall_target_selection_accuracy: Optional[float]
    target_decisions_numerator: int
    target_decisions_denominator: int
    overall_unsafe_action_rate: float
    prohibited_attempted: int
    prohibited_blocked: int
    prohibited_executed: int
    authorized_executed: int = 0
    prohibited_block_rate: Optional[float] = None
    verification_accuracy: Optional[float]
    verification_numerator: int
    verification_denominator: int
    verification_confusion: Dict[str, int]
    recovery_success_rate: Optional[float]
    recovery_eligible_count: int
    recovery_successful_count: int
    safety_invariant_violations_count: int
    recent_violations: List[str]
    runs: List[BenchmarkRunSummaryItem]
