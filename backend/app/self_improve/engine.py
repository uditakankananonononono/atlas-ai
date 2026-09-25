"""The per-module self-improvement engine.

Autonomous loop: record gaps -> detect recurring ones -> plan a feature ->
synthesize real code and tests -> sandbox-test it -> request human approval
-> (on approval) activate into the module's own feature registry. Every
stage is recorded to an append-only ledger.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from .codegen import synthesize_code
from .detector import CapabilityGap, GapDetector
from .events import GapEvent, GapEventStore
from .gate import APPROVED, ApprovalGate, ManualApprovalGate
from .plans import Candidate, FeaturePlan
from .planner import FeaturePlanner
from .registry import FeatureRegistry
from .sandbox import SandboxResult, SandboxRunner
from .testsynth import synthesize_tests

_KIND_SAMPLES: dict[str, list] = {
    "keyword_filter": ["grant for phd students in biology", "unrelated notice",
                       {"title": "grant deadline"}, None, 42],
    "scoring_rule": ["grant for phd students in biology", "totally unrelated",
                     {"title": "grant"}, "grant grant grant"],
    "text_transform": ["hello   world", "many\t\n spaces   here", "", "untouched"],
    "aggregator": [{"category": "a", "value": 1}, {"category": "a", "value": 2},
                   {"category": "b", "value": 5}, "not a dict"],
    "threshold_alert": [{"value": 10}, {"value": -3}, {"value": "not-a-number"}, "junk"],
    "field_extractor": ["contact me at prof@uni.edu on 2026-09-25, score 91.5",
                        "no fields here", None, 7],
}


class SelfImprovementEngine:
    def __init__(self, *, module_id: int, module_slug: str, state_dir: Path | str,
                 gate: ApprovalGate | None = None, sandbox: SandboxRunner | None = None,
                 planner: FeaturePlanner | None = None, min_occurrences: int = 2) -> None:
        self.module_id = module_id
        self.module_slug = module_slug
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.store = GapEventStore(self.state_dir / "gap-events")
        self.detector = GapDetector(self.store, min_occurrences=min_occurrences)
        self.planner = planner or FeaturePlanner()
        self.sandbox = sandbox or SandboxRunner()
        self.registry = FeatureRegistry(module_slug, self.state_dir)
        self.gate: ApprovalGate = gate or ManualApprovalGate(self.state_dir / "approvals.json")
        self._ledger_path = self.state_dir / "ledger.jsonl"
        self._ledger_lock = threading.Lock()
        self._candidates: dict[str, Candidate] = {}

    # -- ledger --------------------------------------------------------------
    def _log(self, event: str, **fields: Any) -> None:
        record = {"at": time.time(), "module": self.module_slug, "event": event, **fields}
        with self._ledger_lock:
            with self._ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True, default=str) + "\n")

    def ledger(self) -> list[dict[str, Any]]:
        if not self._ledger_path.exists():
            return []
        with self._ledger_lock:
            lines = self._ledger_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(l) for l in lines if l.strip()]

    # -- pipeline stages -------------------------------------------------------
    def record_gap(self, signature: str, *, kind: str = "capability_miss",
                   detail: str = "", exemplar: Any = None) -> GapEvent:
        event = GapEvent(module_slug=self.module_slug, signature=signature,
                         kind=kind, detail=detail, exemplar=exemplar)
        self.store.append(event)
        self._log("gap_event_recorded", signature=signature, kind=kind)
        return event

    def detect_gaps(self) -> list[CapabilityGap]:
        gaps = [g for g in self.detector.detect(self.module_slug)
                if not self.registry.covers_gap(g.signature)]
        for gap in gaps:
            self._log("gap_detected", signature=gap.signature,
                      occurrences=gap.occurrences, severity=gap.severity)
        return gaps

    def plan_gap(self, gap: CapabilityGap) -> FeaturePlan:
        plan = self.planner.plan(gap)
        self._log("feature_planned", name=plan.name, kind=plan.kind,
                  gap_signature=gap.signature)
        return plan

    def synthesize(self, plan: FeaturePlan) -> Candidate:
        code = synthesize_code(plan)
        sample = _KIND_SAMPLES[plan.kind]
        # Fold gap exemplars into the sample so tests exercise the real miss.
        for exemplar in self._exemplars_for(plan.gap_signature):
            sample = sample + [exemplar]
        test_code = synthesize_tests(plan, sample)
        candidate = Candidate(plan=plan, code=code, test_code=test_code)
        self._candidates[candidate.key] = candidate
        self._log("feature_synthesized", key=candidate.key, name=plan.name,
                  code_sha256=candidate.code_sha256)
        return candidate

    def _exemplars_for(self, signature: str) -> list:
        return [e.exemplar for e in self.store.all(self.module_slug)
                if e.signature == signature and e.exemplar is not None][:5]

    def evaluate(self, candidate_key: str) -> SandboxResult:
        candidate = self._candidates[candidate_key]
        result = self.sandbox.run(candidate)
        self._log("feature_evaluated", key=candidate_key, passed=result.passed,
                  exit_code=result.exit_code, timed_out=result.timed_out,
                  duration=result.duration_seconds)
        if not result.passed:
            self._log("feature_rejected_by_tests", key=candidate_key,
                      tail=result.stdout[-500:])
        return result

    def propose(self, candidate_key: str) -> str:
        candidate = self._candidates[candidate_key]
        self.registry.save_proposal(
            candidate_key, name=candidate.plan.name, kind=candidate.plan.kind,
            code=candidate.code, test_code=candidate.test_code,
            gap_signature=candidate.plan.gap_signature)
        approval_id = self.gate.request(
            module_id=self.module_id, module_slug=self.module_slug,
            action_type="self_improvement_activation",
            summary=f"Activate self-built feature {candidate.plan.name} "
                    f"({candidate.plan.kind}) on module {self.module_slug}",
            payload={"candidate_key": candidate_key, "name": candidate.plan.name,
                     "kind": candidate.plan.kind, "code_sha256": candidate.code_sha256,
                     "gap_signature": candidate.plan.gap_signature})
        self.registry.set_proposal_approval(candidate_key, approval_id)
        self._log("activation_proposed", key=candidate_key, approval_id=approval_id)
        return approval_id

    def activate(self, candidate_key: str, *, approval_id: str) -> dict[str, Any]:
        proposal = self.registry.get_proposal(candidate_key)
        if proposal.get("approval_id") != approval_id:
            raise PermissionError("approval id does not match this candidate's proposal")
        decision = self.gate.decision(approval_id)
        if decision != APPROVED:
            raise PermissionError(
                f"activation requires an approved gate decision, got {decision!r}")
        entry = self.registry.activate(candidate_key, approval_id=approval_id)
        self._log("feature_activated", key=candidate_key, name=entry["file"],
                  version=entry["version"], approval_id=approval_id)
        return entry

    def rollback(self, feature_name: str, *, approval_id: str) -> dict[str, Any]:
        decision = self.gate.decision(approval_id)
        if decision != APPROVED:
            raise PermissionError(
                f"rollback requires an approved gate decision, got {decision!r}")
        outcome = self.registry.rollback(feature_name, approval_id=approval_id)
        self._log("feature_rolled_back", **outcome)
        return outcome

    def request_rollback(self, feature_name: str) -> str:
        approval_id = self.gate.request(
            module_id=self.module_id, module_slug=self.module_slug,
            action_type="self_improvement_rollback",
            summary=f"Roll back self-built feature {feature_name} on {self.module_slug}",
            payload={"feature": feature_name})
        self._log("rollback_proposed", feature=feature_name, approval_id=approval_id)
        return approval_id

    def dispatch(self, feature_name: str, items: list, params: dict | None = None) -> dict:
        result = self.registry.dispatch(feature_name, items, params)
        self._log("feature_dispatched", feature=feature_name, item_count=len(items))
        return result

    # -- the autonomous loop ---------------------------------------------------
    def run_cycle(self, *, max_new: int = 1) -> dict[str, Any]:
        """One autonomous improvement cycle, up to the human approval gate."""
        report: dict[str, Any] = {"module": self.module_slug, "gaps": [],
                                  "candidates": [], "proposals": [], "failed": []}
        gaps = self.detect_gaps()
        report["gaps"] = [{"signature": g.signature, "occurrences": g.occurrences,
                           "severity": g.severity} for g in gaps]
        for gap in gaps[:max_new]:
            plan = self.plan_gap(gap)
            candidate = self.synthesize(plan)
            result = self.evaluate(candidate.key)
            entry = {"key": candidate.key, "name": plan.name, "kind": plan.kind,
                     "tests_passed": result.passed}
            report["candidates"].append(entry)
            if result.passed:
                approval_id = self.propose(candidate.key)
                report["proposals"].append({"key": candidate.key, "name": plan.name,
                                            "approval_id": approval_id})
            else:
                report["failed"].append(entry)
        self._log("cycle_completed", gaps=len(gaps),
                  proposed=len(report["proposals"]), failed=len(report["failed"]))
        return report

    def status(self) -> dict[str, Any]:
        return {
            "module": self.module_slug,
            "gap_events": len(self.store.all(self.module_slug)),
            "open_gaps": [g.signature for g in self.detect_gaps()],
            "features": self.registry.features(),
            "proposals": self.registry.proposals(),
            "ledger_events": len(self.ledger()),
        }
