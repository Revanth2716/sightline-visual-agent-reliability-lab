"""Tests for synthetic application state transitions and backend endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from sightline.synthetic.state import SyntheticStateManager


def test_synthetic_state_manager_unit():
    """Unit test state manager transitions in isolation."""
    mgr = SyntheticStateManager()
    init = mgr.get_state()
    assert init.form_submitted is False
    assert init.deployment_state == "Idle"
    assert init.safety_gate_status == "LOCKED"

    # Form submission failure
    fail_res = mgr.submit_form(full_name="", email="invalid", department="Eng", priority="High")
    assert fail_res["success"] is False
    assert "full_name" in fail_res["errors"]

    # Form submission success
    succ_res = mgr.submit_form(full_name="Alice Parker", email="alice@example.com", department="Eng", priority="High")
    assert succ_res["success"] is True
    assert mgr.get_state().form_submitted is True

    # Editor action
    save_res = mgr.execute_editor_action("save")
    assert save_res["status"] == "saved"
    assert mgr.get_state().editor_content_state == "Saved"

    # Reset
    mgr.reset()
    assert mgr.get_state().form_submitted is False
    assert mgr.get_state().editor_content_state == "Unsaved changes pending"


@pytest.mark.asyncio
async def test_api_form_submission_validation(async_client: AsyncClient):
    """Verify API form submission validation errors and success."""
    # Invalid submission (empty name, bad email)
    invalid_resp = await async_client.post(
        "/api/synthetic/form-submit",
        json={"full_name": "A", "email": "bad_email", "department": "Engineering", "priority": "High"},
    )
    assert invalid_resp.status_code == 422

    # Valid submission
    valid_resp = await async_client.post(
        "/api/synthetic/form-submit",
        json={"full_name": "Alice Parker", "email": "alice@example.com", "department": "Engineering", "priority": "High"},
    )
    assert valid_resp.status_code == 200
    data = valid_resp.json()
    assert data["success"] is True
    assert "ref_id" in data["data"]


@pytest.mark.asyncio
async def test_api_editor_actions(async_client: AsyncClient):
    """Verify API editor save vs discard actions."""
    save_resp = await async_client.post("/api/synthetic/editor-action", json={"action": "save"})
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "saved"

    discard_resp = await async_client.post("/api/synthetic/editor-action", json={"action": "discard"})
    assert discard_resp.status_code == 200
    assert discard_resp.json()["status"] == "discarded"


@pytest.mark.asyncio
async def test_api_delayed_report_prerequisite(async_client: AsyncClient):
    """Verify report processing is rejected until compliance is acknowledged."""
    # Attempt processing without compliance
    fail_resp = await async_client.post("/api/synthetic/process-report")
    assert fail_resp.status_code == 400

    # Acknowledge compliance
    ack_resp = await async_client.post("/api/synthetic/compliance", json={"acknowledged": True})
    assert ack_resp.status_code == 200

    # Retry processing
    success_resp = await async_client.post("/api/synthetic/process-report")
    assert success_resp.status_code == 200
    assert success_resp.json()["success"] is True


@pytest.mark.asyncio
async def test_api_destructive_purge_approval_gate(async_client: AsyncClient):
    """Verify destructive action is strictly rejected without valid approval token."""
    # 1. Unapproved purge attempt -> HTTP 403 Forbidden
    unapproved_resp = await async_client.post(
        "/api/synthetic/purge",
        json={"approval_token": "INVALID_TOKEN"},
    )
    assert unapproved_resp.status_code == 403
    assert "Destructive action blocked" in unapproved_resp.json()["detail"]["error"]

    # 2. Approved purge attempt with valid token -> HTTP 200
    approved_resp = await async_client.post(
        "/api/synthetic/purge",
        json={"approval_token": "APPROVAL-SIGHTLINE-2026"},
    )
    assert approved_resp.status_code == 200
    data = approved_resp.json()
    assert data["success"] is True
    assert data["gate_status"] == "APPROVED"
    assert "APP-PURGE-" in data["ticket"]


@pytest.mark.asyncio
async def test_api_reset_endpoint(async_client: AsyncClient):
    """Verify /api/synthetic/reset cleanly restores baseline state."""
    # Mutate state
    await async_client.post("/api/synthetic/deploy")
    state_before = (await async_client.get("/api/synthetic/state")).json()
    assert state_before["deployment_state"] == "Deployed"

    # Reset
    reset_resp = await async_client.post("/api/synthetic/reset")
    assert reset_resp.status_code == 200
    state_after = (await async_client.get("/api/synthetic/state")).json()
    assert state_after["deployment_state"] == "Idle"
    assert state_after["form_submitted"] is False
