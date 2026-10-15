"""Pydantic domain models and schemas for Sightline reliability benchmarking."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class LatencyMetric(BaseModel):
    """Statistical summary of execution latencies in milliseconds."""

    count: int = Field(default=0, description="Total sample observations")
    mean_ms: float = Field(default=0.0, description="Mean latency in ms")
    median_ms: float = Field(default=0.0, description="50th percentile latency in ms")
    p95_ms: float = Field(default=0.0, description="95th percentile latency in ms")
    max_ms: float = Field(default=0.0, description="Maximum observed latency in ms")


class TargetSelectionMetrics(BaseModel):
    """Detailed accounting of target grounding choices."""

    decisions_count: int = Field(default=0, description="Total target-selection decisions evaluated")
    correct_selections: int = Field(default=0, description="Selections matching intended target")
    incorrect_selections: int = Field(default=0, description="Selections resolving to wrong element")
    ambiguous_selections: int = Field(default=0, description="Ambiguous queries rejected safely")
    safe_rejections: int = Field(default=0, description="Intentionally rejected invalid targets")


class SafetyActionMetrics(BaseModel):
    """Accounting of protected and prohibited action decisions."""

    prohibited_attempted: int = Field(default=0, description="Unauthorized protected actions attempted")
    prohibited_executed: int = Field(default=0, description="Unauthorized actions executed without authorization (must be 0)")
    prohibited_blocked: int = Field(default=0, description="Unauthorized actions successfully intercepted by approval gate")
    authorized_executed: int = Field(default=0, description="Protected actions executed with valid authorization")
    applicable_decisions: int = Field(default=0, description="Total protected action decision points")


class VerificationEvaluation(BaseModel):
    """Comparison between agent verification verdict and evaluator ground truth."""

    agent_verdict: Optional[str] = Field(default=None, description="Agent verdict: verified | failed | uncertain")
    evaluator_verdict: bool = Field(description="Evaluator ground-truth passed status")
    confusion_class: str = Field(
        description="Confusion classification: true_positive | false_positive | true_negative | false_negative | uncertain"
    )


class RecoveryEvaluation(BaseModel):
    """Accounting of bounded error-recovery performance."""

    recovery_eligible: bool = Field(default=False, description="Whether scenario had a recoverable fault")
    recovery_attempted: bool = Field(default=False, description="Whether bounded recovery retry was initiated")
    recovery_successful: bool = Field(default=False, description="Whether recovery restored intended state")


class TrialDurationMetrics(BaseModel):
    """Monotonic timing measurements for trial phases in milliseconds."""

    total_trial_ms: float = Field(default=0.0, description="Total elapsed duration in ms")
    observation_ms: List[float] = Field(default_factory=list, description="Per-observation latencies in ms")
    grounding_ms: List[float] = Field(default_factory=list, description="Per-grounding latencies in ms")
    action_ms: List[float] = Field(default_factory=list, description="Per-action execution latencies in ms")
    verification_ms: List[float] = Field(default_factory=list, description="Per-verification latencies in ms")


class BenchmarkConfig(BaseModel):
    """Configuration for a reproducible reliability benchmark run."""

    name: str = Field(default="sightline_benchmark", description="Identifier for this benchmark run")
    scenario_ids: List[str] = Field(description="List of scenario IDs to evaluate")
    trials_per_scenario: int = Field(default=1, description="Number of independent trials per scenario")
    max_budget: int = Field(default=8, description="Maximum step budget per trial")
    strategy: str = Field(default="closed_loop", description="Execution strategy: closed_loop | baseline")
    fault_injection: Optional[str] = Field(
        default=None,
        description="Optional controlled fault injection: ambiguous_query | unapproved_destructive | stale_target",
    )
    seed: int = Field(default=42, description="Deterministic seed for reproducibility")

    @field_validator("scenario_ids")
    @classmethod
    def validate_scenarios_non_empty(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("BenchmarkConfig scenario_ids list cannot be empty.")
        return v

    @field_validator("trials_per_scenario")
    @classmethod
    def validate_trials_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"trials_per_scenario must be strictly positive (> 0), got {v}")
        return v

    @field_validator("max_budget")
    @classmethod
    def validate_budget_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"max_budget must be strictly positive (> 0), got {v}")
        return v

    @field_validator("strategy")
    @classmethod
    def validate_strategy_known(cls, v: str) -> str:
        if v not in ("closed_loop", "baseline"):
            raise ValueError(f"Unknown strategy '{v}'; must be 'closed_loop' or 'baseline'.")
        return v

    @field_validator("fault_injection")
    @classmethod
    def validate_fault_known(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("ambiguous_query", "unapproved_destructive", "stale_target"):
            raise ValueError(f"Unsupported fault injection '{v}'.")
        return v


class BenchmarkTrialResult(BaseModel):
    """Structured record of a single evaluated benchmark trial."""

    schema_version: str = Field(default="1.0.0", description="Schema version identifier")
    run_id: str = Field(description="Parent benchmark run identifier")
    trial_index: int = Field(description="Trial index (1-based)")
    scenario_id: str = Field(description="Evaluated scenario identifier")
    strategy: str = Field(description="Execution strategy used")
    started_at: float = Field(description="Start timestamp in seconds")
    completed_at: float = Field(description="End timestamp in seconds")
    execution_status: str = Field(
        description="Execution status: completed | failed | blocked_safety | stopped_ambiguity | budget_exceeded | error"
    )
    ground_truth_passed: bool = Field(description="Independent evaluator ground-truth verdict")
    agent_final_verdict: Optional[str] = Field(default=None, description="Agent closed-loop verdict if verified")
    total_steps: int = Field(default=0, description="Steps executed")
    target_selections: TargetSelectionMetrics = Field(default_factory=TargetSelectionMetrics)
    safety_actions: SafetyActionMetrics = Field(default_factory=SafetyActionMetrics)
    verification_evaluation: VerificationEvaluation
    recovery_evaluation: RecoveryEvaluation = Field(default_factory=RecoveryEvaluation)
    durations: TrialDurationMetrics = Field(default_factory=TrialDurationMetrics)
    safety_violations_count: int = Field(default=0, description="Count of critical safety invariant violations")
    safety_violations: List[str] = Field(default_factory=list, description="Descriptions of any safety violations")
    trace_step_count: int = Field(default=0, description="Number of steps in execution trace")
    artifact_screenshot_ids: List[str] = Field(default_factory=list, description="IDs of screenshots taken")
    error_message: Optional[str] = None


class BenchmarkSummaryReport(BaseModel):
    """Aggregated, serializable summary report for a complete benchmark run."""

    schema_version: str = Field(default="1.0.0", description="Schema version identifier")
    run_id: str = Field(description="Unique benchmark run identifier")
    strategy: str = Field(description="Evaluated strategy: closed_loop | baseline")
    timestamp_utc: str = Field(description="ISO 8601 UTC timestamp of execution")
    config: BenchmarkConfig = Field(description="Exact configuration used to produce this report")
    trials_attempted: int = Field(description="Total trials attempted across all scenarios")
    trials_completed: int = Field(description="Trials where evaluator confirmed intended final state")
    trials_failed: int = Field(description="Trials failing ground-truth verification")
    trials_errored: int = Field(description="Trials encountering unexpected runtime errors")
    task_completion_rate: float = Field(description="completed / attempted (0.0 to 1.0)")
    target_selection_accuracy: Optional[float] = Field(
        default=None, description="correct / decisions_count where decisions_count > 0"
    )
    target_decisions_count: int = Field(default=0)
    unsafe_action_rate: float = Field(
        default=0.0, description="executed_prohibited / attempted_prohibited (must be 0.0)"
    )
    prohibited_actions_attempted: int = Field(default=0)
    prohibited_actions_blocked: int = Field(default=0)
    prohibited_actions_executed: int = Field(default=0)
    authorized_actions_executed: int = Field(default=0, description="Total authorized destructive actions executed")
    prohibited_actions_block_rate: Optional[float] = Field(
        default=None, description="Ratio of blocked unauthorized attempts to attempted (None if 0 attempted)"
    )
    verification_accuracy: Optional[float] = Field(
        default=None, description="(TP + TN) / total_verifications where applicable"
    )
    verification_confusion: Dict[str, int] = Field(
        default_factory=lambda: {
            "true_positive": 0,
            "false_positive": 0,
            "true_negative": 0,
            "false_negative": 0,
            "uncertain": 0,
        }
    )
    recovery_success_rate: Optional[float] = Field(
        default=None, description="successful / eligible where eligible > 0"
    )
    recovery_eligible_count: int = Field(default=0)
    recovery_successful_count: int = Field(default=0)
    latency_summary: Dict[str, LatencyMetric] = Field(default_factory=dict)
    safety_invariant_violations_count: int = Field(default=0)
    safety_invariant_violations: List[str] = Field(default_factory=list)
    trial_results: List[BenchmarkTrialResult] = Field(default_factory=list)
    summary_text: str = Field(default="", description="Human-readable text summary")
