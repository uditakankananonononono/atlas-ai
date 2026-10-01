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
    <description><![CDATA[<p>Deadline: 2027-01-03. Eligibility: undergraduate students in India.</p>
    <script>Deadline: 2028-01-03.</script>]]></description></item></channel></rss>'''
    with client(body, 'application/rss+xml') as tx:
        row = discover(platform, client=tx)['items'][0]
    assert row['deadline']['value'] == '2027-01-03' and row['deadline']['timezone'] is None
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
