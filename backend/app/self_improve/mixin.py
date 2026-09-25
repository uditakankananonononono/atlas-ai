"""Mixin that gives any module service self-improvement capability."""
from __future__ import annotations

from typing import Any

from .engine import SelfImprovementEngine


class SelfImprovingMixin:
    """Attach to a module service to make it self-improving.

    The service can report its own capability gaps, run improvement cycles,
    and dispatch its activated self-built features. Activation still passes
    through the human approval gate - the mixin only automates the work up
    to that boundary.
    """

    self_improve_engine: SelfImprovementEngine | None = None

    def attach_self_improvement(self, engine: SelfImprovementEngine) -> None:
        self.self_improve_engine = engine

    def _require_engine(self) -> SelfImprovementEngine:
        if self.self_improve_engine is None:
            raise RuntimeError(
                "self-improvement engine not attached; call attach_self_improvement first")
        return self.self_improve_engine

    def report_capability_gap(self, signature: str, *, kind: str = "capability_miss",
                              detail: str = "", exemplar: Any = None) -> None:
        self._require_engine().record_gap(signature, kind=kind, detail=detail,
                                          exemplar=exemplar)

    def self_improve(self, *, max_new: int = 1) -> dict[str, Any]:
        return self._require_engine().run_cycle(max_new=max_new)

    def dispatch_self_feature(self, feature_name: str, items: list,
                              params: dict | None = None) -> dict:
        return self._require_engine().dispatch(feature_name, items, params)

    def self_improvement_status(self) -> dict[str, Any]:
        return self._require_engine().status()
