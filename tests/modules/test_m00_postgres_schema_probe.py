"""Pinned observed schema divergences, not proof of all M00 behaviors."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


def test_m00_catalog_after_real_pg_migrations(tmp_path):
    pgserver = pytest.importorskip("pgserver")
    psycopg = pytest.importorskip("psycopg")
    server = pgserver.get_server(tmp_path / "pg", cleanup_mode="stop")
    uri = server.get_uri()
    env = {**os.environ, "ATLAS_DATABASE_URL": uri.replace("postgresql://", "postgresql+psycopg://"), "ATLAS_ENV": "production", "PYTHONPATH": "backend"}
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr[-1000:]
    spec = importlib.util.spec_from_file_location("m00_probe", "scripts/audit/pg_schema_probe_m00.py")
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with psycopg.connect(uri) as conn:
        observed = module.probe(conn)
    (tmp_path / "observed-schema.json").write_text(json.dumps(observed, indent=2))
    print(json.dumps(observed, indent=2))
    request = observed["columns"]["m00_approval_requests"]
    assert request["id"] == "character varying"
    assert request["payload"] == "json"
    assert request["status"] == "character varying"
    assert "user_id" in request and "tenant_id" not in request
    assert "previous_hash" not in observed["columns"]["m00_approval_events"]
    assert observed["partitions"] == [] and observed["triggers"] == []
