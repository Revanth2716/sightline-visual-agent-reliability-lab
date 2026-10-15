"""Artifact manager ensuring screenshots and evidence files are strictly confined to the project artifact directory."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Optional

from sightline.config import Settings, get_settings


class ArtifactManager:
    """Manages screenshot and evidence files in a dedicated, bounded project directory."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.base_dir: Path = self.settings.resolved_artifacts_dir
        self.screenshots_dir: Path = self.base_dir / "screenshots"
        self.benchmarks_dir: Path = self.base_dir / "benchmarks"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary artifact directory structures."""
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.benchmarks_dir.mkdir(parents=True, exist_ok=True)

    def get_screenshot_path(self, observation_id: str) -> Path:
        """Generate safe, sanitized absolute Path for an observation screenshot."""
        # Sanitize observation_id to alphanumeric and underscore
        safe_id = "".join(c for c in observation_id if c.isalnum() or c in ("-", "_"))
        target_path = (self.screenshots_dir / f"{safe_id}.png").resolve()
        
        # Verify no directory traversal
        if not str(target_path).startswith(str(self.base_dir.resolve())):
            raise ValueError(f"Path traversal detected: {target_path} is outside {self.base_dir}")
        return target_path

    def get_benchmark_report_path(self, run_id: str) -> Path:
        """Generate safe, sanitized absolute Path for a benchmark JSON report."""
        safe_id = "".join(c for c in run_id if c.isalnum() or c in ("-", "_"))
        target_path = (self.benchmarks_dir / f"{safe_id}.json").resolve()
        if not str(target_path).startswith(str(self.base_dir.resolve())):
            raise ValueError(f"Path traversal detected: {target_path} is outside {self.base_dir}")
        return target_path

    def to_safe_relative_path(self, absolute_path: Path | str) -> str:
        """Convert an absolute path to a project-relative or artifact-relative path string.
        
        Prevents leaking the user's host filesystem structure (e.g. /workspace/projects/...).
        """
        p = Path(absolute_path).resolve()
        project_root = Path(__file__).parent.parent.parent.resolve()
        try:
            rel = p.relative_to(project_root)
            return str(rel).replace("\\", "/")
        except ValueError:
            # Fallback if outside project root (should not occur)
            return p.name

    def validate_file_in_artifacts(self, file_path: Path | str) -> bool:
        """Check whether a given file path is strictly inside the artifacts directory."""
        try:
            resolved = Path(file_path).resolve()
            return str(resolved).startswith(str(self.base_dir.resolve()))
        except Exception:
            return False

    @property
    def is_test_artifacts(self) -> bool:
        """Indicates whether this manager is targeting an isolated test artifacts area."""
        resolved = str(self.base_dir.resolve()).replace("\\", "/")
        norm_dir = self.settings.artifacts_dir.strip("/\\")
        if norm_dir == "artifacts":
            return False
        return (
            ".test_artifacts" in resolved
            or "test_artifacts" in resolved
            or "pytest" in resolved
            or "tmp" in resolved
        )

    def cleanup_artifacts(
        self,
        older_than_seconds: Optional[int] = None,
        force_non_test: bool = False,
    ) -> int:
        """Clean up generated screenshots.

        Safety Invariant: By default, cleanup is strictly confined to isolated test artifact
        directories to prevent accidental deletion of historical evaluation screenshots.
        """
        if not self.is_test_artifacts and not force_non_test:
            # Refuse to clean production artifacts to protect historical benchmark evidence
            return 0

        count = 0
        now = time.time()
        if self.screenshots_dir.exists():
            for f in self.screenshots_dir.glob("*.png"):
                if older_than_seconds is None or (now - f.stat().st_mtime) > older_than_seconds:
                    try:
                        f.unlink()
                        count += 1
                    except Exception:
                        pass
        return count


# Singleton instance
default_artifact_manager = ArtifactManager()
