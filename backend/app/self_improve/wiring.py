"""Wire the self-improvement engine into every Atlas module.

attach_all() builds one engine per catalog module (M00-M25), sharing a
state root. Each module then detects its own gaps, builds its own features,
tests them, and queues them for human-approved activation.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from app.modules.catalog import MODULES

from .engine import SelfImprovementEngine
from .gate import ApprovalGate, ManualApprovalGate

DEFAULT_STATE_ENV = "ATLAS_SELF_IMPROVE_HOME"


def default_state_dir() -> Path:
    return Path(os.environ.get(DEFAULT_STATE_ENV, Path.home() / ".atlas" / "self_improve"))


_engines: dict[str, SelfImprovementEngine] = {}


def attach_all(*, state_dir: Path | str | None = None,
               gate_factory: Callable[[str], ApprovalGate] | None = None,
               min_occurrences: int = 2) -> dict[str, SelfImprovementEngine]:
    root = Path(state_dir) if state_dir else default_state_dir()
    engines: dict[str, SelfImprovementEngine] = {}
    for module in MODULES:
        gate = gate_factory(module.slug) if gate_factory else ManualApprovalGate(
            root / "approvals" / f"{module.slug}.json")
        engines[module.slug] = SelfImprovementEngine(
            module_id=module.id, module_slug=module.slug, state_dir=root,
            gate=gate, min_occurrences=min_occurrences)
    return engines


def engine_for(slug: str, *, state_dir: Path | str | None = None) -> SelfImprovementEngine:
    """Process-wide lazy engine accessor for a module slug."""
    global _engines
    if not _engines or state_dir is not None:
        _engines = attach_all(state_dir=state_dir)
    if slug not in _engines:
        raise KeyError(f"unknown module slug {slug!r}")
    return _engines[slug]


def reset_engines() -> None:
    global _engines
    _engines = {}
