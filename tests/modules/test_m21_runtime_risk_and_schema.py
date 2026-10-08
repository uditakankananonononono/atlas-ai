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
    assert _alembic(db, "downgrade", "20261008_m16_view_version").returncode == 0
    assert "claire_runtime_goals" not in inspect(create_engine(f"sqlite:///{db}")).get_table_names()
    assert _alembic(db, "upgrade", "20261008_m21_runtime_revoke").returncode == 0  # CONVERTED slice 12 (was slice 10 designated, slice 6 cancel): the model now has designated_approvers too, so the store needs the head revision to write a row; still covers 'a non-empty goals table is never dropped'
    store = GoalStore(f"sqlite:///{db}")
    store.create("t", "a", "p", [{"kind": "tool_receipt", "tool": "x", "min_count": 1}], 1)
    store.close()
    r = _alembic(db, "downgrade", "20261008_m16_view_version")
    assert r.returncode != 0 and "holds goal evidence" in r.stderr
    assert "claire_runtime_goals" in inspect(create_engine(f"sqlite:///{db}")).get_table_names()


def _prepare_at_previous_head(db):
    assert _alembic(db, "upgrade", "20261008_m16_view_version").returncode == 0


def test_upgrade_refuses_a_preexisting_wrong_shape_table(tmp_path):
    db = tmp_path / "w.sqlite"
    _prepare_at_previous_head(db)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE claire_runtime_goals (id TEXT PRIMARY KEY)")
    con.commit(); con.close()
    r = _alembic(db, "upgrade", "20261008_m21_runtime_goals")
    assert r.returncode != 0 and "incompatible shape" in r.stderr and "missing column tenant_id" in r.stderr
    con = sqlite3.connect(db)
    assert con.execute("select version_num from alembic_version").fetchone()[0] == "20261008_m16_view_version"  # not stamped
    assert [row[1] for row in con.execute("pragma table_info('claire_runtime_goals')")] == ["id"]  # untouched
    con.close()


def test_upgrade_refuses_wrong_nullability_extra_column_or_missing_index(tmp_path):
    for variant, sql in {
        "nullable": "tenant_id VARCHAR(200)",
        "extra": "tenant_id VARCHAR(200) NOT NULL, rogue TEXT",
        "noindex": "tenant_id VARCHAR(200) NOT NULL",
    }.items():
        db = tmp_path / f"{variant}.sqlite"
        _prepare_at_previous_head(db)
        base = ("id VARCHAR(36) NOT NULL PRIMARY KEY, {t}, actor_id VARCHAR(200) NOT NULL, purpose TEXT NOT NULL, criteria TEXT NOT NULL, "
                "max_steps INTEGER NOT NULL, status VARCHAR(20) NOT NULL, attempts INTEGER NOT NULL, lease_owner VARCHAR(100), "
                "lease_token VARCHAR(64), lease_expires_at VARCHAR(40), blocker VARCHAR(100), report TEXT, verdict TEXT, "
                "created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL").format(t=sql)
        con = sqlite3.connect(db)
        con.execute(f"CREATE TABLE claire_runtime_goals ({base})")
        if variant != "noindex":
            for n, c in (("tenant_id", "tenant_id"), ("actor_id", "actor_id"), ("status", "status")):
                con.execute(f"CREATE INDEX ix_claire_runtime_goals_{n} ON claire_runtime_goals ({c})")
        con.commit(); con.close()
        r = _alembic(db, "upgrade", "20261008_m21_runtime_goals")
        assert r.returncode != 0 and "incompatible shape" in r.stderr, variant


def test_upgrade_noops_and_stamps_a_preexisting_correct_table(tmp_path):
    db = tmp_path / "c.sqlite"
    _prepare_at_previous_head(db)
    store = GoalStore(f"sqlite:///{db}", create_schema=True)  # older create_all rollout, correct shape
    gid = store.create("t", "a", "p", [{"kind": "tool_receipt", "tool": "x", "min_count": 1}], 1)
    store.close()
    assert _alembic(db, "upgrade", "20261008_m21_runtime_goals").returncode == 0
    con = sqlite3.connect(db)
    assert con.execute("select version_num from alembic_version").fetchone()[0] == "20261008_m21_runtime_goals"
    assert con.execute("select count(*) from claire_runtime_goals where id=?", (gid,)).fetchone()[0] == 1  # data kept
    con.close()
