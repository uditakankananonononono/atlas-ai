"""Atlas module self-improvement engine.

Each module can detect its own capability gaps, synthesize a new feature as
real tested code, and integrate it - with activation gated on human approval
through Module 0 (or a manual gate offline). Free-first: no model or network
required; an optional ProposalRefiner can plug in a local model later.
"""
from .detector import CapabilityGap, GapDetector
from .engine import SelfImprovementEngine
from .events import GapEvent, GapEventStore
from .gate import ManualApprovalGate, M00ApprovalGate
from .mixin import SelfImprovingMixin
from .plans import CAPABILITY_KINDS, Candidate, FeaturePlan
from .planner import FeaturePlanner, NullRefiner
from .registry import FeatureRegistry, RegistryError
from .sandbox import SandboxResult, SandboxRunner
from .safety import SafetyViolation, validate_source
from .wiring import attach_all, engine_for

__all__ = [
    "CapabilityGap", "GapDetector", "SelfImprovementEngine", "GapEvent",
    "GapEventStore", "ManualApprovalGate", "M00ApprovalGate",
    "SelfImprovingMixin", "CAPABILITY_KINDS", "Candidate", "FeaturePlan",
    "FeaturePlanner", "NullRefiner", "FeatureRegistry", "RegistryError",
    "SandboxResult", "SandboxRunner", "SafetyViolation", "validate_source",
    "attach_all", "engine_for",
]
