"""Deterministic target grounder with strict ambiguity rejection."""

from __future__ import annotations

from typing import List, Optional

from sightline.grounding.models import (
    GroundingMatchStatus,
    GroundingRequest,
    GroundingResult,
)
from sightline.observation.models import ObservationResult, ObservationStatus, ObservedTarget


class DeterministicGrounder:
    """Deterministically maps goal requests to candidate UI elements within an observation.

    Architecture Invariants:
    - Zero fuzzy-guessing: Prevents catastrophic clicks on similar controls (e.g. Save vs Discard).
    - Returns AMBIGUOUS whenever multiple candidates satisfy the query criteria.
    - Rejects targets out of viewport bounds or lacking valid bounding boxes.
    - Does NOT use non-deterministic external LLMs for grounding.
    """

    def ground(self, observation: ObservationResult, request: GroundingRequest) -> GroundingResult:
        """Resolve a requested target against visible candidates in an observation pass."""
        if observation.status == ObservationStatus.FAILED:
            return GroundingResult(
                status=GroundingMatchStatus.NO_MATCH,
                error_message="Cannot ground target: Observation pass failed.",
            )

        candidates = observation.candidates
        if not candidates:
            return GroundingResult(
                status=GroundingMatchStatus.NO_MATCH,
                error_message="No interactive candidates available in observation.",
            )

        # 1. Direct explicit target_id lookup if provided
        if request.target_id:
            matched = [c for c in candidates if c.target_id == request.target_id]
            if len(matched) == 1:
                target = matched[0]
                if not target.bounding_box.is_within_viewport(
                    observation.viewport_width, observation.viewport_height
                ):
                    return GroundingResult(
                        status=GroundingMatchStatus.OUT_OF_BOUNDS,
                        matched_target=target,
                        candidate_count=1,
                        error_message=f"Target '{target.target_id}' lies outside current viewport.",
                    )
                return GroundingResult(
                    status=GroundingMatchStatus.MATCH_UNIQUE,
                    matched_target=target,
                    confidence=1.0,
                    matching_evidence=[f"Direct target_id exact match: '{target.target_id}'"],
                    candidate_count=1,
                )
            elif len(matched) > 1:
                return GroundingResult(
                    status=GroundingMatchStatus.AMBIGUOUS,
                    ambiguous_candidates=matched,
                    candidate_count=len(matched),
                    error_message=f"Multiple candidates share target_id '{request.target_id}'.",
                )
            else:
                return GroundingResult(
                    status=GroundingMatchStatus.NO_MATCH,
                    error_message=f"Explicit target_id '{request.target_id}' not found in observation.",
                )

        # Filter by role if requested
        eligible = candidates
        if request.role:
            req_role = request.role.lower().strip()
            eligible = [c for c in eligible if c.role.lower() == req_role or c.tag_name.lower() == req_role]
            if not eligible:
                return GroundingResult(
                    status=GroundingMatchStatus.NO_MATCH,
                    candidate_count=0,
                    error_message=f"No candidates match role '{request.role}'.",
                )

        q = request.query.strip().lower()

        # 2. Check exact selector or ID matches
        exact_id_matches = [
            c
            for c in eligible
            if c.target_id.lower() == q
            or c.selector.lower() == q
            or c.selector.lower() == f"#{q}"
        ]
        if len(exact_id_matches) == 1:
            target = exact_id_matches[0]
            if not target.bounding_box.is_within_viewport(
                observation.viewport_width, observation.viewport_height
            ):
                return GroundingResult(
                    status=GroundingMatchStatus.OUT_OF_BOUNDS,
                    matched_target=target,
                    candidate_count=1,
                    error_message=f"Target '{target.target_id}' lies outside current viewport.",
                )
            return GroundingResult(
                status=GroundingMatchStatus.MATCH_UNIQUE,
                matched_target=target,
                confidence=1.0,
                matching_evidence=[f"Exact ID / selector match: '{target.selector}'"],
                candidate_count=1,
            )
        elif len(exact_id_matches) > 1:
            return GroundingResult(
                status=GroundingMatchStatus.AMBIGUOUS,
                ambiguous_candidates=exact_id_matches,
                candidate_count=len(exact_id_matches),
                error_message=f"Multiple candidates matched selector/ID query '{request.query}'.",
            )

        # 3. Check exact visible text / label / placeholder matches
        exact_label_matches: List[ObservedTarget] = []
        for c in eligible:
            text = c.text.strip().lower()
            aria = (c.aria_label or "").strip().lower()
            ph = (c.placeholder or "").strip().lower()
            val = (c.value or "").strip().lower()
            if q in (text, aria, ph, val):
                exact_label_matches.append(c)

        if len(exact_label_matches) == 1:
            target = exact_label_matches[0]
            if not target.bounding_box.is_within_viewport(
                observation.viewport_width, observation.viewport_height
            ):
                return GroundingResult(
                    status=GroundingMatchStatus.OUT_OF_BOUNDS,
                    matched_target=target,
                    candidate_count=1,
                    error_message=f"Target '{target.target_id}' lies outside current viewport.",
                )
            return GroundingResult(
                status=GroundingMatchStatus.MATCH_UNIQUE,
                matched_target=target,
                confidence=1.0,
                matching_evidence=[
                    f"Exact visible label match on target '{target.target_id}': '{target.text}'"
                ],
                candidate_count=1,
            )
        elif len(exact_label_matches) > 1:
            return GroundingResult(
                status=GroundingMatchStatus.AMBIGUOUS,
                ambiguous_candidates=exact_label_matches,
                candidate_count=len(exact_label_matches),
                error_message=f"Ambiguous target: {len(exact_label_matches)} candidates match exact label '{request.query}'.",
            )

        # 4. Controlled Substring Matching
        # Only evaluate substring if exact matches were empty
        substring_matches: List[ObservedTarget] = []
        for c in eligible:
            text = c.text.strip().lower()
            aria = (c.aria_label or "").strip().lower()
            ph = (c.placeholder or "").strip().lower()
            tid = c.target_id.strip().lower()
            sel = c.selector.strip().lower()
            if q and (q in text or q in aria or q in ph or q in tid or q in sel):
                substring_matches.append(c)

        if len(substring_matches) == 1:
            target = substring_matches[0]
            if not target.bounding_box.is_within_viewport(
                observation.viewport_width, observation.viewport_height
            ):
                return GroundingResult(
                    status=GroundingMatchStatus.OUT_OF_BOUNDS,
                    matched_target=target,
                    candidate_count=1,
                    error_message=f"Target '{target.target_id}' lies outside current viewport.",
                )
            return GroundingResult(
                status=GroundingMatchStatus.MATCH_UNIQUE,
                matched_target=target,
                confidence=0.9,
                matching_evidence=[
                    f"Unique substring match on candidate '{target.target_id}' with text '{target.text}'"
                ],
                candidate_count=1,
            )
        elif len(substring_matches) > 1:
            return GroundingResult(
                status=GroundingMatchStatus.AMBIGUOUS,
                ambiguous_candidates=substring_matches,
                candidate_count=len(substring_matches),
                error_message=f"Ambiguous query '{request.query}': matched {len(substring_matches)} candidates. Refusing to guess.",
            )

        # 5. No matches found
        return GroundingResult(
            status=GroundingMatchStatus.NO_MATCH,
            candidate_count=0,
            error_message=f"No candidate matching '{request.query}' was found in observation.",
        )


# Global deterministic grounder
default_grounder = DeterministicGrounder()
