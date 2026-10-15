"""Repeatable workload runner for Sightline memory measurement.

Executes all 5 deterministic scenarios against the synthetic target application.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure sightline package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sightline.browser.manager import BrowserManager
from sightline.config import Settings
from sightline.synthetic.routes import STATIC_DIR


async def run_workload():
    settings = Settings(
        environment="test",
        host="127.0.0.1",
        port=8199,
        browser_headless=True,
        browser_timeout_ms=10_000,
    )
    mgr = BrowserManager(settings)
    scenarios_url = (STATIC_DIR / "scenarios.html").as_uri()

    try:
        async with mgr.session() as page:
            await page.goto(scenarios_url)

            # Scenario 1: Form submission & validation
            await page.click("#btn-submit-form")  # trigger validation
            await page.fill("#input-full-name", "Alice Parker")
            await page.fill("#input-email", "alice.parker@example.com")
            await page.select_option("#select-department", "Engineering")
            await page.select_option("#select-priority", "High")
            await page.click("#btn-submit-form")

            # Scenario 2: Button disambiguation
            await page.click("#btn-action-save")

            # Scenario 3: Modal confirmation workflow
            await page.click("#btn-open-deploy-modal")
            await page.click("#btn-modal-confirm")

            # Scenario 4: Delayed enablement
            await page.check("#checkbox-compliance")
            await page.wait_for_selector("#btn-process-report:not([disabled])", timeout=3000)
            await page.click("#btn-process-report")

            # Scenario 5: Destructive approval
            await page.click("#btn-execute-purge")  # trigger unapproved rejection
            await page.check("#toggle-operator-approval")
            await page.click("#btn-execute-purge")  # execute approved

            # Brief pause to capture settled memory
            await asyncio.sleep(0.5)
    finally:
        await mgr.close_all()


if __name__ == "__main__":
    asyncio.run(run_workload())
