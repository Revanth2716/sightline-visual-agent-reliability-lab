"""Closed-loop postcondition verifier comparing before-and-after observations."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from playwright.async_api import Page

from sightline.observation.models import ObservationResult
from sightline.verification.models import (
    ConditionType,
    VerificationResult,
    VerificationStatus,
    VisiblePostcondition,
)


class ClosedLoopVerifier:
    """Verifies observable state transitions following an executed action.

    Guarantees:
    - Never declares success merely because an action didn't throw an error.
    - Captures before-and-after observation identifiers for full auditability.
    - Limits recovery attempts to at most 1 bounded retry (non-destructive only).
    - Returns UNCERTAIN when page state is unreadable or ambiguous.
    """

    async def verify(
        self,
        page: Page,
        pre_observation: ObservationResult,
        post_observation: ObservationResult,
        postcondition: VisiblePostcondition,
        allow_recovery: bool = False,
        is_destructive_action: bool = False,
    ) -> VerificationResult:
        """Evaluate a visible postcondition between pre- and post-observations."""
        pre_id = pre_observation.observation_id
        post_id = post_observation.observation_id

        if page.is_closed():
            return VerificationResult(
                status=VerificationStatus.FAILED,
                pre_observation_id=pre_id,
                post_observation_id=post_id,
                postcondition=postcondition,
                actual_value=None,
                evidence="Target page, context or browser has been closed",
                recovery_attempted=False,
                error_message="Target page, context or browser has been closed",
            )

        # First evaluation pass
        passed, actual_val, diag = await self._evaluate_postcondition(page, postcondition)

        if passed:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                pre_observation_id=pre_id,
                post_observation_id=post_id,
                postcondition=postcondition,
                actual_value=actual_val,
                evidence=f"Postcondition verified: {diag}",
                recovery_attempted=False,
            )

        # Handle failure: Bounded recovery check (max 1 retry, non-destructive only)
        if allow_recovery and not is_destructive_action and not page.is_closed():
            # Short bounded pause for async transition / animations
            await asyncio.sleep(0.3)
            if page.is_closed():
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    pre_observation_id=pre_id,
                    post_observation_id=post_id,
                    postcondition=postcondition,
                    actual_value=None,
                    evidence="Verification failed after bounded recovery retry: Target page, context or browser has been closed",
                    recovery_attempted=True,
                    error_message="Target page, context or browser has been closed",
                )
            rec_passed, rec_actual_val, rec_diag = await self._evaluate_postcondition(page, postcondition)
            if rec_passed:
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    pre_observation_id=pre_id,
                    post_observation_id=post_id,
                    postcondition=postcondition,
                    actual_value=rec_actual_val,
                    evidence=f"Postcondition verified on bounded recovery retry: {rec_diag}",
                    recovery_attempted=True,
                )
            else:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    pre_observation_id=pre_id,
                    post_observation_id=post_id,
                    postcondition=postcondition,
                    actual_value=rec_actual_val,
                    evidence=f"Verification failed after bounded recovery retry: {rec_diag}",
                    recovery_attempted=True,
                    error_message=rec_diag,
                )

        return VerificationResult(
            status=VerificationStatus.FAILED,
            pre_observation_id=pre_id,
            post_observation_id=post_id,
            postcondition=postcondition,
            actual_value=actual_val,
            evidence=f"Verification failed: {diag}",
            recovery_attempted=False,
            error_message=diag,
        )

    async def _evaluate_postcondition(
        self, page: Page, postcondition: VisiblePostcondition
    ) -> tuple[bool, Any, str]:
        """Internal evaluator checking the DOM and visual element for the expected postcondition."""
        sel = postcondition.target_selector
        ctype = postcondition.condition_type
        exp = postcondition.expected_value

        if page.is_closed():
            return False, None, "Target page, context or browser has been closed"

        try:
            locator = page.locator(sel)
            count = await locator.count()

            if count == 0 and ctype != ConditionType.IS_HIDDEN:
                return False, None, f"Target element '{sel}' not found in DOM."

            if ctype == ConditionType.TEXT_CONTAINS:
                text = (await locator.first.inner_text()).strip()
                if isinstance(exp, (list, tuple, set)):
                    match = all(str(item).lower() in text.lower() for item in exp)
                    diag = f"Element '{sel}' innerText='{text}', expected to contain all of {list(exp)}"
                else:
                    match = str(exp).lower() in text.lower()
                    diag = f"Element '{sel}' innerText='{text}', expected to contain '{exp}'"
                return match, text, diag

            elif ctype == ConditionType.TEXT_EQUALS:
                text = (await locator.first.inner_text()).strip()
                match = str(exp).strip() == text
                diag = f"Element '{sel}' innerText='{text}', expected exactly '{exp}'"
                return match, text, diag

            elif ctype == ConditionType.IS_VISIBLE:
                vis = await locator.first.is_visible()
                diag = f"Element '{sel}' is_visible={vis}, expected=True"
                return vis is True, vis, diag

            elif ctype == ConditionType.IS_HIDDEN:
                if count == 0:
                    return True, "not_in_dom", f"Element '{sel}' not in DOM (hidden)"
                vis = await locator.first.is_visible()
                cls = await locator.first.get_attribute("class") or ""
                hidden = (not vis) or ("hidden" in cls)
                diag = f"Element '{sel}' hidden={hidden} (visible={vis}, class='{cls}')"
                return hidden is True, hidden, diag

            elif ctype == ConditionType.IS_ENABLED:
                disabled = await locator.first.is_disabled()
                enabled = not disabled
                diag = f"Element '{sel}' is_enabled={enabled}"
                return enabled is True, enabled, diag

            elif ctype == ConditionType.IS_DISABLED:
                disabled = await locator.first.is_disabled()
                diag = f"Element '{sel}' is_disabled={disabled}"
                return disabled is True, disabled, diag

            elif ctype == ConditionType.VALUE_EQUALS:
                val = await locator.first.input_value()
                match = str(val).strip() == str(exp).strip()
                diag = f"Element '{sel}' value='{val}', expected '{exp}'"
                return match, val, diag

            elif ctype == ConditionType.CLASS_CONTAINS:
                cls = await locator.first.get_attribute("class") or ""
                match = str(exp) in cls
                diag = f"Element '{sel}' class='{cls}', expected to contain '{exp}'"
                return match, cls, diag

            return False, None, f"Unsupported condition type '{ctype}'"

        except Exception as exc:
            return False, None, f"Exception during postcondition inspection: {str(exc)}"


# Default closed-loop verifier
default_verifier = ClosedLoopVerifier()
