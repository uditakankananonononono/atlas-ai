"""Pytest-native smoke checks for the M19 qualification package.
Runs under the repo's native pytest config (pyproject: pythonpath=backend) with no
environment setup. The seven script suites in this directory are excluded from
collection (see conftest.py) and run standalone with M19_TREE/M19_DB."""
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
for _p in (str(REPO_ROOT), str(BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)  # revision modules import migrations.* and app.*


def test_migration_delivered_at_real_script_location():
    assert (REPO_ROOT / "migrations" / "versions" / "20261017_m19_runs.py").is_file()
    assert not (BACKEND / "migrations" / "versions" / "20261017_m19_runs.py").exists()


def test_migration_discovered_by_real_alembic_config():
    alembic_script = pytest.importorskip("alembic.script")
    import alembic.config
    cfg = alembic.config.Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    sd = alembic_script.ScriptDirectory.from_config(cfg)
    revs = {r.revision for r in sd.walk_revisions()}
    assert "20261017_m19_runs" in revs
    assert sd.get_revision("20261017_m19_runs").down_revision == "20261011_m20_meta_state"


def test_finite_safe_validation_handler_handles_nan_and_decimal():
    from fastapi import FastAPI
    from fastapi.exceptions import RequestValidationError
    from fastapi.testclient import TestClient
    from pydantic import BaseModel, Field
    from app.core.validation_errors import request_validation_error_handler

    class DecIn(BaseModel):
        amount: Decimal = Field(gt=0)

    class NanIn(BaseModel):
        cost: float = Field(gt=0)

    app = FastAPI()
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)

    @app.post("/dec")
    def dec(x: DecIn):
        return {"ok": True}

    @app.post("/nan")
    def nan(x: NanIn):
        return {"ok": True}

    c = TestClient(app, raise_server_exceptions=False)
    r1 = c.post("/dec", json={"amount": -5})
    r2 = c.post("/nan", data='{"cost": NaN}', headers={"content-type": "application/json"})
    assert r1.status_code == 422, r1.text
    assert r2.status_code == 422 and '"nan"' in r2.text, r2.text


def test_run_store_importable():
    from app.modules.m19_idea_incubator.run_store import InMemoryRunStore, SqlRunStore
    assert SqlRunStore is not None and InMemoryRunStore is not None
