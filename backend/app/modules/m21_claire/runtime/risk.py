from __future__ import annotations
from app.modules.m21_claire.models import RiskLevel
from .types import ToolRisk

# Single place that maps a runtime tool's REGISTERED risk to a Claire review level.
_MAP = {ToolRisk.READ: RiskLevel.LOW, ToolRisk.WRITE: RiskLevel.MEDIUM, ToolRisk.EXECUTE: RiskLevel.HIGH}
_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}


def claire_risk(registered: ToolRisk) -> RiskLevel:
    """Fail closed: anything that is not exactly a known ToolRisk is HIGH."""
    return _MAP.get(registered, RiskLevel.HIGH) if isinstance(registered, ToolRisk) else RiskLevel.HIGH


def effective_risk(registered: ToolRisk, *claimed: object) -> RiskLevel:
    """Risk used for review. Names, tags or labels supplied by the model (`claimed`) are accepted
    only if they RAISE the level; a lower or unknown claim never reduces the registered level."""
    level = claire_risk(registered)
    for c in claimed:
        try:
            other = RiskLevel(c.value if isinstance(c, (RiskLevel, ToolRisk)) else str(c).lower())
        except ValueError:
            try:
                other = _MAP[ToolRisk(str(c).lower())]
            except ValueError:
                continue  # unknown claim: ignored, never lowers
        if _ORDER[other] > _ORDER[level]:
            level = other
    return level
