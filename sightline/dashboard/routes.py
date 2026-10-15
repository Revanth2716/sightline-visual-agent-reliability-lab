"""FastAPI route definitions for the Sightline inspection dashboard."""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from sightline.benchmark.models import (
    BenchmarkSummaryReport,
    BenchmarkTrialResult,
)
from sightline.dashboard.models import (
    BenchmarkRunSummaryItem,
    DashboardOverviewStats,
    TrialTraceDetail,
)
from sightline.dashboard.service import DashboardService, default_dashboard_service

dashboard_router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def get_service() -> DashboardService:
    """Dependency helper returning singleton dashboard service."""
    return default_dashboard_service


@dashboard_router.get(
    "/overview",
    response_model=DashboardOverviewStats,
    summary="Get aggregated reliability statistics across all runs",
)
async def get_overview_statistics() -> DashboardOverviewStats:
    """Return portfolio-level overview metrics, numerators/denominators, and runs."""
    svc = get_service()
    return svc.get_overview_stats()


@dashboard_router.get(
    "/runs",
    response_model=List[BenchmarkRunSummaryItem],
    summary="List all available benchmark runs",
)
async def list_runs(
    scenario_id: Optional[str] = Query(None, description="Filter by scenario ID"),
    strategy: Optional[str] = Query(None, description="Filter by strategy (closed_loop | baseline)"),
) -> List[BenchmarkRunSummaryItem]:
    """Return summaries of all valid saved benchmark runs."""
    svc = get_service()
    return svc.list_runs(scenario_id=scenario_id, strategy=strategy)


@dashboard_router.get(
    "/runs/{run_id}",
    response_model=BenchmarkSummaryReport,
    summary="Get full report for a single benchmark run",
)
async def get_run_report(run_id: str) -> BenchmarkSummaryReport:
    """Fetch complete benchmark summary report by unique run_id."""
    svc = get_service()
    try:
        return svc.get_run(run_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark run '{run_id}' not found.",
        ) from exc


@dashboard_router.get(
    "/runs/{run_id}/trials/{trial_index}",
    response_model=BenchmarkTrialResult,
    summary="Get details for an individual trial",
)
async def get_trial_detail(run_id: str, trial_index: int) -> BenchmarkTrialResult:
    """Fetch details and metrics for an individual trial within a run."""
    svc = get_service()
    try:
        return svc.get_trial(run_id, trial_index)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (FileNotFoundError, LookupError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@dashboard_router.get(
    "/runs/{run_id}/trials/{trial_index}/trace",
    response_model=TrialTraceDetail,
    summary="Get execution trace and screenshot mapping for a trial",
)
async def get_trial_trace_data(run_id: str, trial_index: int) -> TrialTraceDetail:
    """Fetch visual execution steps, DOM evidence, and screenshot IDs for a trial."""
    svc = get_service()
    try:
        return svc.get_trial_trace(run_id, trial_index)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (FileNotFoundError, LookupError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
