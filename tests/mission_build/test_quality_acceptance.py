import copy
import pytest
from app.mission_build.quality_program import compare
from app.mission_build.acceptance import inspect_manifest


def test_executed_comparison_rejects_module_regression_and_zero_denominator():
    tasks=[{'id':'a','module':'m1','input':1,'expected':2},{'id':'b','module':'m2','input':2,'expected':3}]
    r=compare(tasks,lambda x:2,lambda x:3)
    assert r['any_module_regressed'] and not r['scoped_acceptance']
    assert r['by_module']['m2']['accuracy_ratio'] is None
    assert not r['million_fold_improvement_established']
    r=compare(tasks,lambda x:0,lambda x:x+1)
    assert r['scoped_acceptance'] and r['executed_cases']==2


def test_adapter_error_and_snapshot_isolation():
    tasks=[{'id':'a','module':'m1','input':{'a':1},'expected':2}];before=copy.deepcopy(tasks)
    def fail(x):x['a']=99;raise RuntimeError('broken')
    r=compare(tasks,fail,lambda x:x['a']+1)
    assert r['any_execution_error'] and not r['scoped_acceptance'] and tasks==before


def manifests():
    e={'id':'concept1','module':'m20','implementation_id':'function1','source_ref':'instinct-doc:36',
       'new_after_baseline':True,'source_sha256':'a'*64,'test_sha256':'b'*64,'test_nodes':['tests/test_a.py::test_a']}
    r={'node_id':'tests/test_a.py::test_a','result':'passed','source_sha256':'a'*64,'test_sha256':'b'*64}
    return e,r


def test_manifest_cannot_close_1000_or_twenty_each_with_padding():
    e,r=manifests();alias=dict(e,id='concept2')
    out=inspect_manifest([e,alias],[r],expected_modules=['m20','m21'],per_module=20,required_concepts=1000)
    assert out['accepted_count']==1 and out['concept_deficit']==999
    assert out['module_deficits']=={'m20':19,'m21':20}
    assert out['entries'][1]['gaps']==['duplicate implementation alias']
    assert not out['literal_requirement_closed']


@pytest.mark.parametrize('result',['skipped','failed','error'])
def test_not_passed_receipts_do_not_count(result):
    e,r=manifests();r['result']=result
    assert inspect_manifest([e],[r],required_concepts=1000)['accepted_count']==0


def test_stale_digest_missing_sources_and_no_fake_boolean_pass():
    e,r=manifests();r['source_sha256']='c'*64
    assert inspect_manifest([e],[r])['accepted_count']==0
    e,r=manifests();del e['source_ref']
    assert inspect_manifest([e],[r])['accepted_count']==0
    e,r=manifests();r['result']=True
    with pytest.raises(ValueError):inspect_manifest([e],[r])
