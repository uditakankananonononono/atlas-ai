"""Tenant-authenticated API for Claire's evidence-first discovery workspace."""
from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.context import TenantContext, require_tenant
from .cognitive_discovery import (
    DiscoveryStore, Evidence, cross_domain_transfer_report,
    information_value, propose_counterfactuals,
)

router = APIRouter(prefix="/claire/discovery", tags=["claire-cognitive-discovery"])


@lru_cache(maxsize=1)
def _store() -> DiscoveryStore:
    path = os.getenv("CLAIRE_DISCOVERY_DB", "./data/claire_discovery.sqlite3")
    return DiscoveryStore(Path(path))


def _tenant_store(tenant: TenantContext = Depends(require_tenant)) -> tuple[str, DiscoveryStore]:
    return tenant.tenant_id, _store()


class EvidenceIn(BaseModel):
    source: str = Field(min_length=1, max_length=160)
    reference: str = Field(min_length=1, max_length=2000)
    excerpt: str = Field(default="", max_length=8000)
    observed_at: datetime
    reliability: float = Field(default=0.5, ge=0, le=1)


class HypothesisIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    claim: str = Field(min_length=1, max_length=4000)
    domains: list[str] = Field(min_length=1, max_length=12)
    evidence: list[EvidenceIn] = Field(default_factory=list, max_length=30)
    confidence: float = Field(default=0.25, ge=0, le=1)


class AddEvidenceIn(BaseModel):
    evidence: EvidenceIn
    expected_version: int = Field(ge=1)


class StatusIn(BaseModel):
    status: str
    expected_version: int = Field(ge=1)


class ExperimentIn(BaseModel):
    hypothesis_id: str
    question: str = Field(min_length=1, max_length=2000)
    protocol: dict[str, Any]
    expected_observation: str = Field(min_length=1, max_length=2000)


class OutcomeIn(BaseModel):
    outcome: dict[str, Any]


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    procedure: dict[str, Any]
    preconditions: list[str] = Field(default_factory=list, max_length=50)
    known_failures: list[str] = Field(default_factory=list, max_length=50)
    tests: list[dict[str, Any]] = Field(min_length=1, max_length=100)


class SkillEvalIn(BaseModel):
    # Safe declarative operation set; never eval arbitrary Python or shell.
    operation: str
    options: dict[str, Any] = Field(default_factory=dict)


class CounterfactualIn(BaseModel):
    observations: list[dict[str, Any]] = Field(min_length=1, max_length=200)
    max_candidates: int = Field(default=12, ge=1, le=50)


class TransferCaseIn(BaseModel):
    id: str = Field(min_length=1, max_length=160)
    domain: str = Field(min_length=1, max_length=160)
    input: dict[str, Any]
    expected: Any


class TransferIn(BaseModel):
    operation: str
    cases: list[TransferCaseIn] = Field(min_length=1, max_length=200)


class ValueIn(BaseModel):
    decision_impact: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    expected_reduction: float = Field(ge=0, le=1)
    generality: float = Field(ge=0, le=1)
    cost: float = Field(ge=0, le=1)
    risk: float = Field(default=0, ge=0, le=1)


def _evidence(items):
    return [Evidence(source=e.source, reference=e.reference, excerpt=e.excerpt,
                     observed_at=e.observed_at.isoformat(), reliability=e.reliability)
            for e in items]


def _safe_runner(operation: str, options: dict[str, Any]):
    """Small, explicit pure-function registry. Extend only with tested operations."""
    if operation == "sum_values":
        def run(procedure, data):
            values = data.get("values")
            if not isinstance(values, list) or any(not isinstance(x, (int, float)) for x in values):
                raise ValueError("values must be a numeric list")
            return sum(values)
        return run
    if operation == "sort_values":
        def run(procedure, data):
            values = data.get("values")
            if not isinstance(values, list):
                raise ValueError("values must be a list")
            return sorted(values, reverse=bool(options.get("reverse", False)))
        return run
    if operation == "count_by_key":
        def run(procedure, data):
            items, key = data.get("items"), options.get("key")
            if not isinstance(items, list) or not isinstance(key, str):
                raise ValueError("items must be a list and options.key a string")
            return sum(1 for item in items if isinstance(item, dict) and key in item)
        return run
    raise ValueError("Unsupported safe operation. Supported: sum_values, sort_values, count_by_key.")


@router.post("/hypotheses", status_code=201)
def create_hypothesis(body: HypothesisIn, pair=Depends(_tenant_store)):
    tenant_id, store = pair
    try:
        return store.create_hypothesis(tenant_id, body.title, body.claim, body.domains,
                                       _evidence(body.evidence), body.confidence)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/hypotheses")
def list_hypotheses(limit: int = Query(50, ge=1, le=200), pair=Depends(_tenant_store)):
    tenant_id, store = pair
    return {"items": store.list_hypotheses(tenant_id, limit)}


@router.get("/hypotheses/{hypothesis_id}")
def get_hypothesis(hypothesis_id: str, pair=Depends(_tenant_store)):
    tenant_id, store = pair
    result = store.get_hypothesis(tenant_id, hypothesis_id)
    if result is None:
        raise HTTPException(404, "hypothesis not found")
    return result


@router.post("/hypotheses/{hypothesis_id}/evidence")
def add_evidence(hypothesis_id: str, body: AddEvidenceIn, pair=Depends(_tenant_store)):
    tenant_id, store = pair
    try:
        return store.add_evidence(tenant_id, hypothesis_id, _evidence([body.evidence])[0],
                                  body.expected_version)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.patch("/hypotheses/{hypothesis_id}/status")
def update_hypothesis_status(hypothesis_id: str, body: StatusIn, pair=Depends(_tenant_store)):
    tenant_id, store = pair
    try:
        return store.set_hypothesis_status(tenant_id, hypothesis_id, body.status, body.expected_version)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/experiments", status_code=201)
def create_experiment(body: ExperimentIn, pair=Depends(_tenant_store)):
    tenant_id, store = pair
    try:
        return store.create_experiment(tenant_id, body.hypothesis_id, body.question,
                                       body.protocol, body.expected_observation)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/experiments")
def list_experiments(hypothesis_id: str | None = None, limit: int = Query(100, ge=1, le=300),
                     pair=Depends(_tenant_store)):
    tenant_id, store = pair
    return {"items": store.list_experiments(tenant_id, hypothesis_id, limit)}


@router.post("/experiments/{experiment_id}/outcome")
def record_outcome(experiment_id: str, body: OutcomeIn, pair=Depends(_tenant_store)):
    tenant_id, store = pair
    try:
        return store.record_experiment_outcome(tenant_id, experiment_id, body.outcome)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/skills", status_code=201)
def register_skill(body: SkillIn, pair=Depends(_tenant_store)):
    tenant_id, store = pair
    try:
        return store.register_skill(tenant_id, body.name, body.description, body.procedure,
                                    body.preconditions, body.known_failures, body.tests)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/skills")
def list_skills(limit: int = Query(100, ge=1, le=300), pair=Depends(_tenant_store)):
    tenant_id, store = pair
    return {"items": store.list_skills(tenant_id, limit)}


@router.post("/skills/{skill_id}/evaluate")
def evaluate_skill(skill_id: str, body: SkillEvalIn, pair=Depends(_tenant_store)):
    tenant_id, store = pair
    try:
        return store.evaluate_skill(tenant_id, skill_id, _safe_runner(body.operation, body.options))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/counterfactuals")
def counterfactuals(body: CounterfactualIn, pair=Depends(_tenant_store)):
    try:
        return {"items": propose_counterfactuals(body.observations, max_candidates=body.max_candidates)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/transfer-evaluation")
def transfer_evaluation(body: TransferIn):
    # Endpoint is tenant-authenticated by app-level router mounting.
    try:
        runner = _safe_runner(body.operation, {})
        cases = [c.model_dump() for c in body.cases]
        return cross_domain_transfer_report(cases, lambda data: runner({}, data))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/information-value")
def value_of_information(body: ValueIn):
    try:
        return {"score": information_value(**body.model_dump()),
                "meaning": "Transparent ranking heuristic; not a probability or an approval."}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/audit")
def audit(pair=Depends(_tenant_store)):
    tenant_id, store = pair
    return store.audit_chain(tenant_id)
