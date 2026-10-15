"""Visual observation subsystem for Sightline."""

from sightline.observation.artifacts import ArtifactManager, default_artifact_manager
from sightline.observation.models import (
    BoundingBox,
    ObservationResult,
    ObservationStatus,
    ObservedTarget,
)
from sightline.observation.observer import VisualObserver, default_visual_observer

__all__ = [
    "ArtifactManager",
    "BoundingBox",
    "ObservationResult",
    "ObservationStatus",
    "ObservedTarget",
    "VisualObserver",
    "default_artifact_manager",
    "default_visual_observer",
]
