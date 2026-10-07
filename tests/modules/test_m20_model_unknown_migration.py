import os,subprocess,sys
import pytest

@pytest.mark.parametrize('kind',['sqlite','postgres'])
def test_model_unknown_upgrade_and_lossy_downgrade_hold(tmp_path,kind):
 if kind=='postgres':
  pgserver=pytest.importorskip('pgserver');pytest.importorskip('psycopg');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop');url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path / "migration.db"}'
 env={**os.environ,'ATLAS_DATABASE_URL':url,'ATLAS_ENV':'production','PYTHONPATH':'backend'}
 def run(args):return subprocess.run([sys.executable,*args],env=env,capture_output=True,text=True,timeout=120)
 result=run(['-m','alembic','upgrade','20261007_m20_risk_register']);assert result.returncode==0,result.stderr[-2000:]
 result=run(['-c',"""
from sqlalchemy import create_engine,text
import os
engine=create_engine(os.environ['ATLAS_DATABASE_URL'])
with engine.begin() as db:
 if "model_outcome_unknown" in {c["name"] for c in __import__("sqlalchemy").inspect(db).get_columns("m20_tasks")}:
  db.execute(text("ALTER TABLE m20_tasks DROP COLUMN model_outcome_unknown"))
 db.execute(text("INSERT INTO m20_tasks (id,tenant_id,goal,state,importance,plan_json,standup_notes_json,created_at,updated_at) VALUES ('legacy','fixture','fixture','blocked',3,'[]','[]',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
"""]);assert result.returncode==0,result.stderr[-2000:]
 result=run(['-m','alembic','upgrade','head']);assert result.returncode==0,result.stderr[-2000:]
 result=run(['-c',"""
from sqlalchemy import create_engine,text
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.model_adapters import FreeFirstPlannerModel
from app.core import model_catalog
from app.core.providers import ProviderOutcomeUnknown
import os
engine=create_engine(os.environ['ATLAS_DATABASE_URL']);repo=GCWRepository(engine,tenant_id='fixture')
assert not repo.load_task('legacy').model_outcome_unknown
async def unknown(*args,**kwargs):raise ProviderOutcomeUnknown('fixture')
model_catalog.generate_free_first=unknown
runtime=GCWRuntime(repo,planner_model=FreeFirstPlannerModel());ctx=runtime.submit_goal('fixture novel')
assert repo.load_task(ctx.id).model_outcome_unknown
fresh=GCWRuntime(GCWRepository(engine,tenant_id='fixture'),planner_model=FreeFirstPlannerModel())
assert fresh.run_task(ctx.id).model_outcome_unknown
"""]);assert result.returncode==0,result.stderr[-2000:]
 result=run(['-m','alembic','downgrade','20261007_m20_risk_register']);assert result.returncode!=0 and 'Cannot remove unresolved M20 model outcome holds' in result.stderr
 result=run(['-c',"""
from sqlalchemy import create_engine,text
import os
with create_engine(os.environ['ATLAS_DATABASE_URL']).connect() as db:
 assert db.execute(text('SELECT count(*) FROM m20_tasks WHERE model_outcome_unknown=true')).scalar()==1
 assert db.execute(text('SELECT version_num FROM alembic_version')).scalar()=='20261007_m20_model_unknown'
"""]);assert result.returncode==0,result.stderr[-2000:]
