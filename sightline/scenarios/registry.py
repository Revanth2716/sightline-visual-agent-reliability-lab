"""Scenario registry and ground-truth verification engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from sightline.models import StateCheckResult
from sightline.scenarios.base import (
    ExpectedCondition,
    ScenarioGroundTruth,
    ScenarioPublicDefinition,
    ScenarioSpecification,
)
from sightline.scenarios.catalog import SCENARIOS


class ScenarioRegistry:
    """Manages scenario specifications, public view generation, and ground truth assertions."""

    def __init__(self, scenarios: Optional[Dict[str, ScenarioSpecification]] = None) -> None:
        self._scenarios = scenarios or SCENARIOS

    def get(self, scenario_id: str) -> Optional[ScenarioSpecification]:
        """Fetch complete specification by ID."""
        return self._scenarios.get(scenario_id)

    def get_public(self, scenario_id: str) -> Optional[ScenarioPublicDefinition]:
        """Fetch agent-safe public definition (isolating ground truth)."""
        spec = self._scenarios.get(scenario_id)
        return spec.get_public_definition() if spec else None

    def list_public(self) -> List[ScenarioPublicDefinition]:
        """List all public scenario definitions for benchmark runners."""
        return [s.get_public_definition() for s in self._scenarios.values()]

    def get_ground_truth(self, scenario_id: str) -> Optional[ScenarioGroundTruth]:
        """Fetch ground-truth specification (for internal evaluator use only)."""
        spec = self._scenarios.get(scenario_id)
        return spec.ground_truth if spec else None

    def evaluate_condition(self, condition: ExpectedCondition, actual_value: Any) -> bool:
        """Evaluate a single ground truth condition against an actual value."""
        pred = condition.predicate.lower()
        expected = condition.expected_value

        if pred == "equals":
            if isinstance(expected, bool):
                return bool(actual_value) is expected
            return str(actual_value).strip() == str(expected).strip()
        elif pred == "contains":
            return str(expected).lower() in str(actual_value).lower()
        elif pred == "not_empty":
            return actual_value is not None and str(actual_value).strip() != ""
        elif pred == "truthy":
            return bool(actual_value) is True
        elif pred == "falsy":
            return not bool(actual_value)
        return False

    def verify_state(
        self, scenario_id: str, live_dom_state: Dict[str, Dict[str, Any]], phase: str = "final"
    ) -> StateCheckResult:
        """Verify live DOM state snapshot against scenario assertions (initial or final)."""
        gt = self.get_ground_truth(scenario_id)
        if not gt:
            return StateCheckResult(
                scenario_id=scenario_id,
                passed=False,
                current_state=live_dom_state,
                expected_state={},
                discrepancies=[f"Scenario '{scenario_id}' not found in registry"],
            )

        assertions = gt.initial_state_assertions if phase == "initial" else gt.expected_final_state
        discrepancies: List[str] = []
        expected_state_map: Dict[str, Any] = {}

        for cond in assertions:
            elem_state = live_dom_state.get(cond.element_id, {})
            actual_val = elem_state.get(cond.attribute)
            expected_state_map[f"{cond.element_id}.{cond.attribute}"] = cond.expected_value

            if not self.evaluate_condition(cond, actual_val):
                discrepancies.append(
                    f"Element '{cond.element_id}' attribute '{cond.attribute}' expected '{cond.expected_value}' "
                    f"({cond.predicate}), but got '{actual_val}'"
                )

        return StateCheckResult(
            scenario_id=scenario_id,
            passed=len(discrepancies) == 0,
            current_state=live_dom_state,
            expected_state=expected_state_map,
            discrepancies=discrepancies,
        )


# Global singleton registry
default_registry = ScenarioRegistry()
