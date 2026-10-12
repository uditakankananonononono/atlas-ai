"""Complete M14 report identity is hashed, never prefix-truncated."""
from datetime import datetime, timezone
from tests.modules.test_m14_wiring import service, project  # noqa: F401
from app.modules.m14_project_builder import service as svc_mod

NOW = datetime(2026, 10, 12, 12, 0, 0, 123456, tzinfo=timezone.utc)


def test_complete_report_identity_distinguishes_long_shared_prefixes(project):
    project.id = "p" * 90 + "A"
    first = svc_mod._report_id("status", project, NOW, "body")
    project.id = "p" * 90 + "B"
    second = svc_mod._report_id("status", project, NOW, "body")
    assert first != second and len(first) == len(second) == 64


def test_identity_binds_tenant_kind_body_and_subsecond_time(project):
    base = svc_mod._report_id("status", project, NOW, "body")
    assert svc_mod._report_id("status", project, NOW, "body") == base
    assert svc_mod._report_id("readme", project, NOW, "body") != base
    assert svc_mod._report_id("status", project, NOW, "different") != base
    assert svc_mod._report_id("status", project, NOW.replace(microsecond=123457), "body") != base
    project.tenant_id = "other-tenant"
    assert svc_mod._report_id("status", project, NOW, "body") != base


def test_status_report_ids_remain_distinct_for_long_project_ids(service, project, monkeypatch):
    class Clock:
        @staticmethod
        def now(tz):
            return NOW
    monkeypatch.setattr(svc_mod, "datetime", Clock)
    project.id = "p" * 90 + "A"
    service.status_report(project)
    project.id = "p" * 90 + "B"
    service.status_report(project)
    records = [e["record"] for e in service._report_gate().ledger("reports")]
    assert records[0]["report_id"] != records[1]["report_id"]
    assert all(len(r["report_id"]) == 64 for r in records)


def test_export_readme_and_status_use_content_bound_identity(service, project, tmp_path):
    import hashlib
    result = service.export_project(project, base_dir=tmp_path)
    records = [e["record"] for e in service._report_gate().ledger("reports")]
    assert len(records) == 2 and records[0]["report_id"] != records[1]["report_id"]
    assert records[0]["report_sha256"] == hashlib.sha256(result.readme.encode()).hexdigest()
    assert all(len(r["report_id"]) == 64 for r in records)


def _expected_callsite_id(kind, project, generated, actual_body):
    # Independent encoding of the public identity contract, not _report_id().
    import hashlib
    import json
    fields = {"body": actual_body, "generated_at": generated.isoformat(),
              "kind": kind, "project_id": project.id, "tenant_id": project.tenant_id}
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _freeze_service_time(monkeypatch):
    class Clock:
        @staticmethod
        def now(tz):
            assert tz == timezone.utc
            return NOW
    monkeypatch.setattr(svc_mod, "datetime", Clock)


def test_status_emit_callsite_binds_exact_actual_identity(service, project, monkeypatch):
    import hashlib
    _freeze_service_time(monkeypatch)
    project.id = "long-project-" + "x" * 90
    view = service.status_report(project)
    records = [entry["record"] for entry in service._report_gate().ledger("reports")]
    assert len(records) == 1
    assert view.generated_at == NOW
    assert records[0]["report_id"] == _expected_callsite_id("status", project, NOW, view.markdown)
    assert records[0]["report_sha256"] == hashlib.sha256(view.markdown.encode()).hexdigest()


def test_export_emit_callsites_bind_exact_readme_and_status_identity(service, project, tmp_path, monkeypatch):
    import hashlib
    _freeze_service_time(monkeypatch)
    result = service.export_project(project, base_dir=tmp_path)
    readme = (tmp_path / project.id / "README.md").read_text()
    status = (tmp_path / project.id / "STATUS.md").read_text()
    assert readme == result.readme
    records = [entry["record"] for entry in service._report_gate().ledger("reports")]
    assert len(records) == 2
    for record, kind, body in zip(records, ("readme", "status"), (readme, status), strict=True):
        assert record["report_id"] == _expected_callsite_id(kind, project, NOW, body)
        assert record["report_sha256"] == hashlib.sha256(body.encode()).hexdigest()
