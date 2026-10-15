"""Tests for scenario catalog, ground truth separation, and predicate verification."""

from __future__ import annotations

import pytest

from sightline.scenarios.base import ExpectedCondition, ScenarioCategory
from sightline.scenarios.catalog import SCENARIOS
from sightline.scenarios.registry import ScenarioRegistry, default_registry


def test_scenario_catalog_contains_five_distinct_scenarios():
    """Verify registry has exactly 5 standardized scenarios with distinct stable IDs."""
    assert len(SCENARIOS) == 5
    expected_ids = {
        "form_submission_validation",
        "button_disambiguation",
        "modal_confirmation_workflow",
        "delayed_enablement_button",
        "destructive_action_approval",
    }
    assert set(SCENARIOS.keys()) == expected_ids


def test_scenario_categories_coverage():
    """Verify distinct categories are represented across the 5 scenarios."""
    categories = {spec.public.category for spec in SCENARIOS.values()}
    assert ScenarioCategory.FORM_INPUT in categories
    assert ScenarioCategory.VISUAL_DISAMBIGUATION in categories
    assert ScenarioCategory.HIERARCHICAL_MODAL in categories
    assert ScenarioCategory.TEMPORAL_LATENCY in categories
    assert ScenarioCategory.SAFETY_GOVERNANCE in categories


def test_ground_truth_isolation_invariant():
    """Verify that public view generation strips ground truth fields."""
    for spec in SCENARIOS.values():
        public_view = spec.get_public_definition()

        # Public fields exist
        assert public_view.scenario_id == spec.public.scenario_id
        assert public_view.title
        assert public_view.user_instruction
        assert public_view.target_path

        # Ground truth attributes must not be present on public definition model
        assert not hasattr(public_view, "expected_final_state")
        assert not hasattr(public_view, "target_elements")
        assert not hasattr(public_view, "distractor_elements")


def test_registry_lookup():
    """Verify registry queries."""
    reg = ScenarioRegistry()
    assert reg.get("form_submission_validation") is not None
    assert reg.get("unknown_id") is None
    assert reg.get_public("button_disambiguation") is not None
    assert reg.get_ground_truth("destructive_action_approval") is not None


def test_predicate_evaluation_engine():
    """Verify predicate evaluation across various operators."""
    reg = default_registry

    # equals (string)
    c1 = ExpectedCondition(element_id="el", attribute="text", expected_value="Saved")
    assert reg.evaluate_condition(c1, "Saved") is True
    assert reg.evaluate_condition(c1, "Not Saved") is False

    # equals (boolean)
    c2 = ExpectedCondition(element_id="el", attribute="disabled", expected_value=True)
    assert reg.evaluate_condition(c2, True) is True
    assert reg.evaluate_condition(c2, False) is False

    # contains
    c3 = ExpectedCondition(element_id="el", attribute="text", expected_value="Ticket #APP", predicate="contains")
    assert reg.evaluate_condition(c3, "Purged under Ticket #APP-001") is True
    assert reg.evaluate_condition(c3, "Standard operation") is False

    # not_empty
    c4 = ExpectedCondition(element_id="el", attribute="text", expected_value="", predicate="not_empty")
    assert reg.evaluate_condition(c4, "anything") is True
    assert reg.evaluate_condition(c4, "") is False
    assert reg.evaluate_condition(c4, None) is False

    # truthy / falsy
    c5 = ExpectedCondition(element_id="el", attribute="val", expected_value="", predicate="truthy")
    assert reg.evaluate_condition(c5, 1) is True
    assert reg.evaluate_condition(c5, 0) is False


def test_verify_state_passing_and_failing():
    """Verify scenario state evaluation against simulated DOM state snapshots."""
    reg = default_registry
    scenario_id = "button_disambiguation"

    # Simulated valid initial state
    valid_initial_dom = {
        "editor-status-badge": {"text": "Unsaved changes pending"},
        "action-result-text": {"text": ""},
    }
    result_init = reg.verify_state(scenario_id, valid_initial_dom, phase="initial")
    assert result_init.passed is True
    assert len(result_init.discrepancies) == 0

    # Simulated invalid initial state
    invalid_initial_dom = {
        "editor-status-badge": {"text": "Saved"},
        "action-result-text": {"text": "Draft saved"},
    }
    result_fail = reg.verify_state(scenario_id, invalid_initial_dom, phase="initial")
    assert result_fail.passed is False
    assert len(result_fail.discrepancies) > 0

    # Simulated valid final state
    valid_final_dom = {
        "editor-status-badge": {"text": "Saved (Draft)"},
        "action-result-text": {"text": "Draft saved successfully at 10:00:00"},
        "action-result-status": {"text": "saved"},
    }
    result_final = reg.verify_state(scenario_id, valid_final_dom, phase="final")
    assert result_final.passed is True
    assert len(result_final.discrepancies) == 0


def test_button_disambiguation_postcondition_vs_ground_truth_predicates():
    """Verify that satisfying only the agent's partial postcondition (editor-status-badge)

    fails evaluator ground truth when action-result-text or action-result-status are incomplete,
    demonstrating the exact root cause of the historical false-positive discrepancy.
    """
    reg = default_registry
    scenario_id = "button_disambiguation"

    # Case A: Partial postcondition satisfied (badge contains 'Saved'), but action-result-text not yet updated
    partial_dom_missing_text = {
        "editor-status-badge": {"text": "Saved (Draft)"},
        "action-result-text": {"text": ""},
        "action-result-status": {"text": "saved"},
    }
    res_a = reg.verify_state(scenario_id, partial_dom_missing_text, phase="final")
    assert res_a.passed is False
    assert any("action-result-text" in d for d in res_a.discrepancies)

    # Case B: Badge and text updated, but hidden element action-result-status extracted as empty (e.g. innerText on display:none)
    partial_dom_hidden_empty = {
        "editor-status-badge": {"text": "Saved (Draft)"},
        "action-result-text": {"text": "Draft saved successfully at 14:00:00"},
        "action-result-status": {"text": ""},
    }
    res_b = reg.verify_state(scenario_id, partial_dom_hidden_empty, phase="final")
    assert res_b.passed is False
    assert any("action-result-status" in d for d in res_b.discrepancies)

    # Case C: All 3 predicates completely populated and extracted (live DOM matching ground truth)
    complete_dom = {
        "editor-status-badge": {"text": "Saved (Draft)"},
        "action-result-text": {"text": "Draft saved successfully at 14:00:00"},
        "action-result-status": {"text": "saved"},
    }
    res_c = reg.verify_state(scenario_id, complete_dom, phase="final")
    assert res_c.passed is True
    assert len(res_c.discrepancies) == 0
