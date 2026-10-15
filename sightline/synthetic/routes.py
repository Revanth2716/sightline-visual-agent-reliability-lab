"""FastAPI router for the local synthetic target application."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from sightline.safety.policy import PolicyDecision, default_approval_gate
from sightline.synthetic.state import synthetic_state

synthetic_router = APIRouter(prefix="", tags=["Synthetic Target"])

STATIC_DIR = Path(__file__).parent / "static"


class FormSubmissionRequest(BaseModel):
    full_name: str
    email: str
    department: str = "Engineering"
    priority: str = "High"


class EditorActionRequest(BaseModel):
    action: str = Field(description="'save' or 'discard'")


class ComplianceRequest(BaseModel):
    acknowledged: bool


class PurgeRequest(BaseModel):
    approval_token: Optional[str] = None


# HTML Page routes
@synthetic_router.get("/synthetic", include_in_schema=False)
@synthetic_router.get("/synthetic/", include_in_schema=False)
async def serve_synthetic_index():
    """Serve the synthetic portal index."""
    index_file = STATIC_DIR / "index.html"
    return FileResponse(index_file)


@synthetic_router.get("/synthetic/scenarios.html", include_in_schema=False)
async def serve_synthetic_scenarios():
    """Serve the synthetic scenarios playground."""
    scenarios_file = STATIC_DIR / "scenarios.html"
    return FileResponse(scenarios_file)


# API state management routes
@synthetic_router.get("/api/synthetic/state")
async def get_synthetic_state() -> Dict[str, Any]:
    """Inspect current synthetic application state snapshot."""
    return synthetic_state.get_state().model_dump()


@synthetic_router.post("/api/synthetic/reset")
async def reset_synthetic_state() -> Dict[str, Any]:
    """Reset synthetic application to clean initial conditions."""
    return synthetic_state.reset().model_dump()


@synthetic_router.post("/api/synthetic/form-submit")
async def handle_form_submit(req: FormSubmissionRequest) -> Dict[str, Any]:
    """Process customer intake form submission with validation."""
    result = synthetic_state.submit_form(
        full_name=req.full_name,
        email=req.email,
        department=req.department,
        priority=req.priority,
    )
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=result)
    return result


@synthetic_router.post("/api/synthetic/editor-action")
async def handle_editor_action(req: EditorActionRequest) -> Dict[str, Any]:
    """Handle Save vs Discard editor actions."""
    action_clean = req.action.strip().lower()
    if action_clean not in ("save", "discard"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unsupported editor action '{req.action}'. Expected 'save' or 'discard'.",
        )
    result = synthetic_state.execute_editor_action(action_clean)
    if result.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))
    return result


@synthetic_router.post("/api/synthetic/deploy")
async def handle_deploy() -> Dict[str, Any]:
    """Handle confirmed production deployment."""
    return synthetic_state.deploy_update()


@synthetic_router.post("/api/synthetic/compliance")
async def handle_compliance(req: ComplianceRequest) -> Dict[str, Any]:
    """Acknowledge compliance prerequisites."""
    return synthetic_state.acknowledge_compliance(req.acknowledged)


@synthetic_router.post("/api/synthetic/process-report")
async def handle_process_report() -> Dict[str, Any]:
    """Process compliance report."""
    result = synthetic_state.process_report()
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)
    return result


@synthetic_router.post("/api/synthetic/purge")
async def handle_purge(req: PurgeRequest) -> Dict[str, Any]:
    """Handle database purge action with explicit approval gate enforcement."""
    # 1. Enforce safety policy at server boundary
    policy_verdict = default_approval_gate.evaluate_action(
        action_name="purge_database",
        target_selector="#btn-execute-purge",
        approval_token=req.approval_token,
    )
    if policy_verdict.decision != PolicyDecision.ALLOW:
        synthetic_state.record_blocked_purge()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": policy_verdict.reason,
                "gate_status": "LOCKED",
                "risk_level": policy_verdict.risk_level.value,
            },
        )

    # 2. Execute against synthetic state
    result = synthetic_state.attempt_purge(approval_token=req.approval_token)
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=result)
    return result
