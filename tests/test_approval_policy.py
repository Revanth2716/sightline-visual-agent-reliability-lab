"""Tests for safety policy, risk classification, and ApprovalGate enforcement."""

from __future__ import annotations

import pytest

from sightline.safety.policy import (
    ActionRiskLevel,
    ApprovalGate,
    PolicyDecision,
)


def test_action_risk_classification():
    """Verify selectors and action types are accurately categorized into risk tiers."""
    gate = ApprovalGate()

    # Critical destructive
    assert gate.classify_risk("#btn-execute-purge") == ActionRiskLevel.CRITICAL_DESTRUCTIVE
    assert gate.classify_risk("#btn-wipe-database") == ActionRiskLevel.CRITICAL_DESTRUCTIVE
    assert gate.classify_risk("#btn-drop-tables") == ActionRiskLevel.CRITICAL_DESTRUCTIVE

    # High risk
    assert gate.classify_risk("#btn-deploy-release") == ActionRiskLevel.HIGH

    # Medium risk
    assert gate.classify_risk("#btn-submit-form", action_type="click") == ActionRiskLevel.MEDIUM
    assert gate.classify_risk("#input-name", action_type="type") == ActionRiskLevel.MEDIUM

    # Low / benign
    assert gate.classify_risk("#btn-action-save", action_type="click") == ActionRiskLevel.LOW
    assert gate.classify_risk("#link-home", action_type="click") == ActionRiskLevel.LOW


def test_destructive_action_strictly_requires_approval():
    """Verify destructive action is blocked by policy unless approval is granted."""
    gate = ApprovalGate()

    # 1. Attempt unapproved destructive action
    res_unapproved = gate.evaluate_action(
        action_name="click",
        target_selector="#btn-execute-purge",
        approval_token=None,
    )
    assert res_unapproved.decision == PolicyDecision.REQUIRE_APPROVAL
    assert res_unapproved.risk_level == ActionRiskLevel.CRITICAL_DESTRUCTIVE
    assert "Destructive action blocked" in res_unapproved.reason

    # 2. Attempt with invalid token
    res_invalid = gate.evaluate_action(
        action_name="click",
        target_selector="#btn-execute-purge",
        approval_token="WRONG_TOKEN",
    )
    assert res_invalid.decision == PolicyDecision.REQUIRE_APPROVAL

    # 3. Attempt with valid system approval token
    res_approved = gate.evaluate_action(
        action_name="click",
        target_selector="#btn-execute-purge",
        approval_token="APPROVAL-SIGHTLINE-2026",
    )
    assert res_approved.decision == PolicyDecision.ALLOW
    assert res_approved.risk_level == ActionRiskLevel.CRITICAL_DESTRUCTIVE


def test_operator_override_and_verdict_granting():
    """Verify manual operator review workflow."""
    gate = ApprovalGate()
    action_id = "act-purge-001"

    assert gate.is_approved(action_id) is False

    # Grant explicit approval
    verdict = gate.grant_approval(
        action_id=action_id,
        reviewer="lead_sre_engineer",
        notes="Verified emergency maintenance window ticket.",
    )
    assert verdict.approved is True
    assert verdict.reviewer == "lead_sre_engineer"
    assert gate.is_approved(action_id) is True

    # Evaluate with operator override
    res = gate.evaluate_action(
        action_name="click",
        target_selector="#btn-execute-purge",
        operator_override=True,
    )
    assert res.decision == PolicyDecision.ALLOW


def test_policy_audit_log_records_events():
    """Verify all policy checks are appended to the audit log."""
    gate = ApprovalGate()
    gate.evaluate_action("click", "#link-nav")
    gate.evaluate_action("click", "#btn-execute-purge")

    log = gate.get_action_log()
    assert len(log) == 2
    assert log[0].target_selector == "#link-nav"
    assert log[0].decision == PolicyDecision.ALLOW
    assert log[1].target_selector == "#btn-execute-purge"
    assert log[1].decision == PolicyDecision.REQUIRE_APPROVAL
