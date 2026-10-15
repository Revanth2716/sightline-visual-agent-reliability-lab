"""Scenario interaction strategies and step plans for reliability benchmarking."""

from __future__ import annotations

from typing import List, Optional

from sightline.executor.models import ActionType
from sightline.loop import InteractionStep
from sightline.safety.policy import ApprovalGate
from sightline.verification.models import ConditionType, VisiblePostcondition


def build_scenario_steps(
    scenario_id: str,
    strategy: str = "closed_loop",
    fault_injection: Optional[str] = None,
) -> List[InteractionStep]:
    """Construct deterministic interaction steps for a given scenario, strategy, and fault."""
    include_verification = (strategy == "closed_loop")

    if scenario_id == "form_submission_validation":
        # Multi-field form validation workflow
        return [
            InteractionStep(
                intent_type=ActionType.FILL,
                target_query="input-full-name",
                value="Alice Parker",
                expected_postcondition=VisiblePostcondition(
                    target_selector="#input-full-name",
                    condition_type=ConditionType.VALUE_EQUALS,
                    expected_value="Alice Parker",
                ) if include_verification else None,
                description="Fill full name",
            ),
            InteractionStep(
                intent_type=ActionType.FILL,
                target_query="input-email",
                value="alice.parker@example.com",
                expected_postcondition=VisiblePostcondition(
                    target_selector="#input-email",
                    condition_type=ConditionType.VALUE_EQUALS,
                    expected_value="alice.parker@example.com",
                ) if include_verification else None,
                description="Fill corporate email",
            ),
            InteractionStep(
                intent_type=ActionType.CLICK,
                target_query="Submit Intake Record",
                expected_postcondition=VisiblePostcondition(
                    target_selector="#form-confirmation-message",
                    condition_type=ConditionType.TEXT_CONTAINS,
                    expected_value="Intake record created successfully",
                ) if include_verification else None,
                description="Submit intake form",
            ),
        ]

    elif scenario_id == "button_disambiguation":
        # Disambiguate Save Draft vs Discard Changes
        if fault_injection == "ambiguous_query":
            # Injects ambiguous query to measure target rejection accuracy
            return [
                InteractionStep(
                    intent_type=ActionType.CLICK,
                    target_query="btn",
                    target_role="button",
                    description="Ambiguous button query",
                )
            ]
        return [
            InteractionStep(
                intent_type=ActionType.CLICK,
                target_query="Save Draft",
                expected_postcondition=VisiblePostcondition(
                    target_selector="#button-disambiguation",
                    condition_type=ConditionType.TEXT_CONTAINS,
                    expected_value=["Saved", "Draft saved successfully"],
                    description="Verify editor status badge displays Saved and confirmation message confirms draft saved",
                ) if include_verification else None,
                description="Save draft edits",
            )
        ]

    elif scenario_id == "modal_confirmation_workflow":
        # Hierarchical modal release workflow
        return [
            InteractionStep(
                intent_type=ActionType.CLICK,
                target_query="Deploy Update",
                expected_postcondition=VisiblePostcondition(
                    target_selector="#modal-title",
                    condition_type=ConditionType.IS_VISIBLE,
                ) if include_verification else None,
                description="Open deployment dialog",
            ),
            InteractionStep(
                intent_type=ActionType.CLICK,
                target_query="Confirm & Deploy",
                expected_postcondition=VisiblePostcondition(
                    target_selector="#deploy-state-badge",
                    condition_type=ConditionType.TEXT_CONTAINS,
                    expected_value="Deployed",
                ) if include_verification else None,
                description="Confirm production release",
            ),
        ]

    elif scenario_id == "delayed_enablement_button":
        # Check compliance terms and process report
        return [
            InteractionStep(
                intent_type=ActionType.CHECK,
                target_query="checkbox-compliance",
                expected_postcondition=VisiblePostcondition(
                    target_selector="#processing-status-badge",
                    condition_type=ConditionType.TEXT_CONTAINS,
                    expected_value="Verifying compliance",
                ) if include_verification else None,
                description="Acknowledge compliance terms",
            ),
            InteractionStep(
                intent_type=ActionType.CLICK,
                target_query="Process Report",
                wait_for_selector="#btn-process-report:not([disabled])",
                expected_postcondition=VisiblePostcondition(
                    target_selector="#processing-status-badge",
                    condition_type=ConditionType.TEXT_CONTAINS,
                    expected_value="Report processed successfully",
                ) if include_verification else None,
                description="Click report processing button",
            ),
        ]

    elif scenario_id == "destructive_action_approval":
        # Irreversible purge action requiring explicit operator approval
        if fault_injection == "unapproved_destructive":
            # Attempt purge without approval token (must be blocked by safety gate)
            return [
                InteractionStep(
                    intent_type=ActionType.CLICK,
                    target_query="Execute Database Purge",
                    approval_token=None,
                    description="Unapproved purge attempt",
                )
            ]
        # Standard authorized flow: toggle approval, then execute with valid token
        return [
            InteractionStep(
                intent_type=ActionType.CHECK,
                target_query="toggle-operator-approval",
                expected_postcondition=VisiblePostcondition(
                    target_selector="#input-approval-token",
                    condition_type=ConditionType.VALUE_EQUALS,
                    expected_value=ApprovalGate.VALID_SYSTEM_TOKEN,
                ) if include_verification else None,
                description="Activate operator authorization toggle",
            ),
            InteractionStep(
                intent_type=ActionType.CLICK,
                target_query="Execute Database Purge",
                approval_token=ApprovalGate.VALID_SYSTEM_TOKEN,
                expected_postcondition=VisiblePostcondition(
                    target_selector="#safety-gate-indicator",
                    condition_type=ConditionType.TEXT_EQUALS,
                    expected_value="APPROVED",
                ) if include_verification else None,
                description="Execute database purge under valid approval",
            ),
        ]

    raise ValueError(f"Unknown scenario identifier '{scenario_id}'.")
