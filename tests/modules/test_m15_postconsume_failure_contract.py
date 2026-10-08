"""Real LaTeX render, one-shot SQL approval and faulted delivery stages."""
import pytest
from test_m15_approved_delivery import env,approve,REPORT
from app.modules.m15_document_generator import delivery

@pytest.mark.parametrize('stage',['put','save','sign'])
def test_consumed_failure_reports_unknown_and_never_replays(env,monkeypatch,stage):
    aid,version=approve(env,'latex',REPORT)
    original=getattr(env.store,stage)
    def fail(*a,**kw): raise OSError('synthetic storage failure')
    monkeypatch.setattr(env.store,stage,fail)
    expected=getattr(delivery,'DeliveryOutcomeUnknown',delivery.DeliveryError)
    with pytest.raises(expected,match='consumed') as caught:env.svc().deliver(aid)
    assert isinstance(caught.value.__cause__,OSError)
    assert [e['event'] for e in env.center.audit(aid)].count('effect_consumed')==1
    monkeypatch.setattr(env.store,stage,original)
    with pytest.raises(delivery.DeliveryConflict):env.svc().deliver(aid)
    if stage=='sign':assert env.svc().readback(aid)['download_url']
    else:assert env.store.get('tenant-a',aid) is None
