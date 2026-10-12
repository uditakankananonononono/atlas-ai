"""Rows 51/53: Fastweb and ChallengeRocket read -> open -> inspect -> prefill plan -> stage, never submit.

Hermetic fake pages (no live accounts). Proves the Atlas side of the linkage only.
Binding integrity: every plan is checked against what M13 stage() would actually bind.
"""
import pytest
from app.modules.m01_opportunity_discovery import prefill_plan
from app.modules.m01_opportunity_discovery.prefill_plan import plan_prefill, forbidden_value, _stage_binding
from app.modules.m13_browser_agent.application_flow import extract_field_descriptors, WorkflowStateError
from test_m01_student_browser import browser, run  # noqa: F401  (fixture reuse; sibling test module)

PROFILE = {'full_name': 'Asha Rao', 'email': 'asha@example.org', 'school': 'DPS', 'graduation_year': '2027'}
FORM = ('<form><label for="n">Full name</label><input id="n" name="full_name" required>'
        '<label for="e">Email address</label><input id="e" name="email" type="email" required>'
        '<label for="s">School</label><input id="s" name="school">'
        '<label for="d">Date of birth</label><input id="d" name="dob" required>'
        '<label for="x">Anything else</label><input id="x" name="misc">'
        '<button id="send" type="submit">Submit</button></form>')
CASES = {
    'fastweb': ('https://www.fastweb.com/college-scholarships',
                '<h3><a href="/college-scholarships/scholarships/1234-stem-award">STEM award</a></h3>'),
    'challengerocket': ('https://challengerocket.com/hackathons-and-challenges.html',
                        '<div class="challenge-card__title"><h3><a href="/hackathon-future-city-26">Future City</a></h3></div>'),
}


def plan_for(html, profile=PROFILE):
    ds = [d.__dict__ for d in extract_field_descriptors(html)]
    return plan_prefill(profile, ds), ds


def assert_binding_exact(plan, ds):
    """What stage() would really bind equals the plan, and never touches a withheld/other-party field."""
    got = _stage_binding(ds, plan['fields'])
    assert got == {sel: plan['fields'][key] for sel, key in plan['matched'].items()}
    assert not set(got) & (set(plan['withheld']) | set(plan['other_party']))


def test_plan_matches_exactly_and_withholds_sensitive():
    plan, ds = plan_for(FORM)
    assert plan['fields'] == {'full_name': 'Asha Rao', 'email': 'asha@example.org', 'school': 'DPS'}
    assert plan['withheld'] == ['#d'] and plan['unmatched_optional'] == ['#x'] and plan['submitted'] is False
    assert_binding_exact(plan, ds)


def test_fields_are_keyed_by_profile_key_so_duplicate_page_names_cannot_overwrite():
    html = ('<input id="a" name="name" placeholder="Full name"><input id="b" name="name" placeholder="Your name">')
    plan, ds = plan_for(html)
    assert plan['fields'] == {} and len(plan['binding_conflicts']) == 2   # two claims: neither filled
    html = '<input id="a" name="v" placeholder="Full name"><input id="b" name="v" placeholder="School">'
    plan, ds = plan_for(html)
    assert plan['fields'] == {'full_name': 'Asha Rao', 'school': 'DPS'}
    assert_binding_exact(plan, ds)


@pytest.mark.parametrize('label', ['Guardian email', 'Parent/guardian email address', 'Recommender email',
                                   'Teacher email', 'Emergency contact email'])
def test_other_party_email_never_gets_owner_email(label):
    plan, ds = plan_for(f'<label for="g">{label}</label><input id="g" name="e2" type="email" required>')
    assert plan['fields'] == {} and plan['other_party'] == ['#g'] and plan['unmatched_required'] == []


def test_extra_email_control_drops_only_the_conflicting_field_not_the_owner_email():
    html = ('<label for="a">Email address</label><input id="a" name="a" type="email">'
            '<label for="b">Contact email</label><input id="b" name="b" type="email">')
    plan, ds = plan_for(html)
    assert plan['fields'] == {'email': 'asha@example.org'} and plan['matched'] == {'#a': 'email'}
    assert plan['unmatched_optional'] == ['#b']
    assert_binding_exact(plan, ds)
    # two fields both claiming the owner email: only those two are dropped (nothing else is affected)
    html = ('<label for="a">Email</label><input id="a" name="a" type="email">'
            '<label for="b">Email address</label><input id="b" name="b" type="email">'
            '<label for="s">School</label><input id="s" name="s">')
    plan, _ = plan_for(html)
    assert plan['fields'] == {'school': 'DPS'} and {c['selector'] for c in plan['binding_conflicts']} == {'#a', '#b'}
    plan, _ = plan_for('<label for="a">Reach us</label><input id="a" name="a" type="email">')
    assert plan['fields'] == {}     # labeled with something else: not assumed to be the owner's


def test_unlabeled_email_only_when_it_is_the_single_non_other_party_email_control():
    plan, _ = plan_for('<input id="a" type="email">')
    assert plan['fields'] == {'email': 'asha@example.org'}
    plan, _ = plan_for('<input id="a" type="email"><input id="b" type="email">')
    assert plan['fields'] == {}
    g = ('<fieldset><legend>Parent or guardian</legend><label for="g">Email</label><input id="g" name="g" type="email"></fieldset>'
         '<input id="a" type="email">')
    plan, _ = plan_for(g)
    # Labeled guardian Email is excluded by the planner, but M13 stage() would still bind the owner
    # email to it (first email-typed field wins). The simulation catches that: fail closed, no fill.
    assert plan['other_party'] == ['#g'] and plan['fields'] == {}
    assert any(c['selector'] == '#a' and '#g' in c['reason'] for c in plan['binding_conflicts'])


@pytest.mark.parametrize('html,other', [
    ('<fieldset><legend>Guardian details</legend><label for="n">Name</label><input id="n" name="n"><label for="e">Email</label><input id="e" name="e" type="email"></fieldset>', {'#n', '#e'}),
    ('<section aria-label="Recommender information"><label for="n">Name</label><input id="n" name="n"><label for="e">Email</label><input id="e" name="e" type="email"></section>', {'#n', '#e'}),
    ('<h3 id="h">Teacher / counselor</h3><div aria-labelledby="h"><label for="n">Name</label><input id="n" name="n"><label for="e">Email</label><input id="e" name="e" type="email"></div>', {'#n', '#e'}),
    ('<h2>Emergency contact</h2><div><label for="n">Name</label><input id="n" name="n"><label for="e">Email</label><input id="e" name="e" type="email"></div>', {'#n', '#e'}),
    ('<div><span>x</span><input id="n" aria-label="Name" name="n"><div role="group" aria-label="Mentor"><input id="e" aria-label="Email" name="e" type="email"></div></div>', {'#e'}),
])
def test_section_context_keeps_generic_name_and_email_off_owner_keys(html, other):
    plan, ds = plan_for(html)
    assert plan['fields'] == {} and plan['matched'] == {}
    assert set(plan['other_party']) == other
    assert all(d['context'] for d in ds if d['selector'] in other)


def test_owner_section_and_guardian_section_on_one_page():
    html = ('<fieldset><legend>Applicant</legend><label for="n">Full name</label><input id="n" name="n">'
            '<label for="e">Email address</label><input id="e" name="e" type="email"></fieldset>'
            '<fieldset><legend>Parent or guardian</legend><label for="gn">Name</label><input id="gn" name="gn">'
            '<label for="ge">Email address</label><input id="ge" name="ge" type="email"></fieldset>')
    plan, ds = plan_for(html)
    assert plan['fields'] == {'full_name': 'Asha Rao', 'email': 'asha@example.org'}
    assert plan['matched'] == {'#n': 'full_name', '#e': 'email'} and set(plan['other_party']) == {'#gn', '#ge'}
    assert_binding_exact(plan, ds)


REMATCH = ('<label for="b">Birth school</label><input id="b">'
           '<label for="s">School</label><input id="s">'
           '<label for="n">Full name</label><input id="n"><button id="send" type="submit">Submit</button>')
REMATCH_MIRRORED = ('<label for="n">Full name</label><input id="n">'
                    '<label for="s">School</label><input id="s">'
                    '<label for="b">Birth school</label><input id="b"><button id="send" type="submit">Submit</button>')


def _stage_through_real_flow(browser, html, fields):
    sessions = browser.flow.browser.sessions
    sid = run(browser.start('t', 'a', 'fastweb', True, True))['session_id']
    page = sessions.pages[('t', sid)]
    page.url, page.html = 'https://www.fastweb.com/college-scholarships', html
    run(browser.flow.inspect('t', 'a', sid))
    run(browser.stage('t', 'a', sid, fields, '#send'))
    return page


def test_withheld_field_rematch_hazard_is_real_and_planner_avoids_it_through_real_stage(browser):  # noqa: F811
    # Withheld 'Birth school' comes first. Un-planned data through REAL stage lands in the withheld field.
    page = _stage_through_real_flow(browser, REMATCH, {'school': 'DPS'})
    assert page.values.get('#b') == 'DPS'
    # Planner: refuses the school key, and the real stage then fills only the safe field.
    plan, ds = plan_for(REMATCH)
    assert plan['withheld'] == ['#b'] and 'school' not in plan['fields']
    assert any(c['key'] == 'school' for c in plan['binding_conflicts'])
    assert plan['fields'] == {'full_name': 'Asha Rao'}
    page2 = _stage_through_real_flow(browser, REMATCH, plan['fields'])
    assert page2.values == {'#n': 'Asha Rao'} and '#b' not in page2.values


def test_mirrored_field_order_owner_first_fills_owner_fields(browser):  # noqa: F811
    plan, ds = plan_for(REMATCH_MIRRORED)
    assert plan['withheld'] == ['#b']
    assert plan['fields'] == {'full_name': 'Asha Rao', 'school': 'DPS'}
    assert plan['matched'] == {'#n': 'full_name', '#s': 'school'}
    assert_binding_exact(plan, ds)
    page = _stage_through_real_flow(browser, REMATCH_MIRRORED, plan['fields'])
    assert page.values == {'#n': 'Asha Rao', '#s': 'DPS'}


def test_selector_only_fields_and_simulation_combined():
    html = '<input id="p1" placeholder="Full name"><input id="p2" placeholder="School"><input id="p3" placeholder="Birth school">'
    plan, ds = plan_for(html)
    assert all(d['name'] == '' for d in ds)               # nothing but selectors to go on
    assert plan['fields'] == {'full_name': 'Asha Rao', 'school': 'DPS'}      # exact set; #p3 'Birth school' is later in DOM
    assert plan['matched'] == {'#p1': 'full_name', '#p2': 'school'}
    assert '#p3' in plan['withheld'] and '#p3' not in _stage_binding(ds, plan['fields'])
    assert_binding_exact(plan, ds)


def test_plan_token_binds_page_fields_and_submit_selector(browser):  # noqa: F811
    sessions = browser.flow.browser.sessions
    sid = run(browser.start('t', 'a', 'fastweb', True, True))['session_id']
    page = sessions.pages[('t', sid)]
    page.url, page.html = 'https://www.fastweb.com/college-scholarships', FORM
    plan = run(browser.plan_prefill('t', 'a', sid, PROFILE, '#send'))
    assert plan['submitted'] is False and plan['page_url'] == page.url and len(plan['plan_token']) == 64
    assert page.values == {}                                  # planning fills nothing
    tok = plan['plan_token']
    page.html = FORM.replace('<label for="x">', '<fieldset><legend>Parent or guardian</legend><label for="x">')
    with pytest.raises(WorkflowStateError):                    # descriptors drifted
        run(browser.stage('t', 'a', sid, plan['fields'], '#send', plan_token=tok))
    page.html = FORM
    with pytest.raises(WorkflowStateError):                    # field value drifted
        run(browser.stage('t', 'a', sid, {**plan['fields'], 'school': 'Other'}, '#send', plan_token=tok))
    page.html = FORM.replace('</form>', '<button id="send2" type="submit">Other</button></form>')
    with pytest.raises(WorkflowStateError, match='changed since the prefill plan'):   # real second submit control
        run(browser.stage('t', 'a', sid, plan['fields'], '#send2', plan_token=tok))
    page.html = FORM
    page.url = 'https://www.fastweb.com/college-scholarships/other'
    with pytest.raises(WorkflowStateError):                    # page URL drifted
        run(browser.stage('t', 'a', sid, plan['fields'], '#send', plan_token=tok))
    assert page.values == {}
    page.url = 'https://www.fastweb.com/college-scholarships'
    ok = run(browser.stage('t', 'a', sid, plan['fields'], '#send', plan_token=tok))
    assert ok['submitted'] is False and page.values == {'#n': 'Asha Rao', '#e': 'asha@example.org', '#s': 'DPS'}


def test_html_name_attribute_cannot_override_team_name_label():
    plan, ds = plan_for('<label for="t">Team name</label><input id="t" name="name" required>')
    assert plan['fields'] == {} and plan['other_party'] == ['#t']
    plan, ds = plan_for('<label for="t">Project title</label><input id="t" name="name">')
    assert plan['fields'] == {}


def test_select_is_typed_select_by_extraction_and_skipped_by_plan():
    html = '<label for="c">Country</label><select id="c" name="country"><option>India</option></select>'
    ds = [d.__dict__ for d in extract_field_descriptors(html)]
    assert ds[0]['input_type'] == 'select'
    plan = plan_prefill({'country': 'India'}, ds)
    assert plan['fields'] == {} and plan['withheld'] == ['#c']


NON_PHONE_FORBIDDEN = [
    ('school', '123-45-6789'), ('full_name', 'SSN 078-05-1120'), ('city', '1234 5678 9012'), ('school', '4111 1111 1111 1111'),
    ('school', '123456789'),                      # unseparated SSN
    ('city', '123 45 6789'), ('city', '123.45.6789'), ('city', '123\u201345\u20136789'), ('city', '123\u00a045\u00a06789'),
    ('city', '123_45_6789'), ('city', '1234/5678/9012'),   # odd separators
    ('school', '123456789012'), ('school', '4111111111111111'), ('school', '12345678901234567890'),  # 12, 16, 20 unbroken
    ('school', '1234567890123456789012345'),      # 25 digits
    ('github_url', 'https://github.com/user123456789'),    # fail closed on digit runs inside URLs too
]


@pytest.mark.parametrize('key,value', NON_PHONE_FORBIDDEN)
def test_forbidden_values_refused_under_any_non_phone_key(key, value):
    assert forbidden_value(key, value)
    plan, ds = plan_for(FORM, {**PROFILE, key: value})
    assert key in plan['refused_value_keys'] and value not in str(plan['fields'])
    assert all(not forbidden_value(k, v) for k, v in plan['fields'].items())


@pytest.mark.parametrize('value', ['123456789', '123-45-6789', '078 05 1120', '123456789012', '919876543210', '4111111111111111',
                                   '1234 5678 9012 3456', '12345678901234567890', 'call 9876543210', '12345', '+1234567890123456'])
def test_phone_key_refuses_id_shaped_values(value):
    assert forbidden_value('phone', value)


@pytest.mark.parametrize('value', ['+91 98765 43210', '+1 (415) 555-0132', '9876543210', '+44 20 7946 0958', '020 7946 0958'])
def test_phone_key_accepts_phone_shaped_values(value):
    assert not forbidden_value('phone', value)


def test_phone_key_residual_is_documented_not_hidden():
    # A '+'-prefixed 12-digit string is indistinguishable from an international number: accepted by design.
    assert not forbidden_value('phone', '+1234 5678 9012')


@pytest.mark.parametrize('key,value', [('graduation_year', '2027'), ('school', 'DPS 12'), ('city', 'Sector 62'),
                                       ('github_url', 'https://github.com/asha-rao'), ('school', '12345678'), ('city', '1234567890')])
def test_ordinary_values_not_refused(key, value):
    assert not forbidden_value(key, value)


def test_phone_value_cannot_smuggle_an_id_through_the_planner():
    html = '<label for="p">Phone number</label><input id="p" name="p" type="tel">'
    for bad in ('123456789', '4111 1111 1111 1111', '078-05-1120'):
        plan, _ = plan_for(html, {'phone': bad})
        assert plan['fields'] == {} and plan['refused_value_keys'] == ['phone']
    plan, _ = plan_for(html, {'phone': '+91 98765 43210'})
    assert plan['fields'] == {'phone': '+91 98765 43210'}


def test_planned_key_that_stage_would_bind_elsewhere_is_dropped(monkeypatch):
    real = prefill_plan._stage_binding
    monkeypatch.setattr(prefill_plan, '_stage_binding',
                        lambda ds, data: {**real(ds, data), '#d': 'X'} if 'school' in data else real(ds, data))
    plan, _ = plan_for(FORM)
    assert 'school' not in plan['fields'] and any(c['key'] == 'school' for c in plan['binding_conflicts'])


@pytest.mark.parametrize('pid', CASES)
def test_listing_to_staged_form_without_submit(browser, pid):  # noqa: F811
    url, listing = CASES[pid]
    sessions = browser.flow.browser.sessions
    sid = run(browser.start('t', 'a', pid, True, True))['session_id']
    page = sessions.pages[('t', sid)]
    page.url, page.html = url, listing
    link = run(browser.read('t', 'a', sid))['links'][0]
    browser.time[0] += 60
    child = run(browser.open('t', 'a', sid, link['id']))
    cpage = sessions.pages[('t', child['session_id'])]
    cpage.html = FORM
    inspected = run(browser.flow.inspect('t', 'a', child['session_id']))
    plan = plan_prefill(PROFILE, inspected['fields'])
    assert plan['unmatched_required'] == [] and '#d' in plan['withheld']
    assert_binding_exact(plan, inspected['fields'])
    staged = run(browser.stage('t', 'a', child['session_id'], plan['fields'], '#send'))
    assert staged['submitted'] is False and not cpage.clicks
    assert all(v['matches'] for v in staged['preview'].values())
    assert cpage.values == {'#n': 'Asha Rao', '#e': 'asha@example.org', '#s': 'DPS'}
    assert '#d' not in cpage.values and '#x' not in cpage.values
    assert not any(forbidden_value('x', v) for v in cpage.values.values())


def test_visible_label_wins_over_html_name_attribute():
    plan, _ = plan_for('<label for="t">Nickname</label><input id="t" name="name">')
    assert plan['fields'] == {} and plan['unmatched_optional'] == ['#t']
    plan, _ = plan_for('<input id="t" name="name">')       # no label at all: name attr is the only evidence
    assert plan['fields'] == {'full_name': 'Asha Rao'}


SELECT_FORM = ('<form><label for="c">Country</label><select id="c" name="country"><option>India</option></select>'
               '<label for="n">Full name</label><input id="n" name="full_name"><button id="send" type="submit">Submit</button></form>')


def test_generic_m13_stage_refuses_to_fill_a_select(browser):  # noqa: F811
    sessions = browser.flow.browser.sessions
    sid = run(browser.start('t', 'a', 'fastweb', True, True))['session_id']
    page = sessions.pages[('t', sid)]
    page.url, page.html = 'https://www.fastweb.com/college-scholarships', SELECT_FORM
    run(browser.flow.inspect('t', 'a', sid))
    with pytest.raises(WorkflowStateError):
        run(browser.flow.stage('t', 'a', sid, {'country': 'India', 'full_name': 'Asha Rao'}, '#send'))
    assert page.values == {}          # nothing filled, not even the text field


def test_editorial_sources_refuse_staging_in_the_real_stage_path(browser):  # noqa: F811
    sessions = browser.flow.browser.sessions
    sid = run(browser.start('t', 'a', 'opportunitydesk', True, True))['session_id']
    page = sessions.pages[('t', sid)]
    page.html = FORM
    with pytest.raises(PermissionError):
        run(browser.stage('t', 'a', sid, {'full_name': 'Asha Rao'}, '#send'))
    assert page.values == {} and not page.clicks
