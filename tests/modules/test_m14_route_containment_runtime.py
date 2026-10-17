"""Runtime HTTP tests for M14 route-error containment (v2 decoder + v3 unmapped routes).

Runs the actual FastAPI router through TestClient on python 3.12 with the
project-declared deps. Auth uses the app's documented development header path
(ATLAS_DEV_NO_AUTH=1 + ATLAS_ENV=local); only get_service is overridden, the
standard FastAPI wiring override, so the route functions, exception mapping and
Service logic under test execute unchanged. Repository and planner generation
are scripted at the Service constructor, which is the injection point the
production code itself exposes.
"""
from __future__ import annotations

import os

os.environ.setdefault("ATLAS_DEV_NO_AUTH", "1")
os.environ.setdefault("ATLAS_ENV", "local")
os.environ.setdefault("ATLAS_DATABASE_URL", "sqlite:////tmp/m14-runtime-test.db")

import base64
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.providers import ProviderError, ProviderOutcomeUnknown
from app.modules.m14_project_builder import routes as m14_routes
from app.modules.m14_project_builder.errors import (
    ArtifactIdConflict,
    PlannerOutputInvalid,
    ProjectRevisionConflict,
)
from app.modules.m14_project_builder.schemas import Budget, ProjectPlan, ProjectTask, ProjectView
from app.modules.m14_project_builder.service import PlannerUnavailable, Service

HEADERS = {"X-Atlas-Tenant": "t1", "X-Atlas-Actor": "runtime-tester"}


def _plan() -> ProjectPlan:
    return ProjectPlan(
        goal="build a research planner",
        tasks=[ProjectTask(id="t1", title="task one", objective="do the first thing", agent_kind="coder")],
    )


def _project(status: str = "draft", plan: ProjectPlan | None = None) -> ProjectView:
    return ProjectView(
        id="p1", tenant_id="t1", goal="build a research planner", brief={},
        budget=Budget(), status=status, revision=1, plan=plan,
    )


class _Sink:
    def put(self, item, user_id=None):
        return SimpleNamespace(id="appr-1", status=SimpleNamespace(value="pending"))


class _Repo:
    """Minimal scripted repository; only the methods the Service calls."""

    def __init__(self, project, save_exc=None, artifact_exc=None):
        self._project = project
        self._save_exc = save_exc
        self._artifact_exc = artifact_exc

    def get(self, project_id):
        return self._project

    def save(self, item, expected_revision=None):
        if self._save_exc is not None:
            raise self._save_exc
        return item

    def save_artifact(self, project_id, manifest, payload):
        if self._artifact_exc is not None:
            raise self._artifact_exc

    def list_artifacts(self, project_id):
        return []

    def artifact_payloads(self, project_id):
        return {}

    def save_milestones(self, project_id, milestones):
        pass

    def list_milestones(self, project_id):
        return []


def _client(service: Service) -> TestClient:
    app = FastAPI()
    app.include_router(m14_routes.router)
    app.dependency_overrides[m14_routes.get_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def _service(project, generate_fn, **repo_kw) -> Service:
    return Service(_Sink(), generate_fn=generate_fn, repository=_Repo(project, **repo_kw))


def _gen_text(text: str):
    async def gen(prompt, provider, key):
        return ("model-x", text)
    return gen


def _gen_raise(exc: Exception):
    async def gen(prompt, provider, key):
        raise exc
    return gen


# --- v2 decoder containment, executed at runtime -----------------------------

def test_plan_nested_recursion_becomes_502():
    client = _client(_service(_project(), _gen_text("[" * 1100 + "]" * 1100)))
    r = client.post("/project-builder/projects/p1/plan", headers=HEADERS)
    assert r.status_code == 502
    assert r.json()["detail"] == {"state": "invalid_planner_output", "plan_created": False}


def test_plan_huge_integer_becomes_502():
    client = _client(_service(_project(), _gen_text('{"tasks": ' + "1" * 5000 + "}")))
    r = client.post("/project-builder/projects/p1/plan", headers=HEADERS)
    assert r.status_code == 502
    assert r.json()["detail"] == {"state": "invalid_planner_output", "plan_created": False}


def test_plan_provider_error_becomes_503():
    client = _client(_service(_project(), _gen_raise(ProviderError("planner down"))))
    r = client.post("/project-builder/projects/p1/plan", headers=HEADERS)
    assert r.status_code == 503
    assert r.json()["detail"]["state"] == "unavailable"
    assert r.json()["detail"]["plan_created"] is False


def test_plan_outcome_unknown_becomes_409():
    client = _client(_service(_project(), _gen_raise(ProviderOutcomeUnknown("lost"))))
    r = client.post("/project-builder/projects/p1/plan", headers=HEADERS)
    assert r.status_code == 409
    assert r.json()["detail"] == {"state": "unknown", "retry_allowed": False, "plan_created": False}


# --- v3 unmapped-route containment, executed at runtime ----------------------

def test_propose_revision_conflict_becomes_409():
    project = _project(status="planned", plan=_plan())
    service = _service(project, _gen_text("{}"), save_exc=ProjectRevisionConflict("project revision conflict"))
    r = _client(service).post("/project-builder/projects/p1/execution-proposals", headers=HEADERS)
    assert r.status_code == 409
    assert r.json()["detail"] == {"state": "revision_conflict", "proposal_created": False}


def test_scope_revision_conflict_becomes_409():
    service = _service(_project(), _gen_text("{}"), save_exc=ProjectRevisionConflict("project revision conflict"))
    r = _client(service).post("/project-builder/projects/p1/scope", headers=HEADERS, json={"constraints": {}, "kind": None, "brief_keywords": []})
    assert r.status_code == 409
    assert r.json()["detail"] == {"state": "revision_conflict"}


def test_register_artifact_id_conflict_becomes_409():
    service = _service(_project(), _gen_text("{}"), artifact_exc=ArtifactIdConflict("artifact id already exists"))
    body = {
        "task_id": "t1",
        "kind": "code",
        "uri": "workspace://p1/a.txt",
        "content_base64": base64.b64encode(b"hello").decode(),
        "provenance": {"generator": "runtime-test"},
    }
    r = _client(service).post("/project-builder/projects/p1/artifacts", headers=HEADERS, json=body)
    assert r.status_code == 409
    assert r.json()["detail"] == {"state": "artifact_conflict"}


def test_feedback_provider_error_becomes_503():
    project = _project(status="planned", plan=_plan())
    service = _service(project, _gen_raise(ProviderError("planner down")))
    r = _client(service).post("/project-builder/projects/p1/feedback", headers=HEADERS, json={"feedback": "please revise the plan", "provider": "shared"})
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert detail["state"] == "unavailable"
    assert detail["revision_applied"] is False


def test_feedback_outcome_unknown_becomes_409():
    project = _project(status="planned", plan=_plan())
    service = _service(project, _gen_raise(ProviderOutcomeUnknown("lost")))
    r = _client(service).post("/project-builder/projects/p1/feedback", headers=HEADERS, json={"feedback": "please revise the plan", "provider": "shared"})
    assert r.status_code == 409
    assert r.json()["detail"] == {"state": "unknown", "retry_allowed": False, "revision_applied": False}


def test_feedback_invalid_planner_output_502_not_422():
    # PlannerOutputInvalid subclasses ValueError; if the ValueError handler ran
    # first this would come back 422. 502 proves the typed ordering.
    project = _project(status="planned", plan=_plan())
    service = _service(project, _gen_text("this is not json"))
    r = _client(service).post("/project-builder/projects/p1/feedback", headers=HEADERS, json={"feedback": "please revise the plan", "provider": "shared"})
    assert r.status_code == 502
    assert r.json()["detail"] == {"state": "invalid_planner_output", "revision_applied": False}


def test_feedback_unmapped_runtime_error_stays_500():
    # Negative control: no broad catch was added anywhere in the chain.
    project = _project(status="planned", plan=_plan())
    service = _service(project, _gen_raise(RuntimeError("boom")))
    r = _client(service).post("/project-builder/projects/p1/feedback", headers=HEADERS, json={"feedback": "please revise the plan", "provider": "shared"})
    assert r.status_code == 500
