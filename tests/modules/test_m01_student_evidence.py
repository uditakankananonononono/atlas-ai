"""Offline adapters use fixtures; generated adversarial data is not live evidence."""
from pathlib import Path
import hashlib

import httpx
import pytest

from app.modules.m01_opportunity_discovery.student_evidence import deadline_evidence
from app.modules.m01_opportunity_discovery.student_platforms import BY_ID, discover, PlatformUnavailable
from app.modules.m01_opportunity_discovery.student_intelligence import annotate

FIXTURE = Path(__file__).parents[1] / 'fixtures' / 'm01' / 'simplify-public-table.html'


def client(body, ctype='text/plain', status=200):
    return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(
        status, content=body, headers={'content-type': ctype}, request=req)))


def test_public_simplify_fixture_is_not_copilot_and_never_follows_links():
    payload = FIXTURE.read_bytes()
    calls = []
    def transport(req):
        calls.append(str(req.url))
        return httpx.Response(200, content=payload, headers={'content-type':'text/plain'}, request=req)
    with httpx.Client(transport=httpx.MockTransport(transport)) as tx:
        result = discover('simplify', client=tx)
    assert calls == [BY_ID['simplify'].url]
    assert result['items'] and result['content_sha256'] == hashlib.sha256(payload).hexdigest()
    for row in result['items']:
        assert row['deadline']['value'] is None and row['eligibility']['verdict'] is None
        assert row['source_url'] == BY_ID['simplify'].url and row['fetched_at'].endswith('+00:00')
        assert 'score' not in row and 'detail_page_not_fetched' in row['unknowns']
        assert annotate(row)['deadline'] == row['deadline']


@pytest.mark.parametrize('text,value,precision,tz', [
    ('Deadline: 2027-01-03', '2027-01-03', 'date', None),
    ('Apply by January 3, 2027.', '2027-01-03', 'date', None),
    ('Deadline: 2027-01-03T14:00:00+05:30.', '2027-01-03T14:00:00+05:30', 'instant', 'UTC+05:30'),
    ('Applications close 2027-01-03T14:00Z.', '2027-01-03T14:00:00+00:00', 'instant', 'UTC'),
    ('Event date 2027-01-03. Posted January 3, 2027.', None, 'unknown', None),
    ('Deadline: 2027-02-30.', None, 'unknown', None),
    ('Deadline: 2027-01-03 at 5pm IST.', None, 'unknown', None),
    ('Deadline: 2027-01-03 to 2027-01-05.', None, 'unknown', None),
    ('Deadline: 2027-01-03. Apply by 2027-01-04.', None, 'unknown', None),
    ('Deadline: 2027-01-03T14:00.', None, 'unknown', None),
])
def test_deadline_precision_and_ambiguity(text, value, precision, tz):
    result = deadline_evidence(text)
    assert (result['value'], result['precision'], result['timezone']) == (value, precision, tz)
    assert result['evidence'] or value is None


@pytest.mark.parametrize('platform', [p for p in BY_ID if BY_ID[p].mode == 'rss'])
def test_all_rss_routes_preserve_exact_evidence_without_inference(platform):
    body = b'''<rss><channel><item><title>Evidence Award</title><link>https://publisher.example/award</link>
    <description><![CDATA[<p>Eligibility: undergraduate students in India. Deadline: 2027-01-03.</p>
    <script>Deadline: 2028-01-03.</script>]]></description></item></channel></rss>'''
    with client(body, 'application/rss+xml') as tx:
        row = discover(platform, client=tx)['items'][0]
    assert row['deadline']['value'] is None and row['deadline']['timezone'] is None
    assert 'qualified_or_negated_deadline' in row['deadline']['unknowns']
    assert row['eligibility']['evidence'] == ['Eligibility: undergraduate students in India.']
    assert row['eligibility']['verdict'] is None
    assert '2028' not in row['description']


def test_query_no_match_is_empty_not_layout_failure():
    with client(FIXTURE.read_bytes()) as tx:
        assert discover('simplify', 'nonexistent unique phrase', client=tx)['items'] == []


@pytest.mark.parametrize('status', [301, 403, 429, 500])
def test_new_adapter_stops_on_failure(status):
    with client(FIXTURE.read_bytes(), status=status) as tx:
        with pytest.raises(PlatformUnavailable): discover('simplify', client=tx)


def test_github_closed_and_unsafe_rows_excluded():
    template = '<table><tr><td>Company</td><td>{role}</td><td>India</td><td><a href="{url}"><img alt="Apply"></a></td><td>0d</td></tr></table>'
    for url, role in [('http://unsafe.example/apply', 'Intern'), ('https://evil.example:bad/', 'Intern'),
                      ('https://safe.example/', 'Intern 🔒')]:
        with client(template.format(url=url, role=role).encode()) as tx:
            with pytest.raises(PlatformUnavailable): discover('simplify', client=tx)


def test_oversized_stream_stops_before_consuming_entire_response():
    class Stream(httpx.SyncByteStream):
        def __init__(self): self.chunks = 0; self.closed = False
        def __iter__(self):
            for _ in range(100):
                self.chunks += 1
                yield b'x' * 100000
        def close(self): self.closed = True
    stream = Stream()
    tx = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(
        200, stream=stream, headers={'content-type':'text/plain'}, request=req)))
    with tx:
        with pytest.raises(PlatformUnavailable, match='2 MB'): discover('simplify', client=tx)
    assert stream.chunks == 21 and stream.closed


def test_redirect_not_followed_even_with_redirecting_client():
    calls = []
    def transport(req):
        calls.append(str(req.url))
        return httpx.Response(302, headers={'location':'https://private.example/'}, request=req)
    with httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=True) as tx:
        with pytest.raises(PlatformUnavailable, match='302'): discover('simplify', client=tx)
    assert calls == [BY_ID['simplify'].url]


def test_xml_entity_declarations_are_not_parsed():
    payload = b'<!DOCTYPE rss [<!ENTITY a "Expansion">]><rss><channel><item><title>&a;</title></item></channel></rss>'
    with client(payload, 'application/rss+xml') as tx:
        with pytest.raises(PlatformUnavailable, match='declarations'): discover('scholarshiproar', client=tx)


@pytest.mark.parametrize('text', [
    'Deadline: 2027-01-030', 'Deadline: January 3, 20270',
    'Deadline: 2027-01-03, 17:00', 'Deadline: 2027-01-03T12:00Zgarbage',
    'Deadline: 2027-01-03T12:00:000Z', 'Deadline: 2027-01-03T12:00Z to 2027-01-04',
])
def test_no_truncated_date_prefix_success(text):
    assert deadline_evidence(text)['value'] is None


def test_instant_deadline_filters_do_not_crash_or_invent_timezone():
    from datetime import date
    from app.modules.m01_opportunity_discovery.student_intelligence import deadline_window, exclude_expired
    card = {'deadline': deadline_evidence('Deadline: 2027-01-03T23:30:00-05:00.')}
    assert deadline_window([card], date(2027,1,3), date(2027,1,3)) == [card]
    assert exclude_expired([card], today=date(2027,1,4)) == []
    assert card['deadline']['timezone'] == 'UTC-05:00'


def test_eligibility_abbreviation_keeps_full_evidence():
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    sentence = 'Eligibility: U.S. citizens studying engineering must be enrolled full-time.'
    row = evidence_card({'title':'Award','description': sentence}, fetched_at='2026-10-01T00:00:00+00:00', content_sha256='f'*64)
    assert row['eligibility']['evidence'] == [sentence]
    assert row['eligibility']['verdict'] is None


@pytest.mark.parametrize('suffix', ['5pm', '11 PM', 'midnight', 'end of day', 'noon Eastern', '11pm UTC', 'Pacific Time'])
def test_audit_stated_unparsed_clock_is_not_date_only(suffix):
    result = deadline_evidence('Deadline: Oct 1, 2026 ' + suffix)
    assert result['value'] is None and 'unsupported_deadline_time_or_timezone' in result['unknowns']


@pytest.mark.parametrize('text', ['Deadline: 2026-10-01 or 2026-10-05',
    'Deadline: 2026-10-01/2026-10-05', 'Deadline: Oct 1, 2026 and Oct 2, 2026'])
def test_audit_multiple_date_values_are_conflicts(text):
    result = deadline_evidence(text)
    assert result['value'] is None and 'conflicting_deadline_statements' in result['unknowns']


@pytest.mark.parametrize('text', ['Deadline: 2026-10-01T10:00:00.123Z', 'Deadline: 2026-10-01T10:00+0530'])
def test_audit_supported_iso_forms(text):
    result = deadline_evidence(text)
    assert result['value'] is not None and result['timezone'] is not None


def test_audit_eligibility_sentence_boundary_and_truncation():
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    row = evidence_card({'title':'Award', 'description':'Eligibility: U.S. citizens. Winners receive a prize.'}, fetched_at='x', content_sha256='f'*64)
    assert row['eligibility']['evidence'] == ['Eligibility: U.S. citizens.']
    row = evidence_card({'title':'Award', 'description':'Eligibility: ' + 'x '*400}, fetched_at='x', content_sha256='f'*64)
    assert 'eligibility_evidence_truncated' in row['unknowns']


def test_audit_company_flags_not_asserted_on_child_rows():
    from app.modules.m01_opportunity_discovery.student_platforms import _read_github_readme
    def row(company):
        return '<tr><td>'+company+'</td><td>Intern</td><td>NYC</td><td><a href="https://example.org/apply"><img alt="Apply"></a></td><td>0d</td></tr>'
    rows = _read_github_readme(('<table>'+row('Company 🇺🇸')+row('↳')+'</table>').encode())
    assert rows[1]['eligibility_statements'] == []
    assert 'company_marker_applicability_unknown' in rows[1]['source_unknowns']


def test_audit_fetch_total_budget(monkeypatch):
    from app.modules.m01_opportunity_discovery import student_platforms as module
    ticks = iter([0., 0., 20.])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(ticks))
    with client(FIXTURE.read_bytes()) as tx:
        with pytest.raises(PlatformUnavailable, match='time budget'): discover('simplify', client=tx)

@pytest.mark.parametrize('tail', ['5 p.m.', '17h', '1700', 'by 5', 'EOD', 'close of business', 'AoE', 'CET', 'CST', 'AEST', 'JST', 'BST', 'PT', 'ET', '+0530', '-0800', '\n5pm'])
def test_reaudit_arbitrary_tail_not_date_only(tail):
    r = deadline_evidence('Deadline: Oct 1, 2026 ' + tail)
    assert r['value'] is None and 'unsupported_deadline_time_or_timezone' in r['unknowns']

@pytest.mark.parametrize('text', ['Deadline: 2026-10-01 / 10-05', 'Deadline: Oct 1, 2026 / Oct 5', 'Deadline: Oct 1, 2026. Extended to Oct 8, 2026.'])
def test_reaudit_abbreviated_or_extended_conflict(text):
    assert 'conflicting_deadline_statements' in deadline_evidence(text)['unknowns']

@pytest.mark.parametrize('month', ['Sept', 'Sept.'])
def test_reaudit_september(month):
    assert deadline_evidence(f'Deadline: {month} 1, 2026')['value'] == '2026-09-01'

@pytest.mark.parametrize('iso', ['2026-10-01t10:00:00z', '2026-10-01T10:00:00-0800'])
def test_reaudit_iso_case_and_offset(iso):
    assert deadline_evidence('Deadline: ' + iso)['precision'] == 'instant'

def test_reaudit_fraction_precision_reason():
    r = deadline_evidence('Deadline: 2026-10-01T10:00:00.1234567Z')
    assert r['value'] is None and 'unsupported_deadline_fraction_precision' in r['unknowns']

def test_reaudit_eligibility_no_silent_context_loss():
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    desc = 'Eligibility: Dr. Smith lab only. Not for minors.\nMust be enrolled.'
    r = evidence_card({'title':'Award', 'description':desc}, fetched_at='x', content_sha256='f'*64)
    assert r['eligibility']['source_context'] == desc
    assert 'eligibility_context_boundary_unknown' in r['unknowns']
    desc = 'Eligibility: ' + 'x'*590
    r = evidence_card({'title':'Award', 'description':desc}, fetched_at='x', content_sha256='f'*64)
    assert ('eligibility_evidence_truncated' in r['unknowns']) == (len(desc) > 600)

@pytest.mark.parametrize('offset', ['+1260', '+0199', '-0060', '+00:99', '+1500', '+14:01'])
def test_third_audit_offset_fields(offset):
    r = deadline_evidence('Deadline: 2026-10-01T12:00'+offset)
    assert r['value'] is None and 'invalid_deadline_timezone_offset' in r['unknowns']

@pytest.mark.parametrize('symbol', ['🕔', '⏰', '∑', '€', '−'])
def test_third_audit_symbols_not_punctuation(symbol):
    assert deadline_evidence('Deadline: Oct 1, 2026 '+symbol)['value'] is None

@pytest.mark.parametrize('text', ['Deadline: Oct. 1st, 2026', 'Deadline: 1 October 2026', 'Submissions due by October 1, 2026', 'Applications close on October  1,\n2026'])
def test_third_audit_safe_english_grammar(text):
    assert deadline_evidence(text)['value'] == '2026-10-01'

def test_third_audit_rss_full_evidence():
    text = 'Eligibility: '+('student '*90)+'Not open to minors. Deadline: October 1, 2026.'
    body = ('<rss><channel><item><title>Award</title><link>https://example.org/a</link><description>'+text+'</description></item></channel></rss>').encode()
    with client(body, 'application/rss+xml') as tx:
        row = discover('scholarshiproar', client=tx)['items'][0]
    assert row['deadline']['value'] is None
    assert 'qualified_or_negated_deadline' in row['deadline']['unknowns']
    assert 'eligibility_evidence_truncated' in row['unknowns']
    assert row['description_original_length'] == len(text)

def test_third_audit_spaced_initial():
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    row = evidence_card({'title':'Award','description':'Eligibility: A. Chen lab only. No minors.'}, fetched_at='x', content_sha256='f'*64)
    assert row['eligibility']['evidence'][0] == 'Eligibility: A. Chen lab only.'

@pytest.mark.parametrize('prefix', ['Early bird ', 'Registration ', 'Previous ', "Last year's ", 'No '])
def test_round4_qualified_deadline_abstains(prefix):
    r = deadline_evidence(prefix+'deadline: Oct 1, 2026')
    assert r['value'] is None and 'qualified_or_negated_deadline' in r['unknowns']

@pytest.mark.parametrize('sentence', ['Must be enrolled.', 'Must be 18.', 'Only juniors may apply.', 'Restricted to residents.', 'Available to international students.', 'Not open to minors.', 'Minimum GPA 3.5.', 'Requirements: US citizenship.'])
def test_round4_eligibility_cues(sentence):
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    r = evidence_card({'title':'Award','description':sentence}, fetched_at='x', content_sha256='f'*64)
    assert r['eligibility']['evidence'] and 'eligibility_not_stated_in_listing' not in r['unknowns']

def test_round4_fulltext_query_and_html_blocks():
    text = '<p>Eligibility: Students.</p><p>Award: $500.</p><p>'+('x '*350)+'unique-query-term</p>'
    body = ('<rss><channel><item><title>Award</title><link>https://example.org/a</link><description><![CDATA['+text+']]></description></item></channel></rss>').encode()
    with client(body, 'application/rss+xml') as tx:
        rows = discover('scholarshiproar', 'unique-query-term', client=tx)['items']
    assert len(rows) == 1 and rows[0]['eligibility']['evidence'][0] == 'Eligibility: Students.'

@pytest.mark.parametrize('prefix', ['没有', 'без ', 'لا ', 'No\n', 'Not the\n', 'aucune '])
def test_r5_unicode_and_multiline_qualifier(prefix):
    assert deadline_evidence(prefix+'deadline: November 12, 2026')['value'] is None

@pytest.mark.parametrize('caveat', ['provisional', 'obsolete', 'not final', 'subject to change'])
def test_r5_post_field_caveat(caveat):
    assert deadline_evidence('Deadline: November 12, 2026. Award: $500. This date is '+caveat+'.')['value'] is None

@pytest.mark.parametrize('text', ['Requirements gathering workshop', 'Available to download: brochure', 'Minimum GPA calculation explained', 'Available to watch on YouTube', 'You must act now to save 20%', 'Eligibility checker available on our website', 'Who can apply? Read our website to find out.'])
def test_r5_nonrequirements_not_eligibility(text):
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    row = evidence_card({'title':'Award','description':text}, fetched_at='x', content_sha256='x')
    assert not row['eligibility']['evidence']

def test_r5_block_boundary_and_header_value():
    from app.modules.m01_opportunity_discovery.student_platforms import _plain_text
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    text = _plain_text('<p>Eligibility:</p><p>Undergraduates only</p><p>Award: $500</p>')
    assert '\n' in text
    row = evidence_card({'title':'Award','description':text}, fetched_at='x', content_sha256='x')
    assert 'Undergraduates only' in row['eligibility']['evidence'][0]
    assert 'Award' not in row['eligibility']['evidence'][0]

def test_r5_many_cues_bounded_work():
    import time
    start = time.monotonic()
    result = deadline_evidence(('Deadline: November 12, 2026.\n') * 20000)
    assert time.monotonic() - start < 2.0
    assert 'deadline_input_limit_exceeded' in result['unknowns']

@pytest.mark.parametrize('prefix', ['No'+' '*3000, 'Not the'+' '*6000, 'ليس. ', '不是; '])
def test_r6_no_truncated_qualifier(prefix):
    assert deadline_evidence(prefix+'deadline: November 12, 2026')['value'] is None

@pytest.mark.parametrize('desc', ['x'*100001+'No deadline: November 12, 2026', 'Archived listing. No current application round.', 'Deadline: November 12, 2026. '*258])
def test_r6_title_cannot_override_safety(desc):
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    r=evidence_card({'title':'Deadline: November 12, 2026','description':desc}, fetched_at='x', content_sha256='x')
    assert r['deadline']['value'] is None

@pytest.mark.parametrize('text', ['Eligibility:\nAward: $500', 'Requirements:\nDeadline: November 12, 2026', 'Applicants must:\nLocation: Delhi'])
def test_r6_no_unrelated_label_join(text):
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    r=evidence_card({'title':'Award','description':text}, fetched_at='x', content_sha256='x')
    assert not r['eligibility']['evidence']

def test_r6_eligibility_work_and_output_bounded():
    import time,json
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    start=time.monotonic()
    r=evidence_card({'title':'Award','description':'Eligibility: students. '*8000}, fetched_at='x', content_sha256='x')
    assert time.monotonic()-start < 1
    assert len(json.dumps(r['eligibility'])) < 12000
    assert 'eligibility_input_limit_exceeded' in r['unknowns']

@pytest.mark.parametrize('tail', ['Award: $500. Deadline is invalid', 'Eligibility: students. Deadline is not valid', 'Location: Delhi. The deadline is не окончательно'])
def test_r7_standalone_field_only(tail):
    assert deadline_evidence('Deadline: November 12, 2026. '+tail)['value'] is None

@pytest.mark.parametrize('title', ['Not the deadline', 'Deadline is invalid', 'अंतिम तिथि नहीं'])
def test_r7_unknown_title_wins(title):
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    assert evidence_card({'title':title,'description':'Deadline: November 12, 2026'}, fetched_at='x', content_sha256='x')['deadline']['value'] is None

@pytest.mark.parametrize('field', ['Contact: student office', 'Fees: students pay $50', 'Funding: students receive money', 'Benefits: students receive $500', 'Selection: GPA ranking'])
def test_r7_unknown_field_not_eligibility(field):
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    assert not evidence_card({'title':'Award','description':'Eligibility:\n'+field}, fetched_at='x', content_sha256='x')['eligibility']['evidence']

def test_r7_card_output_bound():
    import json
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    r=evidence_card({'title':'x'*15000,'description':'x'*200000}, fetched_at='x', content_sha256='x')
    assert len(json.dumps(r).encode()) <= 20000

def test_r7_aggregate_limit_and_no_reason_loss():
    import json
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    body=('<rss><channel>'+''.join('<item><title>'+('x'*15000)+'</title><link>https://example.org/'+str(i)+'</link><description>Eligibility: students.</description></item>' for i in range(100))+'</channel></rss>').encode()
    with client(body,'application/rss+xml') as tx:
        r=discover('scholarshiproar',limit=100,client=tx)
    assert sum(len(json.dumps(i).encode()) for i in r['items']) <= 200000
    card=evidence_card({'title':'Deadline: November 12, 2026','description':'x'*100001+'Deadline: November 13, 2026'}, fetched_at='x', content_sha256='x')
    assert 'deadline_input_limit_exceeded' in card['deadline']['unknowns']
    assert 'conflicting_deadline_statements' in card['deadline']['unknowns']

@pytest.mark.parametrize('title', ['Cancelled listing','Canceled opportunity','Withdrawn listing','Obsolete listing'])
def test_r8_inactive_title_abstains(title):
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    r=evidence_card({'title':title,'description':'Deadline: November 12, 2026'}, fetched_at='x', content_sha256='x')
    assert r['deadline']['value'] is None

@pytest.mark.parametrize('length', [25000,100000])
def test_r8_every_field_output_bound(length):
    import json
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    r=evidence_card({'title':'Award','description':'','url':'https://example.org/'+('x'*length),'extra':'x'*length}, fetched_at='x', content_sha256='x')
    assert len(json.dumps(r).encode()) <= 20000

def test_r8_same_line_unknown_field_abstains():
    from app.modules.m01_opportunity_discovery.student_evidence import evidence_card
    r=evidence_card({'title':'Award','description':'Eligibility: Contact: student office'}, fetched_at='x', content_sha256='x')
    assert not r['eligibility']['evidence']
