"""m14 status reports pass the report gate (group 142): labeled claims emit, unlabeled/vacuous refuse."""
import pytest

from app.runtime.guardrails.errors import GuardrailRefusal
from tests.modules.test_m14_wiring import GOOD_PROV, b64, client, project, service  # noqa: F401
from app.modules.m14_project_builder import service as svc_mod


def test_status_report_carries_labeled_claims_and_is_ledgered(service, project):
    view = service.status_report(project)
    assert "## Claims" in view.markdown and "UNVERIFIED" in view.markdown
    assert "VERIFIED |" not in view.markdown.replace("UNVERIFIED |", "")  # nothing verified without a validator result
    assert service._report_gate().ledger("reports")[-1]["record"]["verdict"] == "emitted"


def test_artifact_validator_result_is_the_only_verified_claim(service, project):
    from app.modules.m14_project_builder.schemas import ArtifactRegisterRequest
    service.register_artifact(project, ArtifactRegisterRequest(
        task_id="t1", kind="dataset", uri="workspace://p/t/d.csv",
        content_base64=b64(b"x"), provenance=GOOD_PROV))
    md = service.status_report(project).markdown
    assert "computed validator result" in md and "| VERIFIED |" in md


def _render(monkeypatch, body):
    monkeypatch.setattr(svc_mod.report_engine, "render_status_report", lambda ctx: body)


def test_unlabeled_claim_refused_before_report_leaves(service, project, monkeypatch):
    _render(monkeypatch, "# r\n\nCLAIM: results are conclusive\n")
    with pytest.raises(GuardrailRefusal) as held:
        service.status_report(project)
    assert held.value.code == "REPGATE:refused:unmarked_claims"


def test_conflicting_labels_refused(service, project, monkeypatch):
    _render(monkeypatch, "# r\n\nCLAIM: x [VERIFIED] [UNVERIFIED]\n")
    with pytest.raises(GuardrailRefusal) as held:
        service.status_report(project)
    assert held.value.code == "REPGATE:refused:conflicting_claims"


def test_claim_free_report_refused_as_vacuous(service, project, monkeypatch):
    _render(monkeypatch, "# r\n\njust prose\n")
    with pytest.raises(GuardrailRefusal) as held:
        service.status_report(project)
    assert held.value.code == "REPGATE:refused:vacuous"


@pytest.mark.parametrize("path,method", [("status-report", "get"), ("exports", "post")])
def test_route_translates_report_refusal_to_422_not_500(client, monkeypatch, path, method):
    pid = client.post("/project-builder/projects", json={"goal": "Analyze this dataset"}).json()["id"]
    _render(monkeypatch, "# r\n\nCLAIM: unlabeled result\n")
    response = getattr(client, method)(f"/project-builder/projects/{pid}/{path}")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["refused_by"] == "report_gate" and detail["code"] == "REPGATE:refused:unmarked_claims"


@pytest.mark.parametrize("renderer", ["status", "readme"])
def test_real_direct_renderer_refuses_unmarked_supplied_goal(renderer):
    from app.modules.m14_project_builder.reports import StatusReportContext, render_status_report
    from app.modules.m14_project_builder.exports import ReadmeContext, render_readme
    goal = "Project\nCLAIM: unmarked supplied result"
    with pytest.raises(GuardrailRefusal, match="unmarked_claims"):
        if renderer == "status":
            render_status_report(StatusReportContext(project_id="p", goal=goal, status="draft"))
        else:
            render_readme(ReadmeContext(project_id="p", goal=goal, status="draft"))


def test_real_service_export_refuses_unmarked_goal_before_any_files(service, project, tmp_path):
    project.goal = "Project\nCLAIM: unmarked result"
    with pytest.raises(GuardrailRefusal, match="unmarked_claims"):
        service.export_project(project, base_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_alternate_readme_renderer_refused_before_files(service, project, tmp_path, monkeypatch):
    monkeypatch.setattr(svc_mod.export_engine, "render_readme", lambda ctx: "CLAIM: unmarked result\n")
    with pytest.raises(GuardrailRefusal, match="unmarked_claims"):
        service.export_project(project, base_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert service._report_gate().ledger("reports")[-1]["record"]["verdict"] == "refused:unmarked_claims"


def test_alternate_status_renderer_refused_before_export_files(service, project, tmp_path, monkeypatch):
    _render(monkeypatch, "CLAIM: unmarked result\n")
    with pytest.raises(GuardrailRefusal, match="unmarked_claims"):
        service.export_project(project, base_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_export_readme_and_status_are_both_hash_bound(service, project, tmp_path):
    import hashlib
    view = service.export_project(project, base_dir=tmp_path)
    records = [e["record"] for e in service._report_gate().ledger("reports")]
    assert len(records) == 2 and all(r["verdict"] == "emitted" for r in records)
    assert records[0]["report_sha256"] == hashlib.sha256(view.readme.encode()).hexdigest()
    status_bytes = (tmp_path / project.id / "STATUS.md").read_bytes()
    assert records[1]["report_sha256"] == hashlib.sha256(status_bytes).hexdigest()


def test_direct_readme_preserves_project_state_as_unverified_not_claim_label():
    from app.modules.m14_project_builder.exports import ReadmeContext, render_readme
    from tests.modules.test_m14_exports import TestReadme
    context = TestReadme()._context()
    body = render_readme(context)
    assert "| Milestone | Phase | State |" in body
    assert "| UNVERIFIED |" in body
    assert "| VERIFIED |" not in body
