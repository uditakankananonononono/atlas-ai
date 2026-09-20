import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m21_claire.personalization import PersonalizationRepository

def repos(tmp_path):
 e=create_engine(f"sqlite:///{tmp_path/'p.db'}");Base.metadata.create_all(e);s=sessionmaker(bind=e);return PersonalizationRepository('a',s),PersonalizationRepository('b',s)
def test_decisions_corrections_and_owner_reasoning_retrieve_by_vector_and_tenant(tmp_path):
 a,b=repos(tmp_path)
 a.add('decision',{'decision':'Pick official API','reason':'more reliable','context':'tooling'},[1,0])
 a.add('correction',{'original':'Generic','correction':'Be direct','context':'email'},[.9,.1])
 a.add('reasoning_note',{'title':'Vendor choice','owner_authored_note':'I value audit logs'},[0,1])
 got=a.retrieve([1,0]);assert [x['kind'] for x in got[:2]]==['m21_decisions','m21_corrections'];assert b.retrieve([1,0])==[]
def test_rankings_and_weekly_reviews_are_real_persistent_signals(tmp_path):
 a,_=repos(tmp_path)
 assert a.add('ranking',{'context':'tools','options':['a','b'],'ranking':['b','a']})
 assert a.add('review',{'artifact_id':'x','rating':'good','note':'keep concise'})
def test_behavioral_telemetry_is_owner_opt_in_and_scope_limited(tmp_path):
 a,_=repos(tmp_path)
 with pytest.raises(PermissionError):a.log_telemetry('link_click',{'url':'x'})
 a.set_telemetry_consent(True,['link_click']);assert a.log_telemetry('link_click',{'url':'x'})
 with pytest.raises(PermissionError):a.log_telemetry('draft_edit_time',{'seconds':9})
 a.set_telemetry_consent(False,[])
 with pytest.raises(PermissionError):a.log_telemetry('link_click',{'url':'x'})
