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

def test_voice_lora_requires_real_owner_samples_and_is_approval_gated():
 from app.core.approvals import ApprovalStore
 from app.modules.m21_claire.training import TrainingService
 a=ApprovalStore();s=TrainingService(a)
 with pytest.raises(ValueError):s.voice_dataset(['short']*49)
 dataset=s.voice_dataset([f'Owner writing sample {i} with real content.' for i in range(50)])
 p=s.propose_training(dataset,'llama3.1:8b','lora')
 assert p['status']=='pending' and p['payload']['example_count']==50 and p['payload']['publishing'] is False
 assert a.list()[0].action_type=='train_personalization_model'

def test_preference_dataset_needs_complete_real_rankings_and_minimum_signal():
 from app.core.approvals import ApprovalStore
 from app.modules.m21_claire.training import TrainingService
 s=TrainingService(ApprovalStore())
 with pytest.raises(ValueError):s.preference_dataset([{'options':['a','b'],'ranking':['a']}]*20)
 with pytest.raises(ValueError):s.preference_dataset([{'options':['a','b'],'ranking':['a','b']}]*19)
 d=s.preference_dataset([{'context':f'c{i}','options':['a','b'],'ranking':['b','a']} for i in range(20)])
 assert d.kind=='preference' and all(x['provenance']=='owner_ranked' for x in d.examples)
 assert s.propose_training(d,'local-ranking-model','pairwise')['status']=='pending'
