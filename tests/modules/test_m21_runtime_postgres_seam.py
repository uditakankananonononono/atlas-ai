"""Real ephemeral PG evidence; no learned model, live deployment or cutover."""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pgserver
import pytest
from sqlalchemy import create_engine, inspect, text
from app.modules.m21_claire.runtime.goals import GoalStore

CRITERIA = [{"kind":"tool_receipt", "tool":"lookup", "min_count":1}]


@pytest.fixture(scope="module")
def migrated_pg(tmp_path_factory):
    path = tmp_path_factory.mktemp("claire-pg")
    server = pgserver.get_server(path / "data", cleanup_mode="stop")
    url = server.get_uri().replace("postgresql://", "postgresql+psycopg://")
    env = {**os.environ, "ATLAS_DATABASE_URL":url, "PYTHONPATH":"backend", "ATLAS_ENV":"production"}
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "20261008_m21_runtime_revoke"],
                            env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    with engine.connect() as connection:
        version = connection.scalar(text("SELECT version()"))
        assert "PostgreSQL" in version
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261008_m21_runtime_revoke"
    print("ACTUAL_PG_VERSION:", version)
    print("MIGRATION_TARGET: 20261008_m21_runtime_revoke; create_all=False")
    yield url, engine
    engine.dispose()
    server.cleanup()


def test_real_pg_migration_current_claire_columns_and_unique_effect_key(migrated_pg):
    url, engine = migrated_pg
    schema = inspect(engine)
    assert {"cancel_requested_at", "designated_approvers"} <= {c["name"] for c in schema.get_columns("claire_runtime_goals")}
    assert {"revoked_at", "revoked_by"} <= {c["name"] for c in schema.get_columns("claire_runtime_approvals")}
    assert "resolved_by" in {c["name"] for c in schema.get_columns("claire_runtime_effects")}
    assert any(c["name"] == "uq_claire_runtime_effects_goal_key" and c["column_names"] == ["goal_id","idempotency_key"] for c in schema.get_unique_constraints("claire_runtime_effects"))


def test_real_pg_concurrent_claim_and_expired_token_fenced_after_reopen(migrated_pg):
    url, _ = migrated_pg
    now = [datetime(2026, 10, 9, tzinfo=timezone.utc)]
    first = GoalStore(url, clock=lambda:now[0], lease_seconds=10)
    second = GoalStore(url, clock=lambda:now[0], lease_seconds=10)
    gid = first.create("pg-tenant", "actor", "lookup pg", CRITERIA, 3)
    barrier = Barrier(2)
    def claim(pair):
        store, wid = pair
        barrier.wait(timeout=10)
        return store.claim(wid)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(claim, [(first,"one"),(second,"two")]))
        winning = [c for c in claims if c is not None]
        assert len(winning) == 1 and winning[0].goal_id == gid
        old = winning[0]
        now[0] += timedelta(seconds=11)
        first.close()
        fresh = GoalStore(url, clock=lambda:now[0], lease_seconds=10)
        try:
            new = fresh.claim("after-reopen")
            assert new and new.goal_id == gid and new.lease_token != old.lease_token
            assert not second.renew(old)
            assert not second.settle(old,"completed",blocker=None,report={},verdict=None)
            report = {"receipts":[{"tool":"lookup","ok":True,"content":{"value":"pg"}}]}
            assert fresh.settle(new,"completed",blocker=None,report=report,verdict={"accepted":True})
            assert fresh.get("other", "actor", gid) is None
            assert fresh.get("pg-tenant", "other", gid) is None
        finally: fresh.close()
        reopened = GoalStore(url)
        try:
            got = reopened.get("pg-tenant", "actor", gid)
            assert got["status"] == "completed" and got["attempts"] == 2
            assert got["report"]["receipts"][0]["content"] == {"value":"pg"}
        finally: reopened.close()
    finally: first.close(); second.close()


def test_real_pg_worker_real_tool_receipt_survives_separate_store(migrated_pg):
    import asyncio
    from pydantic import BaseModel
    from app.modules.m21_claire.runtime.engine import Engine
    from app.modules.m21_claire.runtime.worker import Worker
    from app.modules.m21_claire.runtime.tools import Tool, ReadOnlyToolRegistry
    from app.modules.m21_claire.runtime.types import AgentDecision, ToolCall
    class Args(BaseModel): key: str
    class Lookup(Tool):
        name, arguments_model = "lookup", Args
        def run(self, args): return {"value":args.key}
    class Script:
        async def decide(self, messages):
            if len(messages) == 2:
                return AgentDecision(tool_call=ToolCall(name="lookup",arguments={"key":"real-tool-pg"}))
            return AgentDecision(final="scripted model only")
    url, _ = migrated_pg
    producer = GoalStore(url)
    consumer = GoalStore(url)
    registry = ReadOnlyToolRegistry(); registry.register(Lookup())
    try:
        gid = producer.create("worker-tenant", "worker-actor", "lookup", CRITERIA, 3)
        assert asyncio.run(Worker(consumer, lambda c:Engine(Script(),registry), "worker").run_once()) == gid
    finally: producer.close(); consumer.close()
    fresh = GoalStore(url)
    try:
        got = fresh.get("worker-tenant","worker-actor",gid)
        assert got["status"] == "completed" and got["verdict"]["accepted"] is True
        assert got["report"]["receipts"][0]["content"] == {"value":"real-tool-pg"}
    finally: fresh.close()
