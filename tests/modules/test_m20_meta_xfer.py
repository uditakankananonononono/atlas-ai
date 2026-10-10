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

def grouped_episode(domain='laboratory',ident='policy1'):
 return {'episode_id':ident,'domain':domain,'provenance':'fixture:observed:'+ident,'outcome':'succeeded','problem':{'objective':'dependency_safe_setup_continuity','tasks':['a','b','c','d'],'dependencies':[['a','d']],'groups':{'a':'red','b':'blue','c':'red','d':'red'}},'executed_order':['a','c','d','b']}

def grouped_target():
 return {'domain':'manufacturing','problem':{'objective':'dependency_safe_setup_continuity','tasks':['alpha','beta','gamma','omega'],'dependencies':[['alpha','omega']],'groups':{'alpha':'machine1','beta':'machine2','gamma':'machine1','omega':'machine1'}}}

def switches(plan,groups):return sum(groups[a]!=groups[b]for a,b in zip(plan,plan[1:]))

def test_induced_policy_transfers_beyond_retrieval_and_generic_topological_baseline(tmp_path):
 l=learner(tmp_path);record=l.learn(grouped_episode());r=l.transfer(grouped_target())
 assert record['learned_policy']=='prefer_previous_group_then_lexical'
 assert record['policy_mismatch_counts']=={'lexical_ready_first':3,'prefer_previous_group_then_lexical':0}
 assert r['plan']==['alpha','gamma','omega','beta']
 groups=grouped_target()['problem']['groups']
 assert switches(r['plan'],groups)==1<switches(['alpha','beta','gamma','omega'],groups)==2
 assert r['plan']!=grouped_episode()['executed_order'] and r['mapping']['learned_policy']==record['learned_policy']
 assert r['status']=='plan_candidate'and learner(tmp_path).transfer(grouped_target())==r
 # Same task structure but a different demonstrated policy must change target plan.
 other=grouped_episode(ident='lexical');other['executed_order']=['a','b','c','d']
 l2=learner(tmp_path,'other');assert l2.learn(other)['learned_policy']=='lexical_ready_first'
 assert l2.transfer(grouped_target())['plan']==['alpha','beta','gamma','omega']

def test_nondiscriminating_or_unsupported_demonstration_abstains(tmp_path):
 l=learner(tmp_path)
 e=grouped_episode();e['problem']['groups']={k:'same'for k in e['problem']['tasks']};e['executed_order']=['a','b','c','d']
 assert l.learn(e)['status']=='abstained'and l.patterns=={}
 e=grouped_episode();e['executed_order']=['b','a','c','d']
 assert l.learn(e)['status']=='abstained'and l.patterns=={}

@pytest.mark.parametrize('domain',['manufacturing','travel','publishing'])
def test_policy_transfer_heldout_quality_and_missing_group_abstention(tmp_path,domain):
 l=learner(tmp_path);l.learn(grouped_episode());d=grouped_target();d['domain']=domain
 r=l.transfer(d);assert switches(r['plan'],d['problem']['groups'])<switches(sorted(d['problem']['tasks']),d['problem']['groups'])
 assert all(r['plan'].index(a)<r['plan'].index(b)for a,b in d['problem']['dependencies'])
 d['problem']['groups'].pop('beta');assert l.transfer(d)['status']=='abstained'

def test_evidence_identity_fails_and_success_persistence_rollback(tmp_path,monkeypatch):
 l=learner(tmp_path);e=grouped_episode();e['outcome']='failed';assert l.learn(e)['status']=='excluded'
 l.learn(grouped_episode());fresh=learner(tmp_path);assert fresh.patterns==l.patterns
 altered=grouped_episode();altered['executed_order']=['a','b','c','d']
 with pytest.raises(ValueError,match='episode identity'):l.learn(altered)
 before=fresh.patterns.copy()
 def fail(session):raise RuntimeError('commit failure')
 monkeypatch.setattr(fresh.repo,'_before_commit',fail)
 with pytest.raises(RuntimeError):fresh.learn(grouped_episode('other','p2'))
 assert fresh.patterns==before==learner(tmp_path).patterns
