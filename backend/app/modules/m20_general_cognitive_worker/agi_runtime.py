"""Measured autonomy primitives for Atlas's General Cognitive Worker.

This module does not label the system AGI. It implements properties that can
be tested: a persistent evidence-backed world model, self-directed *proposal*
of goals (activation remains authority-gated), isolated supplied pure-code tests (generation/admission unavailable), and caller-evaluator-bound improvement with
immutable baselines and rollback.
"""
from __future__ import annotations

import ast
import copy
import tempfile
import hashlib
import json
import math
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .safety import ApprovalGate
from .schemas import ApprovalGateDecision, ApprovalGateRequest, Risk, ToolSpec
from .tools import ToolRegistry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class PersistentWorldModel:
    """Tenant-scoped supplied observations and local hash-chain snapshots.

    Chain checks detect unrehashed changes only. Full database rewrite/deletion
    is not detected without an independent anchor; evidence truth is unverified.

    Conflicting values coexist as hypotheses. A supplied support-share is recomputed from
    caller reliability and weight, not predictive confidence, so updating the model never erases
    inconvenient evidence.
    """

    def __init__(self, path: str, tenant_id: str) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self.path, self.tenant_id = path, tenant_id
        with self._db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS world_evidence(
              id TEXT PRIMARY KEY, tenant TEXT NOT NULL, subject TEXT NOT NULL,
              predicate TEXT NOT NULL, value_json TEXT NOT NULL, source TEXT NOT NULL,
              reliability REAL NOT NULL, weight REAL NOT NULL, observed_at TEXT NOT NULL,
              content_hash TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS world_lookup ON world_evidence(tenant,subject,predicate);
            CREATE TABLE IF NOT EXISTS world_snapshots(
              id TEXT PRIMARY KEY, tenant TEXT NOT NULL, created_at TEXT NOT NULL,
              previous_hash TEXT NOT NULL, state_hash TEXT NOT NULL, snapshot_hash TEXT NOT NULL,
              state_json TEXT NOT NULL);
            """)

    def _db(self):
        return sqlite3.connect(self.path)

    def observe(self, *, subject: str, predicate: str, value: Any, source: str,
                reliability: float = 1.0, weight: float = 1.0, observed_at: str | None = None) -> str:
        if not subject.strip() or not predicate.strip() or not source.strip():
            raise ValueError("subject, predicate and source are required")
        if isinstance(reliability,bool) or isinstance(weight,bool) or not isinstance(reliability,(int,float)) or not isinstance(weight,(int,float)) or not math.isfinite(reliability) or not math.isfinite(weight) or not 0 <= reliability <= 1 or weight <= 0:
            raise ValueError("reliability must be [0,1] and weight positive")
        at, eid = observed_at or _now(), str(uuid4())
        payload = {"tenant": self.tenant_id, "subject": subject, "predicate": predicate,
                   "value": value, "source": source, "reliability": reliability,
                   "weight": weight, "observed_at": at}
        with self._db() as db:
            db.execute("INSERT INTO world_evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (eid, self.tenant_id, subject, predicate, json.dumps(value, sort_keys=True, allow_nan=False),
                        source, reliability, weight, at, _hash(payload)))
        return eid

    def hypotheses(self, subject: str, predicate: str) -> list[dict[str, Any]]:
        with self._db() as db:
            return self._hypotheses(db, subject, predicate)

    def _hypotheses(self, db, subject, predicate):
        rows = db.execute("SELECT value_json,source,reliability,weight,observed_at,content_hash "
                          "FROM world_evidence WHERE tenant=? AND subject=? AND predicate=?",
                          (self.tenant_id, subject, predicate)).fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        scale = max((weight for _,_,_,weight,_,_ in rows), default=1.0)
        for value_json, source, reliability, weight, at, digest in rows:
            item = grouped.setdefault(value_json, {"value": json.loads(value_json), "support": 0.0,
                                                   "sources": [], "latest_at": at, "evidence_hashes": []})
            item["support"] += reliability * (weight / scale)
            item["sources"].append(source); item["evidence_hashes"].append(digest)
            item["latest_at"] = max(item["latest_at"], at)
        total = sum(x["support"] for x in grouped.values())
        result = []
        for item in grouped.values():
            item["supplied_support_share"] = round(item["support"] / total, 6) if total else 0.0
            raw_support = item["support"] * scale
            item["support"] = raw_support if math.isfinite(raw_support) else None
            item["support_status"] = "supplied_weight_sum" if item["support"] is not None else "sum_exceeds_float_range"
            item["sources"] = sorted(set(item["sources"]))
            item["status"]="supplied_weight_rollup_only";item["evidence_verified"]=False;item["predictive_confidence_available"]=False
            result.append(item)
        return sorted(result, key=lambda x: (-x["supplied_support_share"], json.dumps(x["value"], sort_keys=True)))

    def _state(self, db):
        keys = db.execute("SELECT DISTINCT subject,predicate FROM world_evidence WHERE tenant=? ORDER BY 1,2",
                          (self.tenant_id,)).fetchall()
        return {json.dumps([s, p], ensure_ascii=False, separators=(",", ":")): self._hypotheses(db, s, p)
                for s, p in keys}

    def state(self) -> dict[str, Any]:
        with self._db() as db:
            db.execute("BEGIN")
            return self._state(db)

    def snapshot(self) -> dict[str, str]:
        created, sid = _now(), str(uuid4())
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._state(db)
            prior = db.execute("SELECT snapshot_hash FROM world_snapshots WHERE tenant=? ORDER BY rowid DESC LIMIT 1",
                               (self.tenant_id,)).fetchone()
            previous_hash = prior[0] if prior else "GENESIS"
            state_hash = _hash(state)
            snapshot_hash = _hash({"tenant": self.tenant_id, "created_at": created,
                                   "previous_hash": previous_hash, "state_hash": state_hash})
            db.execute("INSERT INTO world_snapshots VALUES(?,?,?,?,?,?,?)",
                       (sid, self.tenant_id, created, previous_hash, state_hash, snapshot_hash,
                        json.dumps(state, sort_keys=True)))
        return {"id": sid, "previous_hash": previous_hash, "state_hash": state_hash,
                "snapshot_hash": snapshot_hash}

    def verify_chain(self) -> bool:
        with self._db() as db:
            rows = db.execute("SELECT created_at,previous_hash,state_hash,snapshot_hash,state_json "
                              "FROM world_snapshots WHERE tenant=? ORDER BY rowid", (self.tenant_id,)).fetchall()
        try:
            previous = "GENESIS"
            for created, linked, state_hash, snapshot_hash, state_json in rows:
                if linked != previous or _hash(json.loads(state_json)) != state_hash:
                    return False
                expected = _hash({"tenant": self.tenant_id, "created_at": created,
                                  "previous_hash": linked, "state_hash": state_hash})
                if expected != snapshot_hash:
                    return False
                previous = snapshot_hash
            return True
        except (ValueError, TypeError):
            return False


@dataclass
class GoalProposal:
    id: str
    objective: str
    rationale: str
    evidence: list[str]
    heuristic_gap_priority: float
    risk: Risk
    status: str = "proposed"
    approval_id: str | None = None


class AutonomousGoalEngine:
    """Generates useful candidate goals but cannot silently gain authority."""

    def __init__(self, approval_gate: ApprovalGate) -> None:
        self.approvals, self.proposals = approval_gate, {}
        self._reviewed_goals={};self._spent_goal_approvals=set();self._goal_lock=RLock()

    def propose_from_gaps(self, world: PersistentWorldModel, *, mission: str,
                          max_goals: int = 5) -> list[GoalProposal]:
        if not mission.strip():
            raise ValueError("mission is required")
        candidates = []
        for key, hypotheses in world.state().items():
            confidence = hypotheses[0]["supplied_support_share"] if hypotheses else 0.0
            if len(hypotheses) > 1 or confidence < .8:
                candidates.append((confidence, key, hypotheses))
        goals = []
        for confidence, key, hypotheses in sorted(candidates)[:max_goals]:
            goal = GoalProposal(str(uuid4()), f"Resolve uncertainty about {key}",
                                f"Supports mission: {mission}; supplied support share {confidence:.2f}",
                                [h for x in hypotheses for h in x["evidence_hashes"]],
                                round(1 - confidence, 6), Risk.READ)
            self.proposals[goal.id] = goal; goals.append(goal)
        return goals

    @staticmethod
    def _goal_binding(goal):
        return _hash({'id':goal.id,'objective':goal.objective,'rationale':goal.rationale,'evidence':goal.evidence,'heuristic_gap_priority':goal.heuristic_gap_priority,'risk':goal.risk.value})

    def request_activation(self, proposal_id: str) -> str:
        with self._goal_lock:
            goal=self.proposals[proposal_id]
            if goal.status!='proposed':raise PermissionError('goal already reviewed or activated')
            binding=self._goal_binding(goal)
            request=ApprovalGateRequest(action_type='activate_autonomous_goal',risk=Risk.EXTERNAL,summary=goal.objective,payload={'proposal_id':goal.id,'objective':goal.objective,'rationale':goal.rationale,'evidence':list(goal.evidence),'heuristic_gap_priority':goal.heuristic_gap_priority,'goal_risk':goal.risk.value,'goal_hash':binding})
            approval_id=self.approvals.request(request)
            self._reviewed_goals[approval_id]=binding
            goal.approval_id=approval_id;goal.status='waiting_approval'
            return approval_id

    def activate(self, proposal_id: str, approval_id: str) -> GoalProposal:
        with self._goal_lock:
            goal=self.proposals[proposal_id]
            if goal.approval_id!=approval_id or approval_id in self._spent_goal_approvals or self._reviewed_goals.get(approval_id)!=self._goal_binding(goal) or self.approvals.decision(approval_id)!=ApprovalGateDecision.APPROVED:
                raise PermissionError('exact unchanged unspent goal activation approval is required')
            self._spent_goal_approvals.add(approval_id);goal.status='active'
            return goal


_ALLOWED_NODES = {ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Assign, ast.Name,
                  ast.Load, ast.Store, ast.Constant, ast.Dict, ast.List, ast.Tuple, ast.Set, ast.BinOp,
                  ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Compare, ast.Eq, ast.NotEq, ast.Lt,
                  ast.LtE, ast.Gt, ast.GtE, ast.BoolOp, ast.And, ast.Or, ast.If, ast.IfExp, ast.UnaryOp,
                  ast.USub, ast.UAdd, ast.Not, ast.Subscript, ast.Slice, ast.For, ast.ListComp,
                  ast.comprehension, ast.Call, ast.keyword}
_ALLOWED_CALLS = {"len", "min", "max", "sum", "sorted", "round", "abs", "all", "any", "str", "int", "float", "bool"}


@dataclass
class SynthesizedTool:
    name: str
    source: str
    description: str
    parameters: dict[str, Any]
    cases: list[dict[str, Any]]
    source_hash: str = ""
    status: str = "proposed"
    test_report: dict[str, Any] = field(default_factory=dict)


class ToolSynthesisLab:
    """Isolated supplied pure-code tests only. Generation/admission unavailable."""

    def __init__(self, registry: ToolRegistry, approval_gate: ApprovalGate) -> None:
        self.registry, self.approvals, self.proposals = registry, approval_gate, {}
        self.admission_approvals: dict[str, str] = {}
        self._frozen_candidates = {}

    def propose(self, tool: SynthesizedTool) -> SynthesizedTool:
        if len(tool.source) > 16000 or not 1 <= len(tool.cases) <= 20:
            raise ValueError("source/case bound exceeded or no cases")
        frozen = json.dumps(asdict(tool), sort_keys=True, allow_nan=False)
        if len(frozen.encode()) > 64000:
            raise ValueError("candidate JSON exceeds 64KB")
        if any(not isinstance(case,dict) or set(case) != {"input","expected"} or not isinstance(case["input"],dict) for case in tool.cases):
            raise ValueError("cases must have object input and expected JSON value")
        tool = copy.deepcopy(tool)
        tree = ast.parse(tool.source)
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        if len(functions) != 1 or functions[0].name != "run":
            raise ValueError("tool source must define exactly one run(arguments) function")
        args = functions[0].args
        if len(args.args) != 1 or args.args[0].arg != "arguments" or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults:
            raise ValueError("run must take exactly one arguments parameter")
        for node in ast.walk(tree):
            if type(node) not in _ALLOWED_NODES:
                raise ValueError(f"forbidden syntax: {type(node).__name__}")
            if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_CALLS):
                raise ValueError("only allowlisted pure builtins may be called")
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise ValueError("dunder access is forbidden")
        tool.source_hash = hashlib.sha256(tool.source.encode()).hexdigest()
        self.proposals[tool.name] = tool
        self._frozen_candidates[tool.name] = json.dumps(asdict(tool), sort_keys=True, allow_nan=False)
        return copy.deepcopy(tool)

    def test(self, name: str) -> dict[str, Any]:
        from .sandbox import SandboxRunner
        frozen = self._frozen_candidates[name]
        if json.dumps(asdict(self.proposals[name]), sort_keys=True, allow_nan=False) != frozen:
            raise PermissionError("candidate changed after static inspection")
        candidate = json.loads(frozen)
        # This wrapper executes only INSIDE the OS-isolated process. The
        # service never compiles or executes supplied generated source.
        wrapper = "import json\n" + candidate["source"] + "\n"
        wrapper += "cases=json.loads(" + repr(json.dumps(candidate["cases"], allow_nan=False)) + ")\n"
        wrapper += "outputs=[run(case['input']) for case in cases]\n"
        wrapper += "print(json.dumps(outputs, allow_nan=False))\n"
        with tempfile.TemporaryDirectory(prefix="atlas-pure-code-") as root:
            result = SandboxRunner(workspace_root=root, max_output_bytes=64000).run_python(
                "test", wrapper, timeout_seconds=2)
        report = {"status": "isolated_supplied_pure_code_test_only", "passed": False,
                  "source_hash": candidate["source_hash"], "candidate_hash": hashlib.sha256(frozen.encode()).hexdigest(),
                  "case_count": len(candidate["cases"]), "timeout_seconds": 2, "memory_mb": 512,
                  "tool_admission_available": False, "model_generation_verified": False,
                  "returncode": result.returncode, "timed_out": result.timed_out,
                  "duration_seconds": result.duration_seconds}
        if result.returncode == 0 and not result.timed_out:
            try:
                outputs = json.loads(result.stdout)
                expected = [case["expected"] for case in candidate["cases"]]
                report["outputs"] = outputs
                report["passed"] = json.dumps(outputs, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False)
            except (ValueError, KeyError, TypeError):
                report["error"] = "invalid output JSON or test cases"
        return report

    def request_admission(self, name: str) -> str:
        self.proposals[name]
        raise PermissionError('synthesized tool admission unavailable until isolated execution and exact-source review are implemented')

    def admit(self, name: str, *, approval_id: str) -> SynthesizedTool:
        self.proposals[name]
        raise PermissionError('synthesized tool admission unavailable until isolated execution and exact-source review are implemented')


@dataclass(frozen=True)
class ImmutableBaseline:
    name: str
    version: int
    content: str
    benchmark_score: float
    content_hash: str
    parent_hash: str
    created_at: str


class SelfImprovementLab:
    """Caller-evaluator scores, exact-review local versioning. No learned improvement proof."""

    def __init__(self, approval_gate: ApprovalGate) -> None:
        self.approvals = approval_gate
        self.history: dict[str, list[ImmutableBaseline]] = {}
        self.candidates: dict[str, dict[str, Any]] = {}
        self.change_approvals: dict[str, str] = {}
        self._improvement_lock = RLock()
        self._evaluated = {}
        self._reviewed = {}
        self._spent = set()

    def establish(self, name: str, content: str, evaluator: Callable[[str], float]) -> ImmutableBaseline:
        with self._improvement_lock:
            if name in self.history:
                raise ValueError("baseline already exists")
            baseline = self._version(name, content, self._score(evaluator(content)), "GENESIS", 1)
            self.history[name] = [baseline]
            return baseline

    def evaluate(self, name: str, candidate: str, evaluator: Callable[[str], float], *, min_gain: float = 0.0) -> dict[str, Any]:
        with self._improvement_lock:
            baseline = self.history[name][-1]
            score = self._score(evaluator(candidate))
            min_gain = self._score(min_gain)
            report = {"id": str(uuid4()), "name": name, "candidate": candidate,
                      "candidate_hash": hashlib.sha256(candidate.encode()).hexdigest(),
                      "baseline_hash": baseline.content_hash, "baseline_version": baseline.version, "baseline_score": baseline.benchmark_score,
                      "candidate_score": score, "gain": self._score(score-baseline.benchmark_score),
                      "passed": score-baseline.benchmark_score >= min_gain}
            self.candidates[report["id"]] = dict(report)
            self._evaluated[report["id"]] = _hash(report)
            return dict(report)

    def request_apply(self, candidate_id: str) -> str:
        with self._improvement_lock:
            report = self.candidates[candidate_id]
            if not report["passed"] or self._evaluated.get(candidate_id) != _hash(report):
                raise PermissionError("candidate did not pass its benchmark gate")
            request = ApprovalGateRequest(action_type="apply_self_improvement", risk=Risk.EXTERNAL,
                                          summary=f"Apply caller-evaluated candidate to {report['name']}",
                                          payload={k: report[k] for k in ("id", "name", "candidate_hash",
                                                                           "baseline_hash", "baseline_score",
                                                                           "candidate_score", "gain", "baseline_version")})
            approval_id = self.approvals.request(request)
            self.change_approvals[candidate_id] = approval_id
            self._reviewed[approval_id] = _hash(report)
            return approval_id

    def apply(self, candidate_id: str, *, approval_id: str) -> ImmutableBaseline:
        with self._improvement_lock:
            report = self.candidates[candidate_id]
            current = self.history[report["name"]][-1]
            if (self.change_approvals.get(candidate_id) != approval_id or
                    self.approvals.decision(approval_id) != ApprovalGateDecision.APPROVED or
                    approval_id in self._spent or self._reviewed.get(approval_id) != _hash(report) or
                    self._evaluated.get(candidate_id) != _hash(report) or
                    not report["passed"] or current.content_hash != report["baseline_hash"] or
                    current.version != report["baseline_version"]):
                raise PermissionError("approved, passing candidate against current baseline required")
            version = self._version(report["name"], report["candidate"], report["candidate_score"],
                                    current.content_hash, current.version+1)
            self._spent.add(approval_id)
            self.history[report["name"]].append(version)
            return version

    def request_rollback(self, name: str, version: int) -> str:
        with self._improvement_lock:
            target = next(v for v in self.history[name] if v.version == version)
            current = self.history[name][-1]
            request = ApprovalGateRequest(action_type="rollback_self_improvement", risk=Risk.EXTERNAL,
                                          summary=f"Rollback {name} to content from version {version}",
                                          payload={"name": name, "target_version": version,
                                                   "target_hash": target.content_hash,
                                                   "current_hash": current.content_hash, "current_version": current.version})
            approval_id = self.approvals.request(request)
            self.change_approvals[f"rollback:{name}:{version}:{current.content_hash}"] = approval_id
            self._reviewed[approval_id] = _hash({"target":asdict(target), "current":asdict(current)})
            return approval_id

    def rollback(self, name: str, version: int, *, approval_id: str) -> ImmutableBaseline:
        with self._improvement_lock:
            target = next(v for v in self.history[name] if v.version == version)
            current = self.history[name][-1]
            key = f"rollback:{name}:{version}:{current.content_hash}"
            if (self.change_approvals.get(key) != approval_id or
                    self.approvals.decision(approval_id) != ApprovalGateDecision.APPROVED or
                    approval_id in self._spent or
                    self._reviewed.get(approval_id) != _hash({"target":asdict(target), "current":asdict(current)})):
                raise PermissionError("exact rollback approval required")
            current = self.history[name][-1]
            restored = self._version(name, target.content, target.benchmark_score,
                                     current.content_hash, current.version+1)
            self._spent.add(approval_id)
            self.history[name].append(restored)
            return restored

    @staticmethod
    def _score(value):
        if isinstance(value, bool) or not isinstance(value, (float,int)) or not math.isfinite(value):
            raise ValueError("finite numeric evaluator score/minimum gain required")
        return value

    @staticmethod
    def _version(name: str, content: str, score: float, parent: str, version: int) -> ImmutableBaseline:
        return ImmutableBaseline(name, version, content, score, hashlib.sha256(content.encode()).hexdigest(), parent, _now())
