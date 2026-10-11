import pytest

from app.modules.m01_opportunity_discovery import tool_registry as r


def test_seven_named_with_her_stated_claims_unverified():
    assert [t.name for t in r.NAMED] == ['RippleMatch', 'Simplify', 'RaiseMe', 'Bold.org', 'Fastweb', 'Devpost', 'ChallengeRocket']
    assert r.get('ripplematch').spec_free_claim == 'Completely Free for Students'
    assert r.get('challengerocket').spec_free_claim == '100% Free for students'
    assert all(not t.free_verified for t in r.REGISTRY)
    assert r.registry_payload()['free_claims_verified'] is False


def test_unknown_terms_are_marked_stubs_not_guessed():
    for i in ('paperbleach', 'clicky', 'okara'):
        t = r.get(i)
        assert t.status == r.UNKNOWN_STUB and not t.buildable
        assert t.url == '' and t.capabilities == () and 'UNKNOWN' in t.notes
        with pytest.raises(LookupError):
            r.request_action(i, 'profile_export')


def test_plus_more_are_candidates_not_counted_as_approved():
    assert r.PLUS_MORE_TARGET == 10
    assert all(t.status == r.CANDIDATE_PENDING for t in r.CANDIDATES)
    assert not {t.id for t in r.CANDIDATES} & {t.id for t in r.NAMED}


@pytest.mark.parametrize('action,code', [
    ('submit', r.APPLY_REFUSED_AUTOSUBMIT), ('autofill', r.APPLY_REFUSED_AUTOSUBMIT),
    ('pay', r.APPLY_REFUSED_SPEND), ('upgrade', r.APPLY_REFUSED_SPEND),
    ('login', r.APPLY_REFUSED_TOS), ('bypass_challenge', r.APPLY_REFUSED_TOS),
])
def test_refusals(action, code):
    with pytest.raises(PermissionError, match=code):
        r.request_action('simplify', action)


def test_prepare_only_and_capability_limits():
    assert r.request_action('fastweb', 'deadline_sync')['prepare_only']
    with pytest.raises(PermissionError):
        r.request_action('raiseme', 'open_form_for_user')
    p = r.describe('simplify')
    assert p['autosubmit'] is False and p['autofill'] is False and p['live_accounts_used'] is False
    assert p['account_mode'] == 'user_own_logged_in_account'


def test_no_network_imports():
    import inspect
    src = inspect.getsource(r)
    assert 'httpx' not in src and 'requests' not in src and 'playwright' not in src

# --- auditor pins (immutability, exact refusals, no aliasing) ---
import dataclasses
from app.modules.m01_opportunity_discovery import tool_registry as r
@pytest.mark.parametrize('action,code',[(a,r.APPLY_REFUSED_AUTOSUBMIT)for a in ['submit','autosubmit','apply','autofill']]+[(a,r.APPLY_REFUSED_SPEND)for a in ['pay','subscribe','upgrade','purchase']]+[(a,r.APPLY_REFUSED_TOS)for a in ['login','signup','create_account','bypass_challenge','scrape','unknown']])
def test_all_refusals_exact(action,code):
 with pytest.raises(PermissionError)as e:r.request_action('ripplematch',action)
 assert str(e.value)==code
@pytest.mark.parametrize('tool',[t.id for t in r.NAMED+r.CANDIDATES])
def test_all_capabilities_prepare_only(tool):
 t=r.get(tool)
 for a in t.capabilities:assert r.request_action(tool,a)=={'tool':tool,'action':a,'prepare_only':True}
def test_descriptor_immutable():
 with pytest.raises(dataclasses.FrozenInstanceError):r.get('simplify').free_verified=True
def test_counts_and_candidate_status():
 p=r.registry_payload();assert p['counts']=={'spec_named':7,'unknown_stubs':3,'candidates_pending':10,'plus_more_target':10}
 assert all(t.status==r.CANDIDATE_PENDING and not t.free_verified for t in r.CANDIDATES)
def test_payload_not_aliased_to_registry():
 p=r.describe('simplify');p['capabilities'].append('submit');p['free_verified']=True;assert not r.get('simplify').free_verified;assert 'submit'not in r.get('simplify').capabilities


def test_simplify_exact_free_claim_fragment():
    assert r.get('simplify').spec_free_claim == '(Simplify.jobs) Chrome Extension (Completely Free)'
