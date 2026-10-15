"""End-to-end tests exercising all 5 deterministic scenarios using real headless Chromium.

Captures browser console errors, page exceptions, and verifies bidirectional UI state transitions.
"""

from __future__ import annotations

import pytest

from sightline.browser.manager import BrowserManager


@pytest.mark.asyncio
async def test_e2e_scenario_1_form_validation(browser_mgr: BrowserManager, scenarios_file_url: str):
    """E2E Scenario 1: Form validation errors on empty input, success on valid submission."""
    console_errors: list[str] = []
    page_errors: list[str] = []

    async with browser_mgr.session() as page:
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(scenarios_file_url)

        # 1. Verify initial conditions
        name_val = await page.input_value("#input-full-name")
        email_val = await page.input_value("#input-email")
        assert name_val == ""
        assert email_val == ""

        # 2. Trigger validation errors
        await page.click("#btn-submit-form")
        name_err_visible = await page.is_visible("#name-error")
        email_err_visible = await page.is_visible("#email-error")
        assert name_err_visible is True
        assert email_err_visible is True

        # 3. Fill valid inputs
        await page.fill("#input-full-name", "Alice Parker")
        await page.fill("#input-email", "alice.parker@example.com")
        await page.select_option("#select-department", "Engineering")
        await page.select_option("#select-priority", "High")

        # 4. Submit form
        await page.click("#btn-submit-form")

        # 5. Verify success transition
        feedback_status = await page.inner_text("#form-feedback-status")
        assert feedback_status.strip().lower() == "success"
        confirmation_text = await page.inner_text("#form-confirmation-message")
        assert "Intake record created successfully" in confirmation_text
        assert "Alice Parker" in confirmation_text

        # 6. Verify zero uncaught errors
        assert len(page_errors) == 0, f"Uncaught page errors: {page_errors}"
        assert len(console_errors) == 0, f"Browser console errors: {console_errors}"


@pytest.mark.asyncio
async def test_e2e_scenario_2_button_disambiguation(browser_mgr: BrowserManager, scenarios_file_url: str):
    """E2E Scenario 2: Save Draft vs Discard changes produce distinct, verified outcomes."""
    console_errors: list[str] = []
    page_errors: list[str] = []

    async with browser_mgr.session() as page:
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(scenarios_file_url)

        # Initial state
        initial_badge = await page.inner_text("#editor-status-badge")
        assert "unsaved changes pending" in initial_badge.strip().lower()

        # Step 1: Click Discard -> distinct discard outcome
        await page.click("#btn-action-discard")
        discard_badge = await page.inner_text("#editor-status-badge")
        assert "changes discarded" in discard_badge.strip().lower()
        discard_text = await page.inner_text("#action-result-text")
        assert "discarded" in discard_text.strip().lower()

        # Step 2: Click Save Draft -> distinct save outcome
        await page.click("#btn-action-save")
        saved_badge = await page.inner_text("#editor-status-badge")
        assert "saved" in saved_badge.strip().lower()
        saved_text = await page.inner_text("#action-result-text")
        assert "draft saved successfully" in saved_text.strip().lower()

        # Verify zero console or page errors
        assert len(page_errors) == 0, f"Uncaught page errors: {page_errors}"
        assert len(console_errors) == 0, f"Browser console errors: {console_errors}"


@pytest.mark.asyncio
async def test_e2e_scenario_3_modal_workflow(browser_mgr: BrowserManager, scenarios_file_url: str):
    """E2E Scenario 3: Open confirmation dialog, dismiss, re-open, and confirm deployment."""
    console_errors: list[str] = []
    page_errors: list[str] = []

    async with browser_mgr.session() as page:
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(scenarios_file_url)

        # Initial state: modal hidden
        overlay_classes = await page.get_attribute("#deploy-modal-overlay", "class")
        assert "hidden" in (overlay_classes or "")
        init_state = await page.inner_text("#deploy-state-badge")
        assert init_state.strip().lower() == "idle"

        # Step 1: Open modal
        await page.click("#btn-open-deploy-modal")
        overlay_open = await page.get_attribute("#deploy-modal-overlay", "class")
        assert "hidden" not in (overlay_open or "")

        # Step 2: Dismiss modal via Cancel button -> state remains Idle
        await page.click("#btn-modal-cancel")
        overlay_dismissed = await page.get_attribute("#deploy-modal-overlay", "class")
        assert "hidden" in (overlay_dismissed or "")
        assert (await page.inner_text("#deploy-state-badge")).strip().lower() == "idle"

        # Step 3: Re-open modal and confirm deployment
        await page.click("#btn-open-deploy-modal")
        await page.click("#btn-modal-confirm")

        # Step 4: Verify modal closes and deployment state updates
        overlay_final = await page.get_attribute("#deploy-modal-overlay", "class")
        assert "hidden" in (overlay_final or "")
        final_state = await page.inner_text("#deploy-state-badge")
        assert "deployed" in final_state.strip().lower()
        audit_text = await page.inner_text("#deploy-audit-log")
        assert "Deployment v1.4.2 released" in audit_text

        # Verify zero console or page errors
        assert len(page_errors) == 0, f"Uncaught page errors: {page_errors}"
        assert len(console_errors) == 0, f"Browser console errors: {console_errors}"


@pytest.mark.asyncio
async def test_e2e_scenario_4_delayed_enablement(browser_mgr: BrowserManager, scenarios_file_url: str):
    """E2E Scenario 4: Button is disabled until compliance terms are acknowledged."""
    console_errors: list[str] = []
    page_errors: list[str] = []

    async with browser_mgr.session() as page:
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(scenarios_file_url)

        # Initial state: button disabled
        is_disabled = await page.is_disabled("#btn-process-report")
        assert is_disabled is True

        # Check compliance
        await page.check("#checkbox-compliance")

        # Wait for asynchronous enablement
        await page.wait_for_selector("#btn-process-report:not([disabled])", timeout=3000)
        is_now_disabled = await page.is_disabled("#btn-process-report")
        assert is_now_disabled is False

        # Click enabled button
        await page.click("#btn-process-report")

        # Verify final state
        status_text = await page.inner_text("#processing-status-badge")
        assert "report processed successfully" in status_text.strip().lower()

        # Verify zero console or page errors
        assert len(page_errors) == 0, f"Uncaught page errors: {page_errors}"
        assert len(console_errors) == 0, f"Browser console errors: {console_errors}"


@pytest.mark.asyncio
async def test_e2e_scenario_5_destructive_approval_enforcement(browser_mgr: BrowserManager, scenarios_file_url: str):
    """E2E Scenario 5: Destructive action rejected without approval, allowed with approval."""
    console_errors: list[str] = []
    page_errors: list[str] = []

    async with browser_mgr.session() as page:
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(scenarios_file_url)

        # Initial state: gate is LOCKED
        gate_status = await page.inner_text("#safety-gate-indicator")
        assert gate_status.strip().lower() == "locked"
        db_status = await page.inner_text("#database-status-badge")
        assert db_status.strip().lower() == "active"

        # 1. Attempt destructive purge without authorization -> REJECTED
        await page.click("#btn-execute-purge")
        alert_text = await page.inner_text("#purge-feedback-alert")
        assert "SAFETY VIOLATION" in alert_text
        assert "Purge rejected" in alert_text
        # Gate must remain LOCKED
        assert (await page.inner_text("#safety-gate-indicator")).strip().lower() == "locked"
        assert (await page.inner_text("#database-status-badge")).strip().lower() == "active"

        # 2. Grant operator authorization via approval toggle (auto-populates valid token)
        await page.check("#toggle-operator-approval")
        token_val = await page.input_value("#input-approval-token")
        assert token_val == "APPROVAL-SIGHTLINE-2026"

        # 3. Execute purge with approval
        await page.click("#btn-execute-purge")

        # 4. Verify approved state transition
        assert (await page.inner_text("#safety-gate-indicator")).strip().lower() == "approved"
        final_db_status = await page.inner_text("#database-status-badge")
        assert "purged under ticket" in final_db_status.strip().lower()
        success_alert = await page.inner_text("#purge-feedback-alert")
        assert "PURGE COMPLETE" in success_alert

        # Verify zero console or page errors
        assert len(page_errors) == 0, f"Uncaught page errors: {page_errors}"
        assert len(console_errors) == 0, f"Browser console errors: {console_errors}"
