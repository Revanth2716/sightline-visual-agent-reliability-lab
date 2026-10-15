"""Sightline — Visual Agent Reliability Lab.

A local-first, deterministic foundation for measuring the reliability of AI agents
interacting with web interfaces.
"""

__version__ = "0.1.0"
__author__ = "Sightline Engineering Team"

from sightline.config import Settings, get_settings
from sightline.scenarios.catalog import SCENARIOS

__all__ = ["__version__", "Settings", "get_settings", "SCENARIOS"]
