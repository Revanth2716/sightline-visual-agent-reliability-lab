"""Visual and structural observation capture component."""

from __future__ import annotations

import time
import uuid
from typing import List, Optional

from playwright.async_api import Page

from sightline.config import Settings, get_settings
from sightline.observation.artifacts import ArtifactManager, default_artifact_manager
from sightline.observation.models import (
    BoundingBox,
    ObservationResult,
    ObservationStatus,
    ObservedTarget,
)


class VisualObserver:
    """Captures viewport screenshots and extracts actionable interactive target candidates.

    Architecture Note:
    DOM-assisted candidate extraction is combined with Playwright viewport bounding-box
    measurement. This is honestly recorded as 'dom_assisted_bounding_box' evidence and
    does NOT pretend to be an autonomous computer-vision model.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        artifact_manager: Optional[ArtifactManager] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.artifact_manager = artifact_manager or (
            default_artifact_manager
            if self.settings.artifacts_dir == default_artifact_manager.settings.artifacts_dir
            else ArtifactManager(self.settings)
        )

    async def observe(self, page: Page, run_id: Optional[str] = None) -> ObservationResult:
        """Capture screenshot and extract candidates from the active page viewport."""
        obs_id = f"obs_{uuid.uuid4().hex[:12]}"
        now = time.time()

        # Viewport dimensions
        vp_size = page.viewport_size or {
            "width": self.settings.browser_viewport_width,
            "height": self.settings.browser_viewport_height,
        }
        vw = vp_size["width"]
        vh = vp_size["height"]

        screenshot_path_str: Optional[str] = None
        screenshot_id: Optional[str] = None
        status = ObservationStatus.COMPLETE
        error_msg: Optional[str] = None

        # 1. Capture viewport screenshot safely into artifacts directory
        try:
            screenshot_target = self.artifact_manager.get_screenshot_path(obs_id)
            await page.screenshot(path=str(screenshot_target), full_page=False)
            screenshot_path_str = self.artifact_manager.to_safe_relative_path(screenshot_target)
            screenshot_id = screenshot_target.stem
        except Exception as exc:
            status = ObservationStatus.DEGRADED
            error_msg = f"Screenshot capture failed: {str(exc)}"

        # 2. Extract interactive candidates via DOM query
        candidates: List[ObservedTarget] = []
        try:
            js_query = """() => {
                const selector = 'button, input, select, textarea, a[href], [role="button"], [role="checkbox"], [role="dialog"], [tabindex="0"]';
                const elements = Array.from(document.querySelectorAll(selector));
                return elements.map((el, idx) => {
                    const style = window.getComputedStyle(el);
                    const isVisible = (
                        style.display !== 'none' &&
                        style.visibility !== 'hidden' &&
                        parseFloat(style.opacity || '1') > 0 &&
                        el.offsetWidth > 0 &&
                        el.offsetHeight > 0
                    );
                    const isDisabled = (
                        el.disabled === true ||
                        el.getAttribute('aria-disabled') === 'true' ||
                        el.classList.contains('disabled')
                    );
                    
                    let role = el.getAttribute('role') || el.tagName.toLowerCase();
                    if (el.tagName.toLowerCase() === 'input') {
                        const type = (el.getAttribute('type') || 'text').toLowerCase();
                        if (type === 'checkbox') role = 'checkbox';
                        else if (type === 'submit') role = 'button';
                        else role = 'textbox';
                    }

                    // Build minimal stable selector
                    let sel = '';
                    if (el.id) {
                        sel = '#' + CSS.escape(el.id);
                    } else if (el.name) {
                        sel = el.tagName.toLowerCase() + '[name="' + CSS.escape(el.name) + '"]';
                    } else if (el.getAttribute('data-action')) {
                        sel = el.tagName.toLowerCase() + '[data-action="' + CSS.escape(el.getAttribute('data-action')) + '"]';
                    } else {
                        sel = el.tagName.toLowerCase() + ':nth-of-type(' + (idx + 1) + ')';
                    }

                    return {
                        index: idx,
                        id: el.id || '',
                        selector: sel,
                        tagName: el.tagName.toLowerCase(),
                        role: role,
                        text: (el.innerText || el.textContent || '').trim(),
                        placeholder: el.getAttribute('placeholder') || null,
                        value: el.value || null,
                        ariaLabel: el.getAttribute('aria-label') || null,
                        domVisible: isVisible,
                        domDisabled: isDisabled
                    };
                });
            }"""

            raw_elements = await page.evaluate(js_query)

            for item in raw_elements:
                sel = item["selector"]
                # Resolve exact viewport bounding box using Playwright locator
                try:
                    locator = page.locator(sel).first
                    box = await locator.bounding_box()
                except Exception:
                    continue

                if not box:
                    # Element has no layout or is detached
                    continue

                width = float(box["width"])
                height = float(box["height"])

                # Reject non-positive dimensions
                if width <= 0 or height <= 0:
                    continue

                x = float(box["x"])
                y = float(box["y"])

                try:
                    bbox = BoundingBox(x=x, y=y, width=width, height=height)
                except ValueError:
                    continue

                in_viewport = bbox.is_within_viewport(vw, vh)
                dom_visible = item["domVisible"]
                dom_disabled = item["domDisabled"]

                # Exclude hidden, detached, disabled, or out-of-viewport elements from actionable candidates
                is_actionable = dom_visible and (not dom_disabled) and in_viewport

                if not is_actionable:
                    # Prompt requirement: Exclude hidden, detached, disabled, or non-interactive elements from actionable candidates
                    continue

                target_id = item["id"] if item["id"] else f"target_{item['index']}"

                candidates.append(
                    ObservedTarget(
                        target_id=target_id,
                        selector=sel,
                        tag_name=item["tagName"],
                        role=item["role"],
                        text=item["text"],
                        placeholder=item["placeholder"],
                        value=item["value"],
                        aria_label=item["ariaLabel"],
                        bounding_box=bbox,
                        is_visible=dom_visible,
                        is_enabled=not dom_disabled,
                        is_actionable=True,
                        evidence_source="dom_assisted_bounding_box",
                    )
                )

        except Exception as exc:
            status = ObservationStatus.FAILED if status == ObservationStatus.DEGRADED else ObservationStatus.DEGRADED
            error_msg = f"{error_msg}; Element extraction error: {str(exc)}" if error_msg else f"Element extraction error: {str(exc)}"

        return ObservationResult(
            observation_id=obs_id,
            timestamp=now,
            viewport_width=vw,
            viewport_height=vh,
            screenshot_path=screenshot_path_str,
            screenshot_id=screenshot_id,
            candidates=candidates,
            status=status,
            error_message=error_msg,
        )


# Default visual observer instance
default_visual_observer = VisualObserver()
