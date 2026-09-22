import json, subprocess, sys
from pathlib import Path
from app.platform import health

def test_readiness_fails_closed_when_a_probe_raises():
    ready,checks=health.readiness(lambda:True,lambda:(_ for _ in ()).throw(ConnectionError()),lambda:True)
    assert not ready and checks=={"database":True,"redis":False,"migrations":True}

def test_local_compose_has_one_shot_migration_and_deep_probe():
    text=Path("deploy/local/docker-compose.yml").read_text()
    assert "service_completed_successfully" in text and "scripts/migrate.py" in text and "/ready" in text
    assert "ports: [\"8000:8080\"]" in text and "5432:" not in text and "6379:" not in text

def test_bootstrap_rejects_default_secrets_and_acceptance_is_honest(tmp_path):
    script=Path("scripts/bootstrap_local.sh").read_text(); assert "CHANGE_ME" in script and "config --quiet" in script
    out=tmp_path/"evidence.json"
    run=subprocess.run([sys.executable,"scripts/module_acceptance.py","--output",str(out)],check=True)
    data=json.loads(out.read_text()); assert len(data["modules"])==26
    assert all(row["live_acceptance"]=="not_run" and row["production_acceptance"]=="not_run" for row in data["modules"])
    assert len(data["evidence_sha256"])==64

def test_operations_docs_cover_restore_rotation_and_no_false_claims():
    text=Path("docs/operations/RUNBOOK.md").read_text().lower()
    for phrase in ("restore drill","credential leak","alembic head","do not prove"):
        assert phrase in text

def test_onboarding_names_no_external_effect_boundary():
    text=Path("frontend/components/onboarding/OnboardingChecklist.tsx").read_text()
    assert "Nothing here sends, publishes, submits or spends" in text
    assert "atlas:onboarding:complete" in text
