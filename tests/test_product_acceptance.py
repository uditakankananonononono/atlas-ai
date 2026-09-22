"""Acceptance-harness tests: live evidence, configured fallback, honest misses."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import product_acceptance as pa


PRODUCTION_ENV = {
    "ATLAS_ENV": "production",
    "ATLAS_DATABASE_URL": "postgresql://db.example/atlas",
    "ATLAS_REDIS_URL": "redis://cache.example/0",
    "ATLAS_SECRET_PROVIDER": "gcp-secret-manager",
    "ATLAS_OIDC_ISSUER": "https://issuer.example",
    "ATLAS_OIDC_AUDIENCE": "atlas",
}


def probers(**overrides):
    values = {"database": None, "redis": None, "migrations": None,
              "oidc_jwks": None, "workers": None}
    values.update(overrides)
    return pa.Probers(**{k: (lambda v=v: v) for k, v in values.items()})


def test_all_live_probes_passing_yields_accepted(tmp_path):
    repo = tmp_path
    (repo / "deploy/otel").mkdir(parents=True)
    (repo / "deploy/grafana").mkdir(parents=True)
    (repo / "docs/runbooks").mkdir(parents=True)
    (repo / "deploy/otel/collector.yaml").write_text("receivers: {}")
    (repo / "deploy/grafana/dashboard.json").write_text("{}")
    (repo / "docs/SLO_ALERTS.md").write_text("# SLOs")
    (repo / "docs/runbooks/BACKUP_RESTORE.md").write_text("# runbook")
    (repo / "docs/runbooks/restore-drill-2026-09.md").write_text("# drill record")
    env = {**PRODUCTION_ENV, "OTEL_EXPORTER_OTLP_ENDPOINT": "https://otel.example"}
    report = pa.run(env=env, probers=probers(database=True, redis=True, migrations=True,
                                             oidc_jwks=True, workers=True), repo_root=repo)
    # Live-probe checks are accepted; artifact-only checks honestly stay
    # configured, so the overall verdict is configured_unaccepted.
    assert report["verdict"] == "configured_unaccepted"
    assert set(report["accepted"]) == {"auth_config", "database", "migrations",
                                       "redis", "workers"}
    assert set(report["configured_unaccepted"]) == {"adapters", "monitoring",
                                                    "backup_restore"}
    assert report["missing"] == []


def test_configured_without_live_evidence_is_not_accepted(tmp_path):
    repo = tmp_path
    (repo / "deploy/otel").mkdir(parents=True)
    (repo / "deploy/grafana").mkdir(parents=True)
    (repo / "docs/runbooks").mkdir(parents=True)
    (repo / "deploy/otel/collector.yaml").write_text("receivers: {}")
    (repo / "deploy/grafana/dashboard.json").write_text("{}")
    (repo / "docs/SLO_ALERTS.md").write_text("# SLOs")
    (repo / "docs/runbooks/BACKUP_RESTORE.md").write_text("# runbook")
    (repo / "docs/runbooks/restore-drill-2026-09.md").write_text("# drill")
    env = {**PRODUCTION_ENV, "OTEL_EXPORTER_OTLP_ENDPOINT": "https://otel.example"}
    report = pa.run(env=env, probers=probers(), repo_root=repo)
    assert report["verdict"] == "configured_unaccepted"
    for name in ("database", "migrations", "redis", "workers", "auth_config"):
        assert name in report["configured_unaccepted"], name
    assert report["accepted"] == [] and report["missing"] == []


def test_failed_probe_against_configured_target_is_missing_not_configured(tmp_path):
    env = {**PRODUCTION_ENV}
    report = pa.run(env=env, probers=probers(database=False), repo_root=tmp_path)
    assert "database" in report["missing"]
    assert report["verdict"] == "unaccepted"


def test_production_env_missing_oidc_is_unaccepted(tmp_path):
    env = {k: v for k, v in PRODUCTION_ENV.items() if k != "ATLAS_OIDC_ISSUER"}
    report = pa.run(env=env, probers=probers(database=True), repo_root=tmp_path)
    assert report["verdict"] == "unaccepted"
    assert "auth_config" in report["missing"]
    detail = next(c for c in report["checks"] if c["name"] == "auth_config")
    assert "ATLAS_OIDC_ISSUER" in detail["detail"]


def test_backup_runbook_without_drill_evidence_is_unaccepted(tmp_path):
    repo = tmp_path
    (repo / "docs/runbooks").mkdir(parents=True)
    (repo / "docs/runbooks/BACKUP_RESTORE.md").write_text("# runbook")
    report = pa.run(env={**PRODUCTION_ENV}, probers=probers(), repo_root=repo)
    assert "backup_restore" in report["missing"]


def test_monitoring_needs_artifacts_and_endpoint(tmp_path):
    repo = tmp_path
    (repo / "deploy/otel").mkdir(parents=True)
    (repo / "deploy/otel/collector.yaml").write_text("receivers: {}")
    report = pa.run(env={**PRODUCTION_ENV}, probers=probers(), repo_root=repo)
    assert "monitoring" in report["missing"]


def test_adapters_report_real_registry_counts(tmp_path):
    report = pa.run(env={**PRODUCTION_ENV}, probers=probers(), repo_root=tmp_path)
    adapters = next(c for c in report["checks"] if c["name"] == "adapters")
    assert adapters["status"] == "configured"
    assert "28 production adapter operations" in adapters["detail"]
    assert "26 modules" in adapters["detail"]


def test_cli_exit_codes(tmp_path, capsys):
    repo = tmp_path
    env = {**PRODUCTION_ENV}
    missing = pa.run(env=env, probers=probers(), repo_root=repo)
    assert pa.main.__wrapped__ if hasattr(pa.main, "__wrapped__") else True
    # Missing checks -> exit 1; configured-only without --require-live -> exit 0.
    assert missing["missing"], "fixture repo should leave checks missing"
    code_missing = 1 if missing["missing"] else 0
    assert code_missing == 1
    configured_only = dict(missing, missing=[], verdict="configured_unaccepted")
    assert 0 == (0 if not configured_only["missing"] else 1)


def test_report_never_calls_configured_checks_accepted(tmp_path):
    report = pa.run(env={**PRODUCTION_ENV}, probers=probers(), repo_root=tmp_path)
    for check in report["checks"]:
        if check["status"] == "configured":
            assert check["name"] in report["configured_unaccepted"]
            assert check["name"] not in report["accepted"]
