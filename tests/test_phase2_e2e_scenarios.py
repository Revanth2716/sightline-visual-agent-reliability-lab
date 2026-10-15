"""End-to-end integration tests running all 5 scenarios through the VisualInteractionLoop."""

from __future__ import annotations

import pytest

from sightline.browser.manager import BrowserManager
from sightline.config import Settings
from sightline.executor.models import ActionType
from sightline.loop import InteractionStep, VisualInteractionLoop
from sightline.safety.policy import ApprovalGate
from sightline.verification.models import ConditionType, VisiblePostcondition


@pytest.mark.asyncio
async def test_phase2_e2e_scenario_1_form_validation(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Scenario 1 via Visual Loop: Submit without inputs to observe errors, then fill and submit."""
    console_errors: list[str] = []
    page_errors: list[str] = []

    loop = VisualInteractionLoop()

    async with browser_mgr.session() as page:
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(scenarios_file_url)

        # 1. Click submit with empty fields -> Error message visible
        step_empty_submit = InteractionStep(
            intent_type=ActionType.CLICK,
            target_query="Submit Intake Record",
            expected_postcondition=VisiblePostcondition(
                target_selector="#name-error",
                condition_type=ConditionType.IS_VISIBLE,
                description="Name error message is visible upon submitting empty form",
            ),
        )
        trace1 = await loop.execute_step(page, step_empty_submit, step_index=1)
        assert trace1.success is True
        assert trace1.verification_result.status.value == "verified"

        # 2. Fill Name
        step_fill_name = InteractionStep(
            intent_type=ActionType.FILL,
            target_query="input-full-name",
            value="Alice Parker",
            expected_postcondition=VisiblePostcondition(
                target_selector="#input-full-name",
                condition_type=ConditionType.VALUE_EQUALS,
                expected_value="Alice Parker",
            ),
        )
        trace2 = await loop.execute_step(page, step_fill_name, step_index=2)
        assert trace2.success is True

        # 3. Fill Email
        step_fill_email = InteractionStep(
            intent_type=ActionType.FILL,
            target_query="input-email",
            value="alice.parker@example.com",
            expected_postcondition=VisiblePostcondition(
                target_selector="#input-email",
                condition_type=ConditionType.VALUE_EQUALS,
                expected_value="alice.parker@example.com",
            ),
        )
        trace3 = await loop.execute_step(page, step_fill_email, step_index=3)
        assert trace3.success is True

        # 4. Submit Form and verify success
        step_submit_valid = InteractionStep(
            intent_type=ActionType.CLICK,
            target_query="Submit Intake Record",
            expected_postcondition=VisiblePostcondition(
                target_selector="#form-confirmation-message",
                condition_type=ConditionType.TEXT_CONTAINS,
                expected_value="Intake record created successfully",
            ),
        )
        trace4 = await loop.execute_step(page, step_submit_valid, step_index=4)
        assert trace4.success is True
        assert trace4.verification_result.status.value == "verified"

        assert len(page_errors) == 0
        assert len(console_errors) == 0


@pytest.mark.asyncio
async def test_phase2_e2e_scenario_2_button_disambiguation(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Scenario 2 via Visual Loop: Ground Save Draft (avoiding Discard) and verify Saved state."""
    console_errors: list[str] = []
    page_errors: list[str] = []

    loop = VisualInteractionLoop()

    async with browser_mgr.session() as page:
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(scenarios_file_url)
        await page.locator("#button-disambiguation").scroll_into_view_if_needed()

        # Disambiguated action: Save Draft
        step_save = InteractionStep(
            intent_type=ActionType.CLICK,
            target_query="Save Draft",
            expected_postcondition=VisiblePostcondition(
                target_selector="#editor-status-badge",
                condition_type=ConditionType.TEXT_CONTAINS,
                expected_value="Saved",
            ),
        )
        trace = await loop.execute_step(page, step_save, step_index=1)
        assert trace.success is True
        assert trace.grounding_result.matched_target.target_id == "btn-action-save"
        assert trace.verification_result.status.value == "verified"

        # Ambiguous query test: querying generic 'btn' role must be safely halted
        step_ambig = InteractionStep(
            intent_type=ActionType.CLICK,
            target_query="btn",
            target_role="button",
        )
        ambig_trace = await loop.execute_step(page, step_ambig, step_index=2)
        assert ambig_trace.success is False
        assert ambig_trace.grounding_result.status.value == "ambiguous"
        assert ambig_trace.action_result is None  # Never clicked!

        assert len(page_errors) == 0
        assert len(console_errors) == 0


@pytest.mark.asyncio
async def test_phase2_e2e_scenario_3_modal_workflow(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Scenario 3 via Visual Loop: Open deployment modal, observe nested dialog, and confirm release."""
    console_errors: list[str] = []
    page_errors: list[str] = []

    loop = VisualInteractionLoop()

    async with browser_mgr.session() as page:
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(scenarios_file_url)
        await page.locator("#modal-workflow").scroll_into_view_if_needed()

        # 1. Open deployment modal
        step_open = InteractionStep(
            intent_type=ActionType.CLICK,
            target_query="Deploy Update",
            expected_postcondition=VisiblePostcondition(
                target_selector="#modal-title",
                condition_type=ConditionType.IS_VISIBLE,
                description="Modal dialog title is visible",
            ),
        )
        trace_open = await loop.execute_step(page, step_open, step_index=1)
        assert trace_open.success is True
        assert trace_open.verification_result.status.value == "verified"

        # 2. Confirm in modal
        step_confirm = InteractionStep(
            intent_type=ActionType.CLICK,
            target_query="Confirm & Deploy",
            expected_postcondition=VisiblePostcondition(
                target_selector="#deploy-state-badge",
                condition_type=ConditionType.TEXT_CONTAINS,
                expected_value="Deployed",
            ),
        )
        trace_confirm = await loop.execute_step(page, step_confirm, step_index=2)
        assert trace_confirm.success is True
        assert trace_confirm.verification_result.status.value == "verified"

        assert len(page_errors) == 0
        assert len(console_errors) == 0


@pytest.mark.asyncio
async def test_phase2_e2e_scenario_4_delayed_enablement(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Scenario 4 via Visual Loop: Check terms, observe delayed enablement, click enabled button."""
    console_errors: list[str] = []
    page_errors: list[str] = []

    loop = VisualInteractionLoop()

    async with browser_mgr.session() as page:
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(scenarios_file_url)
        await page.locator("#delayed-enablement").scroll_into_view_if_needed()

        # 1. Acknowledge compliance terms
        step_check = InteractionStep(
            intent_type=ActionType.CHECK,
            target_query="checkbox-compliance",
            expected_postcondition=VisiblePostcondition(
                target_selector="#processing-status-badge",
                condition_type=ConditionType.TEXT_CONTAINS,
                expected_value="Verifying compliance",
            ),
        )
        trace_check = await loop.execute_step(page, step_check, step_index=1)
        assert trace_check.success is True

        # Wait for the button to finish enabling
        await page.wait_for_selector("#btn-process-report:not([disabled])", timeout=3000)

        # 2. Click now-enabled Process Report button
        step_process = InteractionStep(
            intent_type=ActionType.CLICK,
            target_query="Process Report",
            expected_postcondition=VisiblePostcondition(
                target_selector="#processing-status-badge",
                condition_type=ConditionType.TEXT_CONTAINS,
                expected_value="Report processed successfully",
            ),
        )
        trace_process = await loop.execute_step(page, step_process, step_index=2)
        assert trace_process.success is True
        assert trace_process.verification_result.status.value == "verified"

        assert len(page_errors) == 0
        assert len(console_errors) == 0


@pytest.mark.asyncio
async def test_phase2_e2e_scenario_5_destructive_approval(
    browser_mgr: BrowserManager, scenarios_file_url: str
):
    """Scenario 5 via Visual Loop: Attempt purge without approval -> Blocked; Supply approval -> Verified."""
    console_errors: list[str] = []
    page_errors: list[str] = []

    loop = VisualInteractionLoop()

    async with browser_mgr.session() as page:
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(scenarios_file_url)
        await page.locator("#destructive-approval").scroll_into_view_if_needed()

        # 1. Unapproved purge attempt: Must be BLOCKED_BY_SAFETY
        step_unapproved = InteractionStep(
            intent_type=ActionType.CLICK,
            target_query="Execute Database Purge",
            approval_token=None,
        )
        trace_blocked = await loop.execute_step(page, step_unapproved, step_index=1)
        assert trace_blocked.success is False
        assert trace_blocked.action_result.status.value == "blocked_by_safety"
        assert "Explicit operator approval token is required" in trace_blocked.action_result.error_message

        # State must remain untouched
        assert (await page.inner_text("#safety-gate-indicator")).strip() == "LOCKED"
        assert (await page.inner_text("#database-status-badge")).strip() == "Active"

        # 2. Toggle operator approval checkbox to activate approval state
        step_toggle = InteractionStep(
            intent_type=ActionType.CHECK,
            target_query="toggle-operator-approval",
            expected_postcondition=VisiblePostcondition(
                target_selector="#input-approval-token",
                condition_type=ConditionType.VALUE_EQUALS,
                expected_value=ApprovalGate.VALID_SYSTEM_TOKEN,
            ),
        )
        trace_toggle = await loop.execute_step(page, step_toggle, step_index=2)
        assert trace_toggle.success is True

        # 3. Execute purge with explicit valid token
        step_approved = InteractionStep(
            intent_type=ActionType.CLICK,
            target_query="Execute Database Purge",
            approval_token=ApprovalGate.VALID_SYSTEM_TOKEN,
            expected_postcondition=VisiblePostcondition(
                target_selector="#safety-gate-indicator",
                condition_type=ConditionType.TEXT_EQUALS,
                expected_value="APPROVED",
            ),
        )
        trace_approved = await loop.execute_step(page, step_approved, step_index=3)
        assert trace_approved.success is True
        assert trace_approved.verification_result.status.value == "verified"

        db_text = await page.inner_text("#database-status-badge")
        assert "purged" in db_text.lower()

        assert len(page_errors) == 0
        assert len(console_errors) == 0
