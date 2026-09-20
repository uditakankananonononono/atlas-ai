from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m02_competition_manager.onboarding import OnboardingService
def services(tmp_path):
 e=create_engine(f"sqlite:///{tmp_path/'o.db'}");Base.metadata.create_all(e);s=sessionmaker(bind=e);return OnboardingService('a',s),OnboardingService('b',s)
def test_launch_proactively_asks_for_writings_essays_and_activities_then_stops_after_completion(tmp_path):
 a,b=services(tmp_path);step=a.launch_step();assert step['show'] and step['requested_document_types']==['writings','essays','activity_descriptions'] and step['skip_available']
 done=a.complete(['writings','essays','activity_descriptions'],['doc1','doc2']);assert done['application_pipeline_ready']
 assert a.launch_step()=={'show':False,'completed':True,'skipped':False}
 assert b.launch_step()['show'] is True
def test_skip_is_respected_but_warns_drafting_unavailable(tmp_path):
 a,_=services(tmp_path);out=a.skip();assert 'unavailable' in out['warning'];assert a.launch_step()=={'show':False,'completed':False,'skipped':True}
def test_onboarding_rejects_unknown_types_or_fake_empty_index(tmp_path):
 a,_=services(tmp_path)
 for types,ids in [(['college_records'],['x']),(['writings'],[])]:
  try:a.complete(types,ids)
  except ValueError:pass
  else:raise AssertionError
