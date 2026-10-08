import os
import sqlite3
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect

from app.modules.m21_claire.models import RiskLevel
from app.modules.m21_claire.runtime.goals import Base, GoalStore
from app.modules.m21_claire.runtime.risk import claire_risk, effective_risk
from app.modules.m21_claire.runtime.types import ToolRisk


def test_mapping_is_complete_and_unknown_fails_closed():
    assert [claire_risk(r) for r in ToolRisk] == [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
    for bad in ("read", None, 0, "shell_command", object()):
        assert claire_risk(bad) is RiskLevel.HIGH


def test_model_claims_never_lower_review_level_but_can_raise_it():
    assert effective_risk(ToolRisk.EXECUTE, "read", "low", "safe", None, ToolRisk.READ) is RiskLevel.HIGH
    assert effective_risk(ToolRisk.WRITE, "low", "banana") is RiskLevel.MEDIUM
    assert effective_risk(ToolRisk.READ, "high") is RiskLevel.HIGH
    assert effective_risk(ToolRisk.READ, "execute") is RiskLevel.HIGH


def test_alembic_head_creates_runtime_goals_matching_the_model_and_store_works(tmp_path):
    db = tmp_path / "m.sqlite"
    env = {**os.environ, "ATLAS_DATABASE_URL": f"sqlite:///{db}"}
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, text=True, capture_output=True, timeout=110)
    assert r.returncode == 0, r.stderr
    insp = inspect(create_engine(f"sqlite:///{db}"))
    table = Base.metadata.tables["claire_runtime_goals"]
    assert {c["name"]: c["nullable"] for c in insp.get_columns("claire_runtime_goals")} == {c.name: c.nullable for c in table.columns}
    assert {i["name"] for i in insp.get_indexes("claire_runtime_goals")} >= {i.name for i in table.indexes}
    store = GoalStore(f"sqlite:///{db}")  # no create_all: the migrated schema is what runs
    gid = store.create("t", "a", "purpose", [{"kind": "tool_receipt", "tool": "x", "min_count": 1}], 3)
    assert store.get("t", "a", gid)["status"] == "queued" and store.get("t", "b", gid) is None
    store.close()


def test_store_without_migration_or_opt_in_does_not_create_tables(tmp_path):
    db = tmp_path / "n.sqlite"
    store = GoalStore(f"sqlite:///{db}")
    with pytest.raises(Exception) as e:
        store.create("t", "a", "p", [{"kind": "tool_receipt", "tool": "x", "min_count": 1}], 1)
    assert "no such table" in str(e.value)  # test asserts the failure text; production never echoes it
    store.close()
    assert sqlite3.connect(db).execute("select count(*) from sqlite_master").fetchone()[0] == 0


def _alembic(db, *args):
    env = {**os.environ, "ATLAS_DATABASE_URL": f"sqlite:///{db}"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], env=env, text=True, capture_output=True, timeout=110)


def test_runtime_goals_downgrade_drops_only_an_empty_table(tmp_path):
    db = tmp_path / "d.sqlite"
    assert _alembic(db, "upgrade", "20261008_m21_runtime_goals").returncode == 0
    assert _alembic(db, "downgrade", "20261008_m16_identity_forward").returncode == 0
    assert "claire_runtime_goals" not in inspect(create_engine(f"sqlite:///{db}")).get_table_names()
    assert _alembic(db, "upgrade", "20261008_m21_runtime_goals").returncode == 0
    store = GoalStore(f"sqlite:///{db}")
    store.create("t", "a", "p", [{"kind": "tool_receipt", "tool": "x", "min_count": 1}], 1)
    store.close()
    r = _alembic(db, "downgrade", "20261008_m16_identity_forward")
    assert r.returncode != 0 and "holds goal evidence" in r.stderr
    assert "claire_runtime_goals" in inspect(create_engine(f"sqlite:///{db}")).get_table_names()
