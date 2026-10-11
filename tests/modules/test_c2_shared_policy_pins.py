"""C2 phase1 shared guard pins; synthetic data only."""
import pytest
from app.modules.c30 import policy
from app.modules.m20_general_cognitive_worker import launch_quiz_c2 as core
from app.modules.m20_general_cognitive_worker import launch_quiz_c2_routes as routes

CASES = [('spend','SPEND'),('outreach','OUTREACH'),('fakeacct','FAKEACCT'),
         ('fake_account','FAKEACCT'),('autopost','AUTOPOST'),('scrape','SCRAPE'),('trade','TRADE')]

@pytest.mark.parametrize('action,reason', CASES)
def test_shared_denial_and_alias_forward(action, reason, monkeypatch):
    calls=[]
    real=policy.check
    def check(a,p):
        calls.append((a,p)); return real(a,p)
    monkeypatch.setattr(policy,'check',check)
    with pytest.raises(core.QuizError,match='^POLICY_REFUSED_'+reason+'$'):
        core.enforce_policy(action)
    assert calls == [('fakeacct' if action=='fake_account' else action,'POLICY')]

@pytest.mark.parametrize('action,reason', CASES)
def test_shared_hook_same_denial_reverse(action, reason):
    with pytest.raises(core.QuizError,match='^POLICY_REFUSED_'+reason+'$'):
        core.shared_policy_hook(action)

@pytest.mark.parametrize('action', ['', 'DRAFT', 'send', 'fake-account', 'Fakeacct', None, [], True])
def test_unknown_actions_stay_constant_safe(action):
    with pytest.raises(core.QuizError,match='^POLICY_REFUSED_UNSUPPORTED$'):
        core.enforce_policy(action)
    with pytest.raises(core.QuizError,match='^POLICY_REFUSED_UNSUPPORTED$'):
        core.shared_policy_hook(action)

def test_offline_draft_is_not_unknown_policy_action(monkeypatch):
    def forbidden(*args): raise AssertionError('draft must not call deny-only policy.check')
    monkeypatch.setattr(policy,'check',forbidden)
    assert core.enforce_policy('draft') is None
    assert core.shared_policy_hook('draft') is True

def test_adapter_injects_exact_shared_hook():
    assert routes._engine.policy_hook is core.shared_policy_hook

@pytest.mark.parametrize('action,reason', CASES)
def test_true_hook_cannot_bypass_shared_denials(action,reason):
    calls=[]
    e=core.LaunchQuiz(policy_hook=lambda a: calls.append(a) or True)
    sid=e.start('synthetic',consent=True)['session_id']
    with pytest.raises(core.QuizError,match='^POLICY_REFUSED_'+reason+'$'):
        e.plan('synthetic',sid,'Task',action=action)
    assert calls==[]

def test_shared_error_propagates_as_quizerror(monkeypatch):
    def deny(a,p): raise ValueError('POLICY_REFUSED_TEST')
    monkeypatch.setattr(policy,'check',deny)
    with pytest.raises(core.QuizError,match='^POLICY_REFUSED_TEST$'):
        core.enforce_policy('spend')

def test_accidental_shared_allow_still_fails_closed(monkeypatch):
    monkeypatch.setattr(policy,'check',lambda a,p: None)
    for action,_ in CASES:
        with pytest.raises(core.QuizError,match='^POLICY_REFUSED_UNSUPPORTED$'):
            core.enforce_policy(action)

def test_default_hook_keeps_draft_plan_working():
    e=core.LaunchQuiz(policy_hook=core.shared_policy_hook)
    sid=e.start('synthetic',consent=True)['session_id']
    for choice in ('accuracy','evidence','compare','detailed'):
        q=e.question('synthetic',sid)
        e.answer('synthetic',sid,q['id'],choice,'Synthetic explanation.')
    assert e.plan('synthetic',sid,'Task')['status']=='draft'

@pytest.mark.parametrize('result', [1, None])
def test_hook_requires_literal_true_not_truthy_or_none(result):
    e=core.LaunchQuiz(policy_hook=lambda action: result)
    sid=e.start('synthetic',consent=True)['session_id']
    for choice in ('accuracy','evidence','compare','detailed'):
        q=e.question('synthetic',sid)
        e.answer('synthetic',sid,q['id'],choice,'Synthetic explanation.')
    with pytest.raises(core.QuizError,match='^POLICY_REFUSED_SHARED$'):
        e.plan('synthetic',sid,'Task')
