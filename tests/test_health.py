"""Tests for Sightline health, system status, and public API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from sightline.models import HealthStatus
from sightline.scenarios.catalog import SCENARIOS


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Verify root endpoint returns system metadata and navigation links."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "Sightline" in data["name"]
    assert "synthetic_portal" in data
    assert "health_check" in data


@pytest.mark.asyncio
async def test_healthz_endpoint(async_client: AsyncClient):
    """Verify healthz endpoint returns valid HealthStatus schema."""
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    health = HealthStatus(**data)
    assert health.status == "healthy"
    assert health.bound_host == "127.0.0.1"
    assert health.available_scenarios == 5
    assert health.browser_available is True
    assert health.browser_path is not None


@pytest.mark.asyncio
async def test_api_health_endpoint_alias(async_client: AsyncClient):
    """Verify /api/health behaves identically to /healthz."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_list_scenarios_endpoint(async_client: AsyncClient):
    """Verify /api/scenarios lists all 5 public scenario definitions without exposing ground truth."""
    response = await async_client.get("/api/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) == 5

    scenario_ids = [s["scenario_id"] for s in scenarios]
    for expected_id in SCENARIOS.keys():
        assert expected_id in scenario_ids

    # Ground truth isolation invariant check: evaluator fields must NOT be in public payload
    for s in scenarios:
        assert "expected_final_state" not in s
        assert "target_elements" not in s
        assert "distractor_elements" not in s
        assert "initial_state_assertions" not in s
        assert "requires_approval" not in s
        assert "max_steps_allowed" not in s


@pytest.mark.asyncio
async def test_get_single_scenario_endpoint(async_client: AsyncClient):
    """Verify /api/scenarios/{id} fetches public definition."""
    response = await async_client.get("/api/scenarios/form_submission_validation")
    assert response.status_code == 200
    data = response.json()
    assert data["scenario_id"] == "form_submission_validation"
    assert "Multi-Field Form" in data["title"]
    assert "expected_final_state" not in data


@pytest.mark.asyncio
async def test_get_unknown_scenario_returns_404(async_client: AsyncClient):
    """Verify unknown scenario ID returns 404."""
    response = await async_client.get("/api/scenarios/non_existent_scenario_xyz")
    assert response.status_code == 404
