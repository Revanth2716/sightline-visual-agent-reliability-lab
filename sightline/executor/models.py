"""Data models for bounded action execution."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from sightline.observation.models import ObservedTarget


class ActionType(str, Enum):
    """Permitted bounded action categories."""

    CLICK = "click"
    FILL = "fill"
    CHECK = "check"
    UNCHECK = "uncheck"
    SELECT_OPTION = "select_option"
    READ = "read"


class ExecutionStatus(str, Enum):
    """Status outcome of attempting a bounded action."""

    SUCCESS = "success"
    BLOCKED_BY_SAFETY = "blocked_by_safety"
    TARGET_NOT_FOUND = "target_not_found"
    TARGET_STALE = "target_stale"
    TARGET_DISABLED = "target_disabled"
    OUT_OF_BOUNDS = "out_of_bounds"
    BUDGET_EXCEEDED = "budget_exceeded"
    UNSUPPORTED_ACTION = "unsupported_action"
    FAILED = "failed"


class ActionIntent(BaseModel):
    """Specification of an intended interaction on a grounded target."""

    action_type: ActionType = Field(description="Action verb to perform")
    target: ObservedTarget = Field(description="Target resolved from recent observation pass")
    value: Optional[str] = Field(default=None, description="Input string, select option, or payload")
    approval_token: Optional[str] = Field(
        default=None,
        description="Explicit operator approval token required for critical destructive actions",
    )
    description: Optional[str] = Field(default=None, description="Human-readable description of intent")


class ActionResult(BaseModel):
    """Structured record of an action execution attempt."""

    status: ExecutionStatus
    action_intent: ActionIntent
    step_index: int
    execution_time_ms: float
    evidence: str = Field(description="Evidence recorded during or immediately following action")
    error_message: Optional[str] = None
