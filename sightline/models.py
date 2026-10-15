"""Core domain data models for Sightline."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    """System health check payload."""

    status: str = Field(default="healthy", description="Status string: healthy | degraded")
    app_name: str = Field(description="Name of the service")
    version: str = Field(description="Service semantic version")
    bound_host: str = Field(description="Host bound (loopback only)")
    bound_port: int = Field(description="Port bound")
    browser_available: bool = Field(description="Whether a Chromium binary was detected")
    browser_path: Optional[str] = Field(default=None, description="Path to detected Chromium binary")
    available_scenarios: int = Field(description="Count of loaded deterministic scenarios")


class ApprovalRequest(BaseModel):
    """Request for explicit human approval on high-risk actions."""

    action_id: str
    scenario_id: str
    target_element: str
    risk_level: str
    justification: str


class ApprovalVerdict(BaseModel):
    """Verdict recorded by the approval gate."""

    action_id: str
    approved: bool
    reviewer: str = "human_operator"
    timestamp: float
    notes: Optional[str] = None


class StateCheckResult(BaseModel):
    """Result of checking a scenario condition against live DOM/app state."""

    scenario_id: str
    passed: bool
    current_state: Dict[str, Any]
    expected_state: Dict[str, Any]
    discrepancies: List[str] = Field(default_factory=list)
