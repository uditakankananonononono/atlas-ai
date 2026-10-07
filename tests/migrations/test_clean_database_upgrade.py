import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_clean_database_upgrades_to_head_with_product_and_cognitive_tables(tmp_path):
    database=tmp_path/'clean.sqlite'
    env={**os.environ,'ATLAS_DATABASE_URL':f'sqlite:///{database}'}
    result=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,
                          text=True,capture_output=True,timeout=90)
    assert result.returncode==0,result.stderr
    with sqlite3.connect(database) as db:
        tables={row[0] for row in db.execute("select name from sqlite_master where type='table'")}
        revision=db.execute('select version_num from alembic_version').fetchone()[0]
        m01_columns={row[1] for row in db.execute("pragma table_info('m01_opportunities')")}
        task_columns={row[1] for row in db.execute("pragma table_info('m20_tasks')")}
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    expected_head=ScriptDirectory.from_config(Config('alembic.ini')).get_current_head()
    assert revision==expected_head
    assert {'match_engine','deadline_engine'} <= m01_columns
    assert {'m10_reviewer_public_keys','m10_reviewer_key_events'} <= tables
    assert {'m00_approval_requests','collection_sources','m20_tasks','m20_semantic_facts','m20_episodes','m22_install_proposals','m22_install_jobs','m22_tool_portfolio'} <= tables
    assert {'m20_risk_registers', 'm20_risk_revisions'} <= tables
    assert 'm20_action_records' in tables and 'runtime_metadata_json' in task_columns
    assert len(tables) >= 110


def test_historical_m20_revision_has_no_future_action_table_or_task_metadata(tmp_path):
 database=tmp_path/'historical.sqlite'
 env={**os.environ,'ATLAS_DATABASE_URL':f'sqlite:///{database}'}
 result=subprocess.run([sys.executable,'-m','alembic','upgrade','20260922_m20_runtime_schema'],env=env,text=True,capture_output=True,timeout=90)
 assert result.returncode==0,result.stderr
 with sqlite3.connect(database) as db:
  tables={row[0] for row in db.execute("select name from sqlite_master where type='table'")}
  columns={row[1] for row in db.execute("pragma table_info('m20_tasks')")}
 assert 'm20_action_records' not in tables and 'runtime_metadata_json' not in columns
 result=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,text=True,capture_output=True,timeout=90)
 assert result.returncode==0,result.stderr
 with sqlite3.connect(database) as db:
  assert db.execute("select name from sqlite_master where name='m20_action_records'").fetchone()
  assert 'runtime_metadata_json' in {row[1] for row in db.execute("pragma table_info('m20_tasks')")}
