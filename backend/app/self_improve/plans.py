"""Shared dataclasses for the self-improvement pipeline."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

CAPABILITY_KINDS = (
    "keyword_filter", "scoring_rule", "text_transform",
    "aggregator", "threshold_alert", "field_extractor",
)


@dataclass(frozen=True)
class FeaturePlan:
    module_slug: str
    name: str
    kind: str
    description: str
    gap_signature: str
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in CAPABILITY_KINDS:
            raise ValueError(f"unknown capability kind {self.kind!r}")
        if not self.name.replace("_", "").isalnum() or not self.name.islower():
            raise ValueError(f"feature name must be snake_case, got {self.name!r}")


@dataclass(frozen=True)
class Candidate:
    plan: FeaturePlan
    code: str
    test_code: str
    created_at: float = field(default_factory=time.time)

    @property
    def key(self) -> str:
        return hashlib.sha256(self.code.encode()).hexdigest()[:16]

    @property
    def code_sha256(self) -> str:
        return hashlib.sha256(self.code.encode()).hexdigest()

    @property
    def test_sha256(self) -> str:
        return hashlib.sha256(self.test_code.encode()).hexdigest()
