"""SQLite durability sub-unit, not original metacognition semantic closure."""
from datetime import datetime,timezone,timedelta
import pytest,sqlalchemy as sa
from app.modules.m20_general_cognitive_worker.meta_persistence import MetaRepository,DurableWorldModels,DurableEpistemicCalendar,DurableCuriosity,DurableMetaLearner
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository

def repo(tmp_path,tenant='a'):
 r=MetaRepository(sa.create_engine(f'sqlite:///{tmp_path}/meta.sqlite'),tenant_id=tenant);r.create_schema();return r

def test_world_restart_exact_and_tenant_isolation(tmp_path):
 a=DurableWorldModels.load(repo(tmp_path));a.register('m',{'x':'old'});a.revise('m',{'x':'new'});a.apply_evidence('m',supported=False,weight=2.5)
 b=DurableWorldModels.load(repo(tmp_path));assert b.models==a.models
 assert b.models['m'].version==2 and b.models['m'].log_odds==-2.5 and b.models['m'].posterior is None
 assert b.models['m'].history[0]['assumptions']=={'x':'old'}
 assert DurableWorldModels.load(repo(tmp_path,'b')).models=={}

def test_calendar_curiosity_restart_without_recompute(tmp_path):
 r=repo(tmp_path);cal=DurableEpistemicCalendar.load(r);now=datetime(2026,1,1,tzinfo=timezone.utc)
 b=cal.register('belief',formed_at=now,review_interval_days=3);cal.mark_reviewed(b.belief_id,now=now+timedelta(days=7))
 fresh=DurableEpistemicCalendar.load(repo(tmp_path));assert fresh.beliefs==cal.beliefs
 assert fresh.beliefs[b.belief_id].next_review()==now+timedelta(days=10)
 from app.modules.m20_general_cognitive_worker.semantic_memory import SemanticMemory
 c=DurableCuriosity.load(r);c.detect_gaps('zebra curious',SemanticMemory());c.detect_gaps('zebra',SemanticMemory())
 freshc=DurableCuriosity.load(repo(tmp_path));assert freshc._gap_counts=={'zebra':2,'curious':1}
 assert freshc.allocate(idle_budget=9)==c.allocate(idle_budget=9)

def test_write_failure_atomic_memory_and_sql(tmp_path,monkeypatch):
 r=repo(tmp_path);a=DurableWorldModels.load(r);a.register('m',{'x':'old'})
 from copy import deepcopy
 before=deepcopy(a.models)
 def fail(session):raise RuntimeError('injected before commit')
 monkeypatch.setattr(r,'_before_commit',fail)
 with pytest.raises(RuntimeError):a.revise('m',{'x':'new'})
 assert a.models==before and DurableWorldModels.load(repo(tmp_path)).models==before and a._revision==1

def test_stale_writer_refused(tmp_path):
 a=DurableWorldModels.load(repo(tmp_path));b=DurableWorldModels.load(repo(tmp_path));a.register('a',{})
 with pytest.raises(RuntimeError,match='stale'):b.register('b',{})
 assert b.models=={} and set(DurableWorldModels.load(repo(tmp_path)).models)=={'a'}

def test_service_optin_reuses_calibration_restart(tmp_path):
 r=repo(tmp_path);g=GCWRepository(r.engine,tenant_id='a');g.create_schema()
 s=CognitiveWorkerService(meta_repository=r,calibration_repository=g,seed_judgment_skills=False)
 claim=s.calibration.assess_claim('test',.8,evidence_count=7);s.calibration.resolve(claim.id,True);s.world_models.register('m',{})
 fresh=CognitiveWorkerService(meta_repository=repo(tmp_path),calibration_repository=g,seed_judgment_skills=False)
 assert fresh.calibration.claims==s.calibration.claims and fresh.world_models.models==s.world_models.models
 with pytest.raises(ValueError,match='tenant'):CognitiveWorkerService(meta_repository=r,calibration_repository=GCWRepository(r.engine,tenant_id='b'))

def test_migration_columns_composite_key_and_downgrade(tmp_path):
 import importlib.util
 from pathlib import Path
 from alembic.migration import MigrationContext
 from alembic.operations import Operations
 p=Path(__file__).resolve().parents[2]/'migrations/versions/20261011_m20_meta_state.py';spec=importlib.util.spec_from_file_location('migration',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 engine=sa.create_engine(f'sqlite:///{tmp_path}/migration.sqlite')
 with engine.begin() as c:
  m.op=Operations(MigrationContext.configure(c));m.upgrade();i=sa.inspect(c)
  assert {x['name']for x in i.get_columns('m20_meta_state')}=={'tenant_id','kind','revision','payload'}
  assert i.get_pk_constraint('m20_meta_state')['constrained_columns']==['tenant_id','kind']
  c.execute(sa.text("INSERT INTO m20_meta_state VALUES ('a','world',1,'{}')"))
  with pytest.raises(sa.exc.IntegrityError):c.execute(sa.text("INSERT INTO m20_meta_state VALUES ('a','world',2,'{}')"))
  m.downgrade();assert not sa.inspect(c).has_table('m20_meta_state')

def test_patterns_preserve_fields_duplicate_sources_and_tenant(tmp_path):
 from app.modules.m20_general_cognitive_worker.schemas import Episode,EpisodeOutcome,ActionRecord
 p=DurableMetaLearner.load(repo(tmp_path))
 episode=Episode(task_id='t',goal='research professors and draft outreach',actions=[ActionRecord(tool='web_search'),ActionRecord(tool='draft_email'),ActionRecord(tool='send_email')],outcome=EpisodeOutcome.SUCCEEDED)
 first=p.abstract(episode);p.abstract(episode)
 fresh=DurableMetaLearner.load(repo(tmp_path))
 assert fresh.patterns==p.patterns and next(iter(fresh.patterns.values())).successes==1
 assert first.source_episode_ids==[episode.id]
 assert DurableMetaLearner.load(repo(tmp_path,'b')).patterns=={}
 assert all(x['capability_executed'] is False for x in fresh.transfer('calculate astronomy'))

@pytest.mark.parametrize('wrapper,operation,args,kwargs',[
 (DurableEpistemicCalendar,'register',('new belief',),{}),
 (DurableCuriosity,'detect_gaps',('zebra',),{}),
])
def test_each_new_snapshot_write_rolls_back(tmp_path,monkeypatch,wrapper,operation,args,kwargs):
 r=repo(tmp_path);a=wrapper.load(r)
 if wrapper is DurableCuriosity:
  from app.modules.m20_general_cognitive_worker.semantic_memory import SemanticMemory
  args=(*args,SemanticMemory())
 def fail(session):raise RuntimeError('rollback')
 monkeypatch.setattr(r,'_before_commit',fail)
 with pytest.raises(RuntimeError):getattr(a,operation)(*args,**kwargs)
 assert a._revision==0 and r.read(a.kind)==(0,None)
 assert getattr(a,a.attribute)=={}

def test_invalid_payload_never_commits(tmp_path):
 r=repo(tmp_path)
 with pytest.raises(ValueError):r.write('world',0,{'invalid':float('nan')})
 assert r.read('world')==(0,None)

def test_mounted_restart_and_cross_tenant_binding_refused(tmp_path,monkeypatch,oidc_auth_headers):
 from fastapi.testclient import TestClient
 from app.main import app
 from app.modules.m20_general_cognitive_worker import routes
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_services',{})
 r=repo(tmp_path);g=GCWRepository(r.engine,tenant_id='a');g.create_schema()
 s=CognitiveWorkerService(meta_repository=r,calibration_repository=g,seed_judgment_skills=False)
 routes.bind_service(s,tenant_id='a')
 with pytest.raises(ValueError,match='tenant'):routes.bind_service(s,tenant_id='b')
 c=TestClient(app);path='/api/v1/api/modules/20/meta/world-models';h=oidc_auth_headers('a','owner')
 assert c.post(path,json={'name':'m','assumptions':{'x':'old'}}).status_code==401
 assert c.post(path,headers=h,json={'name':'m','assumptions':{'x':'old'}}).status_code==201
 assert c.post(path+'/m/revise',headers=h,json={'assumptions':{'x':'new'}}).status_code==200
 fresh=CognitiveWorkerService(meta_repository=repo(tmp_path),calibration_repository=g,seed_judgment_skills=False)
 routes.bind_service(fresh,tenant_id='a');response=c.get(path,headers=h)
 assert response.status_code==200 and response.json()['models'][0]['version']==2
 assert response.json()['capability_executed'] is False
 assert c.get(path,headers=oidc_auth_headers('b','owner')).status_code==503

def test_existing_calibration_write_failure_does_not_publish(tmp_path,monkeypatch):
 from app.modules.m20_general_cognitive_worker.persistence import DurableCalibrationEngine
 r=repo(tmp_path);g=GCWRepository(r.engine,tenant_id='a');g.create_schema();a=DurableCalibrationEngine.load(g)
 claim=a.assess_claim('text',.3,evidence_count=9)
 def fail(claim):raise RuntimeError('failed claim commit')
 monkeypatch.setattr(g,'save_claim',fail)
 with pytest.raises(RuntimeError):a.resolve(claim.id,True)
 assert a.claims[claim.id].resolved is False
 assert DurableCalibrationEngine.load(GCWRepository(r.engine,tenant_id='a')).claims[claim.id].resolved is False
 assert DurableCalibrationEngine.load(GCWRepository(r.engine,tenant_id='b')).claims=={}
