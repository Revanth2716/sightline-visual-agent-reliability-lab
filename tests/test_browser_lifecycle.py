"""Tests for Playwright browser lifecycle manager, isolated contexts, and resource teardown."""

from __future__ import annotations

import pytest

from sightline.browser.manager import BrowserManager
from sightline.config import Settings


@pytest.mark.asyncio
async def test_browser_lazy_start(test_settings: Settings):
    """Verify browser is not started until explicitly invoked."""
    mgr = BrowserManager(test_settings)
    assert mgr.is_running is False

    try:
        browser = await mgr.start()
        assert mgr.is_running is True
        assert browser.is_connected() is True
    finally:
        await mgr.close_all()
    assert mgr.is_running is False


@pytest.mark.asyncio
async def test_isolated_contexts_isolation(test_settings: Settings):
    """Verify separate contexts maintain isolated storage states."""
    mgr = BrowserManager(test_settings)
    try:
        ctx1 = await mgr.create_isolated_context(session_id="session_1")
        ctx2 = await mgr.create_isolated_context(session_id="session_2")
        assert ctx1 != ctx2

        # Add a cookie in ctx1
        await ctx1.add_cookies([{"name": "token", "value": "secret123", "domain": "localhost", "path": "/"}])
        cookies_1 = await ctx1.cookies()
        cookies_2 = await ctx2.cookies()

        assert any(c["name"] == "token" for c in cookies_1)
        assert not any(c["name"] == "token" for c in cookies_2)
    finally:
        await mgr.close_all()


@pytest.mark.asyncio
async def test_session_context_manager_cleanup_on_success(test_settings: Settings):
    """Verify session() yields working page and closes both page and context on normal exit."""
    mgr = BrowserManager(test_settings)
    page_ref = None
    try:
        async with mgr.session() as page:
            page_ref = page
            assert not page.is_closed()
            await page.goto("data:text/html,<title>Clean Test</title><h1>Success</h1>")
            title = await page.title()
            assert title == "Clean Test"

        # After exiting context manager, page must be closed
        assert page_ref.is_closed()
    finally:
        await mgr.close_all()


@pytest.mark.asyncio
async def test_session_context_manager_cleanup_on_exception(test_settings: Settings):
    """Verify session() ensures resource teardown even when an unhandled exception is raised."""
    mgr = BrowserManager(test_settings)
    page_ref = None

    with pytest.raises(RuntimeError, match="Intentional test failure"):
        async with mgr.session() as page:
            page_ref = page
            await page.goto("data:text/html,<h1>Error Handled</h1>")
            raise RuntimeError("Intentional test failure")

    # Page and context must still be closed
    assert page_ref is not None
    assert page_ref.is_closed()
    await mgr.close_all()
    assert mgr.is_running is False
