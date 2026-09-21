from types import SimpleNamespace
import pytest
from app.workers import action_registry
from app.workers.tasks import execute_approved_action

def test_registered_executor_is_required_and_receives_exact_approved_payload(monkeypatch):
 action_registry._EXECUTORS.clear(); view={'status':SimpleNamespace(value='approved'),'module_id':5,'action_type':'send_email','payload':{'to':'owner@example.test'},'user_id':'tenant'}
 service=SimpleNamespace(get=lambda _:view,consume_effect=lambda *a,**k:{'effect_id':k['effect_id']})
 monkeypatch.setattr('app.modules.m00_approval_center.service.default_service',lambda:service)
 with pytest.raises(LookupError): execute_approved_action.run('a','effect-1')
 action_registry.register_executor(5,'send_email',lambda payload:{'sent_to':payload['to']})
 out=execute_approved_action.run('a','effect-1');assert out['status']=='executed' and out['result']=={'sent_to':'owner@example.test'}
