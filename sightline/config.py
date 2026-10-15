"""Sightline configuration models and environment loader."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


def resolve_chromium_binary() -> Optional[str]:
    """Auto-detect existing Chromium executable on Windows/local machine to prevent re-downloads."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        playwright_dir = Path(local_app_data) / "ms-playwright"
        if playwright_dir.exists():
            # Look for existing chromium installations
            candidates = sorted(playwright_dir.glob("chromium-*/chrome-win64/chrome.exe"), reverse=True)
            if candidates and candidates[0].exists():
                return str(candidates[0])
            # Also check chrome-win
            candidates_win = sorted(playwright_dir.glob("chromium-*/chrome-win/chrome.exe"), reverse=True)
            if candidates_win and candidates_win[0].exists():
                return str(candidates_win[0])
            # Check headless shell
            candidates_shell = sorted(
                playwright_dir.glob("chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe"),
                reverse=True,
            )
            if candidates_shell and candidates_shell[0].exists():
                return str(candidates_shell[0])
    return None


class Settings(BaseModel):
    """Runtime configuration for Sightline — Visual Agent Reliability Lab."""

    app_name: str = "Sightline Visual Agent Reliability Lab"
    version: str = "0.1.0"
    environment: str = Field(default="development", description="Environment mode")

    # Local-first networking (strictly bound to loopback)
    host: str = Field(default="127.0.0.1", description="Loopback host binding")
    port: int = Field(default=8100, description="Local HTTP server port")

    # Browser automation settings
    browser_headless: bool = Field(default=True, description="Run Chromium in headless mode")
    browser_timeout_ms: int = Field(default=15_000, description="Default action timeout in milliseconds")
    browser_viewport_width: int = Field(default=1280, description="Viewport width")
    browser_viewport_height: int = Field(default=800, description="Viewport height")
    chromium_executable_path: Optional[str] = Field(
        default_factory=resolve_chromium_binary,
        description="Explicit Chromium path; if None, auto-discovers in ms-playwright or Playwright cache",
    )

    # Artifact and storage settings
    artifacts_dir: str = Field(
        default_factory=lambda: os.environ.get("SIGHTLINE_ARTIFACTS_DIR", "artifacts"),
        description="Project-relative artifact storage directory",
    )

    @property
    def resolved_artifacts_dir(self) -> Path:
        """Resolve and ensure the dedicated artifact storage directory."""
        path = (Path(__file__).parent.parent / self.artifacts_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    # Base URLs
    @property
    def base_url(self) -> str:
        """Construct the local base URL for the server."""
        return f"http://{self.host}:{self.port}"

    @property
    def synthetic_base_url(self) -> str:
        """Construct the synthetic website base URL."""
        return f"http://{self.host}:{self.port}/synthetic"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()
