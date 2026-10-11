import copy
import json
import random
import pytest
from app.modules.c30 import loop


def exp(i='a', tags=None, **kw):
    x = dict(id=i, hypothesis='fixture hypothesis', tags=['idea'] if tags is None else tags,
             expected_metric=dict(name='score', direction='higher'), runner='r',
             declared_seconds=2, effect='none', priority=0)
    x.update(kw)
    return x


def req(experiments=None, **kw):
    x = dict(as_of='2026-10-11', seed=42, budget=dict(max_experiments=50, max_total_seconds=600),
             experiments=experiments or [exp()], runners={'r': lambda e, rng: {'metric_value': 2.0}})
    x.update(kw)
    return x


def row(i='old', **kw):
    x = dict(id=i, as_of='2026-10-10', outcome='success', metric_name='score',
             direction='higher', metric_value=4.0, tags=['idea'], error=None, order_index=0)
    x.update(kw)
    return x


def refusal(x, code):
    with pytest.raises(ValueError) as e:
        loop.run(x)
    assert str(e.value).startswith('PLAN_REFUSED_' + code)


def test_order_novelty_then_priority_then_id():
    x = req([exp('z', ['new'], priority=1), exp('b', priority=100),
             exp('a', ['new'], priority=1), exp('mixed', ['idea','fresh'], priority=0)],
            prior_log=[row()])
    out = loop.run(x)
    assert [r['id'] for r in out['log'][1:]] == ['a','z','mixed','b']
    assert [r['order_index'] for r in out['log']] == list(range(5))


def test_seed_only_runner_not_order_and_deterministic():
    x = req([exp('b'), exp('a')], runners={'r': lambda e,rng: {'metric_value':rng.random()}})
    a = loop.run(x); b = loop.run(x)
    assert json.dumps(a,sort_keys=True) == json.dumps(b,sort_keys=True)
    assert a['log'][0]['metric_value'] == round(random.Random(42).random(),6)
    x['seed']=43; c=loop.run(x)
    assert [r['id'] for r in c['log']] == ['a','b']
    assert a['log'][0]['metric_value'] != c['log'][0]['metric_value']


def test_copy_prefix_nested_and_input_unchanged():
    prior=[row()]; x=req(prior_log=prior); before=copy.deepcopy(x['experiments'])
    out=loop.run(x)
    assert prior == [row()] and x['experiments']==before
    assert out['log'][:1] == prior and out['log'] is not prior
    out['log'][0]['tags'].append('changed')
    assert prior[0]['tags']==['idea']


def test_runner_cannot_mutate_input_or_internal_metadata():
    def mutate(e,rng):
        e['id']='bad';e['tags'].append('bad');return {'metric_value':1.0}
    x=req(runners={'r':mutate}); r=loop.run(x)
    assert r['log'][0]['id']=='a' and r['log'][0]['tags']==['idea']
    assert x['experiments']==[exp()]


@pytest.mark.parametrize('outcome',['success','failure'])
def test_terminal_suppression(outcome):
    r=row('a',as_of='2026-10-11',outcome=outcome,metric_value=2.0 if outcome=='success' else None,error=None if outcome=='success' else 'fail')
    x=req(prior_log=[r], runners={'r':lambda e,rng:pytest.fail('must not run')})
    out=loop.run(x)
    assert out['log']==[r] and out['suppressed_replays']==1 and out['tried']==0


def test_skipped_retry_and_index_continue():
    x=req(budget={'max_experiments':1,'max_total_seconds':1})
    first=loop.run(x);assert first['log'][0]['outcome']=='skipped_budget'
    second=loop.run(req(prior_log=first['log']))
    assert [r['outcome'] for r in second['log']]==['skipped_budget','success']
    assert [r['order_index'] for r in second['log']]==[0,1]


def test_count_budget_and_cheaper_after_expensive():
    out=loop.run(req([exp('a',declared_seconds=20),exp('b',declared_seconds=3),exp('c',declared_seconds=2)],budget={'max_experiments':1,'max_total_seconds':3}))
    assert [r['outcome'] for r in out['log']]==['skipped_budget','success','skipped_budget']
    assert (out['tried'],out['succeeded'],out['failed'],out['skipped'])==(1,1,0,2)
    assert out['declared_seconds_used']==3 and out['text']=='tried 1 of 3 defined experiments'


def test_exact_time_boundary_and_scope():
    r=loop.run(req(budget={'max_experiments':1,'max_total_seconds':2,'max_cash':0}))
    assert r['tried']==1 and r['declared_seconds_used']==2
    assert set(r['scope'])=={'implemented','not_implemented','data_source','as_of'}
    assert r['scope']['as_of']=='2026-10-11'


@pytest.mark.parametrize('key',['cash','approval_token','needs_approval','network','file_write','account'])
@pytest.mark.parametrize('value',[None,False,0,''])
def test_effect_keys_even_falsy_before_any_call(key,value):
    calls=[]
    x=req([exp('a'),exp('b',**{key:value})],runners={'r':lambda e,rng:calls.append(e)})
    refusal(x,'EFFECTFUL');assert calls==[]


@pytest.mark.parametrize('value',['spend',None,False,'network'])
def test_effect_must_none(value):refusal(req([exp(effect=value)]),'EFFECTFUL')


@pytest.mark.parametrize('cash',[1,-1,None,False,'0',float('nan')])
def test_budget_cash_refused(cash):refusal(req(budget={'max_experiments':1,'max_total_seconds':2,'max_cash':cash}),'EFFECTFUL')


@pytest.mark.parametrize('seed',[None,False,True,-1,2**63,1.2,'42'])
def test_bad_seed(seed):refusal(req(seed=seed),'BAD_TYPE')


def test_missing_seed_and_budget():
    x=req();del x['seed'];refusal(x,'BAD_TYPE')
    x=req();del x['budget'];refusal(x,'NOBUDGET')


@pytest.mark.parametrize('kw',[{'max_experiments':0,'max_total_seconds':2},{'max_experiments':True,'max_total_seconds':2},{'max_experiments':1,'max_total_seconds':0},{'max_experiments':1,'max_total_seconds':float('inf')}])
def test_bad_budget(kw):refusal(req(budget=kw),'BAD_TYPE')


@pytest.mark.parametrize('kw',[{'hypothesis':''},{'hypothesis':None},{'expected_metric':None},{'expected_metric':{}},{'expected_metric':{'name':'','direction':'higher'}}])
def test_hypothesis_metric_required(kw):refusal(req([exp(**kw)]),'NOHYPOTHESIS')


@pytest.mark.parametrize('kw',[{'tags':[]},{'tags':['x','x']},{'declared_seconds':False},{'declared_seconds':float('nan')},{'priority':float('inf')},{'runner':'missing'},{'surprise':1},{'expected_metric':{'name':'s','direction':'wrong'}}])
def test_bad_experiment(kw):refusal(req([exp(**kw)]),'BAD_TYPE')


def test_duplicates_and_unknown_request():
    refusal(req([exp(),exp()]),'BAD_TYPE')
    refusal(req(epsilon=.2),'BAD_TYPE')


@pytest.mark.parametrize('patch',[{'extra':1},{'order_index':True},{'metric_value':float('inf')},{'direction':'x'},{'tags':[]},{'outcome':'timeout'},{'error':False},{'metric_value':None}])
def test_bad_prior_rows(patch):refusal(req(prior_log=[row(**patch)]),'BAD_TYPE')


def test_duplicate_terminal_prior_refused():refusal(req(prior_log=[row(),row(order_index=1)]),'BAD_TYPE')


def test_prior_failure_schema_and_skips_dont_establish_novelty():
    p=row(outcome='skipped_budget',metric_value=None)
    r=loop.run(req([exp('b',['fresh'],priority=1),exp('a',priority=2)],prior_log=[p]))
    assert [x['id'] for x in r['log'][1:]]==['a','b']


def test_crash_isolation_error_cap_and_failed_budget():
    def f(e,rng):
        if e['id']=='a':raise RuntimeError('x'*300)
        return {'metric_value':3.0}
    r=loop.run(req([exp('a'),exp('b')],runners={'r':f}))
    assert r['failed']==1 and r['succeeded']==1 and r['declared_seconds_used']==4
    assert len(r['log'][0]['error'])==200


@pytest.mark.parametrize('value',[None,True,float('nan'),float('inf'),'1'])
def test_bad_runner_metric_is_failure(value):
    r=loop.run(req(runners={'r':lambda e,rng:{'metric_value':value}}));assert r['failed']==1


def test_metric_groups_direction_and_tag_counts():
    es=[exp('a'),exp('b',expected_metric={'name':'latency','direction':'lower'}),exp('c',expected_metric={'name':'score','direction':'lower'})]
    r=loop.run(req(es,prior_log=[row()]))
    assert len(r['metric_stats'])==3
    gs={(g['metric_name'],g['direction']):g for g in r['metric_stats']}
    assert gs['score','higher']['best']==4 and gs['score','higher']['worst']==2
    assert r['tag_counts']['idea']=={'defined':3,'tried_success':3,'tried_failure':0,'skipped_budget':0,'untried':0}


def test_unrecorded_guard(monkeypatch):
    monkeypatch.setattr(loop,'_append_record',lambda log,record:None)
    refusal(req(),'UNRECORDED')


def test_no_effect_entrypoints_or_host_imports():
    import ast
    from pathlib import Path
    tree=ast.parse(Path(loop.__file__).read_text())
    public=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and not n.name.startswith('_')]
    assert public==['run']
    imported=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert not any(m and ('m08' in m or 'self_improve' in m) for m in imported)


def test_count_guard_with_spare_time():
    r=loop.run(req([exp('a'),exp('b')],budget={'max_experiments':1,'max_total_seconds':100}))
    assert r['tried']==1 and [x['outcome'] for x in r['log']]==['success','skipped_budget']


def test_lower_direction_best_is_minimum():
    prior=[row(direction='lower',metric_value=7)]
    r=loop.run(req([exp(expected_metric={'name':'score','direction':'lower'})],prior_log=prior))
    assert r['metric_stats'][0]['best']==2 and r['metric_stats'][0]['worst']==7


def test_empty_supplied_set_reports_zero():
    x=req();x['experiments']=[]
    r=loop.run(x);assert r['text']=='tried 0 of 0 defined experiments' and r['log']==[]


def test_large_numeric_rejected_as_typed_refusal():
    refusal(req([exp(priority=10**500)]),'BAD_TYPE')


def test_seed_upper_boundary_accepted():
    assert loop.run(req(seed=2**63-1))['succeeded']==1


@pytest.mark.parametrize('field',['id','hypothesis','runner'])
def test_text_cap1000_accept1001_refuse(field):
    x=req();x['experiments'][0][field]='x'*1000
    if field=='runner':x['runners']={'x'*1000:lambda e,rng:{'metric_value':1}}
    assert loop.run(x)['succeeded']==1
    x['experiments'][0][field]='x'*1001
    with pytest.raises(ValueError,match='PLAN_REFUSED_TEXT_TOO_LONG:'+field):loop.run(x)


def test_tags_string_typed_refusal():refusal(req([exp(tags='idea')]),'BAD_TYPE:tags')


@pytest.mark.parametrize('error',['x'*201,123,False,None])
def test_prior_error_invalid_exact(error):
    refusal(req(prior_log=[row(outcome='failure',metric_value=None,error=error)]),'BAD_TYPE:error')


def test_prior_error200_accepted():
    assert loop.run(req(prior_log=[row(outcome='failure',metric_value=None,error='x'*200)]))['succeeded']==1


def test_seed0_accept_upper_exclusive():
    assert loop.run(req(seed=0))['succeeded']==1
    refusal(req(seed=2**63),'BAD_TYPE:seed')


def test_list_budget_refusal():refusal(req(budget=[]),'BAD_TYPE:budget')


@pytest.mark.parametrize('key,value',[('experiments','wrong'),('runners',[])])
def test_wrong_collections_separately(key,value):refusal(req(**{key:value}),'BAD_TYPE:experiments_or_runners')


@pytest.mark.parametrize('runners',[{' ':lambda e,rng:None},{'r':False}])
def test_runner_key_and_callable_separate(runners):refusal(req(runners=runners),'BAD_TYPE:runners')


@pytest.mark.parametrize('seconds',[0,-1])
def test_declared_seconds_nonpositive(seconds):refusal(req([exp(declared_seconds=seconds)]),'BAD_TYPE:declared_seconds')


def test_priority_missing_zero_negative_order():
    a=exp('b');del a['priority']
    out=loop.run(req([a,exp('a',priority=0),exp('c',priority=-1)]))
    assert [r['id'] for r in out['log']]==['a','b','c']


def test_exact_all_tag_counts_mixed_and_suppression():
    es=[exp('a',['x']),exp('b',['y']),exp('c',['x','y']),exp('d',['z']),exp('e',['z'])]
    prior=[row('e',as_of='2026-10-11',tags=['z'])]
    def runner(e,rng):
        if e['id']=='b':raise RuntimeError('fail')
        return {'metric_value':1}
    r=loop.run(req(es,prior_log=prior,runners={'r':runner},budget={'max_experiments':3,'max_total_seconds':100}))
    assert r['tag_counts']=={
        'x':dict(defined=2,tried_success=2,tried_failure=0,skipped_budget=0,untried=0),
        'y':dict(defined=2,tried_success=1,tried_failure=1,skipped_budget=0,untried=0),
        'z':dict(defined=2,tried_success=0,tried_failure=0,skipped_budget=1,untried=1)}
    assert r['suppressed_replays']==1 and r['tried']==3 and r['skipped']==1


def test_seconds_used_round6_exact():
    r=loop.run(req([exp(declared_seconds=0.123456789)]))
    assert r['declared_seconds_used']==0.123457


@pytest.mark.parametrize('tags', ['abc', ('a', 'b')])
def test_nonempty_nonlist_tags_exact_type_refusal(tags):
    with pytest.raises(ValueError) as error:
        loop.run(req([exp(tags=tags)]))
    assert str(error.value) == 'PLAN_REFUSED_BAD_TYPE:tags'


@pytest.mark.parametrize('tags', [[' '], [5]])
def test_tag_elements_exact_bad_type_refusal(tags):
    with pytest.raises(ValueError) as error:
        loop.run(req([exp(tags=tags)]))
    assert str(error.value) == 'PLAN_REFUSED_BAD_TYPE:tags'
