"""Row 849 mounted app tests. Same tests at supplied base and patched tree."""
import copy
import pytest
from fastapi.testclient import TestClient
from app.main import app

PATH = '/api/v1/modules/20/rows/849/run'
H = {'x-atlas-tenant':'row849', 'x-atlas-actor':'tester'}

def payload(**kw):
    p = {'facts':['bird'], 'rules':[{'id':'fly','if':['bird'],'unless':['penguin'],'then':'flies'}],
         'added_facts':['penguin'], 'removed_facts':[], 'query_atoms':['flies']}
    p.update(kw)
    return p

def call(p):
    return TestClient(app).post(PATH, json=p, headers=H)

def success(p):
    r=call(p)
    assert r.status_code == 200, r.text
    return r.json()

def test_row849_mounted_retracts_exception():
    r=success(payload())
    assert r['row']==849
    assert r['before']['stable_models']==[['bird','flies']]
    assert r['stable_models']==[['bird','penguin']]
    assert r['retracted_conclusions']==['flies']
    assert r['new_conclusions']==['penguin']
    assert r['queries'][0]['status']=='not_entailed'
    assert r['queries'][0]['not_entailed_does_not_mean_false'] is True

def test_row849_removal_restores_conclusion():
    r=success(payload(facts=['bird','penguin'],added_facts=[],removed_facts=['penguin']))
    assert r['stable_models']==[['bird','flies']]
    assert r['new_conclusions']==['flies']
    assert r['retracted_conclusions']==['penguin']

def test_row849_ambiguity_not_resolved():
    r=success(payload(facts=[],added_facts=[],rules=[{'id':'a','if':[],'unless':['b'],'then':'a'},
                    {'id':'b','if':[],'unless':['a'],'then':'b'}],query_atoms=['a']))
    assert r['stable_models']==[['b'],['a']]
    assert r['cautious_conclusions']==[]
    assert r['queries'][0]['status']=='ambiguous'
    assert r['default_priority_applied'] is False

def test_row849_inconsistency_not_spurious_retraction():
    r=success(payload(facts=[],added_facts=[],rules=[{'id':'r','if':[],'unless':['a'],'then':'a'}]))
    assert r['consistent'] is False
    assert r['revision_comparable'] is False
    assert r['retracted_conclusions'] is None and r['new_conclusions'] is None

def test_row849_no_change_and_boundary():
    r=success(payload(added_facts=[]))
    assert r['retracted_conclusions']==[] and r['new_conclusions']==[]
    assert r['no_real_world_truth_claim'] is True
    assert 'absence from a model is not falsity' in r['boundary']

@pytest.mark.parametrize('change,code',[
    ({'added_facts':['bird']},'ADDED_ALREADY_PRESENT'),
    ({'removed_facts':['absent']},'REMOVED_NOT_PRESENT'),
    ({'facts':['bird','bird']},'DUPLICATE:facts'),
    ({'rules':[]},'EMPTY:rules'),
    ({'added_facts':['x']*17},'TOO_MANY:added_facts'),
    ({'truth':True},'CONCLUSION_REFUSED'),
    ({'rules':[{'id':'big','if':[],'unless':[],'then':'x'*65}]},'TEXT_TOO_LONG:atom'),
    ({'facts':['bad\u200b']},'CONTROL_CHARS:atom'),
])
def test_row849_rejects_bad_revision(change,code):
    r=call(payload(**change))
    assert r.status_code==400, r.text
    assert r.json()=={'detail':'NONMON849:'+code}

def test_row849_optional_bound_before_search():
    rules=[{'id':str(i),'if':[],'unless':[],'then':str(i)} for i in range(13)]
    r=call(payload(facts=[],rules=rules,added_facts=[]))
    assert r.status_code==400, r.text
    assert r.json()=={'detail':'NONMON849:TOO_MANY:optional_atoms'}

def test_row849_production_identity_no_override(monkeypatch,oidc_auth_headers):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    monkeypatch.setenv('ATLAS_ENV','production')
    c=TestClient(app)
    assert c.post(PATH,json=payload()).status_code==401
    r=c.post(PATH,json=payload(),headers=oidc_auth_headers('row849','alice'))
    assert r.status_code==200,r.text
    assert r.json()['retracted_conclusions']==['flies']
