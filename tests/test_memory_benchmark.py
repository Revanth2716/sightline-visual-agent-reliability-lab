"""Memory assertion test verifying reproducible resource constraints and process teardown."""

from __future__ import annotations

import json
from pathlib import Path
import pytest


def test_reproduced_memory_measurements():
    """Verify that measured memory across all 3 trials remains strictly within hardware limits

    and confirms complete process teardown (zero lingering Chromium processes).
    """
    json_path = Path(__file__).parent / "memory_measurement_results.json"
    assert json_path.exists(), "Memory measurement results JSON must exist from reproducible trials"

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(data) >= 3, "At least 3 comparable trials must be recorded"

    for trial in data:
        # 1. Zero process leaks
        assert trial["LingeringChromiumProcesses"] == 0, f"Trial {trial['Trial']} leaked Chromium processes!"

        # 2. Python root process lightweight footprint
        assert trial["PythonPeakWS_MB"] < 50.0, f"Python process exceeded 50 MB: {trial['PythonPeakWS_MB']} MB"

        # 3. Chromium private bytes footprint
        assert trial["ChromiumPeakPriv_MB"] < 250.0, f"Chromium private bytes exceeded 250 MB: {trial['ChromiumPeakPriv_MB']} MB"

        # 4. Total process tree working set within 8 GB laptop limits (< 800 MB)
        assert trial["TreePeakWS_MB"] < 800.0, f"Total process tree exceeded 800 MB limit: {trial['TreePeakWS_MB']} MB"
