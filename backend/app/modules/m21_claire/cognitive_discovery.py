"""Evidence-first cognitive discovery primitives for Claire.

This module is deliberately not described as AGI. It implements durable, auditable
research objects: hypotheses, evidence, experiments, verified skills, and value-of-
information prioritisation. It does not crawl websites or execute external actions.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Evidence:
    source: str
    reference: str
    excerpt: str
    observed_at: str
    reliability: float = 0.5

    def validate(self) -> None:
        if not self.source.strip() or not self.reference.strip():
            raise ValueError("Evidence requires source and reference.")
        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError("reliability must be in [0, 1].")
        parsed = datetime.fromisoformat(self.observed_at)
        if parsed.tzinfo is None:
            raise ValueError("observed_at must include a timezone.")
        if len(self.excerpt) > 8000:
            raise ValueError("excerpt exceeds 8000 characters.")


@dataclass(frozen=True)
class Hypothesis:
    id: str
    tenant_id: str
    title: str
    claim: str
    domains: tuple[str, ...]
    status: str
    confidence: float
    evidence: tuple[Evidence, ...]
    created_at: str
    updated_at: str
    version: int = 1

    def validate(self) -> None:
        if not self.tenant_id.strip() or not self.title.strip() or not self.claim.strip():
            raise ValueError("tenant_id, title and claim are required.")
        if not self.domains or any(not d.strip() for d in self.domains):
            raise ValueError("At least one non-empty domain is required.")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0, 1].")
        if self.status not in {"proposed", "testing", "supported", "rejected", "inconclusive"}:
            raise ValueError("Invalid hypothesis status.")
        for item in self.evidence:
            item.validate()


@dataclass(frozen=True)
class Experiment:
    id: str
    hypothesis_id: str
    tenant_id: str
    question: str
    protocol: dict[str, Any]
    expected_observation: str
    status: str
    outcome: dict[str, Any] | None
    created_at: str
    completed_at: str | None = None


@dataclass(frozen=True)
class Skill:
    id: str
    tenant_id: str
    name: str
    description: str
    procedure: dict[str, Any]
    preconditions: list[str]
    known_failures: list[str]
    tests: list[dict[str, Any]]
    status: str
    score: float | None
    version: int
    created_at: str
    updated_at: str


class DiscoveryStore:
    """SQLite-backed, tenant-scoped storage with optimistic version checks.

    Set CLAIRE_DISCOVERY_DB to a durable path in production. SQLite is suitable for
    local development/single-node deployment; use a PostgreSQL adapter for multi-node
    production. The store never interprets evidence text as executable instructions.
    """
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._lock = threading.RLock()
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS hypotheses (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, body TEXT NOT NULL,
                version INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_hypotheses_tenant
                ON hypotheses(tenant_id, updated_at);
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                hypothesis_id TEXT NOT NULL, body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(hypothesis_id) REFERENCES hypotheses(id)
            );
            CREATE INDEX IF NOT EXISTS ix_experiments_tenant
                ON experiments(tenant_id, created_at);
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL,
                body TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_skills_tenant ON skills(tenant_id, name);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL,
                kind TEXT NOT NULL, object_id TEXT NOT NULL, body TEXT NOT NULL,
                created_at TEXT NOT NULL, previous_hash TEXT, event_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_events_tenant
                ON events(tenant_id, id);
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    def _event(self, db, tenant_id: str, kind: str, object_id: str, body: Any) -> None:
        previous = db.execute(
            "SELECT event_hash FROM events WHERE tenant_id=? ORDER BY id DESC LIMIT 1",
            (tenant_id,),
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else None
        event_body = {
            "tenant_id": tenant_id, "kind": kind, "object_id": object_id,
            "body": body, "created_at": utc_now(), "previous_hash": previous_hash,
        }
        event_hash = canonical_hash(event_body)
        db.execute(
            "INSERT INTO events(tenant_id,kind,object_id,body,created_at,previous_hash,event_hash) "
            "VALUES(?,?,?,?,?,?,?)",
            (tenant_id, kind, object_id, self._json(body), event_body["created_at"],
             previous_hash, event_hash),
        )

    def create_hypothesis(self, tenant_id: str, title: str, claim: str,
                          domains: Iterable[str], evidence: Iterable[Evidence] = (),
                          confidence: float = 0.25) -> dict[str, Any]:
        now = utc_now()
        h = Hypothesis(
            id=str(uuid4()), tenant_id=tenant_id, title=title, claim=claim,
            domains=tuple(dict.fromkeys(d.strip() for d in domains if d.strip())),
            status="proposed", confidence=confidence, evidence=tuple(evidence),
            created_at=now, updated_at=now,
        )
        h.validate()
        body = asdict(h)
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO hypotheses VALUES(?,?,?,?,?,?)",
                       (h.id, tenant_id, self._json(body), h.version, now, now))
            self._event(db, tenant_id, "hypothesis.created", h.id, body)
        return body

    def get_hypothesis(self, tenant_id: str, hypothesis_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT body FROM hypotheses WHERE tenant_id=? AND id=?",
                             (tenant_id, hypothesis_id)).fetchone()
        return json.loads(row["body"]) if row else None

    def list_hypotheses(self, tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be in [1, 200].")
        with self._connect() as db:
            rows = db.execute(
                "SELECT body FROM hypotheses WHERE tenant_id=? ORDER BY updated_at DESC LIMIT ?",
                (tenant_id, limit),
            ).fetchall()
        return [json.loads(row["body"]) for row in rows]

    def add_evidence(self, tenant_id: str, hypothesis_id: str, evidence: Evidence,
                     expected_version: int) -> dict[str, Any]:
        evidence.validate()
        with self._lock, self._connect() as db:
            row = db.execute("SELECT body,version FROM hypotheses WHERE tenant_id=? AND id=?",
                             (tenant_id, hypothesis_id)).fetchone()
            if row is None:
                raise KeyError("hypothesis not found")
            if row["version"] != expected_version:
                raise RuntimeError("version conflict; reload before updating")
            body = json.loads(row["body"])
            body["evidence"].append(asdict(evidence))
            body["confidence"] = self._confidence(body["evidence"])
            body["updated_at"] = utc_now()
            body["version"] += 1
            Hypothesis(**{**body, "domains": tuple(body["domains"]),
                          "evidence": tuple(Evidence(**e) for e in body["evidence"])}).validate()
            db.execute("UPDATE hypotheses SET body=?,version=?,updated_at=? WHERE tenant_id=? AND id=?",
                       (self._json(body), body["version"], body["updated_at"], tenant_id, hypothesis_id))
            self._event(db, tenant_id, "hypothesis.evidence_added", hypothesis_id, asdict(evidence))
        return body

    @staticmethod
    def _confidence(evidence: list[dict[str, Any]]) -> float:
        """Reliability-weighted support score, not a calibrated probability."""
        if not evidence:
            return 0.25
        weights = [max(0.01, float(e["reliability"])) for e in evidence]
        return round(sum(weights) / sum([1.0] * len(weights)), 4)

    def set_hypothesis_status(self, tenant_id: str, hypothesis_id: str,
                              status: str, expected_version: int) -> dict[str, Any]:
        if status not in {"proposed", "testing", "supported", "rejected", "inconclusive"}:
            raise ValueError("Invalid hypothesis status.")
        with self._lock, self._connect() as db:
            row = db.execute("SELECT body,version FROM hypotheses WHERE tenant_id=? AND id=?",
                             (tenant_id, hypothesis_id)).fetchone()
            if row is None:
                raise KeyError("hypothesis not found")
            if row["version"] != expected_version:
                raise RuntimeError("version conflict; reload before updating")
            body = json.loads(row["body"])
            if status == "supported" and not body["evidence"]:
                raise ValueError("Cannot support a hypothesis without evidence.")
            body["status"] = status
            body["updated_at"] = utc_now()
            body["version"] += 1
            db.execute("UPDATE hypotheses SET body=?,version=?,updated_at=? WHERE tenant_id=? AND id=?",
                       (self._json(body), body["version"], body["updated_at"], tenant_id, hypothesis_id))
            self._event(db, tenant_id, "hypothesis.status_changed", hypothesis_id,
                        {"status": status, "version": body["version"]})
        return body

    def create_experiment(self, tenant_id: str, hypothesis_id: str, question: str,
                          protocol: dict[str, Any], expected_observation: str) -> dict[str, Any]:
        h = self.get_hypothesis(tenant_id, hypothesis_id)
        if h is None:
            raise KeyError("hypothesis not found")
        if not question.strip() or not expected_observation.strip():
            raise ValueError("question and expected_observation are required")
        if len(json.dumps(protocol)) > 12000:
            raise ValueError("protocol exceeds 12KB")
        now = utc_now()
        e = Experiment(str(uuid4()), hypothesis_id, tenant_id, question, protocol,
                       expected_observation, "proposed", None, now)
        body = asdict(e)
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO experiments VALUES(?,?,?,?,?)",
                       (e.id, tenant_id, hypothesis_id, self._json(body), now))
            self._event(db, tenant_id, "experiment.created", e.id, body)
        return body

    def record_experiment_outcome(self, tenant_id: str, experiment_id: str,
                                  outcome: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT body FROM experiments WHERE tenant_id=? AND id=?",
                             (tenant_id, experiment_id)).fetchone()
            if row is None:
                raise KeyError("experiment not found")
            body = json.loads(row["body"])
            if body["status"] != "proposed":
                raise ValueError("Only proposed experiments can receive an outcome.")
            if len(json.dumps(outcome)) > 16000:
                raise ValueError("outcome exceeds 16KB")
            body["outcome"] = outcome
            body["status"] = "completed"
            body["completed_at"] = utc_now()
            db.execute("UPDATE experiments SET body=? WHERE tenant_id=? AND id=?",
                       (self._json(body), tenant_id, experiment_id))
            self._event(db, tenant_id, "experiment.completed", experiment_id, outcome)
        return body

    def list_experiments(self, tenant_id: str, hypothesis_id: str | None = None,
                         limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 300:
            raise ValueError("limit must be in [1, 300].")
        with self._connect() as db:
            if hypothesis_id:
                rows = db.execute(
                    "SELECT body FROM experiments WHERE tenant_id=? AND hypothesis_id=? "
                    "ORDER BY created_at DESC LIMIT ?", (tenant_id, hypothesis_id, limit)
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT body FROM experiments WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",
                    (tenant_id, limit),
                ).fetchall()
        return [json.loads(r["body"]) for r in rows]

    def register_skill(self, tenant_id: str, name: str, description: str,
                       procedure: dict[str, Any], preconditions: list[str],
                       known_failures: list[str], tests: list[dict[str, Any]]) -> dict[str, Any]:
        if not name.strip() or not description.strip():
            raise ValueError("name and description are required")
        if not tests:
            raise ValueError("At least one executable acceptance test is required.")
        if len(json.dumps(procedure)) > 20000:
            raise ValueError("procedure exceeds 20KB")
        now = utc_now()
        skill = Skill(str(uuid4()), tenant_id, name, description, procedure, preconditions,
                      known_failures, tests, "unverified", None, 1, now, now)
        body = asdict(skill)
        with self._lock, self._connect() as db:
            old = db.execute("SELECT id,version FROM skills WHERE tenant_id=? AND name=?",
                             (tenant_id, name)).fetchone()
            if old:
                # Keep the stored row id: the SQL key, the body and the returned id must agree.
                body["id"] = old["id"]
                body["version"] = old["version"] + 1
                skill = Skill(**body)
                body = asdict(skill)
                db.execute("UPDATE skills SET body=?,version=?,updated_at=? WHERE tenant_id=? AND name=?",
                           (self._json(body), body["version"], now, tenant_id, name))
            else:
                db.execute("INSERT INTO skills VALUES(?,?,?,?,?,?)",
                           (skill.id, tenant_id, name, self._json(body), skill.version, now))
            self._event(db, tenant_id, "skill.registered", body["id"], body)
        return body

    def evaluate_skill(self, tenant_id: str, skill_id: str,
                       runner: Callable[[dict[str, Any], dict[str, Any]], Any]) -> dict[str, Any]:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT body FROM skills WHERE tenant_id=? AND id=?",
                             (tenant_id, skill_id)).fetchone()
            if row is None:
                raise KeyError("skill not found")
            body = json.loads(row["body"])
        passed = 0
        results = []
        for test in body["tests"]:
            try:
                actual = runner(body["procedure"], test["input"])
                ok = actual == test["expected"]
                results.append({"passed": ok, "actual_hash": canonical_hash(actual),
                                "expected_hash": canonical_hash(test["expected"])})
                passed += int(ok)
            except Exception as exc:
                results.append({"passed": False, "error_type": type(exc).__name__})
        score = passed / len(body["tests"])
        status = "verified" if score == 1.0 else ("partially_verified" if score > 0 else "rejected")
        body["score"], body["status"], body["updated_at"] = score, status, utc_now()
        with self._lock, self._connect() as db:
            db.execute("UPDATE skills SET body=?,updated_at=? WHERE tenant_id=? AND id=?",
                       (self._json(body), body["updated_at"], tenant_id, skill_id))
            self._event(db, tenant_id, "skill.evaluated", skill_id,
                        {"score": score, "status": status, "results": results})
        return {"skill": body, "results": results}

    def list_skills(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 300:
            raise ValueError("limit must be in [1, 300].")
        with self._connect() as db:
            rows = db.execute("SELECT body FROM skills WHERE tenant_id=? ORDER BY updated_at DESC LIMIT ?",
                              (tenant_id, limit)).fetchall()
        return [json.loads(r["body"]) for r in rows]

    def audit_chain(self, tenant_id: str) -> dict[str, Any]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM events WHERE tenant_id=? ORDER BY id", (tenant_id,)).fetchall()
        previous = None
        for row in rows:
            body = json.loads(row["body"])
            event = {"tenant_id": tenant_id, "kind": row["kind"], "object_id": row["object_id"],
                     "body": body, "created_at": row["created_at"], "previous_hash": row["previous_hash"]}
            if row["previous_hash"] != previous or canonical_hash(event) != row["event_hash"]:
                return {"valid": False, "checked": row["id"], "reason": "hash_chain_mismatch"}
            previous = row["event_hash"]
        return {"valid": True, "checked": len(rows), "head": previous}


def information_value(*, decision_impact: float, uncertainty: float,
                      expected_reduction: float, generality: float, cost: float,
                      risk: float = 0.0) -> float:
    """Transparent prioritisation heuristic, not a learned probability.

    Inputs are normalised to [0,1]; cost is a relative cost score. High-risk
    experiments are deprioritised, not automatically approved.
    """
    vals = [decision_impact, uncertainty, expected_reduction, generality, cost, risk]
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in vals):
        raise ValueError("all inputs must be finite values in [0, 1]")
    benefit = decision_impact * uncertainty * expected_reduction * generality
    return round(benefit * (1 - 0.75 * risk) / (0.05 + cost), 6)


def propose_counterfactuals(observations: list[dict[str, Any]], *,
                            max_candidates: int = 12) -> list[dict[str, Any]]:
    """Create explicit candidate questions from structured observations.

    This does not claim causal discovery. Candidates are prompts for an experiment,
    and must be tested against an appropriate baseline before being accepted.
    """
    if not 1 <= max_candidates <= 50:
        raise ValueError("max_candidates must be in [1, 50]")
    candidates = []
    seen = set()
    for obs in observations:
        domain = str(obs.get("domain", "")).strip()
        outcome = str(obs.get("outcome", "")).strip()
        factor = str(obs.get("factor", "")).strip()
        context = str(obs.get("context", "")).strip()
        if not all((domain, outcome, factor)):
            continue
        question = f"In {domain}, would changing '{factor}' alter '{outcome}' in context '{context}'?"
        key = canonical_hash(question)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "id": str(uuid4()), "domain": domain, "question": question,
            "baseline": obs.get("baseline"), "intervention": obs.get("intervention"),
            "confounders_to_check": list(obs.get("possible_confounders", []))[:20],
            "status": "unvalidated_hypothesis", "requires_human_or_domain_validation": True,
        })
        if len(candidates) >= max_candidates:
            break
    return candidates


def cross_domain_transfer_report(cases: list[dict[str, Any]],
                                 runner: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
    """Evaluate a candidate method on labeled held-out cases across domains."""
    if not cases:
        raise ValueError("cases cannot be empty")
    ids = [str(c.get("id", "")) for c in cases]
    if any(not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("each case needs a unique non-empty id")
    domains = {str(c.get("domain", "")).strip() for c in cases}
    if "" in domains:
        raise ValueError("each case needs a domain")
    results = []
    for case in cases:
        try:
            actual = runner(case["input"])
            passed = actual == case["expected"]
            results.append({"id": case["id"], "domain": case["domain"], "passed": passed,
                            "actual_hash": canonical_hash(actual)})
        except Exception as exc:
            results.append({"id": case["id"], "domain": case["domain"], "passed": False,
                            "error_type": type(exc).__name__})
    by_domain = {}
    for domain in sorted(domains):
        subset = [r for r in results if r["domain"] == domain]
        by_domain[domain] = {"passed": sum(r["passed"] for r in subset),
                             "total": len(subset), "accuracy": sum(r["passed"] for r in subset)/len(subset)}
    total = len(results)
    return {
        "case_count": total, "domain_count": len(domains),
        "accuracy": sum(r["passed"] for r in results) / total,
        "worst_domain_accuracy": min(v["accuracy"] for v in by_domain.values()),
        "by_domain": by_domain, "results": results,
        "interpretation": "Finite benchmark only; does not establish general intelligence or causal validity.",
    }
