"""Service- and route-level tests for the Module 14 wiring chunk."""

import asyncio
import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m14_project_builder.routes import router
from app.modules.m14_project_builder.schemas import (
    ArtifactRegisterRequest,
    CreateProjectRequest,
    FeedbackRequest,
    MilestoneAdvanceRequest,
    MilestonePlanRequest,
    ScopeConstraintsView,
    ScopeRequest,
)
from app.modules.m14_project_builder.service import Service
from app.modules.m14_project_builder.sql_repository import SqlProjectRepository

UTC = timezone.utc
START = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)

PLAN_JSON = json.dumps({
    "tasks": [
        {"id": "lit", "title": "Literature review", "objective": "Survey prior work",
         "agent_kind": "literature", "dependencies": [],
         "acceptance_criteria": ["sources_reviewed"]},
        {"id": "draft", "title": "Draft paper", "objective": "Write the paper",
         "agent_kind": "writer", "dependencies": ["lit"],
         "acceptance_criteria": ["all_sections_drafted"]},
    ],
    "assumptions": ["open data"],
    "risks": ["timeline"],
    "quality_gates": ["review"],
})


class FakeSink:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)
        return item


async def fake_generate(prompt, provider, model):
    return provider, PLAN_JSON


async def bad_generate(prompt, provider, model):
    return provider, "not json"


@pytest.fixture
def service():
    return Service(FakeSink(), generate_fn=fake_generate)


@pytest.fixture
def project(service):
    return service.create("tenant1", CreateProjectRequest(goal="Build an ISEF project"))


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


GOOD_PROV = {"source": "https://example.org",
             "retrieved_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat()}


class TestServiceCore:
    def test_create_get_list(self, service, project):
        assert service.get("tenant1", project.id).goal == "Build an ISEF project"
        assert [p.id for p in service.list("tenant1")] == [project.id]
        assert service.list("other-tenant") == []
        with pytest.raises(KeyError):
            service.get("tenant1", "nope")

    def test_plan_marks_roots_ready(self, service, project):
        response = asyncio.run(service.plan(project))
        tasks = {t.id: t for t in response.project.plan.tasks}
        assert tasks["lit"].status == "ready"
        assert tasks["draft"].status == "blocked"
        assert response.project.status == "planned"
        assert response.project.revision == 1
        assert response.requires_human_review

    def test_plan_rejects_invalid_json(self, project):
        svc = Service(FakeSink(), generate_fn=bad_generate)
        with pytest.raises(ValueError):
            asyncio.run(svc.plan(project))

    def test_execution_proposal_gated(self, service, project):
        with pytest.raises(ValueError):
            service.propose_execution(project)
        asyncio.run(service.plan(project))
        proposal = service.propose_execution(service.get("tenant1", project.id))
        assert proposal.status == "pending"
        assert service._approvals.items[0].module_id == 14
        assert proposal.action_type == "execute_project_plan"


class TestServiceScope:
    def test_scope_persists_into_brief(self, service, project):
        view = service.scope_project(project, ScopeRequest(
            constraints=ScopeConstraintsView(deadline=START + timedelta(days=60)),
        ))
        assert view.kind == "research_project"
        assert view.feasible
        assert "## In scope" in view.markdown
        updated = service.get("tenant1", project.id)
        assert updated.status == "scoped"
        assert updated.brief["scope"]["kind"] == "research_project"

    def test_scope_infeasible_still_recorded(self, service, project):
        view = service.scope_project(project, ScopeRequest(
            constraints=ScopeConstraintsView(deadline=START + timedelta(days=1)),
        ))
        assert not view.feasible
        assert any("deadline" in i for i in view.issues)


class TestServiceMilestones:
    def _planned(self, service, project):
        return service.plan_milestones(project, MilestonePlanRequest(
            kind="coding_project", start=START))

    def test_plan_and_progress(self, service, project):
        views = self._planned(service, project)
        assert len(views) == 6
        progress = service.milestone_progress(project)
        assert progress.overall_progress == 0.0
        assert progress.counts_by_status == {"pending": 6}

    def test_advance_flow(self, service, project):
        self._planned(service, project)
        mid = "p-requirements" if False else f"{project.id}:requirements"
        view = service.advance_milestone(project, mid, MilestoneAdvanceRequest(
            status="in_progress", at=START))
        assert view.status == "in_progress"
        assert view.actual_start == START
        # completion requires acceptance evidence
        with pytest.raises(ValueError):
            service.advance_milestone(project, mid, MilestoneAdvanceRequest(
                status="completed", at=START + timedelta(hours=8)))
        done = service.advance_milestone(project, mid, MilestoneAdvanceRequest(
            status="completed", at=START + timedelta(hours=8),
            evidence={"scope_agreed": "reviewed in call"}))
        assert done.status == "completed"
        progress = service.milestone_progress(project)
        assert progress.overall_progress == pytest.approx(8 / 86, abs=0.001)

    def test_advance_unknown_milestone(self, service, project):
        self._planned(service, project)
        with pytest.raises(KeyError):
            service.advance_milestone(project, "ghost", MilestoneAdvanceRequest(
                status="in_progress", at=START))

    def test_dependency_gate_on_complete(self, service, project):
        self._planned(service, project)
        arch = f"{project.id}:architecture"
        service.advance_milestone(project, arch, MilestoneAdvanceRequest(
            status="in_progress", at=START))
        with pytest.raises(ValueError) as exc:
            service.advance_milestone(project, arch, MilestoneAdvanceRequest(
                status="completed", at=START + timedelta(hours=2),
                evidence={"components_defined": "x", "interfaces_defined": "y"}))
        assert "dependency" in str(exc.value)

    def test_slippage_and_replan(self, service, project):
        self._planned(service, project)
        later = START + timedelta(days=30)
        findings = service.milestone_slippage(project, as_of=later)
        assert any(f.kind == "overdue" for f in findings)
        replanned = service.replan_milestones(project, as_of=later)
        assert all(m.planned_end >= later for m in replanned
                   if m.status == "pending")


class TestServiceArtifacts:
    def test_register_validates_fail_closed(self, service, project):
        with pytest.raises(ValueError):
            service.register_artifact(project, ArtifactRegisterRequest(
                task_id="t1", kind="dataset", uri="workspace://p1/t1/d.csv",
                content_base64=b64(b"data"), provenance={"source": "x"}))

    def test_register_list_validate(self, service, project):
        manifest = service.register_artifact(project, ArtifactRegisterRequest(
            task_id="t1", kind="dataset", uri="workspace://p1/t1/d.csv",
            content_base64=b64(b"data"), provenance=GOOD_PROV))
        assert service.list_artifacts(project)[0].id == manifest.id
        report = service.validate_artifacts(project)
        assert report.passed and report.score == 1.0

    def test_bad_base64_rejected(self, service, project):
        with pytest.raises(ValueError):
            service.register_artifact(project, ArtifactRegisterRequest(
                task_id="t1", kind="dataset", uri="workspace://p1/t1/d.csv",
                content_base64="!!!", provenance=GOOD_PROV))


class TestServiceFeedbackAndExport:
    def test_feedback_revises_plan(self, service, project):
        with pytest.raises(ValueError):
            asyncio.run(service.apply_feedback(project, FeedbackRequest(
                feedback="add a data task")))
        asyncio.run(service.plan(project))
        response = asyncio.run(service.apply_feedback(
            service.get("tenant1", project.id),
            FeedbackRequest(feedback="add a data task")))
        assert response.revision_applied
        assert response.project.revision == 2
        assert response.requires_human_review

    def test_export_assembles_verified_directory(self, service, project, tmp_path):
        service.scope_project(project, ScopeRequest())
        service.plan_milestones(project, MilestonePlanRequest(
            kind="research_project", start=START))
        service.register_artifact(project, ArtifactRegisterRequest(
            task_id="t1", kind="dataset", uri="workspace://p1/t1/d.csv",
            content_base64=b64(b"data"), provenance=GOOD_PROV))
        view = service.export_project(project, base_dir=tmp_path)
        assert view.verification["passed"]
        assert view.readme.startswith("# Build an ISEF project")
        assert "## Milestones" in view.readme and "## Artifacts" in view.readme
        assert view.manifest["project_id"] == project.id
        assert view.zip_sha256
        root = tmp_path / project.id
        assert (root / "README.md").exists()
        assert (root / "STATUS.md").exists()
        assert "## Progress" in (root / "STATUS.md").read_text()
        assert (root / "SCOPE.md").exists()
        assert (root / "export_manifest.json").exists()
        assert (tmp_path / f"{project.id}-export.zip").exists()


class TestSqlRepository:
    def test_tenant_isolation(self):
        # Durable repositories may retain data from prior processes; isolate this
        # test run instead of assuming the shared development database is empty.
        import uuid
        suffix = uuid.uuid4().hex
        tenant_a, tenant_b = f"tenant-a-{suffix}", f"tenant-b-{suffix}"
        a = SqlProjectRepository(tenant_a)
        b = SqlProjectRepository(tenant_b)
        svc_a = Service(FakeSink(), generate_fn=fake_generate, repository=a)
        project = svc_a.create(tenant_a, CreateProjectRequest(goal="secret project"))
        assert b.get(project.id) is None
        assert [p.id for p in a.list()] == [project.id]
        assert b.list() == []

    def test_optimistic_revision_conflict(self):
        repo = SqlProjectRepository("tenant-r")
        svc = Service(FakeSink(), generate_fn=fake_generate, repository=repo)
        project = svc.create("tenant-r", CreateProjectRequest(goal="rev test"))
        project.revision = 5
        with pytest.raises(RuntimeError):
            repo.save(project, expected_revision=3)

    def test_milestones_and_artifacts_roundtrip(self):
        repo = SqlProjectRepository("tenant-m")
        svc = Service(FakeSink(), generate_fn=fake_generate, repository=repo)
        project = svc.create("tenant-m", CreateProjectRequest(goal="roundtrip"))
        svc.plan_milestones(project, MilestonePlanRequest(
            kind="data_analysis", start=START))
        assert len(repo.list_milestones(project.id)) == 6
        svc.register_artifact(project, ArtifactRegisterRequest(
            task_id="t1", kind="dataset", uri="workspace://p/t/d.csv",
            content_base64=b64(b"data"), provenance=GOOD_PROV))
        assert len(repo.list_artifacts(project.id)) == 1
        payloads = repo.artifact_payloads(project.id)
        assert list(payloads.values()) == [b"data"]


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRoutes:
    def test_project_crud(self, client):
        created = client.post("/project-builder/projects",
                              json={"goal": "Build an ISEF project"}).json()
        pid = created["id"]
        assert created["status"] == "draft"
        assert client.get(f"/project-builder/projects/{pid}").json()["id"] == pid
        assert any(p["id"] == pid for p in client.get("/project-builder/projects").json())
        assert client.get("/project-builder/projects/nope").status_code == 404

    def test_plan_route_422_on_stub_llm(self, client):
        pid = client.post("/project-builder/projects",
                          json={"goal": "Build an ISEF project"}).json()["id"]
        response = client.post(f"/project-builder/projects/{pid}/plan")
        assert response.status_code == 422

    def test_scope_and_milestones_routes(self, client):
        pid = client.post("/project-builder/projects",
                          json={"goal": "Analyze this dataset"}).json()["id"]
        scope = client.post(f"/project-builder/projects/{pid}/scope", json={
            "constraints": {"deadline": (START + timedelta(days=60)).isoformat()},
        })
        assert scope.status_code == 200
        assert scope.json()["kind"] == "data_analysis"
        created = client.post(f"/project-builder/projects/{pid}/milestones", json={
            "kind": "data_analysis", "start": START.isoformat()})
        assert created.status_code == 200
        assert len(created.json()) == 6
        progress = client.get(f"/project-builder/projects/{pid}/milestones/progress")
        assert progress.json()["overall_progress"] == 0.0
        mid = f"{pid}:question_definition"
        advanced = client.post(
            f"/project-builder/projects/{pid}/milestones/{mid}/advance",
            json={"status": "in_progress", "at": START.isoformat()})
        assert advanced.status_code == 200
        bad = client.post(
            f"/project-builder/projects/{pid}/milestones/{mid}/advance",
            json={"status": "pending", "at": START.isoformat()})
        assert bad.status_code == 422
        missing = client.post(
            f"/project-builder/projects/{pid}/milestones/ghost/advance",
            json={"status": "in_progress"})
        assert missing.status_code == 404

    def test_artifact_routes(self, client):
        pid = client.post("/project-builder/projects",
                          json={"goal": "Analyze this dataset"}).json()["id"]
        rejected = client.post(f"/project-builder/projects/{pid}/artifacts", json={
            "task_id": "t1", "kind": "dataset", "uri": "workspace://p/t/d.csv",
            "content_base64": b64(b"x"), "provenance": {"source": "x"}})
        assert rejected.status_code == 422
        accepted = client.post(f"/project-builder/projects/{pid}/artifacts", json={
            "task_id": "t1", "kind": "dataset", "uri": "workspace://p/t/d.csv",
            "content_base64": b64(b"x"), "provenance": GOOD_PROV})
        assert accepted.status_code == 201
        assert len(client.get(f"/project-builder/projects/{pid}/artifacts").json()) == 1
        report = client.post(f"/project-builder/projects/{pid}/artifacts/validate")
        assert report.json()["passed"]

    def test_feedback_and_export_routes(self, client):
        pid = client.post("/project-builder/projects",
                          json={"goal": "Analyze this dataset"}).json()["id"]
        no_plan = client.post(f"/project-builder/projects/{pid}/feedback",
                              json={"feedback": "change it"})
        assert no_plan.status_code == 422
        client.post(f"/project-builder/projects/{pid}/milestones",
                    json={"kind": "data_analysis", "start": START.isoformat()})
        client.post(f"/project-builder/projects/{pid}/artifacts", json={
            "task_id": "t1", "kind": "dataset", "uri": "workspace://p/t/d.csv",
            "content_base64": b64(b"x"), "provenance": GOOD_PROV})
        export = client.post(f"/project-builder/projects/{pid}/exports")
        assert export.status_code == 201
        assert export.json()["verification"]["passed"]
        assert export.json()["zip_sha256"]


class TestQualityWiring:
    def test_service_requires_plan(self, service, project):
        with pytest.raises(ValueError):
            service.evaluate_plan(project)

    def test_service_evaluates_planned_project(self, service, project):
        asyncio.run(service.plan(project))
        result = service.evaluate_plan(service.get("tenant1", project.id))
        assert result.passed
        assert 0.0 <= result.score <= 1.0

    def test_quality_route(self, client):
        pid = client.post("/project-builder/projects",
                          json={"goal": "Analyze this dataset"}).json()["id"]
        no_plan = client.post(f"/project-builder/projects/{pid}/quality")
        assert no_plan.status_code == 422


class TestStatusReportWiring:
    def test_service_renders_full_state(self, service, project):
        service.plan_milestones(project, MilestonePlanRequest(
            kind="data_analysis", start=START))
        service.register_artifact(project, ArtifactRegisterRequest(
            task_id="t1", kind="dataset", uri="workspace://p/t/d.csv",
            content_base64=b64(b"x"), provenance=GOOD_PROV))
        view = service.status_report(project)
        assert "## Progress" in view.markdown
        assert "## Artifact validation" in view.markdown
        assert view.generated_at.tzinfo is not None

    def test_service_minimal_project(self, service, project):
        view = service.status_report(project)
        assert "**Status:** draft" in view.markdown
        assert "## Progress" not in view.markdown

    def test_status_report_route(self, client):
        pid = client.post("/project-builder/projects",
                          json={"goal": "Analyze this dataset"}).json()["id"]
        response = client.get(f"/project-builder/projects/{pid}/status-report")
        assert response.status_code == 200
        assert "**Status:** draft" in response.json()["markdown"]
        assert client.get("/project-builder/projects/nope/status-report").status_code == 404


class TestRouteEdgeCases:
    def _project(self, client):
        return client.post("/project-builder/projects",
                           json={"goal": "Analyze this dataset"}).json()["id"]

    def test_milestone_plan_unknown_kind_422(self, client):
        pid = self._project(client)
        response = client.post(f"/project-builder/projects/{pid}/milestones",
                               json={"kind": "nope", "start": START.isoformat()})
        assert response.status_code == 422

    def test_milestone_plan_naive_start_422(self, client):
        pid = self._project(client)
        response = client.post(f"/project-builder/projects/{pid}/milestones",
                               json={"kind": "data_analysis",
                                     "start": "2026-09-21T09:00:00"})
        assert response.status_code == 422

    def test_replan_route(self, client):
        pid = self._project(client)
        client.post(f"/project-builder/projects/{pid}/milestones",
                    json={"kind": "data_analysis", "start": START.isoformat()})
        later = (START + timedelta(days=30)).isoformat()
        response = client.post(
            f"/project-builder/projects/{pid}/milestones/replan",
            params={"as_of": later})
        assert response.status_code == 200
        assert all(m["planned_end"] >= later for m in response.json()
                   if m["status"] == "pending")

    def test_replan_without_milestones_422(self, client):
        pid = self._project(client)
        response = client.post(f"/project-builder/projects/{pid}/milestones/replan")
        assert response.status_code == 422

    def test_slippage_route_empty_without_milestones(self, client):
        pid = self._project(client)
        response = client.get(f"/project-builder/projects/{pid}/milestones/slippage")
        assert response.status_code == 200
        assert response.json() == []

    def test_validate_artifacts_empty_set(self, client):
        pid = self._project(client)
        response = client.post(f"/project-builder/projects/{pid}/artifacts/validate")
        assert response.status_code == 200
        assert response.json()["passed"]
        assert response.json()["artifacts"] == []

    def test_progress_without_milestones_422(self, client):
        pid = self._project(client)
        response = client.get(f"/project-builder/projects/{pid}/milestones/progress")
        assert response.status_code == 422

    def test_scope_unknown_kind_422(self, client):
        pid = self._project(client)
        response = client.post(f"/project-builder/projects/{pid}/scope",
                               json={"kind": "nope"})
        assert response.status_code == 422

    def test_export_empty_project(self, client):
        pid = self._project(client)
        response = client.post(f"/project-builder/projects/{pid}/exports")
        assert response.status_code == 201
        assert response.json()["verification"]["passed"]


class TestExportWarnings:
    def test_missing_payload_warns_not_silent(self, service, project, tmp_path):
        manifest = service.register_artifact(project, ArtifactRegisterRequest(
            task_id="t1", kind="dataset", uri="workspace://p/t/d.csv",
            content_base64=b64(b"x"), provenance=GOOD_PROV))
        # Simulate object-store loss: drop the payload behind the service.
        del service._artifact_payloads[("tenant1", project.id)][manifest.id]
        view = service.export_project(project, base_dir=tmp_path)
        assert any(manifest.id in w for w in view.warnings)
        assert view.verification["passed"]  # export is consistent, artifact excluded
