"""Bound approval authority and conditional-dispatch acceptance. No provider effects."""
import copy
import pytest
from sqlalchemy import update
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.auth.context import TenantContext, require_tenant
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center import impact, routes
from app.modules.m00_approval_center.service import ApprovalConflictError
from app.modules.m10_email_assistant.sql_repository import EmailDraftRow, EmailMessageRow, GmailAccountRow
from tests.modules.test_m10_drift_probe import env, PAYLOAD, approve, consume, msg


def pending(env, **changes):
    svc, registry, gmail, sessions = env
    view = svc.submit(module_id=10, action_type='send_email_reply', payload={**PAYLOAD, **changes}, user_id='t1')
    with sessions.begin() as db:
        db.execute(update(EmailDraftRow).where(EmailDraftRow.id == 'd-1').values(approval_id=view['id']))
    return view


def test_bound_preview_cross_tenant_returns_no_foreign_state_and_zero_reads(env, monkeypatch):
    svc, registry, gmail, _ = env
    view = svc.submit(module_id=10, action_type='send_email_reply', payload=PAYLOAD, user_id='tenant-b')
    monkeypatch.setattr(routes, 'impact_preview', lambda s, aid: impact.impact_preview(s, aid, registry=registry))
    app = FastAPI();app.include_router(routes.router)
    app.dependency_overrides[routes.get_service] = lambda: svc
    app.dependency_overrides[require_tenant] = lambda: TenantContext('tenant-b','owner')
    with TestClient(app, raise_server_exceptions=False) as c:
        result = c.get(f"/approval-center/requests/{view['id']}/impact-preview")
    assert result.status_code == 409
    assert gmail.requests == []
    assert 'lab@uni.edu' not in result.text and 'd-1' not in result.text


@pytest.mark.parametrize('field,value', [('account_id','other'),('message_id','other'),('draft_id','other'),('gmail_id','other'),('thread_id','other'),('to','other'),('subject','other'),('body','other')])
def test_bound_capture_resource_and_content_mismatch_fails_before_external_reads(env, field, value):
    svc, registry, gmail, _ = env;view = pending(env, **{field:value})
    with pytest.raises((ApprovalConflictError, RuntimeError)):
        impact.capture_review_state(svc, view['id'], registry=registry)
    assert gmail.requests == []
    assert [e['event'] for e in svc.audit(view['id'])] == ['created']


@pytest.mark.parametrize('field,value', [('message_id','other'),('approval_id','other'),('account_id','other')])
def test_bound_capture_stored_draft_link_mismatch_refuses(env, field, value):
    svc, registry, gmail, sessions=env;view=pending(env)
    with sessions.begin() as db:db.execute(update(EmailDraftRow).where(EmailDraftRow.id=='d-1').values(**{field:value}))
    with pytest.raises(ApprovalConflictError):impact.capture_review_state(svc,view['id'],registry=registry)
    assert gmail.requests==[]


@pytest.mark.parametrize('invalid', ['missing-target','trashed-target','sent-draft','missing-draft'])
def test_bound_capture_initial_invalid_baseline_refuses(env, invalid):
    svc, registry, gmail, sessions=env;view=pending(env)
    if invalid=='missing-target':gmail.thread=[]
    if invalid=='trashed-target':gmail.thread[1]['labelIds']=['TRASH']
    if invalid in ('sent-draft','missing-draft'):
        with sessions.begin() as db:db.execute(update(EmailDraftRow).where(EmailDraftRow.id=='d-1').values(status='sent' if invalid=='sent-draft' else 'pending_approval',id='gone' if invalid=='missing-draft' else 'd-1'))
    with pytest.raises(ApprovalConflictError):impact.capture_review_state(svc,view['id'],registry=registry)
    with pytest.raises(ApprovalConflictError):svc.decide(view['id'],ApprovalStatus.APPROVED,'owner')


def test_bound_capture_explicit_state_and_forged_probe_marker_cannot_authorize(env):
    svc, registry, _, sessions=env;view=pending(env)
    with pytest.raises(ApprovalConflictError):impact.capture_review_state(svc,view['id'],state={'$approval_binding':impact.approval_context(view).binding()},registry=registry)
    with sessions.begin() as db:
        db.add(impact.ApprovalReviewStateRow(approval_id=view['id'],state={'$approval_binding':impact.approval_context(view).binding()},state_hash='x',probe='explicit',captured_at=svc._clock()))
    with pytest.raises(ApprovalConflictError):svc.decide(view['id'],ApprovalStatus.APPROVED,'owner')


def test_bound_legacy_approved_request_without_snapshot_refuses_direct_and_wrapper_consume(env):
    svc, registry, _, sessions=env;view=pending(env)
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    with sessions.begin() as db:db.get(ApprovalRequestRow,view['id']).status='approved'
    with pytest.raises(ApprovalConflictError):consume(svc,registry,view['id'])
    with pytest.raises(ApprovalConflictError):svc.consume_effect(view['id'],module_id=10,action_type='send_email_reply',payload=PAYLOAD,user_id='t1',effect_id='legacy',actor='worker')
    assert [e['event'] for e in svc.audit(view['id'])]==['created']


def test_bound_failed_capture_recovery_requires_fresh_snapshot_before_approval(env):
    svc, registry, gmail, _=env;view=pending(env);gmail.token_status=400
    with pytest.raises(RuntimeError):impact.capture_review_state(svc,view['id'],registry=registry)
    gmail.token_status=200;gmail.thread.append(msg('new',3000,'other@test.invalid'))
    with pytest.raises(ApprovalConflictError):svc.decide(view['id'],ApprovalStatus.APPROVED,'owner')
    impact.capture_review_state(svc,view['id'],registry=registry)
    svc.decide(view['id'],ApprovalStatus.APPROVED,'owner')
    assert consume(svc,registry,view['id'])['allowed']


def test_bound_missing_conditional_adapter_refuses_before_permit(env, monkeypatch):
    from app.workers import action_registry
    from app.workers.tasks import execute_approved_action
    svc, registry, _, _=env;aid=approve(svc,registry)
    monkeypatch.setattr(action_registry,'_CONDITIONAL_EXECUTORS',{})
    monkeypatch.setattr('app.modules.m00_approval_center.service.default_service',lambda:svc)
    with pytest.raises(ApprovalConflictError,match='conditional dispatch unavailable'):execute_approved_action.run(aid,'dispatch')
    assert 'effect_consumed' not in [e['event'] for e in svc.audit(aid)]


@pytest.mark.parametrize('change_at', ['none','before-read','after-read-before-permit','after-permit-before-dispatch','during-dispatch'])
def test_bound_actual_conditional_dispatch_enforces_version_at_effect(env, monkeypatch, change_at):
    import threading
    from app.workers import action_registry
    from app.workers.tasks import execute_approved_action
    svc, registry, gmail, _=env;aid=approve(svc,registry)
    monkeypatch.setattr('app.modules.m00_approval_center.impact.PROBES',registry)
    monkeypatch.setattr('app.modules.m00_approval_center.service.default_service',lambda:svc)
    monkeypatch.setattr(action_registry,'_CONDITIONAL_EXECUTORS',{})
    world={'version':1};effects=[];lock=threading.Lock()
    class Adapter:
        def dispatch_if_current(self,payload,condition):
            with lock:
                if change_at in ('after-permit-before-dispatch','during-dispatch'):
                    world['version']=2
                    gmail.thread.append(msg('dispatch-change',4000,'other@test.invalid'))
                # This fixture adapter's version token is bound to the exact reviewed state.
                expected=impact.impact_preview(svc,aid,registry=registry)['current']['state_hash']
                assert condition['binding']==impact.approval_context(svc.get(aid)).binding()
                if world['version']!=1 or condition['state_hash']!=expected:raise ApprovalConflictError('provider condition refused')
                effects.append(copy.deepcopy(payload));return {'dispatched':True}
    action_registry.register_conditional_executor(10,'send_email_reply',Adapter())
    original=svc.consume_effect
    def interleave(*a,**kw):
        if change_at=='after-read-before-permit':
            world['version']=2
            gmail.thread.append(msg('permit-change',4000,'other@test.invalid'))
        return original(*a,**kw)
    monkeypatch.setattr(svc,'consume_effect',interleave)
    if change_at=='before-read':gmail.thread.append(msg('new',3000,'other@test.invalid'))
    if change_at=='none':assert execute_approved_action.run(aid,'conditional')['result']['dispatched']
    else:
        with pytest.raises(ApprovalConflictError):execute_approved_action.run(aid,'conditional')
    assert len(effects)==(1 if change_at=='none' else 0)


def test_bound_preview_no_snapshot_never_claims_safe_to_consume(env):
    svc, registry, _, sessions=env;view=pending(env)
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    with sessions.begin() as db:db.get(ApprovalRequestRow,view['id']).status='approved'
    assert impact.impact_preview(svc,view['id'],registry=registry)['safe_to_consume'] is False


def test_bound_denial_without_snapshot_remains_available(env):
    svc, _, _, _=env;view=pending(env)
    assert svc.decide(view['id'],ApprovalStatus.DENIED,'owner')['status']==ApprovalStatus.DENIED


def test_bound_snapshot_cannot_be_replayed_to_other_approval(env):
    svc, registry, _, sessions=env;aid=approve(svc,registry);view=pending(env)
    with sessions.begin() as db:
        original=db.get(impact.ApprovalReviewStateRow,aid)
        db.add(impact.ApprovalReviewStateRow(approval_id=view['id'],state=copy.deepcopy(original.state),state_hash=original.state_hash,probe=original.probe,captured_at=original.captured_at))
    with pytest.raises(ApprovalConflictError):svc.decide(view['id'],ApprovalStatus.APPROVED,'owner')


def test_bound_approval_context_is_immutable_and_payload_digest_changes_with_owner(env):
    from dataclasses import FrozenInstanceError
    svc, _, _, _=env;view=pending(env);context=impact.approval_context(view)
    with pytest.raises(FrozenInstanceError):context.tenant_id='other'
    assert impact.approval_context({**view,'user_id':'other'}).payload_hash!=context.payload_hash


@pytest.mark.parametrize('path', ['review-state','consume'])
def test_bound_http_owner_with_foreign_payload_refuses_capture_consume_zero_reads(env,monkeypatch,path):
    svc, registry, gmail, _=env
    view=svc.submit(module_id=10,action_type='send_email_reply',payload=PAYLOAD,user_id='tenant-b')
    monkeypatch.setattr(routes,'capture_review_state',lambda s,aid,**kw:impact.capture_review_state(s,aid,registry=registry,**kw))
    monkeypatch.setattr(routes,'consume_effect_checked',lambda s,aid,**kw:impact.consume_effect_checked(s,aid,registry=registry,**kw))
    app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[routes.get_service]=lambda:svc
    app.dependency_overrides[require_tenant]=lambda:TenantContext('tenant-b','owner')
    body={} if path=='review-state' else {'module_id':10,'action_type':'send_email_reply','payload':PAYLOAD,'effect_id':'foreign'}
    with TestClient(app) as client:result=client.post(f"/approval-center/requests/{view['id']}/{path}",json=body)
    assert result.status_code==409 and gmail.requests==[]
    assert [e['event'] for e in svc.audit(view['id'])]==['created']


def test_bound_disconnected_account_refuses_before_token_read(env):
    svc,registry,gmail,sessions=env;view=pending(env)
    with sessions.begin() as db:db.execute(update(GmailAccountRow).where(GmailAccountRow.id=='acct-1').values(id='removed'))
    with pytest.raises(RuntimeError):impact.capture_review_state(svc,view['id'],registry=registry)
    assert gmail.requests==[]


def test_bound_untrusted_named_probe_cannot_create_m10_snapshot(env):
    svc,_,gmail,_=env;view=pending(env);fake=impact.ProbeRegistry()
    fake.register('send_email_reply',lambda payload:{'$approval_binding':impact.approval_context(view).binding()},module_id=10)
    with pytest.raises(ApprovalConflictError):impact.capture_review_state(svc,view['id'],registry=fake)
    assert gmail.requests==[]


def test_bound_http_capture_explicit_state_cannot_replace_trusted_snapshot(env):
    svc,_,gmail,_=env;view=pending(env)
    app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[routes.get_service]=lambda:svc
    app.dependency_overrides[require_tenant]=lambda:TenantContext('t1','owner')
    with TestClient(app) as client:result=client.post(f"/approval-center/requests/{view['id']}/review-state",json={'state':{'$approval_binding':impact.approval_context(view).binding()}})
    assert result.status_code==409 and gmail.requests==[]
