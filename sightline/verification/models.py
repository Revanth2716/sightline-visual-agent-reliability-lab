"""Data models for closed-loop verification."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    """Evaluation result for closed-loop postcondition verification."""

    VERIFIED = "verified"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class ConditionType(str, Enum):
    """Visible condition check types against live UI."""

    TEXT_CONTAINS = "text_contains"
    TEXT_EQUALS = "text_equals"
    IS_VISIBLE = "is_visible"
    IS_HIDDEN = "is_hidden"
    IS_ENABLED = "is_enabled"
    IS_DISABLED = "is_disabled"
    VALUE_EQUALS = "value_equals"
    CLASS_CONTAINS = "class_contains"


class VisiblePostcondition(BaseModel):
    """Specification of an expected visible postcondition after an action."""

    target_selector: str = Field(description="Selector for visible element to inspect")
    condition_type: ConditionType = Field(description="Visible predicate to evaluate")
    expected_value: Any = Field(default=None, description="Expected string, boolean, or class value")
    description: str = Field(default="", description="Human-readable condition description")


class VerificationResult(BaseModel):
    """Evidence and verdict from post-action verification."""

    status: VerificationStatus
    pre_observation_id: str = Field(description="Observation identifier before action")
    post_observation_id: str = Field(description="Observation identifier after action")
    postcondition: VisiblePostcondition = Field(description="Postcondition asserted")
    actual_value: Any = Field(default=None, description="Actual extracted value from live page")
    evidence: str = Field(description="Diagnostic explanation supporting verdict")
    recovery_attempted: bool = Field(default=False, description="Whether bounded recovery was triggered")
    error_message: Optional[str] = None
