"""FastAPI application for Sightline — Visual Agent Reliability Lab."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, List

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sightline.browser.manager import default_browser_manager
from sightline.config import Settings, get_settings
from sightline.dashboard import dashboard_router
from sightline.models import HealthStatus
from sightline.observation.artifacts import ArtifactManager, default_artifact_manager
from sightline.scenarios.base import ScenarioPublicDefinition
from sightline.scenarios.registry import default_registry
from sightline.synthetic.routes import STATIC_DIR, synthetic_router

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and graceful teardown of browser resources."""
    # Startup: Settings are loaded, browser remains lazily initialized
    yield
    # Shutdown: Ensure all Playwright contexts and browser processes are closed
    await default_browser_manager.close_all()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory for Sightline."""
    cfg = settings or get_settings()

    app = FastAPI(
        title=cfg.app_name,
        version=cfg.version,
        description="Sightline — Visual Agent Reliability Lab: Evaluation foundation for web agents.",
        lifespan=lifespan,
    )

    # Mount synthetic target router and dashboard router
    app.include_router(synthetic_router)
    app.include_router(dashboard_router)

    # Mount static assets for synthetic application
    app.mount("/synthetic", StaticFiles(directory=STATIC_DIR, html=True), name="synthetic-static")

    # Mount frontend static distribution if built
    if FRONTEND_DIST.exists():
        app.mount("/dashboard", StaticFiles(directory=FRONTEND_DIST, html=True), name="dashboard-static")

    @app.get("/", tags=["System"])
    async def root():
        """Root endpoint linking to synthetic portal and documentation."""
        return {
            "name": cfg.app_name,
            "version": cfg.version,
            "status": "online",
            "dashboard": f"{cfg.base_url}/dashboard/" if FRONTEND_DIST.exists() else "Frontend not built (run npm run build in frontend/)",
            "dashboard_api": f"{cfg.base_url}/api/dashboard/overview",
            "synthetic_portal": f"{cfg.base_url}/synthetic/",
            "scenarios_playground": f"{cfg.base_url}/synthetic/scenarios.html",
            "health_check": f"{cfg.base_url}/healthz",
            "scenarios_api": f"{cfg.base_url}/api/scenarios",
        }

    @app.get("/healthz", response_model=HealthStatus, tags=["System"])
    @app.get("/api/health", response_model=HealthStatus, tags=["System"])
    async def health_check() -> HealthStatus:
        """System health and browser availability probe."""
        return HealthStatus(
            status="healthy",
            app_name=cfg.app_name,
            version=cfg.version,
            bound_host=cfg.host,
            bound_port=cfg.port,
            browser_available=bool(cfg.chromium_executable_path),
            browser_path=cfg.chromium_executable_path,
            available_scenarios=len(default_registry.list_public()),
        )

    @app.get("/api/scenarios", response_model=List[ScenarioPublicDefinition], tags=["Scenarios"])
    async def list_scenarios() -> List[ScenarioPublicDefinition]:
        """List public scenario definitions for benchmark runners (isolating ground truth)."""
        return default_registry.list_public()

    @app.get("/api/scenarios/{scenario_id}", response_model=ScenarioPublicDefinition, tags=["Scenarios"])
    async def get_scenario(scenario_id: str) -> ScenarioPublicDefinition:
        """Fetch a single public scenario definition by ID."""
        pub = default_registry.get_public(scenario_id)
        if not pub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario with ID '{scenario_id}' was not found in registry.",
            )
        return pub

    @app.get("/api/artifacts/screenshots/{screenshot_id}", tags=["Artifacts"])
    async def get_screenshot_artifact(screenshot_id: str):
        """Safely serve an observation screenshot artifact by its sanitized ID without exposing host paths."""
        art_mgr = ArtifactManager(cfg)
        try:
            target_path = art_mgr.get_screenshot_path(screenshot_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid artifact identifier.")

        if not target_path.exists():
            # Check default artifact manager if different
            fallback_path = default_artifact_manager.get_screenshot_path(screenshot_id)
            if fallback_path.exists():
                return FileResponse(fallback_path, media_type="image/png")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Screenshot artifact '{screenshot_id}' not found.",
            )
        return FileResponse(target_path, media_type="image/png")

    return app


# Default app instance for uvicorn run: uvicorn sightline.app:app
app = create_app()
