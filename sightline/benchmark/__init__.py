"""Sightline reliability benchmarking subsystem."""

from sightline.benchmark.metrics import (
    compute_latency_summary,
    compute_recovery_success_rate,
    compute_safety_action_metrics,
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
    LatencyMetric,
    RecoveryEvaluation,
    SafetyActionMetrics,
    TargetSelectionMetrics,
    TrialDurationMetrics,
    VerificationEvaluation,
)
from sightline.benchmark.runner import BenchmarkRunner
from sightline.benchmark.strategies import build_scenario_steps

__all__ = [
    "BenchmarkConfig",
    "BenchmarkRunner",
    "BenchmarkSummaryReport",
    "BenchmarkTrialResult",
    "LatencyMetric",
    "RecoveryEvaluation",
    "SafetyActionMetrics",
    "TargetSelectionMetrics",
    "TrialDurationMetrics",
    "VerificationEvaluation",
    "build_scenario_steps",
    "compute_latency_summary",
    "compute_recovery_success_rate",
    "compute_safety_action_metrics",
    "compute_safety_violations",
    "compute_target_selection_accuracy",
    "compute_task_completion_rate",
    "compute_unsafe_action_metrics",
    "compute_verification_accuracy",
]
