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

def test_decision_outcomes_close_the_learning_loop_and_stay_tenant_scoped(tmp_path):
 a,b=repos(tmp_path)
 decision_id=a.add('decision',{'decision':'Enter competition A','reason':'strong mission fit','context':'competitions'},[1,0])
 outcome_id=a.add_decision_outcome(decision_id,{'outcome':'Reached finalist round','rating':'better','lesson':'Mission-fit evidence was predictive','evidence':{'result_url':'https://example.test/result'}})
 history=a.decision_history(decision_id)
 assert history['decision']['reason']=='strong mission fit'
 assert history['outcomes'][0]['id']==outcome_id
 assert history['outcomes'][0]['lesson']=='Mission-fit evidence was predictive'
 with pytest.raises(KeyError):b.decision_history(decision_id)
 with pytest.raises(KeyError):b.add_decision_outcome(decision_id,{'outcome':'x','rating':'unknown','lesson':'x','evidence':{}})

def test_retrieved_decision_includes_outcome_lessons_for_future_recommendations(tmp_path):
 a,_=repos(tmp_path)
 decision_id=a.add('decision',{'decision':'Use an official API','reason':'reliability','context':'collectors'},[1,0])
 a.add_decision_outcome(decision_id,{'outcome':'No collection failures for 30 days','rating':'better','lesson':'Prefer stable versioned APIs','evidence':{'sample_days':30}})
 result=a.retrieve([1,0],1)[0]
 assert result['content']['outcomes'][0]['rating']=='better'
 assert result['content']['outcomes'][0]['lesson']=='Prefer stable versioned APIs'

def scoped(tmp_path,tenant='tenant-a',actor='actor-a'):
 from app.modules.m21_claire.personalization import ScopedPersonalizationRepository
 e=create_engine(f"sqlite:///{tmp_path/'scoped.db'}");Base.metadata.create_all(e)
 return ScopedPersonalizationRepository(tenant,actor,sessionmaker(bind=e))

def test_row2_decision_journal_has_reasoned_similarity_and_actor_isolation(tmp_path):
 a=scoped(tmp_path); other=scoped(tmp_path,actor='actor-b')
 a.add_decision('Use official API','stable and auditable','collectors',[1,0])
 other.add_decision('Scrape private pages','not permitted','collectors',[1,0])
 got=a.retrieve_decisions([1,0]);assert got==[{'decision_id':got[0]['decision_id'],'decision':'Use official API','reason':'stable and auditable','context':'collectors','similarity':1.0}]

def test_row3_correction_loop_returns_owner_few_shot_pair_and_rejects_noop(tmp_path):
 a=scoped(tmp_path);a.add_correction('Dear Sir or Madam','Hi Maya','email',[1,0])
 assert a.correction_examples([1,0])[0]['preferred_output']=='Hi Maya'
 with pytest.raises(ValueError):a.add_correction('same','same','email',[1,0])

def test_row4_voice_fine_tuning_is_hashed_local_approval_proposal():
 from app.core.approvals import ApprovalStore
 from app.modules.m21_claire.training import TrainingService
 s=TrainingService(ApprovalStore());d=s.voice_dataset([f'Owner-authored sample number {i} with enough text.' for i in range(50)])
 out=s.propose_training(d,'llama3.1:8b','lora');assert out['status']=='pending' and len(d.sha256)==64 and out['payload']['publishing'] is False

def test_row5_owner_reasoning_notes_never_capture_hidden_chain_of_thought(tmp_path):
 a=scoped(tmp_path)
 with pytest.raises(PermissionError):a.add_owner_reasoning('Choice','private thought',[1,0],False)
 a.add_owner_reasoning('Choice','I prefer reversible choices',[1,0],True)
 assert a.reasoning_templates([1,0])[0]['hidden_chain_of_thought'] is False

def test_row6_preference_ranking_computes_distinct_ordered_scores(tmp_path):
 a=scoped(tmp_path);a.add_ranking('tools',['api','browser','manual'],['api','browser','manual']);a.add_ranking('tools',['api','manual'],['manual','api'])
 score=a.preference_scores();assert score['api']>score['manual']>score['browser']
 with pytest.raises(ValueError):a.add_ranking('bad',['a','b'],['a'])

def test_row7_telemetry_is_explicit_scoped_and_never_hidden(tmp_path):
 a,_=repos(tmp_path)
 with pytest.raises(PermissionError):a.log_telemetry('link_click',{'url':'x'})
 a.set_telemetry_consent(True,['link_click']);assert a.log_telemetry('link_click',{'url':'x'})
 with pytest.raises(PermissionError):a.log_telemetry('tool_choice',{'tool':'x'})

def test_row8_cognitive_twin_combines_only_consented_actor_records(tmp_path):
 a=scoped(tmp_path);a.add_decision('A','reason','ctx',[1,0]);a.add_correction('x','y','ctx',[1,0]);a.add_owner_reasoning('t','note',[1,0],True);a.add_ranking('ctx',['a','b'],['b','a'])
 out=a.cognitive_twin_context([1,0]);assert set(out)=={'decisions','corrections','reasoning_notes','preference_scores','provenance','external_effects'} and out['external_effects']==[]

def test_row9_weekly_reinforcement_is_review_signal_not_silent_mutation(tmp_path):
 a=scoped(tmp_path);a.add_weekly_review('draft-1','good','Keep the opening');a.add_weekly_review('draft-2','unclear','Ask me first')
 out=a.weekly_signal();assert out['ratings']=={'good':1,'bad':0,'unclear':1} and out['requires_owner_approval_before_behavior_change']

def test_rows2_9_export_delete_and_tenant_actor_boundaries(tmp_path):
 a=scoped(tmp_path);b=scoped(tmp_path,tenant='tenant-b');a.add_decision('A','r','c',[1,0]);b.add_decision('B','r','c',[1,0])
 exported=a.export_data();assert exported['actor_id']=='actor-a' and exported['records']['m21_decisions'][0]['decision']=='A'
 assert a.delete_data()['deleted']['m21_decisions']==1 and a.retrieve_decisions([1,0])==[] and b.retrieve_decisions([1,0])[0]['decision']=='B'
