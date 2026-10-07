"""Real-PG session persistence CAS only; no browser/submission/auth acceptance."""
import json
import os
import subprocess
import sys
import textwrap
import pytest

SCRIPT = textwrap.dedent('''
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.modules.m13_browser_agent.application_store import SQLApplicationSessionStore, ApplicationSessionRow
    from app.modules.m13_browser_agent.application_flow import ApplicationSession, SessionRevisionConflict
    from app.core.database import SessionLocal
    import json
    store = SQLApplicationSessionStore()
    store.create(ApplicationSession(tenant_id="a", session_id="s", actor_id="u", url="https://example.invalid"))
    barrier = Barrier(2)
    def race(label):
        writer = SQLApplicationSessionStore()
        record = writer.get("a", "s")
        record.label = label
        barrier.wait(timeout=10)
        try:
            writer.save(record)
            return "saved"
        except SessionRevisionConflict:
            assert record.revision == 0
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(race, ["one", "two"]))
    assert sorted(outcomes) == ["conflict", "saved"], outcomes
    final = store.get("a", "s")
    assert final.revision == 1 and final.label in {"one", "two"}
    foreign = ApplicationSession.from_dict({**final.to_dict(), "tenant_id": "b", "label": "foreign"})
    try:
        store.save(foreign)
    except SessionRevisionConflict:
        pass
    else:
        raise AssertionError("foreign write accepted")
    assert store.get("a", "s").label == final.label and store.get("b", "s") is None
    # Existing JSON rows have no revision field: load as zero, atomically save once.
    legacy = ApplicationSession(tenant_id="a", session_id="legacy", actor_id="u", url="https://example.invalid").to_dict()
    del legacy["revision"]
    with SessionLocal.begin() as db:
        db.add(ApplicationSessionRow(tenant_id="a", session_id="legacy", data=legacy))
    old = store.get("a", "legacy")
    stale = store.get("a", "legacy")
    assert old.revision == 0
    store.save(old)
    try:
        store.save(stale)
    except SessionRevisionConflict:
        pass
    else:
        raise AssertionError("stale legacy write accepted")
    print(json.dumps({"race": sorted(outcomes), "revision": final.revision, "legacy_revision": store.get("a", "legacy").revision}))
''')


def test_session_cas_on_postgres(tmp_path):
    pgserver = pytest.importorskip("pgserver")
    pytest.importorskip("psycopg")
    server = pgserver.get_server(tmp_path / "pg", cleanup_mode="stop")
    url = server.get_uri().replace("postgresql://", "postgresql+psycopg://")
    env = {**os.environ, "ATLAS_DATABASE_URL": url, "ATLAS_ENV": "production", "PYTHONPATH": "backend"}
    migration = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, capture_output=True, text=True, timeout=120)
    assert migration.returncode == 0, migration.stderr[-1000:]
    run = subprocess.run([sys.executable, "-c", SCRIPT], env=env, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr[-1500:]
    assert json.loads(run.stdout.strip().splitlines()[-1]) == {"race": ["conflict", "saved"], "revision": 1, "legacy_revision": 1}
