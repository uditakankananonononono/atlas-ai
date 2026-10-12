"""v5: shared ID-shaped-value guard, global stage refusals, low-level fill guard, context capture, route wiring."""
import asyncio
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from app.modules.m13_browser_agent.value_guard import forbidden_value, normalize, assert_no_forbidden_values
from app.modules.m13_browser_agent.application_flow import extract_field_descriptors, WorkflowStateError
from app.modules.m13_browser_agent.forms import FieldDescriptor
from app.modules.m13_browser_agent.service import Service as BrowserService
from app.modules.m01_opportunity_discovery.student_browser_routes import install_routes, get_student_browser
from app.modules.m01_opportunity_discovery.prefill_plan import plan_prefill
from test_m01_student_browser import browser, run, Sessions, Audit  # noqa: F401


# ---- value guard -------------------------------------------------------------------------------
@pytest.mark.parametrize('value', [
    '123456789', '123-45-6789', '123 45 6789', '123,456,789', '(123) 456 789', '123\u200b456\u200b789', '123\u2060456\u2060789',
    '\uff11\uff12\uff13\uff0d\uff14\uff15\uff0d\uff16\uff17\uff18\uff19',            # fullwidth digits and hyphen
    '\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669',                         # Arabic-Indic 9 digits
    '123.45.6789', '123_45_6789', '123/45/6789', '123\u201445\u20146789', '123\u00a045\u00a06789',
    '123456789012', '1234,5678,9012', '4111 1111 1111 1111', '1234567890123456789012345',
])
def test_non_phone_key_refuses_all_separator_variants(value):
    assert forbidden_value('school', value)
    with pytest.raises(ValueError): assert_no_forbidden_values({'school': value})


@pytest.mark.parametrize('key,value', [('graduation_year', '2027'), ('school', 'DPS 12'), ('city', 'Sector 62'),
                                       ('school', '12345678'), ('city', '1234567890'), ('city', '12345678901'),   # 10-11 digits accepted by design
                                       ('github_url', 'https://github.com/asha-rao')])
def test_ordinary_and_documented_accepted_values(key, value):
    assert not forbidden_value(key, value)


@pytest.mark.parametrize('value', ['94105-1234', '2020-2024 2025 2026', '123456789'])   # ZIP+4, date run, 9-digit phone
def test_documented_false_positives_are_refused(value):
    assert forbidden_value('city', value)


@pytest.mark.parametrize('key', ['phone', 'mobile_number', 'contact_tel', 'Cell'])
def test_phone_keys_use_shape_rule(key):
    assert forbidden_value(key, '123456789') and forbidden_value(key, '4111 1111 1111 1111') and forbidden_value(key, '078-05-1120')
    assert forbidden_value(key, '919876543210')
    assert not forbidden_value(key, '+91 98765 43210') and not forbidden_value(key, '020 7946 0958')


def test_normalize_strips_format_chars_and_maps_digits():
    assert normalize('1\u200b2\uff13') == '123'


# ---- direct stage path (callers that skip the planner) ---------------------------------------
def _stage(browser, html, fields, platform='fastweb', url='https://www.fastweb.com/college-scholarships'):
    sessions = browser.flow.browser.sessions
    sid = run(browser.start('t', 'a', platform, True, True))['session_id']
    page = sessions.pages[('t', sid)]
    page.url, page.html = url, html
    return page, sid


FORM = '<label for="s">School</label><input id="s" name="school"><button id="send" type="submit">Go</button>'


def test_generic_flow_stage_refuses_id_shaped_values_without_planner(browser):  # noqa: F811
    page, sid = _stage(browser, FORM, {})
    run(browser.flow.inspect('t', 'a', sid))
    for bad in ('123-45-6789', '123456789', '1234 5678 9012'):
        with pytest.raises(ValueError):
            run(browser.flow.stage('t', 'a', sid, {'school': bad}, '#send'))
    assert page.values == {}


from app.modules.m01_opportunity_discovery.student_browser import ADAPTERS as _ADAPTERS
from app.modules.m01_opportunity_discovery.student_platforms import BY_ID as _BY_ID
EDITORIAL = sorted(k for k, v in _ADAPTERS.items() if v.account_workflow == 'editorial_discovery')


def test_editorial_set_is_all_16():
    assert len(EDITORIAL) == 16


@pytest.mark.parametrize('pid', EDITORIAL)
def test_editorial_ban_is_global_for_every_editorial_source(browser, pid):  # noqa: F811
    page, sid = _stage(browser, FORM, {}, platform=pid, url=_BY_ID[pid].url)
    page.html = FORM
    # Direct flow path (what M02 uses), bypassing StudentBrowser.stage, and the wrapper path:
    with pytest.raises(PermissionError):
        run(browser.flow.stage('t', 'a', sid, {'school': 'DPS'}, '#send'))
    with pytest.raises(PermissionError):
        run(browser.stage('t', 'a', sid, {'school': 'DPS'}, '#send'))
    assert page.values == {}


def test_non_editorial_sessions_still_stage(browser):  # noqa: F811
    page, sid = _stage(browser, FORM, {})
    run(browser.flow.inspect('t', 'a', sid))
    run(browser.flow.stage('t', 'a', sid, {'school': 'DPS'}, '#send'))
    assert page.values == {'#s': 'DPS'}


# ---- low-level Service.fill ---------------------------------------------------------------------
class _P:
    url = 'https://example.com/'
    def __init__(self): self.values = {}
    def locator(self, sel):
        p = self
        class L:
            async def fill(self, v): p.values[sel] = v
            async def evaluate(self, script): return 'select:' if sel == '#c' else 'input:text'
        return L()


class _S:
    def __init__(self): self.p = _P()
    async def page(self, *a): return self.p


def _service(tmp_path):
    return BrowserService(_S(), None, Audit(), artifact_root=str(tmp_path))


def test_service_fill_refuses_select_and_id_values_and_fills_text(tmp_path):
    svc = _service(tmp_path)
    fields = [FieldDescriptor('#c', 'Country', 'country', '', 'select'), FieldDescriptor('#n', 'Full name', 'full_name', '', 'text')]
    with pytest.raises(ValueError):
        asyncio.run(svc.fill('t', 's', fields, {'country': 'India', 'full_name': 'Asha'}))
    assert svc.sessions.p.values == {}
    with pytest.raises(ValueError):
        asyncio.run(svc.fill('t', 's', fields[1:], {'full_name': '123-45-6789'}))
    assert svc.sessions.p.values == {}
    assert asyncio.run(svc.fill('t', 's', fields[1:], {'full_name': 'Asha'})) == {'#n': 'Asha'}
    assert svc.sessions.p.values == {'#n': 'Asha'}


# ---- context capture -----------------------------------------------------------------------------
def ctx(html):
    return {d.selector: d.context for d in extract_field_descriptors(html)}


def test_hidden_text_is_excluded_from_context():
    c = ctx('<fieldset><legend>Applicant</legend><span hidden>Guardian</span><span style="display:none">Guardian</span>'
            '<div aria-hidden="true">Guardian</div><input id="a" name="a"></fieldset>')
    assert 'Guardian' not in c['#a'] and 'Applicant' in c['#a']


def test_role_heading_describedby_and_own_labelledby_are_captured():
    assert 'Guardian' in ctx('<div role="heading">Guardian</div><div><input id="a" name="a"></div>')['#a']
    assert 'Mentor' in ctx('<p id="d">Mentor details</p><input id="a" name="a" aria-describedby="d">')['#a']
    assert 'Teacher' in ctx('<span id="l">Teacher</span><input id="a" name="a" aria-labelledby="l">')['#a']
    assert 'Referee' in ctx('<p id="d">Referee</p><div aria-describedby="d"><input id="a" name="a"></div>')['#a']


def test_table_caption_and_row_header_are_captured():
    c = ctx('<table><caption>Parent or guardian</caption><tr><th>Contact</th><td><input id="a" name="a"></td></tr></table>')
    assert 'Parent or guardian' in c['#a'] and 'Contact' in c['#a']


def test_heading_in_a_closed_sibling_section_does_not_leak():
    html = ('<form><fieldset><legend>x</legend><h3>Guardian</h3><input id="g" name="g"></fieldset>'
            '<input id="o" name="o"></form>')
    c = ctx(html)
    assert 'Guardian' in c['#g'] and 'Guardian' not in c['#o']


def test_long_context_keeps_nearest_cues_not_cut_mid_cue():
    html = '<fieldset aria-label="' + ('Applicant ' * 100) + '"><legend>Parent or guardian</legend><input id="a" name="a"></fieldset>'
    c = ctx(html)['#a']
    assert 'Parent or guardian' in c
    assert len(c) <= 600


def test_context_is_used_for_exclusion_not_for_value_matching():
    plan = plan_prefill({'full_name': 'Asha Rao'}, [d.__dict__ for d in extract_field_descriptors(
        '<fieldset><legend>Applicant</legend><label for="n">Full name</label><input id="n" name="n"></fieldset>')])
    assert plan['fields'] == {'full_name': 'Asha Rao'}      # applicant context neither excludes nor changes the match


# ---- route wiring -----------------------------------------------------------------------------------
def test_http_routes_plan_then_stage_with_token_and_reject_drift(browser):  # noqa: F811
    router = APIRouter(); install_routes(router)
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_student_browser] = lambda: browser
    with TestClient(app) as client:
        base = '/opportunity-discovery/student-platforms'
        sid = client.post(base + '/fastweb/browser-sessions', json={'owner_account_confirmed': True, 'terms_permit': True}).json()['session_id']
        page = next(p for (tn, s), p in browser.flow.browser.sessions.pages.items() if s == sid)
        page.url, page.html = 'https://www.fastweb.com/college-scholarships', (
            '<label for="n">Full name</label><input id="n" name="full_name"><button id="send" type="submit">Go</button>')
        plan = client.post(base + f'/browser-sessions/{sid}/prefill-plan', json={'profile': {'full_name': 'Asha Rao'}, 'submit_selector': '#send'})
        assert plan.status_code == 200, plan.text
        body = plan.json(); assert body['fields'] == {'full_name': 'Asha Rao'} and len(body['plan_token']) == 64 and page.values == {}
        bad = client.post(base + f'/browser-sessions/{sid}/stage', json={'fields': {'full_name': 'Someone Else'}, 'submit_selector': '#send', 'plan_token': body['plan_token']})
        assert bad.status_code == 409 and page.values == {}
        ok = client.post(base + f'/browser-sessions/{sid}/stage', json={'fields': body['fields'], 'submit_selector': '#send', 'plan_token': body['plan_token']})
        assert ok.status_code == 200, ok.text
        assert page.values == {'#n': 'Asha Rao'}
        assert client.post(base + f'/browser-sessions/{sid}/stage', json={'fields': {}, 'submit_selector': '#send', 'plan_token': 'zz'}).status_code == 422


@pytest.mark.parametrize("v", ["123a45a6789", "12 3 x 45 y 6789", "ID: 1234abcd56789", "1234567890ab12", "123 Main St Apt 4B 94110"])
def test_letter_interleaved_digits_are_counted(v):
    from app.modules.m13_browser_agent.value_guard import forbidden_value
    assert forbidden_value("school", v)


def test_letter_interleaved_short_value_still_allowed():
    from app.modules.m13_browser_agent.value_guard import forbidden_value
    assert not forbidden_value("school", "Grade 10 Section 4B")


def test_service_fill_checks_dom_type_not_descriptor_label(browser):  # noqa: F811
    """A caller that labels a select/checkbox as 'text' (or uppercase) is still refused from the live DOM."""
    sessions = browser.flow.browser.sessions
    sid = run(browser.start('t', 'a', 'fastweb', True, True))['session_id']
    page = sessions.pages[('t', sid)]
    page.url = 'https://www.fastweb.com/college-scholarships'
    page.html = '<select id="s"><option>a</option></select><input id="c" type="checkbox"><input id="t" name="school">'
    svc = browser.flow.browser
    for sel in ('#s', '#c'):
        d = FieldDescriptor(selector=sel, label='School', name='school', input_type='TEXT')
        with pytest.raises(ValueError, match='not a text-like input'):
            run(svc.fill('t', sid, [d], {'school': 'DPS'}))
        assert page.values == {}
    ok = FieldDescriptor(selector='#t', label='School', name='school', input_type='text')
    assert run(svc.fill('t', sid, [ok], {'school': 'DPS'})) == {'#t': 'DPS'}
