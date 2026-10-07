import pytest
from sqlalchemy import create_engine
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.risk_register import DurableRiskRegister


def test_risk_register_returned_snapshots_are_detached_and_never_grant_approval():
    engine=create_engine('sqlite:///:memory:')
    repo=GCWRepository(engine,tenant_id='fixture');repo.create_schema()
    register=DurableRiskRegister(repo)
    risk={'id':'r','cause':'fixture','severity':3,'occurrence':2,'detection':1,
          'owner':'owner','mitigation':'supplied','test':'supplied','evidence':['supplied']}
    first=register.create(goal='fixture',risks=[risk])
    risk['evidence'].append('caller mutation')
    first['report']['risks'][0]['evidence'].append('return mutation')
    current=register.get(first['id'])
    assert current['report']['risks'][0]['evidence']==['supplied']
    current['report']['risks'][0]['evidence'].append('get mutation')
    history=register.history(first['id']);history[0]['report']['risks'][0]['owner']='mutation'
    assert register.get(first['id'])['report']['risks'][0]['owner']=='owner'
    second=register.patch_risk(first['id'],'r',expected_revision=1,changes={'owner':'new'})
    assert second['revision']==2
    comparison=register.compare(first['id'],from_revision=1,to_revision=2)
    assert comparison['approval_granted'] is False and comparison['evidence_verified'] is False
    comparison['changed'][0]['fields']['owner']['after']='mutation'
    assert register.compare(first['id'],from_revision=1,to_revision=2)['changed'][0]['fields']['owner']['after']=='new'
    assert register.list()[0]['evidence_verified'] is False
    with pytest.raises(ValueError,match='revision conflict'):
        register.patch_risk(first['id'],'r',expected_revision=1,changes={'owner':'stale'})
    engine.dispose()
