"""Comprehensive security verification and approval-gate bypass suite for Sightline Phase 1.

Verifies that no caller—whether via browser, direct HTTP API, manipulated payload,
or missing authorization—can execute critical destructive actions without valid authorization.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from sightline.app import create_app
from sightline.config import Settings
from sightline.safety.policy import PolicyDecision, default_approval_gate
from sightline.synthetic.state import synthetic_state


@pytest.fixture(autouse=True)
def clean_security_state():
    """Ensure state and audit logs are fresh for each security test."""
    synthetic_state.reset()
    yield
    synthetic_state.reset()


@pytest.mark.asyncio
async def test_case_1_destructive_with_no_approval_token():
    """Attack Case 1: Destructive action attempted with no approval token."""
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8199") as client:
        resp = await client.post("/api/synthetic/purge", json={})
        assert resp.status_code == 403
        data = resp.json()["detail"]
        assert data["gate_status"] == "LOCKED"
        assert "Destructive action blocked" in data["error"]
        assert synthetic_state.get_state().database_status == "Active"


@pytest.mark.asyncio
async def test_case_2_destructive_with_invalid_or_malformed_tokens():
    """Attack Case 2: Attempt destructive action with empty, malformed, or fabricated tokens."""
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8199") as client:
        bad_tokens = [
            "",
            "   ",
            "APPROVAL-SIGHTLINE-2025",
            "ADMIN_OVERRIDE_TOKEN",
            "'; DROP TABLE users; --",
            "null",
            "None",
            "APPROVAL_SIGHTLINE_2026",  # wrong separator
        ]
        for token in bad_tokens:
            resp = await client.post("/api/synthetic/purge", json={"approval_token": token})
            assert resp.status_code == 403, f"Token '{token}' should have been rejected!"
            assert synthetic_state.get_state().database_status == "Active"


@pytest.mark.asyncio
async def test_case_3_unsupported_dynamic_revocation_reported():
    """Attack Case 3: Test revoked token behavior.

    Note: Phase 1 implements deterministic static system tokens; dynamic revocation
    is not implemented in Phase 1 (documented gap). Non-system tokens must always fail.
    """
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8199") as client:
        revoked_simulated_token = "REVOKED-TOKEN-2026-EXPIRED"
        resp = await client.post("/api/synthetic/purge", json={"approval_token": revoked_simulated_token})
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_case_4_direct_api_bypass_with_operator_approved_flag():
    """Attack Case 5: Direct HTTP API bypass attempt sending client-side boolean override."""
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8199") as client:
        # Attacker tries to pass operator_approved=True or admin=True
        attack_payload = {
            "approval_token": None,
            "operator_approved": True,
            "admin": True,
            "is_authorized": True,
        }
        resp = await client.post("/api/synthetic/purge", json=attack_payload)
        assert resp.status_code == 403, "Untrusted client flags MUST NOT bypass server gate!"
        assert synthetic_state.get_state().database_status == "Active"


@pytest.mark.asyncio
async def test_case_6_manipulate_payload_fields():
    """Attack Case 6: Attempt to manipulate payload fields or inject extra attributes."""
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8199") as client:
        payload = {
            "approval_token": {"nested": "APPROVAL-SIGHTLINE-2026"},  # wrong type
            "scenario_id": "form_submission_validation",  # wrong scenario context
        }
        resp = await client.post("/api/synthetic/purge", json=payload)
        # Should be rejected either by Pydantic validation (422) or gate (403)
        assert resp.status_code in (403, 422)
        assert synthetic_state.get_state().database_status == "Active"


@pytest.mark.asyncio
async def test_case_7_unrelated_low_risk_actions_unaffected():
    """Attack Case 7: Verify that unrelated low/medium risk actions proceed normally."""
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8199") as client:
        # Form submit (medium risk) works without approval token
        form_resp = await client.post(
            "/api/synthetic/form-submit",
            json={"full_name": "Bob Smith", "email": "bob@example.com", "department": "Finance", "priority": "Low"},
        )
        assert form_resp.status_code == 200

        # Editor action (low risk) works without approval token
        editor_resp = await client.post("/api/synthetic/editor-action", json={"action": "save"})
        assert editor_resp.status_code == 200


@pytest.mark.asyncio
async def test_case_8_approved_destructive_action_succeeds_only_with_valid_token():
    """Attack Case 8: Approved action succeeds when valid token is supplied."""
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8199") as client:
        valid_resp = await client.post(
            "/api/synthetic/purge",
            json={"approval_token": "APPROVAL-SIGHTLINE-2026"},
        )
        assert valid_resp.status_code == 200
        data = valid_resp.json()
        assert data["success"] is True
        assert data["gate_status"] == "APPROVED"
        assert "Purged under Ticket #APP-PURGE-" in data["database_status"]


@pytest.mark.asyncio
async def test_case_9_rejection_leaves_state_completely_unmutated():
    """Attack Case 9: Confirm failed attempts do NOT partially mutate database status or counters."""
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8199") as client:
        initial_state = synthetic_state.get_state()
        assert initial_state.database_status == "Active"
        assert initial_state.purge_execution_count == 0

        # 5 consecutive malicious requests
        for i in range(5):
            await client.post("/api/synthetic/purge", json={"approval_token": f"FAKE_TOKEN_{i}"})

        post_attack_state = synthetic_state.get_state()
        assert post_attack_state.database_status == "Active"
        assert post_attack_state.purge_execution_count == 0
        assert post_attack_state.purge_blocked_count == 5


@pytest.mark.asyncio
async def test_case_10_audit_records_accurately_reflect_attempts():
    """Attack Case 10: Verify default_approval_gate records an accurate audit trail of decisions."""
    app = create_app(Settings(environment="test"))
    initial_log_count = len(default_approval_gate.get_action_log())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8199") as client:
        # 1. Unapproved call -> denied
        await client.post("/api/synthetic/purge", json={"approval_token": "INVALID"})

        # 2. Approved call -> allowed
        await client.post("/api/synthetic/purge", json={"approval_token": "APPROVAL-SIGHTLINE-2026"})

    log = default_approval_gate.get_action_log()
    assert len(log) >= initial_log_count + 2

    last_two = log[-2:]
    assert last_two[0].decision == PolicyDecision.REQUIRE_APPROVAL
    assert last_two[0].action_name == "purge_database"

    assert last_two[1].decision == PolicyDecision.ALLOW
    assert last_two[1].action_name == "purge_database"
    assert last_two[1].approval_token == "APPROVAL-SIGHTLINE-2026"
