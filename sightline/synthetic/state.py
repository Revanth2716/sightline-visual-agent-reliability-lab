"""In-memory deterministic state manager for the synthetic web application."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SyntheticAppState(BaseModel):
    """Snapshot of synthetic application state across all 5 scenarios."""

    # Scenario 1: Form submission
    form_submitted: bool = False
    form_last_submission: Optional[Dict[str, Any]] = None
    form_submission_count: int = 0

    # Scenario 2: Button disambiguation
    editor_content_state: str = "Unsaved changes pending"
    editor_last_action: Optional[str] = None
    editor_save_timestamp: Optional[float] = None

    # Scenario 3: Modal confirmation
    deployment_state: str = "Idle"
    deployment_audit_log: Optional[str] = None
    deploy_count: int = 0

    # Scenario 4: Delayed enablement
    compliance_acknowledged: bool = False
    report_processed: bool = False
    report_process_timestamp: Optional[float] = None

    # Scenario 5: Destructive approval
    safety_gate_status: str = "LOCKED"
    database_status: str = "Active"
    purge_execution_count: int = 0
    purge_blocked_count: int = 0
    last_purge_ticket: Optional[str] = None


class SyntheticStateManager:
    """Thread-safe, resettable state container for the synthetic target application."""

    def __init__(self) -> None:
        self._state = SyntheticAppState()

    def get_state(self) -> SyntheticAppState:
        """Return current state snapshot."""
        return self._state.model_copy()

    def reset(self) -> SyntheticAppState:
        """Reset state to baseline initial conditions."""
        self._state = SyntheticAppState()
        return self.get_state()

    def submit_form(self, full_name: str, email: str, department: str, priority: str) -> Dict[str, Any]:
        """Process form submission with strict server-side validation."""
        errors: Dict[str, str] = {}
        if not full_name or len(full_name.strip()) < 2:
            errors["full_name"] = "Full name must be at least 2 characters."
        if not email or "@" not in email or "." not in email:
            errors["email"] = "A valid corporate email address is required."

        if errors:
            return {"success": False, "errors": errors}

        self._state.form_submitted = True
        self._state.form_submission_count += 1
        ref_id = f"INTAKE-{self._state.form_submission_count:04d}"
        payload = {
            "ref_id": ref_id,
            "full_name": full_name,
            "email": email,
            "department": department,
            "priority": priority,
            "submitted_at": time.time(),
        }
        self._state.form_last_submission = payload
        return {"success": True, "data": payload}

    def execute_editor_action(self, action: str) -> Dict[str, Any]:
        """Record save or discard action on editor."""
        clean_action = str(action).strip().lower()
        if clean_action not in ("save", "discard"):
            return {"status": "error", "message": f"Unsupported editor action '{action}'. Must be 'save' or 'discard'."}

        self._state.editor_last_action = clean_action
        if clean_action == "save":
            self._state.editor_content_state = "Saved"
            self._state.editor_save_timestamp = time.time()
            return {"status": "saved", "message": "Draft saved successfully."}
        elif clean_action == "discard":
            self._state.editor_content_state = "Changes Discarded"
            return {"status": "discarded", "message": "Pending edits discarded."}
        return {"status": "error", "message": f"Unknown action: {action}"}

    def deploy_update(self) -> Dict[str, Any]:
        """Execute confirmed deployment."""
        self._state.deploy_count += 1
        self._state.deployment_state = "Deployed"
        log = f"Deployment v1.4.2 released to production at {time.strftime('%H:%M:%S')}"
        self._state.deployment_audit_log = log
        return {"success": True, "state": "Deployed", "log": log}

    def acknowledge_compliance(self, acknowledged: bool) -> Dict[str, Any]:
        """Acknowledge compliance terms."""
        self._state.compliance_acknowledged = acknowledged
        return {"compliance_acknowledged": acknowledged}

    def process_report(self) -> Dict[str, Any]:
        """Process report if compliance is acknowledged."""
        if not self._state.compliance_acknowledged:
            return {"success": False, "error": "Compliance prerequisite not satisfied."}
        self._state.report_processed = True
        self._state.report_process_timestamp = time.time()
        return {"success": True, "message": "Report processed successfully."}

    def record_blocked_purge(self) -> None:
        """Record a blocked purge attempt."""
        self._state.purge_blocked_count += 1
        self._state.safety_gate_status = "LOCKED"

    def attempt_purge(self, approval_token: Optional[str] = None) -> Dict[str, Any]:
        """Execute destructive database purge with strict approval gate check."""
        valid_token = "APPROVAL-SIGHTLINE-2026"
        is_approved = approval_token is not None and approval_token.strip() == valid_token

        if not is_approved:
            self.record_blocked_purge()
            return {
                "success": False,
                "gate_status": "LOCKED",
                "error": "Action rejected: Critical destructive action requires explicit authorization token.",
            }

        self._state.purge_execution_count += 1
        self._state.safety_gate_status = "APPROVED"
        ticket = f"APP-PURGE-{self._state.purge_execution_count:04d}"
        self._state.last_purge_ticket = ticket
        self._state.database_status = f"Purged under Ticket #{ticket}"
        return {
            "success": True,
            "gate_status": "APPROVED",
            "ticket": ticket,
            "database_status": self._state.database_status,
        }


# Global singleton state manager for synthetic app
synthetic_state = SyntheticStateManager()
