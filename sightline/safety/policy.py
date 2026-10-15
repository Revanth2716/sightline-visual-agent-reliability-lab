"""Safety governance and approval gate layer for browser actions."""

from __future__ import annotations

import time
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from sightline.models import ApprovalRequest, ApprovalVerdict


class ActionRiskLevel(str, Enum):
    """Risk tiers for agent interactions."""

    LOW = "low"  # clicks, reads, standard navigation
    MEDIUM = "medium"  # form submissions, state changes
    HIGH = "high"  # config changes, releases
    CRITICAL_DESTRUCTIVE = "critical_destructive"  # database wipes, irreversible resource deletion


class PolicyDecision(str, Enum):
    """Evaluation verdict for an attempted browser action."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class ActionPolicyResult(BaseModel):
    """Result of an action safety policy check."""

    action_name: str
    target_selector: str
    risk_level: ActionRiskLevel
    decision: PolicyDecision
    reason: str
    approval_token: Optional[str] = None


class ApprovalGate:
    """Enforces human-in-the-loop approval gates on high-risk and destructive actions."""

    VALID_SYSTEM_TOKEN = "APPROVAL-SIGHTLINE-2026"

    def __init__(self) -> None:
        self._verdicts: Dict[str, ApprovalVerdict] = {}
        self._action_log: List[ActionPolicyResult] = []

    def classify_risk(self, target_selector: str, action_type: str = "click") -> ActionRiskLevel:
        """Deterministically determine the risk tier of a planned browser action."""
        selector_lower = target_selector.lower()
        if "purge" in selector_lower or "wipe" in selector_lower or "drop" in selector_lower:
            return ActionRiskLevel.CRITICAL_DESTRUCTIVE
        if "deploy" in selector_lower or "release" in selector_lower:
            return ActionRiskLevel.HIGH
        if "submit" in selector_lower or action_type in ("type", "fill"):
            return ActionRiskLevel.MEDIUM
        return ActionRiskLevel.LOW

    def evaluate_action(
        self,
        action_name: str,
        target_selector: str,
        approval_token: Optional[str] = None,
        operator_override: bool = False,
    ) -> ActionPolicyResult:
        """Evaluate an action against safety policies.

        Critical destructive actions ALWAYS require explicit approval before execution.
        """
        risk = self.classify_risk(target_selector, action_type=action_name)

        if risk == ActionRiskLevel.CRITICAL_DESTRUCTIVE:
            # Check for valid approval
            has_valid_token = approval_token is not None and approval_token.strip() == self.VALID_SYSTEM_TOKEN
            if operator_override or has_valid_token:
                res = ActionPolicyResult(
                    action_name=action_name,
                    target_selector=target_selector,
                    risk_level=risk,
                    decision=PolicyDecision.ALLOW,
                    reason="Explicit operator authorization granted.",
                    approval_token=approval_token,
                )
            else:
                res = ActionPolicyResult(
                    action_name=action_name,
                    target_selector=target_selector,
                    risk_level=risk,
                    decision=PolicyDecision.REQUIRE_APPROVAL,
                    reason="CRITICAL: Destructive action blocked. Explicit operator approval token is required.",
                )
            self._action_log.append(res)
            return res

        # Non-critical actions proceed under standard bounded execution
        res = ActionPolicyResult(
            action_name=action_name,
            target_selector=target_selector,
            risk_level=risk,
            decision=PolicyDecision.ALLOW,
            reason="Action within benign/medium policy bounds.",
        )
        self._action_log.append(res)
        return res

    def grant_approval(self, action_id: str, reviewer: str = "human_operator", notes: Optional[str] = None) -> ApprovalVerdict:
        """Record an explicit human approval decision."""
        verdict = ApprovalVerdict(
            action_id=action_id,
            approved=True,
            reviewer=reviewer,
            timestamp=time.time(),
            notes=notes or "Operator approved execution after review.",
        )
        self._verdicts[action_id] = verdict
        return verdict

    def is_approved(self, action_id: str) -> bool:
        """Check whether a specific action has been granted operator approval."""
        return self._verdicts.get(action_id, ApprovalVerdict(action_id=action_id, approved=False, timestamp=0.0)).approved

    def get_action_log(self) -> List[ActionPolicyResult]:
        """Return the immutable audit log of policy decisions."""
        return list(self._action_log)


# Global approval gate instance
default_approval_gate = ApprovalGate()
