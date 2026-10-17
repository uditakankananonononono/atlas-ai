"""Typed M14 errors. Pure module, no third-party imports."""
from __future__ import annotations


class ProjectRevisionConflict(RuntimeError):
    """Stored project revision differs from the revision the caller read."""


class ArtifactIdConflict(RuntimeError):
    """An artifact with this id already exists for the project."""


class PlannerOutputInvalid(ValueError):
    """Upstream planner output was not valid JSON or did not build a ProjectPlan.

    The message is fixed on purpose: planner text and validation details are never echoed.
    """

    def __init__(self) -> None:
        super().__init__("planner output invalid")
