"""Playwright browser lifecycle manager with isolated sessions and guaranteed cleanup."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from sightline.config import Settings, get_settings


class BrowserManager:
    """Manages Playwright Chromium lifecycle, providing isolated execution contexts

    and robust teardown guarantees on Windows and Linux.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: Dict[str, BrowserContext] = {}
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        """Return True if browser is currently active."""
        return self._browser is not None and self._browser.is_connected()

    async def start(self) -> Browser:
        """Initialize Playwright and launch Chromium singleton if not already started."""
        async with self._lock:
            if self._browser and self._browser.is_connected():
                return self._browser

            if not self._playwright:
                self._playwright = await async_playwright().start()

            launch_kwargs = {
                "headless": self.settings.browser_headless,
                "args": [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            }

            # Use detected local Chromium binary if available to avoid re-downloads
            if self.settings.chromium_executable_path:
                launch_kwargs["executable_path"] = self.settings.chromium_executable_path

            self._browser = await self._playwright.chromium.launch(**launch_kwargs)
            return self._browser

    async def create_isolated_context(
        self, session_id: Optional[str] = None, viewport_width: Optional[int] = None, viewport_height: Optional[int] = None
    ) -> BrowserContext:
        """Create a fresh, isolated BrowserContext with private cookies, storage, and cache."""
        browser = await self.start()
        context = await browser.new_context(
            viewport={
                "width": viewport_width or self.settings.browser_viewport_width,
                "height": viewport_height or self.settings.browser_viewport_height,
            },
            ignore_https_errors=True,
        )
        context.set_default_timeout(self.settings.browser_timeout_ms)

        if session_id:
            self._contexts[session_id] = context
        return context

    async def close_context(self, context_or_id: BrowserContext | str) -> None:
        """Safely close an individual browser context."""
        context: Optional[BrowserContext] = None
        if isinstance(context_or_id, str):
            context = self._contexts.pop(context_or_id, None)
        else:
            context = context_or_id
            # Remove from tracking map if present
            for k, v in list(self._contexts.items()):
                if v == context:
                    del self._contexts[k]

        if context:
            try:
                await context.close()
            except Exception:
                pass

    @asynccontextmanager
    async def session(self, session_id: Optional[str] = None) -> AsyncIterator[Page]:
        """Async context manager delivering an isolated Page session with guaranteed teardown.

        Closes page and isolated context upon completion or exception.
        """
        context = await self.create_isolated_context(session_id=session_id)
        page: Optional[Page] = None
        try:
            page = await context.new_page()
            page.set_default_timeout(self.settings.browser_timeout_ms)
            yield page
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            await self.close_context(context)

    async def close_all(self) -> None:
        """Gracefully terminate all active contexts, the browser instance, and Playwright driver."""
        async with self._lock:
            # 1. Close all active contexts
            for ctx in list(self._contexts.values()):
                try:
                    await ctx.close()
                except Exception:
                    pass
            self._contexts.clear()

            # 2. Close browser
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None

            # 3. Stop playwright driver
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None


# Global singleton instance for testing and runtime
default_browser_manager = BrowserManager()
