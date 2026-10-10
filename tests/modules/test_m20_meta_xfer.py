"""Cross-domain structural strategy induction and adapted dependency plans."""
import sqlalchemy as sa
import pytest
from app.modules.m20_general_cognitive_worker.meta_transfer import TransferLearner
from app.modules.m20_general_cognitive_worker.meta_persistence import MetaRepository

def learner(tmp_path,tenant='a'):
 r=MetaRepository(sa.create_engine(f'sqlite:///{tmp_path}/transfer.sqlite'),tenant_id=tenant);r.create_schema();return TransferLearner.load(r)

def episode(domain='cooking',ident='e1'):
 return {'episode_id':ident,'domain':domain,'provenance':'fixture:observed-execution:'+ident,'outcome':'succeeded','problem':{'objective':'precedence_safe_completion','tasks':['wash','cut','cook'],'dependencies':[['wash','cut'],['cut','cook']]},'executed_order':['wash','cut','cook']}

def target(domain='publishing'):
 return {'domain':domain,'problem':{'objective':'precedence_safe_completion','tasks':['print','edit','approve','draft'],'dependencies':[['draft','edit'],['edit','approve'],['approve','print']]}}

@pytest.mark.parametrize('domain',['publishing','deployment','construction'])
def test_heldout_disjoint_domain_structural_transfer_not_retrieval(tmp_path,domain):
 l=learner(tmp_path);source=l.learn(episode());r=l.transfer(target(domain))
 assert r['status']=='plan_candidate' and r['plan']==['draft','edit','approve','print']
 assert r['plan']!=episode()['executed_order'] and r['execution_authorized'] is False
 assert r['source_episode_ids']==['e1'] and r['source_provenance']==['fixture:observed-execution:e1']
 assert r['mapping']['source_roles']==['prerequisite','dependent']
 assert r['mapping']['target_dependencies']==target()['problem']['dependencies']
 assert r['invariants']==['every task appears once','each prerequisite precedes dependent']
 assert source['preconditions']==['finite acyclic dependencies over declared tasks']
 fresh=learner(tmp_path);assert fresh.transfer(target(domain))==r
 assert learner(tmp_path,'b').transfer(target(domain))['status']=='abstained'


def test_transfer_beats_no_transfer_and_literal_retrieval_baselines(tmp_path):
 l=learner(tmp_path);l.learn(episode());d=target()
 def valid(plan):
  return set(plan)==set(d['problem']['tasks'])and all(plan.index(a)<plan.index(b)for a,b in d['problem']['dependencies'])
 assert valid(l.transfer(d)['plan'])
 assert not valid(episode()['executed_order']) and not valid([])

def test_domain_labels_not_lexical_overlap_and_same_domain_rejected(tmp_path):
 l=learner(tmp_path);l.learn(episode('pipeline cooking'))
 assert l.transfer(target('pipeline publishing'))['status']=='plan_candidate'
 assert l.transfer(target('pipeline cooking'))['status']=='abstained'


def test_failed_duplicate_invalid_outcome_exclusion(tmp_path):
 l=learner(tmp_path);bad=episode();bad['outcome']='failed'
 assert l.learn(bad)['status']=='excluded' and l.patterns=={}
 bad=episode();bad['executed_order']=['cook','cut','wash']
 with pytest.raises(ValueError):l.learn(bad)
 first=l.learn(episode());assert l.learn(episode())==first and len(l.patterns)==1
 bad=episode();bad['domain']='changed'
 with pytest.raises(ValueError,match='episode identity'):l.learn(bad)


def test_unsupported_mapping_cycle_missing_task_abstains(tmp_path):
 l=learner(tmp_path);l.learn(episode())
 d=target();d['problem']['objective']='creative quality'
 assert l.transfer(d)['status']=='abstained'
 for problem in [dict(tasks=['a','b'],dependencies=[['a','b'],['b','a']],objective='precedence_safe_completion'),dict(tasks=['a'],dependencies=[['a','missing']],objective='precedence_safe_completion')]:
  assert l.transfer({'domain':'heldout','problem':problem})['status']=='abstained'


def test_stale_and_failed_commit_no_learning_publish(tmp_path,monkeypatch):
 a,b=learner(tmp_path),learner(tmp_path);a.learn(episode())
 with pytest.raises(RuntimeError,match='stale'):b.learn(episode(ident='e2'))
 assert b.patterns=={}
 fresh=learner(tmp_path)
 def fail(session):raise RuntimeError('rollback')
 monkeypatch.setattr(fresh.repo,'_before_commit',fail)
 with pytest.raises(RuntimeError):fresh.learn(episode('gardening','e2'))
 assert len(fresh.patterns)==len(learner(tmp_path).patterns)==1


def test_mounted_authenticated_persisted_transfer(tmp_path,monkeypatch,oidc_auth_headers):
 from fastapi.testclient import TestClient
 from app.main import app
 from app.modules.m20_general_cognitive_worker import meta_transfer_routes as routes
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_learners',{})
 routes.bind_learner(learner(tmp_path));c=TestClient(app);path='/api/v1/api/modules/20/meta-transfer';headers=oidc_auth_headers('a','owner')
 assert c.post(path+'/learn',json=episode()).status_code==401
 assert c.post(path+'/learn',headers=headers,json=episode()).status_code==200
 routes.bind_learner(learner(tmp_path))
 r=c.post(path+'/transfer',headers=headers,json=target());assert r.status_code==200 and r.json()['plan']==['draft','edit','approve','print']
 assert c.post(path+'/transfer',headers=oidc_auth_headers('b','owner'),json=target()).status_code==503
