"""Optional real PostgreSQL regressions. Set EFFECT_TEST_POSTGRES_URL.

Each test gets an isolated schema. No mocked driver, DDL or ledger methods.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import sqlalchemy as sa

from app.modules.m20_general_cognitive_worker.effect_ledger import EffectLedger, worker_identity


@pytest.fixture
def postgres_url():
    url = os.environ.get("EFFECT_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("set EFFECT_TEST_POSTGRES_URL for real PostgreSQL tests")
    schema = "effects_" + uuid.uuid4().hex
    admin = sa.create_engine(url)
    with admin.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    scoped = sa.engine.make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    try:
        yield scoped
    finally:
        with admin.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_postgres_long_hostname_owner_fits_original_schema(postgres_url):
    engine = sa.create_engine(postgres_url)
    try:
        ledger = EffectLedger(engine, "t")
        # The real encoder with maximal input, persisted to real VARCHAR(64).
        host = "h" * 255
        ledger.worker_id = worker_identity(host, 2147483647)
        res = ledger.reserve(task_id="T", node_id="N", tool="act", args={})
        assert ledger.get(res.effect_id)["owner"] == ledger.worker_id
        columns = {c["name"]: c for c in sa.inspect(engine).get_columns("m20_effect_ledger")}
        assert columns["owner"]["type"].length == 64
        assert len(ledger.worker_id) <= 64
    finally:
        engine.dispose()


def test_postgres_concurrent_first_boot(postgres_url):
    barrier = Barrier(2)
    def boot():
        engine = sa.create_engine(postgres_url)
        @sa.event.listens_for(engine, "before_cursor_execute")
        def synchronize(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().startswith("CREATE TABLE m20_effect_ledger"):
                barrier.wait(timeout=10)
        try:
            return EffectLedger(engine, "t").list()
        finally:
            engine.dispose()
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(boot) for _ in range(2)]
        assert [future.result(timeout=20) for future in futures] == [[], []]


def test_postgres_attempt_fence(postgres_url):
    engine = sa.create_engine(postgres_url)
    try:
        ledger = EffectLedger(engine, "t")
        old = ledger.reserve(task_id="T", node_id="N", tool="act", args={})
        assert ledger.release(old, "not run")
        live = ledger.reserve(task_id="T", node_id="N", tool="act", args={})
        ledger.mark_invoking(live)
        assert ledger.release(old, "stale") is False
        ledger.fail_safe(old, "stale")
        ledger.mark_indeterminate(old, "stale")
        assert ledger.get(live.effect_id)["state"] == "invoking"
        ledger.complete(live, "live receipt")
        assert ledger.get(live.effect_id)["result_summary"] == "live receipt"
    finally:
        engine.dispose()
