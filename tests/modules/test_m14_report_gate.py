"""m14 status reports pass the report gate (group 142): labeled claims emit, unlabeled/vacuous refuse."""
import pytest

from app.runtime.guardrails.errors import GuardrailRefusal
from tests.modules.test_m14_wiring import GOOD_PROV, b64, project, service  # noqa: F401
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
