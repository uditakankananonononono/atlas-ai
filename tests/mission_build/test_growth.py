import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m21_claire.personalization import ScopedPersonalizationRepository


def test_actor_outcome_denial_growth_restart_and_delete(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path}/owner.db');Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine)
    a=ScopedPersonalizationRepository('t','a',sessions);b=ScopedPersonalizationRepository('t','b',sessions)
    ident=a.add_decision('use API','stable','tool',[1,0])
    for method in (b.decision_history,lambda i:b.add_decision_outcome(i,{'outcome':'x','lesson':'x','rating':'better'})):
        with pytest.raises(KeyError):method(ident)
    a.add_decision_outcome(ident,{'outcome':'failed','lesson':'retry smaller','rating':'worse'})
    a.add_decision_outcome(ident,{'outcome':'worked','lesson':'retain fix','rating':'better','evidence':{'case':'c1'}})
    restarted=ScopedPersonalizationRepository('t','a',sessions)
    assert len(restarted.decision_history(ident)['outcomes'])==2
    report=restarted.growth_report()
    assert report['owner_reported_improvement_rate']==1 and report['decisions_with_outcome']==1
    assert not report['learned_model_improvement_verified'] and b.growth_report()['decision_count']==0
    assert restarted.delete_data()['deleted']['m21_decision_outcomes']==2
    assert restarted.growth_report()['owner_reported_improvement_rate'] is None


def test_no_forged_actor_or_unrecognized_rating(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path}/owner.db');Base.metadata.create_all(engine)
    a=ScopedPersonalizationRepository('t','a',sessionmaker(bind=engine))
    ident=a.add_decision('d','r','c',[1])
    for extra in [{'actor_id':'victim'},{'rating':'perfect'}]:
        with pytest.raises(ValueError):a.add_decision_outcome(ident,dict(outcome='x',lesson='x',rating='better',**extra) if 'rating' not in extra else dict(outcome='x',lesson='x',**extra))
