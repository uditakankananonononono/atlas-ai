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
    assert revision=='20260924_m22_install_pipeline'
    assert {'m00_approval_requests','collection_sources','m20_tasks','m20_semantic_facts','m20_episodes','m22_install_proposals','m22_install_jobs','m22_tool_portfolio'} <= tables
    assert len(tables) >= 110
