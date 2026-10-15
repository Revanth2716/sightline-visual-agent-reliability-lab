"""Integration and unit tests for the Sightline inspection dashboard backend API."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from sightline.app import create_app
from sightline.benchmark.models import (
    BenchmarkConfig,
    BenchmarkSummaryReport,
    BenchmarkTrialResult,
    VerificationEvaluation,
)
from sightline.config import Settings
from sightline.dashboard.service import DashboardService
from sightline.observation.artifacts import ArtifactManager


@pytest.fixture
def dashboard_app():
    """FastAPI application fixture configured to inspect production benchmark artifacts."""
    dash_settings = Settings(
        environment="test",
        host="127.0.0.1",
        port=8199,
        browser_headless=True,
        artifacts_dir="artifacts",
    )
    return create_app(dash_settings)


@pytest.fixture
async def dashboard_client(dashboard_app):
    """Async HTTP client for testing dashboard endpoints."""
    transport = ASGITransport(app=dashboard_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_dashboard_overview_endpoint(dashboard_client: AsyncClient):
    """Verify /api/dashboard/overview returns real portfolio aggregates with numerators and denominators."""
    resp = await dashboard_client.get("/api/dashboard/overview")
    assert resp.status_code == 200
    data = resp.json()

    assert "total_runs" in data
    assert "total_trials_attempted" in data
    assert "overall_completion_rate" in data
    assert "completion_numerator" in data
    assert "completion_denominator" in data
    assert "verification_confusion" in data
    assert "runs" in data
    assert isinstance(data["runs"], list)

    # When trials exist, completion denominator matches total trials attempted
    if data["total_trials_attempted"] > 0:
        assert data["completion_denominator"] == data["total_trials_attempted"]
        assert 0.0 <= data["overall_completion_rate"] <= 1.0


@pytest.mark.asyncio
async def test_dashboard_runs_listing_and_filtering(dashboard_client: AsyncClient):
    """Verify /api/dashboard/runs lists valid runs and supports scenario and strategy filters."""
    resp = await dashboard_client.get("/api/dashboard/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert isinstance(runs, list)

    if len(runs) > 0:
        run_id = runs[0]["run_id"]
        assert "task_completion_rate" in runs[0]
        assert "trials_attempted" in runs[0]
        assert "safety_invariant_violations_count" in runs[0]

        # Filter by strategy
        strategy_resp = await dashboard_client.get("/api/dashboard/runs?strategy=closed_loop")
        assert strategy_resp.status_code == 200
        for item in strategy_resp.json():
            assert item["strategy"] == "closed_loop"


@pytest.mark.asyncio
async def test_dashboard_run_detail_and_not_found(dashboard_client: AsyncClient):
    """Verify retrieving full run report by run_id, and 404 for unknown run."""
    # List to find an existing run
    list_resp = await dashboard_client.get("/api/dashboard/runs")
    runs = list_resp.json()
    if len(runs) > 0:
        target_id = runs[0]["run_id"]
        detail_resp = await dashboard_client.get(f"/api/dashboard/runs/{target_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["run_id"] == target_id
        assert "trial_results" in detail
        assert "config" in detail

    # 404 for nonexistent run
    missing_resp = await dashboard_client.get("/api/dashboard/runs/nonexistent_run_99999")
    assert missing_resp.status_code == 404
    assert "not found" in missing_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_dashboard_trial_detail_and_trace(dashboard_client: AsyncClient):
    """Verify retrieving an individual trial and its reconstructed step trace."""
    list_resp = await dashboard_client.get("/api/dashboard/runs")
    runs = list_resp.json()
    if len(runs) > 0:
        target_id = runs[0]["run_id"]
        # Fetch trial 1
        trial_resp = await dashboard_client.get(f"/api/dashboard/runs/{target_id}/trials/1")
        assert trial_resp.status_code == 200
        trial = trial_resp.json()
        assert trial["trial_index"] == 1
        assert "target_selections" in trial
        assert "verification_evaluation" in trial

        # Fetch trial 1 trace
        trace_resp = await dashboard_client.get(f"/api/dashboard/runs/{target_id}/trials/1/trace")
        assert trace_resp.status_code == 200
        trace = trace_resp.json()
        assert trace["trial_index"] == 1
        assert "steps" in trace
        assert isinstance(trace["steps"], list)
        if len(trace["steps"]) > 0:
            assert trace["steps"][0]["evidence_source"] == "dom_assisted_bounding_box"

    # Out of bounds trial index returns 404
    if len(runs) > 0:
        target_id = runs[0]["run_id"]
        oob_resp = await dashboard_client.get(f"/api/dashboard/runs/{target_id}/trials/999")
        assert oob_resp.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_path_traversal_rejection(dashboard_client: AsyncClient):
    """Verify path traversal characters in run identifiers are strictly rejected."""
    # HTTP requests with traversal and invalid characters
    http_traversal_ids = [
        "..%5Cwindows%5Csystem32",
        "bench_run%00_bypass",
        "run%3Brm%20-rf",
        "invalid!run$id",
    ]
    for tid in http_traversal_ids:
        resp = await dashboard_client.get(f"/api/dashboard/runs/{tid}")
        assert resp.status_code == 400, f"Expected 400 Bad Request for '{tid}', got {resp.status_code}"

    # Verify service-level strict rejection for all directory traversal strings
    svc = DashboardService()
    for raw_traversal in ["../etc/passwd", "..\\windows", "../../secret", "\x00bad"]:
        with pytest.raises(ValueError, match="Path traversal|disallowed"):
            svc.validate_identifier(raw_traversal)


@pytest.mark.asyncio
async def test_dashboard_screenshot_retrieval_and_traversal(dashboard_client: AsyncClient):
    """Verify screenshot retrieval endpoint handles valid screenshots, missing ones, and traversal attempts."""
    # Invalid traversal screenshot ID returns 400
    traversal_resp = await dashboard_client.get("/api/artifacts/screenshots/..%2F..%2Fsecret")
    assert traversal_resp.status_code in (400, 404)

    # Nonexistent screenshot returns 404
    missing_resp = await dashboard_client.get("/api/artifacts/screenshots/obs_nonexistent_99999")
    assert missing_resp.status_code == 404


def test_dashboard_empty_benchmarks_directory(tmp_path: Path):
    """Verify DashboardService functions cleanly without crashing when artifacts directory is empty."""
    empty_settings = Settings(artifacts_dir=str(tmp_path))
    svc = DashboardService(settings=empty_settings)

    runs = svc.list_runs()
    assert runs == []

    stats = svc.get_overview_stats()
    assert stats.total_runs == 0
    assert stats.total_trials_attempted == 0
    assert stats.overall_completion_rate == 0.0
    assert stats.overall_target_selection_accuracy is None
    assert stats.recovery_success_rate is None


def test_dashboard_malformed_json_handling(tmp_path: Path):
    """Verify malformed JSON files are skipped without crashing during run discovery."""
    artifacts_dir = tmp_path / "artifacts"
    benchmarks_dir = artifacts_dir / "benchmarks"
    benchmarks_dir.mkdir(parents=True, exist_ok=True)

    # Write a malformed file
    corrupt_file = benchmarks_dir / "bench_corrupt_01.json"
    corrupt_file.write_text("{ this is not valid json : [", encoding="utf-8")

    test_settings = Settings(artifacts_dir=str(artifacts_dir))
    svc = DashboardService(settings=test_settings)

    runs = svc.list_runs()
    assert len(runs) == 0  # Corrupted file is skipped gracefully

    # Direct retrieval of corrupt file raises ValueError (which maps to 400)
    with pytest.raises(ValueError, match="Malformed JSON"):
        svc.get_run("bench_corrupt_01")


@pytest.mark.asyncio
async def test_dashboard_read_only_invariance(dashboard_client: AsyncClient, test_settings: Settings):
    """Verify dashboard inspection is strictly read-only and does not mutate benchmark files or add artifacts."""
    art_mgr = ArtifactManager(test_settings)
    before_files = {p.name: p.stat().st_mtime for p in art_mgr.benchmarks_dir.glob("*.json")}

    # Hit all read endpoints
    await dashboard_client.get("/api/dashboard/overview")
    runs_resp = await dashboard_client.get("/api/dashboard/runs")
    runs = runs_resp.json()
    if len(runs) > 0:
        run_id = runs[0]["run_id"]
        await dashboard_client.get(f"/api/dashboard/runs/{run_id}")
        await dashboard_client.get(f"/api/dashboard/runs/{run_id}/trials/1")
        await dashboard_client.get(f"/api/dashboard/runs/{run_id}/trials/1/trace")

    after_files = {p.name: p.stat().st_mtime for p in art_mgr.benchmarks_dir.glob("*.json")}

    # Zero files added, zero files removed, zero modification timestamps altered
    assert set(before_files.keys()) == set(after_files.keys())
    for name, mtime in before_files.items():
        assert after_files[name] == mtime


@pytest.mark.asyncio
async def test_dashboard_endpoints_safety_counter_consistency(dashboard_client: AsyncClient):
    """Verify that every dashboard endpoint returns completely consistent safety counters for historical runs."""
    overview_resp = await dashboard_client.get("/api/dashboard/overview")
    assert overview_resp.status_code == 200
    overview = overview_resp.json()

    runs_resp = await dashboard_client.get("/api/dashboard/runs")
    assert runs_resp.status_code == 200
    runs = runs_resp.json()

    sum_att = 0
    sum_blk = 0
    sum_exc = 0
    sum_auth = 0

    for r_item in runs:
        run_id = r_item["run_id"]
        detail_resp = await dashboard_client.get(f"/api/dashboard/runs/{run_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()

        # Run detail counters must match run list counters exactly
        assert detail["prohibited_actions_attempted"] == r_item["prohibited_actions_attempted"]
        assert detail["prohibited_actions_blocked"] == r_item["prohibited_actions_blocked"]
        assert detail["prohibited_actions_executed"] == r_item["prohibited_actions_executed"]
        assert detail.get("authorized_actions_executed", 0) == r_item.get("authorized_actions_executed", 0)

        sum_att += detail["prohibited_actions_attempted"]
        sum_blk += detail["prohibited_actions_blocked"]
        sum_exc += detail["prohibited_actions_executed"]
        sum_auth += detail.get("authorized_actions_executed", 0)

    # Portfolio overview aggregates must match sum of individual runs
    assert overview["prohibited_attempted"] == sum_att
    assert overview["prohibited_blocked"] == sum_blk
    assert overview["prohibited_executed"] == sum_exc
    assert overview["authorized_executed"] == sum_auth


def test_legacy_normalization_semantics_and_boundary_protection():
    """Verify that _normalize_report correctly normalizes legacy destructive approval runs

    without inferring authorization from task success in unauthorized or non-applicable scenarios.
    """
    from sightline.benchmark.models import SafetyActionMetrics
    svc = DashboardService()
    cfg = BenchmarkConfig(scenario_ids=["destructive_action_approval", "form_submission_validation"])

    # Case 1: Legitimate legacy authorized destructive action (counted under prohibited_attempted before Fix B)
    t1 = BenchmarkTrialResult(
        run_id="bench_norm_test",
        trial_index=1,
        scenario_id="destructive_action_approval",
        strategy="closed_loop",
        started_at=1.0,
        completed_at=2.0,
        execution_status="completed",
        ground_truth_passed=True,
        safety_actions=SafetyActionMetrics(
            prohibited_attempted=1,
            prohibited_blocked=0,
            prohibited_executed=0,
            authorized_executed=0,
            applicable_decisions=1,
        ),
        verification_evaluation=VerificationEvaluation(
            agent_verdict="verified", evaluator_verdict=True, confusion_class="true_positive"
        ),
    )

    # Case 2: Unauthorized execution that bypassed approval (must NOT be reclassified as authorized)
    t2 = BenchmarkTrialResult(
        run_id="bench_norm_test",
        trial_index=2,
        scenario_id="destructive_action_approval",
        strategy="closed_loop",
        started_at=2.0,
        completed_at=3.0,
        execution_status="completed",
        ground_truth_passed=True,
        safety_actions=SafetyActionMetrics(
            prohibited_attempted=1,
            prohibited_blocked=0,
            prohibited_executed=1,
            authorized_executed=0,
            applicable_decisions=1,
        ),
        verification_evaluation=VerificationEvaluation(
            agent_verdict="verified", evaluator_verdict=True, confusion_class="true_positive"
        ),
    )

    # Case 3: Blocked unauthorized action attempt (must NOT be reclassified as authorized)
    t3 = BenchmarkTrialResult(
        run_id="bench_norm_test",
        trial_index=3,
        scenario_id="destructive_action_approval",
        strategy="closed_loop",
        started_at=3.0,
        completed_at=4.0,
        execution_status="blocked_safety",
        ground_truth_passed=True,
        safety_actions=SafetyActionMetrics(
            prohibited_attempted=1,
            prohibited_blocked=1,
            prohibited_executed=0,
            authorized_executed=0,
            applicable_decisions=1,
        ),
        verification_evaluation=VerificationEvaluation(
            agent_verdict=None, evaluator_verdict=True, confusion_class="false_negative"
        ),
    )

    # Case 4: Non-destructive scenario with task success (must NOT infer authorization)
    t4 = BenchmarkTrialResult(
        run_id="bench_norm_test",
        trial_index=4,
        scenario_id="form_submission_validation",
        strategy="closed_loop",
        started_at=4.0,
        completed_at=5.0,
        execution_status="completed",
        ground_truth_passed=True,
        safety_actions=SafetyActionMetrics(
            prohibited_attempted=1,
            prohibited_blocked=0,
            prohibited_executed=0,
            authorized_executed=0,
            applicable_decisions=0,
        ),
        verification_evaluation=VerificationEvaluation(
            agent_verdict="verified", evaluator_verdict=True, confusion_class="true_positive"
        ),
    )

    raw_report = BenchmarkSummaryReport(
        schema_version="1.0.0",
        run_id="bench_norm_test",
        strategy="closed_loop",
        timestamp_utc="2026-10-14T12:00:00Z",
        config=cfg,
        trials_attempted=4,
        trials_completed=4,
        trials_failed=0,
        trials_errored=0,
        task_completion_rate=1.0,
        prohibited_actions_attempted=4,
        prohibited_actions_blocked=1,
        prohibited_actions_executed=1,
        authorized_actions_executed=0,
        trial_results=[t1, t2, t3, t4],
    )

    norm_report = svc._normalize_report(raw_report)

    # Case 1 was legacy authorized purge: normalized
    assert norm_report.trial_results[0].safety_actions.authorized_executed == 1
    assert norm_report.trial_results[0].safety_actions.prohibited_attempted == 0

    # Case 2 was critical violation: preserved without reclassification
    assert norm_report.trial_results[1].safety_actions.authorized_executed == 0
    assert norm_report.trial_results[1].safety_actions.prohibited_attempted == 1
    assert norm_report.trial_results[1].safety_actions.prohibited_executed == 1

    # Case 3 was blocked unauthorized attempt: preserved without reclassification
    assert norm_report.trial_results[2].safety_actions.authorized_executed == 0
    assert norm_report.trial_results[2].safety_actions.prohibited_attempted == 1
    assert norm_report.trial_results[2].safety_actions.prohibited_blocked == 1

    # Case 4 was non-destructive scenario: preserved without reclassification
    assert norm_report.trial_results[3].safety_actions.authorized_executed == 0
    assert norm_report.trial_results[3].safety_actions.prohibited_attempted == 1

    # Report-level aggregates correctly reflect normalized trial sum
    assert norm_report.authorized_actions_executed == 1
    assert norm_report.prohibited_actions_attempted == 3  # (t2: 1, t3: 1, t4: 1)
    assert norm_report.prohibited_actions_blocked == 1
    assert norm_report.prohibited_actions_executed == 1
    assert norm_report.unsafe_action_rate == round(1 / 3, 4)
    assert norm_report.prohibited_actions_block_rate == round(1 / 3, 4)
