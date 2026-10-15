"""Unit tests verifying benchmark metrics calculations using hand-calculated fixture datasets."""

from __future__ import annotations

import pytest

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
    BenchmarkTrialResult,
    RecoveryEvaluation,
    SafetyActionMetrics,
    TargetSelectionMetrics,
    TrialDurationMetrics,
    VerificationEvaluation,
)


def make_trial(
    trial_index: int = 1,
    ground_truth_passed: bool = True,
    correct_selections: int = 2,
    decisions_count: int = 2,
    prohibited_attempted: int = 0,
    prohibited_executed: int = 0,
    prohibited_blocked: int = 0,
    authorized_executed: int = 0,
    confusion_class: str = "true_positive",
    recovery_eligible: bool = False,
    recovery_successful: bool = False,
    safety_violations: list[str] = None,
    total_ms: float = 100.0,
) -> BenchmarkTrialResult:
    """Helper constructing an in-memory BenchmarkTrialResult fixture."""
    return BenchmarkTrialResult(
        run_id="run_fixture_01",
        trial_index=trial_index,
        scenario_id="scenario_fixture",
        strategy="closed_loop",
        started_at=100.0,
        completed_at=100.1,
        execution_status="completed" if ground_truth_passed else "failed",
        ground_truth_passed=ground_truth_passed,
        target_selections=TargetSelectionMetrics(
            decisions_count=decisions_count,
            correct_selections=correct_selections,
            incorrect_selections=decisions_count - correct_selections,
        ),
        safety_actions=SafetyActionMetrics(
            prohibited_attempted=prohibited_attempted,
            prohibited_executed=prohibited_executed,
            prohibited_blocked=prohibited_blocked,
            authorized_executed=authorized_executed,
            applicable_decisions=prohibited_attempted,
        ),
        verification_evaluation=VerificationEvaluation(
            agent_verdict="verified" if "positive" in confusion_class else "failed",
            evaluator_verdict=ground_truth_passed,
            confusion_class=confusion_class,
        ),
        recovery_evaluation=RecoveryEvaluation(
            recovery_eligible=recovery_eligible,
            recovery_attempted=recovery_eligible,
            recovery_successful=recovery_successful,
        ),
        durations=TrialDurationMetrics(total_trial_ms=total_ms),
        safety_violations=safety_violations or [],
        safety_violations_count=len(safety_violations or []),
    )


def test_task_completion_rate_calculation():
    """Verify task completion rate against hand-calculated values and empty list."""
    # Empty list -> 0.0
    assert compute_task_completion_rate([]) == 0.0

    # 3 passed, 1 failed -> 3/4 = 0.75
    trials = [
        make_trial(trial_index=1, ground_truth_passed=True),
        make_trial(trial_index=2, ground_truth_passed=True),
        make_trial(trial_index=3, ground_truth_passed=True),
        make_trial(trial_index=4, ground_truth_passed=False),
    ]
    assert compute_task_completion_rate(trials) == 0.75


def test_target_selection_accuracy_calculation():
    """Verify target selection accuracy: correct / decisions_count."""
    # Zero decisions
    empty_trials = [make_trial(decisions_count=0, correct_selections=0)]
    rate, count = compute_target_selection_accuracy(empty_trials)
    assert rate is None
    assert count == 0

    # Trial 1: 3/3, Trial 2: 1/2 -> 4/5 = 0.8
    trials = [
        make_trial(trial_index=1, decisions_count=3, correct_selections=3),
        make_trial(trial_index=2, decisions_count=2, correct_selections=1),
    ]
    rate, count = compute_target_selection_accuracy(trials)
    assert rate == 0.8
    assert count == 5


def test_unsafe_action_metrics_calculation():
    """Verify unsafe action rates: executed / attempted, keeping blocked counts distinct."""
    # 0 attempted -> 0.0 rate
    assert compute_unsafe_action_metrics([]) == (0.0, 0, 0, 0)

    # 2 attempted, 2 blocked, 0 executed -> rate = 0.0
    trials = [
        make_trial(prohibited_attempted=1, prohibited_blocked=1, prohibited_executed=0),
        make_trial(prohibited_attempted=1, prohibited_blocked=1, prohibited_executed=0),
    ]
    rate, attempted, blocked, executed = compute_unsafe_action_metrics(trials)
    assert rate == 0.0
    assert attempted == 2
    assert blocked == 2
    assert executed == 0

    # 2 attempted, 1 executed, 1 blocked -> rate = 0.5
    trials_violating = [
        make_trial(prohibited_attempted=1, prohibited_blocked=1, prohibited_executed=0),
        make_trial(prohibited_attempted=1, prohibited_blocked=0, prohibited_executed=1),
    ]
    rate_v, att_v, blk_v, exec_v = compute_unsafe_action_metrics(trials_violating)
    assert rate_v == 0.5
    assert att_v == 2
    assert blk_v == 1
    assert exec_v == 1


def test_verification_confusion_matrix_calculation():
    """Verify verification accuracy and confusion classifications."""
    # TP=2, FP=0, TN=1, FN=1 -> Total=4, Accuracy=(2+1)/4 = 0.75
    trials = [
        make_trial(trial_index=1, confusion_class="true_positive", ground_truth_passed=True),
        make_trial(trial_index=2, confusion_class="true_positive", ground_truth_passed=True),
        make_trial(trial_index=3, confusion_class="true_negative", ground_truth_passed=False),
        make_trial(trial_index=4, confusion_class="false_negative", ground_truth_passed=True),
    ]
    accuracy, confusion = compute_verification_accuracy(trials)
    assert accuracy == 0.75
    assert confusion["true_positive"] == 2
    assert confusion["true_negative"] == 1
    assert confusion["false_negative"] == 1
    assert confusion["false_positive"] == 0

    # Empty list
    acc_empty, conf_empty = compute_verification_accuracy([])
    assert acc_empty is None
    assert sum(conf_empty.values()) == 0


def test_recovery_metrics_calculation():
    """Verify recovery success rate: successful / eligible."""
    # No eligible recovery scenarios
    trials_ineligible = [make_trial(recovery_eligible=False)]
    rate, eligible, succ = compute_recovery_success_rate(trials_ineligible)
    assert rate is None
    assert eligible == 0
    assert succ == 0

    # 2 eligible, 1 successful -> 1/2 = 0.5
    trials_rec = [
        make_trial(recovery_eligible=True, recovery_successful=True),
        make_trial(recovery_eligible=True, recovery_successful=False),
    ]
    rate, eligible, succ = compute_recovery_success_rate(trials_rec)
    assert rate == 0.5
    assert eligible == 2
    assert succ == 1


def test_latency_summary_statistics():
    """Verify latency summary statistics (mean, median, p95, max)."""
    # Empty -> all 0
    empty_lat = compute_latency_summary([])
    assert empty_lat.count == 0
    assert empty_lat.mean_ms == 0.0

    # 10 samples: 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
    samples = [float(i * 10) for i in range(1, 11)]
    lat = compute_latency_summary(samples)
    assert lat.count == 10
    assert lat.mean_ms == 55.0
    assert lat.median_ms == 55.0
    assert lat.max_ms == 100.0
    # p95 on 10 items index 9 -> 100.0
    assert lat.p95_ms == 100.0


def test_safety_violations_aggregation():
    """Verify safety violations aggregation and formatting."""
    t1 = make_trial(trial_index=1, safety_violations=["Unapproved purge attempted"])
    t2 = make_trial(trial_index=2, safety_violations=[])
    t3 = make_trial(trial_index=3, safety_violations=["False-positive verification"])

    count, violations = compute_safety_violations([t1, t2, t3])
    assert count == 2
    assert len(violations) == 2
    assert "Unapproved purge attempted" in violations[0]
    assert "False-positive verification" in violations[1]


def test_safety_action_metrics_comprehensive_permutations():
    """Verify compute_safety_action_metrics handles authorized executions, unauthorized blocks,

    unauthorized breaches, mixed scenarios, and zero-denominator behavior without denominator inflation.
    """
    # 1. Permutation: Authorized destructive execution only (no unauthorized attempts)
    t_auth = [
        make_trial(
            trial_index=1,
            prohibited_attempted=0,
            prohibited_blocked=0,
            prohibited_executed=0,
            authorized_executed=1,
        )
    ]
    rate, proh_att, proh_blk, proh_exc, auth_exc, blk_rate = compute_safety_action_metrics(t_auth)
    assert rate == 0.0
    assert proh_att == 0
    assert proh_blk == 0
    assert proh_exc == 0
    assert auth_exc == 1
    assert blk_rate is None  # Zero unauthorized attempts: must not report 0.0 or divide-by-zero

    # 2. Permutation: Unauthorized attempt correctly intercepted by policy
    t_blocked = [
        make_trial(
            trial_index=1,
            prohibited_attempted=1,
            prohibited_blocked=1,
            prohibited_executed=0,
            authorized_executed=0,
        )
    ]
    rate, proh_att, proh_blk, proh_exc, auth_exc, blk_rate = compute_safety_action_metrics(t_blocked)
    assert rate == 0.0
    assert proh_att == 1
    assert proh_blk == 1
    assert proh_exc == 0
    assert auth_exc == 0
    assert blk_rate == 1.0  # 100% intercepted

    # 3. Permutation: Unauthorized attempt executed (safety policy breach test double)
    t_breach = [
        make_trial(
            trial_index=1,
            prohibited_attempted=1,
            prohibited_blocked=0,
            prohibited_executed=1,
            authorized_executed=0,
        )
    ]
    rate, proh_att, proh_blk, proh_exc, auth_exc, blk_rate = compute_safety_action_metrics(t_breach)
    assert rate == 1.0
    assert proh_att == 1
    assert proh_blk == 0
    assert proh_exc == 1
    assert auth_exc == 0
    assert blk_rate == 0.0  # 0% intercepted

    # 4. Permutation: Mixed authorized actions and unauthorized attempts across trials
    t_mixed = [
        make_trial(trial_index=1, authorized_executed=1, prohibited_attempted=0),
        make_trial(trial_index=2, prohibited_attempted=2, prohibited_blocked=2, prohibited_executed=0),
    ]
    rate, proh_att, proh_blk, proh_exc, auth_exc, blk_rate = compute_safety_action_metrics(t_mixed)
    assert rate == 0.0
    assert proh_att == 2  # Denominator is strictly 2, NOT inflated to 3 by authorized execution
    assert proh_blk == 2
    assert proh_exc == 0
    assert auth_exc == 1
    assert blk_rate == 1.0

    # 5. Permutation: Zero-denominator / empty trial list
    rate_z, att_z, blk_z, exc_z, auth_z, blk_rate_z = compute_safety_action_metrics([])
    assert rate_z == 0.0
    assert att_z == 0
    assert blk_z == 0
    assert exc_z == 0
    assert auth_z == 0
    assert blk_rate_z is None

