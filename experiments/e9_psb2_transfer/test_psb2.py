import hashlib,json,sys
import pytest
from psb2_data import ROOT, PROBLEMS,NATIVE,task,split,freeze,io,manifest
import extended
import psb2_run as run
from psb2_run import backend,dsl,library

@pytest.mark.parametrize('name',PROBLEMS)
def test_no_input_leakage(name):
    train,test=split(name)
    key=lambda r:freeze([r[k] for k in sorted(r) if k.startswith('input')])
    assert not set(map(key,train)) & set(map(key,test))
    assert len(train)==200 and len(test)==1000

@pytest.mark.parametrize('name',PROBLEMS)
def test_witness_coverage(name):
    t=task(name,extended=True)
    assert all(extended.safe_apply(extended.WITNESSES[name],i,{})==o for i,o in t['train']+t['test'])

@pytest.mark.parametrize('name',PROBLEMS)
def test_snapshot_integrity(name):
    m=json.loads((ROOT/'manifest.json').read_text())
    for kind in ['edge','random-sample']:
        p=ROOT/'data'/name/(kind+'.jsonl')
        assert hashlib.sha256(p.read_bytes()).hexdigest()==m[str(p.relative_to(ROOT))]
    dm=json.loads((ROOT/'download_manifest.json').read_text())[name]
    assert len(dm['indices'])==4096 and len(set(dm['indices']))==4096
    assert dm['indices'][0]<10000 and dm['indices'][-1]>990000

def test_empty_output_not_discarded():
    assert extended.safe_apply(('suffix_max','retain_equal_original'),[[]],{})==[]
    assert dsl.safe_apply(('reverse',),(),{}) is None

def test_multiargument_output():
    assert extended.safe_apply(('pairs','matching_sum','first_pair'),[[5,7],12],{})==(5,7)

def test_no_whole_task_oracle_primitive():
    for name in PROBLEMS:
        t=task(name,extended=True)
        assert not any(all(extended.safe_apply((p,),i,{})==o for i,o in t['train']) for p in extended.OPS)

def test_backend_restores_exact_code():
    old=library.solve
    with backend(extended):assert library.solve is extended.solve
    assert library.solve is old

def test_size_matched_empty_random():
    assert library.random_lib(0,0)=={}

def test_witnesses_not_in_search_implementation():
    import inspect
    assert 'WITNESSES' not in inspect.getsource(extended.solve)
    assert 'WITNESSES' not in inspect.getsource(run.main)

def test_exact_no_candidates_from_one_fit_task():
    ts=[task(n) for n in NATIVE[:3]]
    lib,log=library.learn(ts,1000)
    assert lib=={} and log==[]

def test_budget_and_verification():
    t=task('basement',extended=True)
    p,n=extended.solve(t,{},1000)
    assert n<=1000 and p and extended.verify(t,p,{})
    assert not extended.verify(t,('sum',),{})

def test_train_only_within_control(monkeypatch):
    t=task('fuel-cost',extended=True)
    t['test']=[('secret','secret')]
    def check(shards,*args,**kwargs):
        assert all(('secret','secret') not in s['train']+s['test'] for s in shards)
        assert len(shards)==8
        return {},[]
    monkeypatch.setattr(library,'learn',check)
    assert run.within(t,1000,extended,0)==({},[])
