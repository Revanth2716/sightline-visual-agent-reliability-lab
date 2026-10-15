"""Unit tests for BenchmarkRunner configuration, discovery, persistence, and metric recomputation."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from sightline.benchmark.metrics import (
    compute_task_completion_rate,
    compute_unsafe_action_metrics,
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
from sightline.benchmark.runner import BenchmarkRunner
from sightline.executor.models import ExecutionStatus
from sightline.grounding.models import GroundingMatchStatus
from sightline.observation.artifacts import ArtifactManager
from sightline.verification.models import VerificationStatus
from unittest.mock import AsyncMock, MagicMock, patch


def test_runner_discovers_all_five_scenarios():
    """Verify BenchmarkRunner automatically discovers all 5 canonical scenarios."""
    runner = BenchmarkRunner()
    scenarios = runner.discover_scenarios()
    assert len(scenarios) == 5
    assert "form_submission_validation" in scenarios
    assert "button_disambiguation" in scenarios
    assert "modal_confirmation_workflow" in scenarios
    assert "delayed_enablement_button" in scenarios
    assert "destructive_action_approval" in scenarios


def test_config_validation_rejections():
    """Verify BenchmarkConfig rejects invalid parameters with explicit ValueErrors."""
    # Empty scenario IDs
    with pytest.raises(ValueError, match="cannot be empty"):
        BenchmarkConfig(scenario_ids=[])

    # Trials <= 0
    with pytest.raises(ValueError, match="strictly positive"):
        BenchmarkConfig(scenario_ids=["button_disambiguation"], trials_per_scenario=0)

    # Budget <= 0
    with pytest.raises(ValueError, match="strictly positive"):
        BenchmarkConfig(scenario_ids=["button_disambiguation"], max_budget=-1)

    # Unknown strategy
    with pytest.raises(ValueError, match="Unknown strategy"):
        BenchmarkConfig(scenario_ids=["button_disambiguation"], strategy="unsupported_strategy")

    # Unsupported fault injection
    with pytest.raises(ValueError, match="Unsupported fault injection"):
        BenchmarkConfig(scenario_ids=["button_disambiguation"], fault_injection="magic_fault")

    # Unknown scenario in runner validation
    runner = BenchmarkRunner()
    invalid_cfg = BenchmarkConfig(scenario_ids=["nonexistent_scenario_123"])
    with pytest.raises(ValueError, match="Unsupported scenario ID"):
        runner.validate_config(invalid_cfg)


def test_report_persistence_and_overwrite_protection(tmp_path: Path):
    """Verify benchmark reports persist to artifacts and protect against accidental overwrites."""
    art_mgr = ArtifactManager()
    runner = BenchmarkRunner(artifact_manager=art_mgr)

    dummy_cfg = BenchmarkConfig(scenario_ids=["button_disambiguation"], trials_per_scenario=1)
    dummy_report = BenchmarkSummaryReport(
        schema_version="1.0.0",
        run_id="bench_test_persist_01",
        strategy="closed_loop",
        timestamp_utc="2026-10-14T12:00:00Z",
        config=dummy_cfg,
        trials_attempted=1,
        trials_completed=1,
        trials_failed=0,
        trials_errored=0,
        task_completion_rate=1.0,
        trial_results=[
            BenchmarkTrialResult(
                run_id="bench_test_persist_01",
                trial_index=1,
                scenario_id="button_disambiguation",
                strategy="closed_loop",
                started_at=10.0,
                completed_at=11.0,
                execution_status="completed",
                ground_truth_passed=True,
                verification_evaluation=VerificationEvaluation(
                    agent_verdict="verified",
                    evaluator_verdict=True,
                    confusion_class="true_positive",
                ),
            )
        ],
    )

    saved_path = runner.save_report(dummy_report, overwrite=True)
    assert saved_path.exists()
    assert saved_path.name == "bench_test_persist_01.json"
    assert "benchmarks" in str(saved_path).replace("\\", "/")
    assert "artifacts" in str(saved_path).replace("\\", "/")

    # Saving again with overwrite=False must raise FileExistsError
    with pytest.raises(FileExistsError, match="already exists"):
        runner.save_report(dummy_report, overwrite=False)

    # Re-saving with overwrite=True succeeds
    runner.save_report(dummy_report, overwrite=True)

    # Verify no host absolute paths in the persisted JSON
    raw_content = saved_path.read_text(encoding="utf-8")
    assert "C:\\Users\\" not in raw_content
    assert "D:\\Revanth" not in raw_content

    # Clean up test artifact
    saved_path.unlink()


def test_recompute_metrics_from_saved_report():
    """Verify that aggregate metrics can be mathematically recomputed from trial results."""
    cfg = BenchmarkConfig(scenario_ids=["form_submission_validation", "button_disambiguation"], trials_per_scenario=1)
    t1 = BenchmarkTrialResult(
        run_id="bench_recompute",
        trial_index=1,
        scenario_id="form_submission_validation",
        strategy="closed_loop",
        started_at=10.0,
        completed_at=11.0,
        execution_status="completed",
        ground_truth_passed=True,
        safety_actions=SafetyActionMetrics(prohibited_attempted=1, prohibited_blocked=1, prohibited_executed=0),
        verification_evaluation=VerificationEvaluation(
            agent_verdict="verified", evaluator_verdict=True, confusion_class="true_positive"
        ),
    )
    t2 = BenchmarkTrialResult(
        run_id="bench_recompute",
        trial_index=2,
        scenario_id="button_disambiguation",
        strategy="closed_loop",
        started_at=11.0,
        completed_at=12.0,
        execution_status="failed",
        ground_truth_passed=False,
        safety_actions=SafetyActionMetrics(prohibited_attempted=0, prohibited_blocked=0, prohibited_executed=0),
        verification_evaluation=VerificationEvaluation(
            agent_verdict="failed", evaluator_verdict=False, confusion_class="true_negative"
        ),
    )

    report = BenchmarkSummaryReport(
        schema_version="1.0.0",
        run_id="bench_recompute",
        strategy="closed_loop",
        timestamp_utc="2026-10-14T12:00:00Z",
        config=cfg,
        trials_attempted=2,
        trials_completed=1,
        trials_failed=1,
        trials_errored=0,
        task_completion_rate=0.5,
        unsafe_action_rate=0.0,
        trial_results=[t1, t2],
    )

    # Recompute directly from report.trial_results
    recomputed_completion = compute_task_completion_rate(report.trial_results)
    assert recomputed_completion == report.task_completion_rate == 0.5

    recomputed_unsafe_rate, attempted, blocked, executed = compute_unsafe_action_metrics(report.trial_results)
    assert recomputed_unsafe_rate == report.unsafe_action_rate == 0.0
    assert attempted == 1
    assert blocked == 1
    assert executed == 0


def _create_mock_session():
    mock_page = AsyncMock()
    mock_page.locator = MagicMock()
    mock_locator = MagicMock()
    mock_locator.scroll_into_view_if_needed = AsyncMock()
    mock_page.locator.return_value = mock_locator
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_page)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


@pytest.mark.asyncio
async def test_multistep_trial_step1_verified_step2_grounding_failure():
    """Verify that a multi-step trial with step 1 verified and step 2 failing grounding

    does not inherit step 1's verdict, records agent_final_verdict=None,
    evaluates to true_negative, and appends zero safety invariant violations.
    """
    runner = BenchmarkRunner()
    cfg = BenchmarkConfig(scenario_ids=["modal_confirmation_workflow"], strategy="closed_loop")

    t1 = MagicMock(success=True, pre_observation=None, post_observation=None)
    t1.grounding_result.status = GroundingMatchStatus.MATCH_UNIQUE
    t1.action_result.status = ExecutionStatus.SUCCESS
    t1.action_result.execution_time_ms = 10.0
    t1.verification_result.status = VerificationStatus.VERIFIED
    t1.verification_result.recovery_attempted = False
    t1.verification_result.duration_ms = 5.0

    t2_grounding_fail = MagicMock(success=False, pre_observation=None, post_observation=None)
    t2_grounding_fail.grounding_result.status = GroundingMatchStatus.NO_MATCH
    t2_grounding_fail.action_result = None
    t2_grounding_fail.verification_result = None
    t2_grounding_fail.error_message = "Grounding failed: no_match"

    mock_session = _create_mock_session()

    with patch.object(runner.browser_manager, "session", return_value=mock_session), \
         patch("sightline.benchmark.runner.VisualInteractionLoop.execute_step", side_effect=[t1, t2_grounding_fail]), \
         patch.object(runner, "_extract_live_dom_state", new_callable=AsyncMock, return_value={}):
        res = await runner._execute_trial("bench_test_multi", "modal_confirmation_workflow", 1, cfg)

    assert res.agent_final_verdict is None
    assert res.execution_status == "failed"
    assert res.ground_truth_passed is False
    assert res.verification_evaluation.agent_verdict is None
    assert res.verification_evaluation.evaluator_verdict is False
    assert res.verification_evaluation.confusion_class == "true_negative"
    assert res.safety_violations_count == 0
    assert len(res.safety_violations) == 0


@pytest.mark.asyncio
async def test_multistep_trial_step1_verified_step2_verification_failure():
    """Verify that a multi-step trial with step 1 verified and step 2 failing verification

    records agent_final_verdict='failed', evaluates to true_negative, and produces zero violations.
    """
    runner = BenchmarkRunner()
    cfg = BenchmarkConfig(scenario_ids=["modal_confirmation_workflow"], strategy="closed_loop")

    t1 = MagicMock(success=True, pre_observation=None, post_observation=None)
    t1.grounding_result.status = GroundingMatchStatus.MATCH_UNIQUE
    t1.action_result.status = ExecutionStatus.SUCCESS
    t1.action_result.execution_time_ms = 10.0
    t1.verification_result.status = VerificationStatus.VERIFIED
    t1.verification_result.recovery_attempted = False
    t1.verification_result.duration_ms = 5.0

    t2_verif_fail = MagicMock(success=False, pre_observation=None, post_observation=None)
    t2_verif_fail.grounding_result.status = GroundingMatchStatus.MATCH_UNIQUE
    t2_verif_fail.action_result.status = ExecutionStatus.SUCCESS
    t2_verif_fail.action_result.execution_time_ms = 12.0
    t2_verif_fail.verification_result.status = VerificationStatus.FAILED
    t2_verif_fail.verification_result.recovery_attempted = False
    t2_verif_fail.verification_result.duration_ms = 6.0
    t2_verif_fail.error_message = "Postcondition failed"

    mock_session = _create_mock_session()

    with patch.object(runner.browser_manager, "session", return_value=mock_session), \
         patch("sightline.benchmark.runner.VisualInteractionLoop.execute_step", side_effect=[t1, t2_verif_fail]), \
         patch.object(runner, "_extract_live_dom_state", new_callable=AsyncMock, return_value={}):
        res = await runner._execute_trial("bench_test_multi", "modal_confirmation_workflow", 1, cfg)

    assert res.agent_final_verdict == "failed"
    assert res.execution_status == "failed"
    assert res.ground_truth_passed is False
    assert res.verification_evaluation.agent_verdict == "failed"
    assert res.verification_evaluation.evaluator_verdict is False
    assert res.verification_evaluation.confusion_class == "true_negative"
    assert res.safety_violations_count == 0


@pytest.mark.asyncio
async def test_multistep_trial_step1_verified_step2_verified_success():
    """Verify that a successful multi-step trial records agent_final_verdict='verified'

    and evaluates to true_positive when evaluator ground truth passes.
    """
    runner = BenchmarkRunner()
    cfg = BenchmarkConfig(scenario_ids=["modal_confirmation_workflow"], strategy="closed_loop")

    t1 = MagicMock(success=True, pre_observation=None, post_observation=None)
    t1.grounding_result.status = GroundingMatchStatus.MATCH_UNIQUE
    t1.action_result.status = ExecutionStatus.SUCCESS
    t1.action_result.execution_time_ms = 10.0
    t1.verification_result.status = VerificationStatus.VERIFIED
    t1.verification_result.recovery_attempted = False
    t1.verification_result.duration_ms = 5.0

    t2_success = MagicMock(success=True, pre_observation=None, post_observation=None)
    t2_success.grounding_result.status = GroundingMatchStatus.MATCH_UNIQUE
    t2_success.action_result.status = ExecutionStatus.SUCCESS
    t2_success.action_result.execution_time_ms = 12.0
    t2_success.verification_result.status = VerificationStatus.VERIFIED
    t2_success.verification_result.recovery_attempted = False
    t2_success.verification_result.duration_ms = 6.0

    valid_dom = {
        "deploy-modal-overlay": {"class": "modal-overlay hidden"},
        "deploy-state-badge": {"text": "Deployed (v1.4.2)"},
        "deploy-audit-log": {"text": "Deployment v1.4.2 released to production at 10:00"},
    }

    mock_session = _create_mock_session()

    with patch.object(runner.browser_manager, "session", return_value=mock_session), \
         patch("sightline.benchmark.runner.VisualInteractionLoop.execute_step", side_effect=[t1, t2_success]), \
         patch.object(runner, "_extract_live_dom_state", new_callable=AsyncMock, return_value=valid_dom):
        res = await runner._execute_trial("bench_test_multi", "modal_confirmation_workflow", 1, cfg)

    assert res.agent_final_verdict == "verified"
    assert res.execution_status == "completed"
    assert res.ground_truth_passed is True
    assert res.verification_evaluation.agent_verdict == "verified"
    assert res.verification_evaluation.evaluator_verdict is True
    assert res.verification_evaluation.confusion_class == "true_positive"
    assert res.safety_violations_count == 0


@pytest.mark.asyncio
async def test_multistep_trial_step1_verified_step2_verified_evaluator_fails():
    """Verify that when final step is verified by agent but evaluator ground truth fails,

    the trial correctly records false_positive and appends a safety invariant violation.
    """
    runner = BenchmarkRunner()
    cfg = BenchmarkConfig(scenario_ids=["modal_confirmation_workflow"], strategy="closed_loop")

    t1 = MagicMock(success=True, pre_observation=None, post_observation=None)
    t1.grounding_result.status = GroundingMatchStatus.MATCH_UNIQUE
    t1.action_result.status = ExecutionStatus.SUCCESS
    t1.action_result.execution_time_ms = 10.0
    t1.verification_result.status = VerificationStatus.VERIFIED
    t1.verification_result.recovery_attempted = False
    t1.verification_result.duration_ms = 5.0

    t2_success = MagicMock(success=True, pre_observation=None, post_observation=None)
    t2_success.grounding_result.status = GroundingMatchStatus.MATCH_UNIQUE
    t2_success.action_result.status = ExecutionStatus.SUCCESS
    t2_success.action_result.execution_time_ms = 12.0
    t2_success.verification_result.status = VerificationStatus.VERIFIED
    t2_success.verification_result.recovery_attempted = False
    t2_success.verification_result.duration_ms = 6.0

    # Failing DOM state: deploy state still Idle
    invalid_dom = {
        "deploy-modal-overlay": {"class": "modal-overlay hidden"},
        "deploy-state-badge": {"text": "Idle"},
        "deploy-audit-log": {"text": "No deployments executed yet."},
    }

    mock_session = _create_mock_session()

    with patch.object(runner.browser_manager, "session", return_value=mock_session), \
         patch("sightline.benchmark.runner.VisualInteractionLoop.execute_step", side_effect=[t1, t2_success]), \
         patch.object(runner, "_extract_live_dom_state", new_callable=AsyncMock, return_value=invalid_dom):
        res = await runner._execute_trial("bench_test_multi", "modal_confirmation_workflow", 1, cfg)

    assert res.agent_final_verdict == "verified"
    assert res.execution_status == "completed"
    assert res.ground_truth_passed is False
    assert res.verification_evaluation.confusion_class == "false_positive"
    assert res.safety_violations_count == 1
    assert "False-positive verification" in res.safety_violations[0]
