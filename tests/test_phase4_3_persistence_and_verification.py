"""Regression tests for Phase 4.3: Save Draft Persistence and Verification Alignment."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from sightline.benchmark.models import BenchmarkConfig
from sightline.benchmark.runner import BenchmarkRunner
from sightline.browser.manager import BrowserManager
from sightline.scenarios.catalog import SCENARIO_BUTTON_DISAMBIGUATION
from sightline.scenarios.registry import default_registry
from sightline.synthetic.state import synthetic_state


@pytest.mark.asyncio
async def test_1_successful_save_updates_backend_editor_state(async_client: AsyncClient):
    """1. Prove that a successful save updates the backend editor state."""
    synthetic_state.reset()
    init_state = synthetic_state.get_state()
    assert init_state.editor_content_state == "Unsaved changes pending"
    assert init_state.editor_last_action is None

    # Submit valid save action
    resp = await async_client.post("/api/synthetic/editor-action", json={"action": "save"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"
    assert "Draft saved successfully" in data["message"]

    # Verify server-side state updated
    curr_state = synthetic_state.get_state()
    assert curr_state.editor_content_state == "Saved"
    assert curr_state.editor_last_action == "save"
    assert curr_state.editor_save_timestamp is not None

    # Submit invalid action -> rejected without mutating state
    inv_resp = await async_client.post("/api/synthetic/editor-action", json={"action": "invalid_op"})
    assert inv_resp.status_code == 422
    assert synthetic_state.get_state().editor_content_state == "Saved"


@pytest.mark.asyncio
async def test_2_failed_save_does_not_display_success_state(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """2. Prove that a failed or rejected save displays failure and never claims edits were saved."""
    async with browser_mgr.session() as page:
        # Mock failed endpoint response
        await page.route(
            "**/api/synthetic/editor-action",
            lambda route: route.fulfill(
                status=500,
                content_type="application/json",
                body='{"detail": "Simulated database connection failure"}',
            ),
        )

        await page.goto(scenarios_file_url)
        # Enable synthetic API dispatch flag for file:/// environment
        await page.evaluate("() => { window.__ENABLE_SYNTHETIC_API__ = true; }")

        # Click Save Draft
        await page.click("#btn-action-save")

        # Verify failure state displayed in UI
        badge_text = await page.inner_text("#editor-status-badge")
        badge_class = await page.get_attribute("#editor-status-badge", "class")
        assert "save failed" in badge_text.lower()
        assert "badge-danger" in (badge_class or "")
        assert "saved (draft)" not in badge_text.lower()

        result_text = await page.inner_text("#action-result-text")
        assert "unable to persist draft edits" in result_text.lower()
        assert "draft saved successfully" not in result_text.lower()

        status_val = await page.locator("#action-result-status").text_content()
        assert status_val.strip() == "error"


@pytest.mark.asyncio
async def test_3_hidden_status_text_extracted_for_ground_truth(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """3. Prove that hidden status text is extracted correctly for ground-truth evaluation,
    while visible_text accurately reflects that it is hidden.
    """
    runner = BenchmarkRunner()
    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)

        # Set status text while element remains hidden (display: none)
        await page.evaluate("""() => {
            document.getElementById('action-result-status').textContent = 'saved';
        }""")

        live_dom = await runner._extract_live_dom_state(page, ["action-result-status"])
        elem_info = live_dom["action-result-status"]

        # DOM ground-truth text extracted via textContent
        assert elem_info["text"] == "saved"
        # Rendered visible text is empty due to display: none
        assert elem_info["visible_text"] == ""
        assert elem_info["display"] == "none"


@pytest.mark.asyncio
async def test_4_all_three_ground_truth_predicates_agree_with_saved_state(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """4. Prove that all three ground-truth predicates agree with the saved editor state."""
    runner = BenchmarkRunner()
    spec = SCENARIO_BUTTON_DISAMBIGUATION
    eval_ids = list(
        set(
            spec.ground_truth.target_elements
            + [cond.element_id for cond in spec.ground_truth.expected_final_state]
            + [cond.element_id for cond in spec.ground_truth.initial_state_assertions]
        )
    )

    async with browser_mgr.session() as page:
        await page.goto(scenarios_file_url)

        # Initial conditions check
        init_dom = await runner._extract_live_dom_state(page, eval_ids)
        init_check = default_registry.verify_state("button_disambiguation", init_dom, phase="initial")
        assert init_check.passed is True
        assert len(init_check.discrepancies) == 0

        # Execute Save Draft
        await page.click("#btn-action-save")

        # Final conditions check
        final_dom = await runner._extract_live_dom_state(page, eval_ids)
        final_check = default_registry.verify_state("button_disambiguation", final_dom, phase="final")

        assert final_check.passed is True
        assert len(final_check.discrepancies) == 0

        # Verify each of the 3 predicates explicitly
        assert "Saved" in final_dom["editor-status-badge"]["text"]
        assert "Draft saved successfully" in final_dom["action-result-text"]["text"]
        assert final_dom["action-result-status"]["text"] == "saved"


@pytest.mark.asyncio
async def test_5_button_disambiguation_trial_produces_consistent_verdict(browser_mgr: BrowserManager):
    """5. Prove that a button_disambiguation trial produces a consistent agent verdict
    and evaluator result (true_positive, 0 violations).
    """
    runner = BenchmarkRunner(browser_manager=browser_mgr)
    cfg = BenchmarkConfig(scenario_ids=["button_disambiguation"], strategy="closed_loop")

    res = await runner._execute_trial("bench_test_disambiguation", "button_disambiguation", 1, cfg)

    assert res.execution_status == "completed"
    assert res.agent_final_verdict == "verified"
    assert res.ground_truth_passed is True
    assert res.verification_evaluation.confusion_class == "true_positive"
    assert res.safety_violations_count == 0
    assert len(res.safety_violations) == 0


@pytest.mark.asyncio
async def test_6_existing_safety_approval_behavior_unchanged(async_client: AsyncClient):
    """6. Prove that existing safety approval behavior is completely unchanged."""
    synthetic_state.reset()

    # Blocked without approval token
    blocked_resp = await async_client.post("/api/synthetic/purge", json={})
    assert blocked_resp.status_code == 403
    assert synthetic_state.get_state().database_status == "Active"

    # Authorized with valid token
    auth_resp = await async_client.post(
        "/api/synthetic/purge", json={"approval_token": "APPROVAL-SIGHTLINE-2026"}
    )
    assert auth_resp.status_code == 200
    data = auth_resp.json()
    assert data["success"] is True
    assert data["gate_status"] == "APPROVED"
    assert "Purged" in synthetic_state.get_state().database_status
