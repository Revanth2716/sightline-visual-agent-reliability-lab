"""End-to-end integration tests running real Chromium benchmark evaluations."""

from __future__ import annotations

from pathlib import Path
import pytest

from sightline.benchmark.models import BenchmarkConfig
from sightline.benchmark.runner import BenchmarkRunner
from sightline.browser.manager import BrowserManager
from sightline.config import Settings
from sightline.observation.artifacts import ArtifactManager


@pytest.mark.asyncio
async def test_benchmark_real_chromium_execution(
    browser_mgr: BrowserManager, scenarios_file_url: str, test_settings: Settings
):
    """Run an authentic closed-loop benchmark trial through real Chromium and verify scoring."""
    art_mgr = ArtifactManager(test_settings)
    runner = BenchmarkRunner(
        settings=test_settings,
        browser_manager=browser_mgr,
        artifact_manager=art_mgr,
        target_base_url=scenarios_file_url,
    )

    config = BenchmarkConfig(
        name="bench_e2e_closed_loop",
        scenario_ids=["button_disambiguation"],
        trials_per_scenario=1,
        strategy="closed_loop",
        seed=101,
    )

    report = await runner.run(config)

    # 1. Trial accounting
    assert report.trials_attempted == 1
    assert report.trials_completed == 1
    assert report.trials_failed == 0
    assert report.trials_errored == 0
    assert report.task_completion_rate == 1.0

    # 2. Target selection accuracy
    assert report.target_selection_accuracy == 1.0
    assert report.target_decisions_count == 1

    # 3. Safety invariants
    assert report.safety_invariant_violations_count == 0
    assert report.unsafe_action_rate == 0.0

    # 4. Latency measurements present
    assert report.latency_summary["trial_duration_ms"].count == 1
    assert report.latency_summary["trial_duration_ms"].mean_ms > 0

    # 5. Persisted artifact
    report_file = art_mgr.get_benchmark_report_path(report.run_id)
    assert report_file.exists()
    assert report_file.stat().st_size > 0

    # Clean up test report artifact
    report_file.unlink()


@pytest.mark.asyncio
async def test_benchmark_fault_injection_unapproved_destructive(
    browser_mgr: BrowserManager, scenarios_file_url: str, test_settings: Settings
):
    """Run a benchmark trial with unapproved destructive fault injection and verify safety metrics."""
    art_mgr = ArtifactManager(test_settings)
    runner = BenchmarkRunner(
        settings=test_settings,
        browser_manager=browser_mgr,
        artifact_manager=art_mgr,
        target_base_url=scenarios_file_url,
    )

    config = BenchmarkConfig(
        name="bench_e2e_safety_fault",
        scenario_ids=["destructive_action_approval"],
        trials_per_scenario=1,
        strategy="closed_loop",
        fault_injection="unapproved_destructive",
        seed=202,
    )

    report = await runner.run(config)

    assert report.trials_attempted == 1
    # Prohibited action was attempted and blocked
    assert report.prohibited_actions_attempted == 1
    assert report.prohibited_actions_blocked == 1
    assert report.prohibited_actions_executed == 0
    assert report.unsafe_action_rate == 0.0
    assert report.safety_invariant_violations_count == 0

    # Evaluator confirmed the database was NOT purged
    assert report.trial_results[0].execution_status == "blocked_safety"
    assert report.trial_results[0].ground_truth_passed is True

    report_file = art_mgr.get_benchmark_report_path(report.run_id)
    if report_file.exists():
        report_file.unlink()


@pytest.mark.asyncio
async def test_benchmark_baseline_strategy_execution(
    browser_mgr: BrowserManager, scenarios_file_url: str, test_settings: Settings
):
    """Run baseline strategy (without postcondition verification) and compare execution."""
    art_mgr = ArtifactManager(test_settings)
    runner = BenchmarkRunner(
        settings=test_settings,
        browser_manager=browser_mgr,
        artifact_manager=art_mgr,
        target_base_url=scenarios_file_url,
    )

    config = BenchmarkConfig(
        name="bench_e2e_baseline",
        scenario_ids=["button_disambiguation"],
        trials_per_scenario=1,
        strategy="baseline",
        seed=303,
    )

    report = await runner.run(config)

    assert report.strategy == "baseline"
    assert report.trials_attempted == 1
    assert report.trials_completed == 1
    assert report.task_completion_rate == 1.0

    report_file = art_mgr.get_benchmark_report_path(report.run_id)
    if report_file.exists():
        report_file.unlink()
