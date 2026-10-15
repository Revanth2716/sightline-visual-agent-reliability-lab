"""Data models for visual observations and candidate target extraction."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator


class BoundingBox(BaseModel):
    """Viewport-relative 2D bounding box with strict dimension validation."""

    x: float = Field(description="Top-left X coordinate in viewport pixels")
    y: float = Field(description="Top-left Y coordinate in viewport pixels")
    width: float = Field(description="Box width in pixels")
    height: float = Field(description="Box height in pixels")

    @field_validator("width", "height")
    @classmethod
    def validate_positive_dimension(cls, v: float, info) -> float:
        if v <= 0:
            raise ValueError(f"Bounding box {info.field_name} must be strictly positive (> 0), got {v}")
        return v

    def is_within_viewport(self, viewport_width: int, viewport_height: int) -> bool:
        """Return True if the bounding box is completely enclosed within viewport boundaries."""
        if self.x < 0 or self.y < 0:
            return False
        if (self.x + self.width) > viewport_width:
            return False
        if (self.y + self.height) > viewport_height:
            return False
        return True

    @property
    def center(self) -> Tuple[float, float]:
        """Compute center coordinates (x, y) for precise click targeting."""
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)


class ObservedTarget(BaseModel):
    """An interactive element identified during an observation pass.

    Architecture Note:
    Evidence source is recorded honestly. Sightline Phase 2 employs DOM-assisted
    candidate extraction combined with Playwright viewport bounding-box measurement
    and screenshot capture, not an autonomous computer-vision model.
    """

    target_id: str = Field(description="Stable identifier for target in this observation pass")
    selector: str = Field(description="Unique DOM selector or locator hint")
    tag_name: str = Field(description="HTML tag name: button, input, select, etc.")
    role: str = Field(default="generic", description="Semantic role: button, textbox, checkbox, etc.")
    text: str = Field(default="", description="Visible text content")
    placeholder: Optional[str] = Field(default=None, description="Input placeholder text if present")
    value: Optional[str] = Field(default=None, description="Current input value or selected state")
    aria_label: Optional[str] = Field(default=None, description="Accessible label if defined")
    bounding_box: BoundingBox = Field(description="Viewport-relative bounding box")
    is_visible: bool = Field(default=True, description="Whether element is visibly rendered")
    is_enabled: bool = Field(default=True, description="Whether element is enabled (not disabled)")
    is_actionable: bool = Field(default=True, description="Eligible for agent interaction")
    evidence_source: str = Field(
        default="dom_assisted_bounding_box",
        description="Source of candidate identification (honestly distinguished from raw pixel vision)",
    )


class ObservationStatus(str, Enum):
    """Observation capture quality status."""

    COMPLETE = "complete"
    DEGRADED = "degraded"
    FAILED = "failed"


class ObservationResult(BaseModel):
    """Structured capture of page visual and structural state."""

    observation_id: str = Field(description="Unique observation identifier")
    timestamp: float = Field(description="Unix epoch timestamp of observation")
    viewport_width: int = Field(description="Viewport width in pixels")
    viewport_height: int = Field(description="Viewport height in pixels")
    screenshot_path: Optional[str] = Field(
        default=None,
        description="Project-relative path to saved viewport screenshot PNG",
    )
    screenshot_id: Optional[str] = Field(default=None, description="Unique artifact identifier for screenshot")
    candidates: List[ObservedTarget] = Field(
        default_factory=list,
        description="Actionable candidate interactive targets visible in viewport",
    )
    status: ObservationStatus = Field(
        default=ObservationStatus.COMPLETE,
        description="Whether capture succeeded completely or in degraded state",
    )
    error_message: Optional[str] = Field(default=None, description="Error details if degraded or failed")

    def get_actionable_candidates(self) -> List[ObservedTarget]:
        """Return strictly actionable candidates."""
        return [c for c in self.candidates if c.is_actionable]

    def find_target_by_id(self, target_id: str) -> Optional[ObservedTarget]:
        """Lookup target by its assigned observation target_id."""
        for c in self.candidates:
            if c.target_id == target_id:
                return c
        return None
