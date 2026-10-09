"""Registered executor/permit boundary backed by actual SQLite ledger."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service
from app.modules.m00_approval_center.execution import ExecutionRow
from app.workers import action_registry
from app.workers.tasks import execute_approved_action

def test_registered_executor_is_required_and_receives_exact_approved_payload(monkeypatch,tmp_path):
 monkeypatch.setattr(action_registry,'_EXECUTORS',{})
 engine=create_engine(f"sqlite:///{tmp_path}/worker.db");Base.metadata.create_all(engine)
 service=Service(session_factory=sessionmaker(bind=engine,expire_on_commit=False))
 view=service.submit(module_id=5,action_type='send_email',payload={'to':'owner@example.test'},user_id='tenant')
 service.decide(view['id'],ApprovalStatus.APPROVED,'fixture')
 monkeypatch.setattr('app.modules.m00_approval_center.service.default_service',lambda:service)
 with pytest.raises(LookupError):execute_approved_action.run(view['id'],'effect-1')
 assert [e['event'] for e in service.audit(view['id'])]==['created','approved']
 action_registry.register_executor(5,'send_email',lambda payload:{'sent_to':payload['to']})
 out=execute_approved_action.run(view['id'],'effect-1')
 assert out['status']=='executed' and out['result']=={'sent_to':'owner@example.test'}
