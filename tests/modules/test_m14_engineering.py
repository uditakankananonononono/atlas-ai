"""Row-mapped tests for the Module 14 engineering design artifacts (510-534)."""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m14_project_builder.engineering import (
    DESIGN_KINDS,
    DesignDocument,
    UnknownDesignKindError,
    generate_design,
    list_design_kinds,
    spec_for_kind,
    spec_for_row,
    validate_design,
)
from app.modules.m14_project_builder.routes import router
from app.modules.m14_project_builder.schemas import (
    CreateProjectRequest,
    DesignRequest,
)
from app.modules.m14_project_builder.service import Service

UTC = timezone.utc
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


class FakeSink:
    def put(self, item):
        return item


async def fake_generate(prompt, provider, model):
    return provider, "{}"


@pytest.fixture
def service():
    return Service(FakeSink(), generate_fn=fake_generate)


@pytest.fixture
def project(service):
    return service.create("tenant1", CreateProjectRequest(goal="Build Atlas"))


# --- Row mapping: every row 510-534 maps to exactly one kind and back --------
class TestRowMapping:
    def test_fifty_rows_contiguous_510_to_559(self):
        rows = sorted(s.row for s in DESIGN_KINDS)
        assert rows == list(range(510, 560))

    def test_rows_535_to_559_registered(self):
        expected = {
            535: "etl_pipeline", 536: "data_warehouse", 537: "data_lake",
            538: "data_mesh", 539: "stream_processing", 540: "batch_processing",
            541: "lambda_architecture", 542: "kappa_architecture",
            543: "ml_pipeline", 544: "feature_store", 545: "model_registry",
            546: "model_monitoring", 547: "ab_testing", 548: "recommendation",
            549: "search_system", 550: "ranking_system", 551: "fraud_detection",
            552: "anomaly_detection", 553: "time_series", 554: "nlp",
            555: "computer_vision", 556: "speech_recognition",
            557: "speech_synthesis", 558: "machine_translation",
            559: "text_summarization",
        }
        assert {s.row: s.kind for s in DESIGN_KINDS if s.row >= 535} == expected

    @pytest.mark.parametrize("spec", DESIGN_KINDS, ids=lambda s: f"row-{s.row}")
    def test_row_roundtrip(self, spec):
        assert spec_for_row(spec.row) is spec
        assert spec_for_kind(spec.kind) is spec

    def test_unknown_kind_and_row_rejected(self):
        with pytest.raises(UnknownDesignKindError):
            spec_for_kind("nope")
        with pytest.raises(UnknownDesignKindError):
            spec_for_row(999)


# --- Generation: every kind produces a complete, valid, honest document ------
class TestGeneration:
    @pytest.mark.parametrize("spec", DESIGN_KINDS, ids=lambda s: s.kind)
    def test_generates_all_required_sections(self, spec):
        doc = generate_design(spec.kind, "Build Atlas", generated_at=NOW)
        assert doc.row == spec.row and doc.title == spec.title
        for section in spec.required_sections:
            assert f"## {section}" in doc.markdown

    @pytest.mark.parametrize("spec", DESIGN_KINDS, ids=lambda s: s.kind)
    def test_generated_document_passes_validation(self, spec):
        doc = generate_design(spec.kind, "Build Atlas", generated_at=NOW)
        report = validate_design(doc)
        assert report.passed, [f.message for f in report.findings]
        assert report.score == 1.0

    @pytest.mark.parametrize("spec", DESIGN_KINDS, ids=lambda s: s.kind)
    def test_generated_document_never_contains_secrets_or_claims(self, spec):
        # Boundary: generation must never emit secrets or operational claims.
        doc = generate_design(spec.kind, "Build Atlas", generated_at=NOW)
        report = validate_design(doc)
        assert not any(f.check == "no_secrets" for f in report.findings)
        assert not any(f.check == "no_operational_claims" for f in report.findings)

    def test_context_notes_included(self):
        doc = generate_design("requirements", "Build Atlas",
                              context={"Stakeholders": "solo founder"},
                              generated_at=NOW)
        assert "Project note: solo founder" in doc.markdown

    def test_design_artifact_notice_present(self):
        doc = generate_design("auto_scaling", "Build Atlas", generated_at=NOW)
        assert "not evidence of deployment" in doc.markdown


# --- Validation failure paths --------------------------------------------------
class TestValidationFailures:
    def _doc(self, kind, markdown):
        return DesignDocument(kind=kind, row=spec_for_kind(kind).row,
                              title="t", markdown=markdown,
                              generated_at=NOW.isoformat())

    def test_missing_section_fails(self):
        doc = generate_design("caching", "g", generated_at=NOW)
        broken = doc.markdown.replace("## Invalidation", "## Gone")
        report = validate_design(self._doc("caching", broken))
        assert not report.passed
        assert any("Invalidation" in f.message for f in report.findings)

    def test_empty_section_fails(self):
        doc = generate_design("caching", "g", generated_at=NOW)
        broken = doc.markdown.replace(
            "## TTLs\n\nTime-to-live per data class with justification.",
            "## TTLs\n")
        report = validate_design(self._doc("caching", broken))
        assert not report.passed
        assert any(f.check == "section_nonempty" for f in report.findings)

    @pytest.mark.parametrize("marker", ["TBD", "TODO", "to be decided",
                                        "<placeholder", "lorem ipsum"])
    def test_placeholders_fail(self, marker):
        doc = generate_design("monolith", "g", generated_at=NOW)
        broken = doc.markdown + f"\n{marker}\n"
        report = validate_design(self._doc("monolith", broken))
        assert not report.passed
        assert any(f.check == "no_placeholders" for f in report.findings)

    @pytest.mark.parametrize("claim", [
        "The API is deployed on GCP.",
        "The service is currently serving 10k rps.",
        "We run this in production.",
        "The platform achieved 99.99% uptime.",
    ])
    def test_operational_claims_fail(self, claim):
        doc = generate_design("system_architecture", "g", generated_at=NOW)
        broken = doc.markdown + f"\n{claim}\n"
        report = validate_design(self._doc("system_architecture", broken))
        assert not report.passed
        assert any(f.check == "no_operational_claims" for f in report.findings)

    @pytest.mark.parametrize("claim", [
        "The model achieves 94% accuracy on the validation set.",
        "F1 of 0.87 on the eval set.",
        "We trained the model on 1M labeled examples.",
        "WER was 6.2% for English.",
        "Recall = 0.91 for the fraud class.",
    ])
    def test_ml_performance_claims_fail(self, claim):
        # Rows 535-559: a design must never claim a trained model's results.
        doc = generate_design("ml_pipeline", "g", generated_at=NOW)
        broken = doc.markdown + f"\n{claim}\n"
        report = validate_design(self._doc("ml_pipeline", broken))
        assert not report.passed
        assert any(f.check == "no_operational_claims" for f in report.findings)

    @pytest.mark.parametrize("spec", [s for s in DESIGN_KINDS if s.row >= 535],
                             ids=lambda s: f"row-{s.row}-{s.kind}")
    def test_new_kinds_generate_valid_documents(self, spec):
        doc = generate_design(spec.kind, "Build Atlas", generated_at=NOW)
        assert "trained models" in doc.markdown  # honesty notice extended
        report = validate_design(doc)
        assert report.passed, [f.message for f in report.findings]

    @pytest.mark.parametrize("secret", [
        "-----BEGIN RSA PRIVATE KEY-----\nMIIabc",
        "aws key AKIAIOSFODNN7EXAMPLE",
        "token ghp_abcdefghijklmnopqrstuvwxyz123456",
        "api key sk-abcdefghijklmnopqrstuvwx",
        "password = \"Sup3rSecretValue!!\"",
    ])
    def test_secrets_fail(self, secret):
        doc = generate_design("key_management", "g", generated_at=NOW)
        broken = doc.markdown + f"\n{secret}\n"
        report = validate_design(self._doc("key_management", broken))
        assert not report.passed
        assert any(f.check == "no_secrets" for f in report.findings)

    def test_key_management_allows_named_kms_reference(self):
        # Referencing a KMS by name is the correct pattern and must pass.
        doc = generate_design("key_management", "g", generated_at=NOW)
        extended = doc.markdown + "\nKeys live in a managed KMS; no values are stored here.\n"
        report = validate_design(self._doc("key_management", extended))
        assert report.passed

    def test_score_drops_per_error(self):
        doc = generate_design("backup", "g", generated_at=NOW)
        clean = validate_design(doc)
        broken = validate_design(self._doc(
            "backup", doc.markdown.replace("## Retention", "## Gone") + "\nTBD\n"))
        assert clean.score == 1.0
        assert broken.score < 0.6

    def test_quality_result_shape(self):
        doc = generate_design("privacy", "g", generated_at=NOW)
        result = validate_design(doc).to_quality_result()
        assert set(result) == {"passed", "score", "findings", "remediation"}


# --- Service and route wiring ----------------------------------------------------
class TestServiceWiring:
    def test_generate_registers_artifact_fail_closed(self, service, project):
        view = service.generate_design(project, DesignRequest(kind="encryption"))
        assert view.row == 527
        assert view.validation.passed
        artifacts = service.list_artifacts(project)
        assert len(artifacts) == 1
        stored = artifacts[0]
        assert stored.id == view.artifact_id
        assert stored.kind == "design_document"
        assert stored.provenance["design_kind"] == "encryption"
        assert stored.provenance["feature_row"] == "527"
        # payload flows through the artifact pipeline
        payloads = service._artifact_payloads[("tenant1", project.id)]
        assert b"Encryption Implementation" in payloads[stored.id]

    def test_generate_unknown_kind_raises(self, service, project):
        with pytest.raises(UnknownDesignKindError):
            service.generate_design(project, DesignRequest(kind="nope"))

    def test_list_designs(self, service, project):
        service.generate_design(project, DesignRequest(kind="requirements"))
        service.generate_design(project, DesignRequest(kind="data_lineage"))
        designs = service.list_designs(project)
        assert [(d.kind, d.row) for d in designs] == [
            ("requirements", 510), ("data_lineage", 533)]

    def test_design_document_in_artifact_validation(self, service, project):
        service.generate_design(project, DesignRequest(kind="compliance"))
        report = service.validate_artifacts(project)
        assert report.passed  # provenance contract of design_document satisfied


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRoutes:
    def _project(self, client):
        return client.post("/project-builder/projects",
                           json={"goal": "Build Atlas"}).json()["id"]

    def test_generate_route(self, client):
        pid = self._project(client)
        response = client.post(f"/project-builder/projects/{pid}/designs",
                               json={"kind": "api_design"})
        assert response.status_code == 201
        body = response.json()
        assert body["row"] == 512
        assert body["validation"]["passed"]
        assert "## Error Model" in body["markdown"]
        assert body["artifact_id"]

    def test_generate_route_unknown_kind_422(self, client):
        pid = self._project(client)
        response = client.post(f"/project-builder/projects/{pid}/designs",
                               json={"kind": "warp_drive"})
        assert response.status_code == 422

    def test_list_route(self, client):
        pid = self._project(client)
        client.post(f"/project-builder/projects/{pid}/designs",
                    json={"kind": "disaster_recovery"})
        response = client.get(f"/project-builder/projects/{pid}/designs")
        assert response.status_code == 200
        assert response.json() == [{
            "artifact_id": response.json()[0]["artifact_id"],
            "kind": "disaster_recovery", "row": 522,
            "title": "Disaster Recovery",
            "generated_at": response.json()[0]["generated_at"],
        }]

    def test_generate_route_404(self, client):
        response = client.post("/project-builder/projects/nope/designs",
                               json={"kind": "caching"})
        assert response.status_code == 404

    def test_designs_flow_into_export(self, client):
        pid = self._project(client)
        client.post(f"/project-builder/projects/{pid}/designs",
                    json={"kind": "audit_logging"})
        export = client.post(f"/project-builder/projects/{pid}/exports")
        assert export.status_code == 201
        assert export.json()["verification"]["passed"]
        assert export.json()["warnings"] == []
        paths = [e["relative_path"] for e in export.json()["manifest"]["entries"]]
        assert any("design_document" in p for p in paths)
