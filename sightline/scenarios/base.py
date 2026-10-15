"""Base classes and contracts for Sightline benchmark scenarios.

Architecture invariant:
Scenario ground-truth specifications (expected final states and validation predicates)
are strictly isolated from public agent observations. The agent receives only
ScenarioPublicDefinition.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class ScenarioCategory(str, Enum):
    """Categorization of visual agent challenges."""

    FORM_INPUT = "form_input"
    VISUAL_DISAMBIGUATION = "visual_disambiguation"
    HIERARCHICAL_MODAL = "hierarchical_modal"
    TEMPORAL_LATENCY = "temporal_latency"
    SAFETY_GOVERNANCE = "safety_governance"


class ActionRisk(str, Enum):
    """Action safety classification."""

    BENIGN = "benign"
    REVERSIBLE = "reversible"
    CRITICAL_DESTRUCTIVE = "critical_destructive"


class ScenarioPublicDefinition(BaseModel):
    """Public scenario metadata that an agent or runner is permitted to observe."""

    scenario_id: str = Field(description="Unique stable scenario identifier")
    title: str = Field(description="Human-readable title")
    description: str = Field(description="High-level description of the task")
    category: ScenarioCategory = Field(description="Challenge category")
    target_path: str = Field(description="Relative synthetic URL path for the scenario")
    user_instruction: str = Field(description="Goal prompt provided to the agent")
    initial_conditions_summary: str = Field(description="Summary of initial UI state")


class ExpectedCondition(BaseModel):
    """Ground truth assertion for an element or app state."""

    element_id: str = Field(description="DOM ID or selector of target element")
    attribute: str = Field(description="Attribute or state key (e.g. text, value, disabled, class, display)")
    expected_value: Any = Field(description="Expected ground truth value")
    predicate: str = Field(
        default="equals",
        description="Predicate type: equals | contains | not_empty | truthy | falsy",
    )


class ScenarioGroundTruth(BaseModel):
    """Ground truth specification held by the evaluator only.

    NEVER exposed to the agent during evaluation.
    """

    scenario_id: str
    target_elements: List[str] = Field(description="List of legitimate element IDs relevant to task")
    distractor_elements: List[str] = Field(
        default_factory=list, description="List of visually similar or confusing elements"
    )
    initial_state_assertions: List[ExpectedCondition] = Field(description="Assertions to confirm before starting")
    expected_final_state: List[ExpectedCondition] = Field(description="Assertions required to declare task complete")
    requires_approval: bool = Field(default=False, description="Whether this scenario contains gated destructive actions")
    max_steps_allowed: int = Field(default=8, description="Step budget before forcing timeout")


class ScenarioSpecification(BaseModel):
    """Complete scenario definition binding public metadata with evaluator ground truth."""

    public: ScenarioPublicDefinition
    ground_truth: ScenarioGroundTruth

    def get_public_definition(self) -> ScenarioPublicDefinition:
        """Extract public metadata for agent observation."""
        return self.public
