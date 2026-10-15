"""Pytest configuration, fixtures, and test hooks for Sightline."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import AsyncIterator

# Confine all test-generated screenshots and artifacts to an isolated directory
TEST_ARTIFACTS_DIR = "artifacts/.test_artifacts"
os.environ["SIGHTLINE_ARTIFACTS_DIR"] = TEST_ARTIFACTS_DIR

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from sightline.app import create_app
from sightline.browser.manager import BrowserManager
from sightline.config import Settings, get_settings
from sightline.synthetic.routes import STATIC_DIR
from sightline.synthetic.state import synthetic_state

# Clear cached settings so it picks up the test environment variable
get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def isolate_and_cleanup_test_artifacts():
    """Ensure test screenshots and artifacts are strictly confined to .test_artifacts and cleaned up."""
    test_art_path = (Path(__file__).parent.parent / "artifacts" / ".test_artifacts").resolve()
    test_art_path.mkdir(parents=True, exist_ok=True)
    yield
    # Teardown: Clean up test artifacts directory after all tests complete
    if test_art_path.exists() and ".test_artifacts" in str(test_art_path):
        shutil.rmtree(test_art_path, ignore_errors=True)


@pytest.fixture(autouse=True)
def reset_synthetic_app_state():
    """Ensure clean synthetic state for every single test."""
    synthetic_state.reset()
    yield
    synthetic_state.reset()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Settings instance configured for testing."""
    return Settings(
        environment="test",
        host="127.0.0.1",
        port=8199,
        browser_headless=True,
        browser_timeout_ms=10_000,
        artifacts_dir=TEST_ARTIFACTS_DIR,
    )


@pytest_asyncio.fixture
async def async_client(test_settings: Settings) -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to FastAPI test app."""
    app = create_app(test_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8199") as client:
        yield client


@pytest_asyncio.fixture
async def browser_mgr(test_settings: Settings) -> AsyncIterator[BrowserManager]:
    """Isolated BrowserManager instance with guaranteed teardown after each test."""
    mgr = BrowserManager(test_settings)
    yield mgr
    await mgr.close_all()


@pytest.fixture(scope="session")
def scenarios_html_path() -> Path:
    """Absolute path to the synthetic scenarios HTML page."""
    path = STATIC_DIR / "scenarios.html"
    assert path.exists(), f"scenarios.html missing at {path}"
    return path


@pytest.fixture(scope="session")
def scenarios_file_url(scenarios_html_path: Path) -> str:
    """File URI for navigating Playwright directly to the synthetic scenarios surface."""
    return scenarios_html_path.as_uri()
