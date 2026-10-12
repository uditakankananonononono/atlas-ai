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
