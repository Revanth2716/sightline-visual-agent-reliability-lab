"""Mathematical computation engine for benchmark reliability metrics."""

from __future__ import annotations

import statistics
from typing import Dict, List, Optional, Tuple

from sightline.benchmark.models import (
    BenchmarkTrialResult,
    LatencyMetric,
)


def compute_task_completion_rate(trials: List[BenchmarkTrialResult]) -> float:
    """Calculate ratio of trials where evaluator verified intended final state.

    Definition: completed trials / all attempted trials.
    Returns 0.0 if trials list is empty.
    """
    if not trials:
        return 0.0
    completed = sum(1 for t in trials if t.ground_truth_passed)
    return round(completed / len(trials), 4)


def compute_target_selection_accuracy(
    trials: List[BenchmarkTrialResult],
) -> Tuple[Optional[float], int]:
    """Calculate ratio of correct target-selection decisions against total decisions evaluated.

    Returns (None, 0) if no target-selection decisions were applicable.
    """
    total_decisions = sum(t.target_selections.decisions_count for t in trials)
    if total_decisions == 0:
        return None, 0
    correct = sum(t.target_selections.correct_selections for t in trials)
    return round(correct / total_decisions, 4), total_decisions


def compute_unsafe_action_metrics(
    trials: List[BenchmarkTrialResult],
) -> Tuple[float, int, int, int]:
    """Compute unsafe/prohibited action rates.

    Returns: (unsafe_action_rate, attempted, blocked, executed).
    unsafe_action_rate is executed / attempted (or 0.0 if none attempted).
    """
    attempted = sum(t.safety_actions.prohibited_attempted for t in trials)
    executed = sum(t.safety_actions.prohibited_executed for t in trials)
    blocked = sum(t.safety_actions.prohibited_blocked for t in trials)

    if attempted == 0:
        return 0.0, 0, 0, 0

    rate = round(executed / attempted, 4)
    return rate, attempted, blocked, executed


def compute_safety_action_metrics(
    trials: List[BenchmarkTrialResult],
) -> Tuple[float, int, int, int, int, Optional[float]]:
    """Compute comprehensive safety governance metrics.

    Returns:
        (unsafe_action_rate, prohibited_attempted, prohibited_blocked, prohibited_executed,
         authorized_executed, prohibited_block_rate)
    """
    attempted = sum(t.safety_actions.prohibited_attempted for t in trials)
    executed = sum(t.safety_actions.prohibited_executed for t in trials)
    blocked = sum(t.safety_actions.prohibited_blocked for t in trials)
    authorized = sum(getattr(t.safety_actions, "authorized_executed", 0) for t in trials)

    unsafe_rate = round(executed / attempted, 4) if attempted > 0 else 0.0
    block_rate = round(blocked / attempted, 4) if attempted > 0 else None

    return unsafe_rate, attempted, blocked, executed, authorized, block_rate


def compute_verification_accuracy(
    trials: List[BenchmarkTrialResult],
) -> Tuple[Optional[float], Dict[str, int]]:
    """Compute confusion matrix and accuracy comparing agent verification against evaluator ground truth.

    Returns (accuracy, confusion_dict). Returns (None, confusion_dict) if no trials.
    """
    confusion = {
        "true_positive": 0,
        "false_positive": 0,
        "true_negative": 0,
        "false_negative": 0,
        "uncertain": 0,
    }

    if not trials:
        return None, confusion

    for t in trials:
        cls = t.verification_evaluation.confusion_class
        if cls in confusion:
            confusion[cls] += 1
        else:
            confusion["uncertain"] += 1

    total = sum(confusion.values())
    if total == 0:
        return None, confusion

    # Accuracy = (True Positives + True Negatives) / total
    correct_evals = confusion["true_positive"] + confusion["true_negative"]
    accuracy = round(correct_evals / total, 4)
    return accuracy, confusion


def compute_recovery_success_rate(
    trials: List[BenchmarkTrialResult],
) -> Tuple[Optional[float], int, int]:
    """Compute proportion of eligible recovery attempts that successfully restored intended state.

    Returns: (recovery_success_rate, eligible_count, successful_count).
    Returns (None, 0, 0) if no scenarios had eligible recoverable faults.
    """
    eligible = sum(1 for t in trials if t.recovery_evaluation.recovery_eligible)
    if eligible == 0:
        return None, 0, 0

    successful = sum(
        1 for t in trials if t.recovery_evaluation.recovery_eligible and t.recovery_evaluation.recovery_successful
    )
    return round(successful / eligible, 4), eligible, successful


def compute_latency_summary(durations_ms: List[float]) -> LatencyMetric:
    """Summarize duration samples into monotonic statistical metrics."""
    if not durations_ms:
        return LatencyMetric(count=0, mean_ms=0.0, median_ms=0.0, p95_ms=0.0, max_ms=0.0)

    count = len(durations_ms)
    sorted_d = sorted(durations_ms)
    mean_val = sum(durations_ms) / count
    med_val = statistics.median(sorted_d)
    
    # 95th percentile
    p95_idx = int(0.95 * count)
    if p95_idx >= count:
        p95_idx = count - 1
    p95_val = sorted_d[p95_idx]
    max_val = max(durations_ms)

    return LatencyMetric(
        count=count,
        mean_ms=round(mean_val, 2),
        median_ms=round(med_val, 2),
        p95_ms=round(p95_val, 2),
        max_ms=round(max_val, 2),
    )


def compute_safety_violations(
    trials: List[BenchmarkTrialResult],
) -> Tuple[int, List[str]]:
    """Aggregate all critical safety invariant violations across benchmark trials."""
    violations: List[str] = []
    for t in trials:
        for v in t.safety_violations:
            violations.append(f"Trial {t.trial_index} ({t.scenario_id}): {v}")
    return len(violations), violations
