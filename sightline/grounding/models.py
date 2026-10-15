"""Data models for deterministic target grounding."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from sightline.observation.models import ObservedTarget


class GroundingMatchStatus(str, Enum):
    """Categorical outcome of deterministic target grounding."""

    MATCH_UNIQUE = "match_unique"
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"
    STALE = "stale"
    OUT_OF_BOUNDS = "out_of_bounds"


class GroundingRequest(BaseModel):
    """Goal or query to resolve against observed interactive candidates."""

    query: str = Field(description="Visible text label, element ID, or attribute to ground")
    role: Optional[str] = Field(default=None, description="Optional semantic role constraint: button, textbox, etc.")
    target_id: Optional[str] = Field(default=None, description="Explicit target ID from prior observation if known")
    selector_hint: Optional[str] = Field(default=None, description="Optional DOM selector hint")


class GroundingResult(BaseModel):
    """Result of attempting to ground a target within an observation."""

    status: GroundingMatchStatus
    matched_target: Optional[ObservedTarget] = None
    confidence: float = Field(default=0.0, description="Match score: 1.0 for unique exact match, 0.0 otherwise")
    matching_evidence: List[str] = Field(default_factory=list, description="Reasoning and attributes supporting match")
    candidate_count: int = Field(default=0, description="Total matching candidates evaluated")
    ambiguous_candidates: List[ObservedTarget] = Field(
        default_factory=list,
        description="List of competing candidates if status is AMBIGUOUS",
    )
    error_message: Optional[str] = Field(default=None, description="Explanatory failure message")
