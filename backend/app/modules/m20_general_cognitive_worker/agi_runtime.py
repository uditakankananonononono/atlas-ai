"""Measured autonomy primitives for Atlas's General Cognitive Worker.

This module does not label the system AGI. It implements properties that can
be tested: a persistent evidence-backed world model, self-directed *proposal*
of goals (activation remains authority-gated), synthesis and adversarial
admission of narrowly sandboxed tools, and benchmark-bound improvement with
immutable baselines and rollback.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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
    """Tenant-scoped beliefs, evidence and tamper-evident snapshots.

    Conflicting values coexist as hypotheses. Confidence is recomputed from
    source reliability and evidence weight, so updating the model never erases
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
        if not 0 <= reliability <= 1 or weight <= 0:
            raise ValueError("reliability must be [0,1] and weight positive")
        at, eid = observed_at or _now(), str(uuid4())
        payload = {"tenant": self.tenant_id, "subject": subject, "predicate": predicate,
                   "value": value, "source": source, "reliability": reliability,
                   "weight": weight, "observed_at": at}
        with self._db() as db:
            db.execute("INSERT INTO world_evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (eid, self.tenant_id, subject, predicate, json.dumps(value, sort_keys=True),
                        source, reliability, weight, at, _hash(payload)))
        return eid

    def hypotheses(self, subject: str, predicate: str) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT value_json,source,reliability,weight,observed_at,content_hash "
                              "FROM world_evidence WHERE tenant=? AND subject=? AND predicate=?",
                              (self.tenant_id, subject, predicate)).fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for value_json, source, reliability, weight, at, digest in rows:
            item = grouped.setdefault(value_json, {"value": json.loads(value_json), "support": 0.0,
                                                   "sources": [], "latest_at": at, "evidence_hashes": []})
            item["support"] += reliability * weight
            item["sources"].append(source); item["evidence_hashes"].append(digest)
            item["latest_at"] = max(item["latest_at"], at)
        total = sum(x["support"] for x in grouped.values())
        result = []
        for item in grouped.values():
            item["confidence"] = round(item["support"] / total, 6) if total else 0.0
            item["sources"] = sorted(set(item["sources"]))
            result.append(item)
        return sorted(result, key=lambda x: (-x["confidence"], json.dumps(x["value"], sort_keys=True)))

    def state(self) -> dict[str, Any]:
        with self._db() as db:
            keys = db.execute("SELECT DISTINCT subject,predicate FROM world_evidence WHERE tenant=? ORDER BY 1,2",
                              (self.tenant_id,)).fetchall()
        return {f"{s}.{p}": self.hypotheses(s, p) for s, p in keys}

    def snapshot(self) -> dict[str, str]:
        state, created, sid = self.state(), _now(), str(uuid4())
        with self._db() as db:
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


@dataclass
class GoalProposal:
    id: str
    objective: str
    rationale: str
    evidence: list[str]
    expected_value: float
    risk: Risk
    status: str = "proposed"
    approval_id: str | None = None


class AutonomousGoalEngine:
    """Generates useful candidate goals but cannot silently gain authority."""

    def __init__(self, approval_gate: ApprovalGate) -> None:
        self.approvals, self.proposals = approval_gate, {}

    def propose_from_gaps(self, world: PersistentWorldModel, *, mission: str,
                          max_goals: int = 5) -> list[GoalProposal]:
        if not mission.strip():
            raise ValueError("mission is required")
        candidates = []
        for key, hypotheses in world.state().items():
            confidence = hypotheses[0]["confidence"] if hypotheses else 0.0
            if len(hypotheses) > 1 or confidence < .8:
                candidates.append((confidence, key, hypotheses))
        goals = []
        for confidence, key, hypotheses in sorted(candidates)[:max_goals]:
            goal = GoalProposal(str(uuid4()), f"Resolve uncertainty about {key}",
                                f"Supports mission: {mission}; current confidence {confidence:.2f}",
                                [h for x in hypotheses for h in x["evidence_hashes"]],
                                round(1 - confidence, 6), Risk.READ)
            self.proposals[goal.id] = goal; goals.append(goal)
        return goals

    def request_activation(self, proposal_id: str) -> str:
        goal = self.proposals[proposal_id]
        request = ApprovalGateRequest(action_type="activate_autonomous_goal", risk=Risk.EXTERNAL,
                                      summary=goal.objective, payload={"proposal_id": goal.id,
                                      "objective": goal.objective, "evidence": goal.evidence})
        goal.approval_id = self.approvals.request(request)
        goal.status = "waiting_approval"
        return goal.approval_id

    def activate(self, proposal_id: str, approval_id: str) -> GoalProposal:
        goal = self.proposals[proposal_id]
        if goal.approval_id != approval_id or self.approvals.decision(approval_id) != ApprovalGateDecision.APPROVED:
            raise PermissionError("exact goal activation approval is required")
        goal.status = "active"
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
    """Admits generated pure functions only after static and executable tests."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry, self.proposals = registry, {}

    def propose(self, tool: SynthesizedTool) -> SynthesizedTool:
        tree = ast.parse(tool.source)
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        if len(functions) != 1 or functions[0].name != "run":
            raise ValueError("tool source must define exactly one run(arguments) function")
        for node in ast.walk(tree):
            if type(node) not in _ALLOWED_NODES:
                raise ValueError(f"forbidden syntax: {type(node).__name__}")
            if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_CALLS):
                raise ValueError("only allowlisted pure builtins may be called")
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise ValueError("dunder access is forbidden")
        tool.source_hash = hashlib.sha256(tool.source.encode()).hexdigest()
        self.proposals[tool.name] = tool
        return tool

    def test(self, name: str) -> dict[str, Any]:
        tool = self.proposals[name]
        env = {"__builtins__": {x: getattr(__builtins__, x) if not isinstance(__builtins__, dict)
                                else __builtins__[x] for x in _ALLOWED_CALLS}}
        exec(compile(ast.parse(tool.source), f"<synthesized:{name}>", "exec"), env)
        failures = []
        for i, case in enumerate(tool.cases):
            try:
                actual = env["run"](case["input"])
                if actual != case["expected"]:
                    failures.append({"case": i, "expected": case["expected"], "actual": actual})
            except Exception as exc:
                failures.append({"case": i, "error": f"{type(exc).__name__}: {exc}"})
        tool.test_report = {"total": len(tool.cases), "passed": len(tool.cases)-len(failures), "failures": failures}
        tool.status = "tested" if not failures and tool.cases else "rejected"
        return tool.test_report

    def admit(self, name: str, *, approved: bool) -> SynthesizedTool:
        tool = self.proposals[name]
        if not approved or tool.status != "tested":
            raise PermissionError("tested tool and explicit admission approval are required")
        env = {"__builtins__": {x: getattr(__builtins__, x) if not isinstance(__builtins__, dict)
                                else __builtins__[x] for x in _ALLOWED_CALLS}}
        exec(compile(ast.parse(tool.source), f"<synthesized:{name}>", "exec"), env)
        run = env["run"]
        async def handler(arguments):
            return run(arguments)
        self.registry.register(ToolSpec(name=tool.name, description=tool.description,
                                       parameters=tool.parameters, risk=Risk.READ,
                                       capabilities=["synthesized", "pure_transform"]), handler)
        tool.status = "admitted"
        return tool


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
    """Evaluates candidates against immutable baselines before approval/apply."""

    def __init__(self) -> None:
        self.history: dict[str, list[ImmutableBaseline]] = {}
        self.candidates: dict[str, dict[str, Any]] = {}

    def establish(self, name: str, content: str, evaluator: Callable[[str], float]) -> ImmutableBaseline:
        if name in self.history:
            raise ValueError("baseline already exists")
        baseline = self._version(name, content, evaluator(content), "GENESIS", 1)
        self.history[name] = [baseline]
        return baseline

    def evaluate(self, name: str, candidate: str, evaluator: Callable[[str], float], *, min_gain: float = 0.0) -> dict[str, Any]:
        baseline = self.history[name][-1]
        score = evaluator(candidate)
        report = {"id": str(uuid4()), "name": name, "candidate": candidate,
                  "candidate_hash": hashlib.sha256(candidate.encode()).hexdigest(),
                  "baseline_hash": baseline.content_hash, "baseline_score": baseline.benchmark_score,
                  "candidate_score": score, "gain": score-baseline.benchmark_score,
                  "passed": score-baseline.benchmark_score >= min_gain}
        self.candidates[report["id"]] = report
        return report

    def apply(self, candidate_id: str, *, approved: bool) -> ImmutableBaseline:
        report = self.candidates[candidate_id]
        current = self.history[report["name"]][-1]
        if not approved or not report["passed"] or current.content_hash != report["baseline_hash"]:
            raise PermissionError("approved, passing candidate against current baseline required")
        version = self._version(report["name"], report["candidate"], report["candidate_score"],
                                current.content_hash, current.version+1)
        self.history[report["name"]].append(version)
        return version

    def rollback(self, name: str, version: int, *, approved: bool) -> ImmutableBaseline:
        if not approved:
            raise PermissionError("rollback approval required")
        target = next(v for v in self.history[name] if v.version == version)
        current = self.history[name][-1]
        restored = self._version(name, target.content, target.benchmark_score,
                                 current.content_hash, current.version+1)
        self.history[name].append(restored)
        return restored

    @staticmethod
    def _version(name: str, content: str, score: float, parent: str, version: int) -> ImmutableBaseline:
        return ImmutableBaseline(name, version, content, score, hashlib.sha256(content.encode()).hexdigest(), parent, _now())
