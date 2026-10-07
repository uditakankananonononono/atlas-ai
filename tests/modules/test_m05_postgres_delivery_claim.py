"""M05 durable claim concurrency on real PG. No sender or network invocation."""
import json
import os
import subprocess
import sys
import textwrap
import pytest
SCRIPT=textwrap.dedent('''
    from datetime import datetime,timezone
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing
    import json
    from app.modules.m05_outreach_manager.campaigns import OutreachMessage,MessageEvent
    from app.modules.m05_outreach_manager.sql_repository import SqlCampaignRepository
    now=datetime.now(timezone.utc)
    repo=SqlCampaignRepository("a")
    candidate=OutreachMessage(id="m",campaign_id="c",contact_id="u",sequence=1,subject="fixture",body="fixture",status="approved",approval_id="ap",created_at=now,updated_at=now)
    event=MessageEvent(message_id="m",event="delivery_claimed",at=now)
    repo.save_message(candidate,MessageEvent(message_id="m",event="approved",at=now))
    assert not SqlCampaignRepository("b").claim_delivery(candidate,event)
    assert not repo.claim_delivery(candidate.model_copy(update={"version":99}),event)
    assert not repo.claim_delivery(candidate.model_copy(update={"approval_id":"wrong"}),event)
    sibling=candidate.model_copy(update={"id":"other"})
    repo.save_message(sibling,MessageEvent(message_id="other",event="approved",at=now))
    def claim(_):
        # Each process creates an independent DB engine, pool and repository.
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.core.database import DATABASE_URL, engine as inherited_engine
        inherited_engine.dispose(close=False)  # discard inherited pool, never close parent sockets
        engine=create_engine(DATABASE_URL)
        try:
            return SqlCampaignRepository("a",sessionmaker(bind=engine,expire_on_commit=False)).claim_delivery(candidate,event)
        finally:engine.dispose()
    with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context("fork")) as pool:
        outcomes=list(pool.map(claim,[1,2]))
    assert sorted(outcomes)==[False,True],outcomes
    assert repo.get_message("m").status=="sending"
    assert repo.get_message("other").status=="approved" and repo.get_message("other").version==1
    # Crash after claim/before effect: a new process/store refuses blind retry.
    assert not SqlCampaignRepository("a").claim_delivery(candidate,event)
    # Status corruption/legacy stale restore cannot delete the independent claim.
    repo.save_message(candidate,MessageEvent(message_id="m",event="stale_restore",at=now))
    assert not SqlCampaignRepository("a").claim_delivery(candidate,event)
    print(json.dumps({"outcomes":sorted(outcomes),"claim_events":sum(e.event=="delivery_claimed" for e in repo.events("m"))}))
''')

def test_m05_delivery_claim_real_pg_multiprocess(tmp_path):
    pgserver=pytest.importorskip("pgserver");psycopg=pytest.importorskip("psycopg")
    if sys.platform!="linux":pytest.skip("fork concurrency fixture is Linux-only")
    server=pgserver.get_server(tmp_path/"pg",cleanup_mode="stop");uri=server.get_uri()
    env={**os.environ,"ATLAS_DATABASE_URL":uri.replace("postgresql://","postgresql+psycopg://"),"ATLAS_ENV":"production","PYTHONPATH":"backend"}
    migrated=subprocess.run([sys.executable,"-m","alembic","upgrade","head"],env=env,capture_output=True,text=True,timeout=120)
    assert migrated.returncode==0,migrated.stderr[-1500:]
    # Fresh historical baseline may create current models. Also prove the new
    # migration recreates its table for an already-existing prior schema.
    previous=subprocess.run([sys.executable,"-m","alembic","downgrade","20260927_m21_owner_journal"],env=env,capture_output=True,text=True,timeout=120)
    assert previous.returncode==0,previous.stderr[-1000:]
    with psycopg.connect(uri) as conn:
        assert conn.execute("select to_regclass('m05_delivery_claims')").fetchone()[0] is None
    upgraded=subprocess.run([sys.executable,"-m","alembic","upgrade","head"],env=env,capture_output=True,text=True,timeout=120)
    assert upgraded.returncode==0,upgraded.stderr[-1000:]

    run=subprocess.run([sys.executable,"-c",SCRIPT],env=env,capture_output=True,text=True,timeout=120)
    assert run.returncode==0,run.stderr[-1800:]
    assert json.loads(run.stdout.strip().splitlines()[-1])=={"outcomes":[False,True],"claim_events":1}
    with psycopg.connect(uri) as conn:
        assert conn.execute("select tenant_id,message_id,approval_id from m05_delivery_claims").fetchall()==[("a","m","ap")]
