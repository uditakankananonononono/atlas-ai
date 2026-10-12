"""Row 63 delta: execute the real chain PublicFetcher -> T3 concept candidates -> T4 advice-prepared,
over a loopback HTTP server (the https URL is mapped to it by the caller-supplied transport).
Shows the chain runs and keeps provenance, refusals and 'prepared only' status. It does NOT show
that advice is turned into anything (no training, no creation): that stays PARTIAL."""
import hashlib
import importlib.util
import pathlib
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

import pytest

spec = importlib.util.spec_from_file_location('training_data_units', pathlib.Path(__file__).parents[2] / 'backend/app/modules/m20_general_cognitive_worker/training_data_units.py')
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)

PAGES = {
    '/advice/essays': '<html><body><p>Always verify your claims with a concrete example.</p><p>Nice weather.</p><script>always evil()</script></body></html>',
    '/advice/grants': '<html><body><div>Compare three funders before you apply.</div><div>Avoid generic openings.</div></body></html>',
    '/private/notes': '<p>Always do this secret thing.</p>',
}
ROBOTS = 'User-agent: *\nDisallow: /private/\n'
HITS = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        HITS.append(self.path)
        body = ROBOTS if self.path == '/robots.txt' else PAGES.get(self.path)
        code = 200 if body is not None else 404
        b = (body or '').encode()
        self.send_response(code); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)


@pytest.fixture(scope='module')
def port():
    srv = HTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_port
    srv.shutdown()


def make(port, clock=None):
    class NoRedir(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None
    opener = urllib.request.build_opener(NoRedir)

    def transport(url, limit):
        p = urlsplit(url)
        assert p.scheme == 'https' and p.netloc == 'advice.example.org'   # only the permitted origin is ever requested
        try:
            with opener.open('http://127.0.0.1:%d%s' % (port, p.path), timeout=5) as r:
                return m.FetchResponse(r.status, r.read(limit + 1).decode(), {})
        except urllib.error.HTTPError as e:
            return m.FetchResponse(e.code, '', {})
    permit = m.SourcePermit('adv', 'https://advice.example.org', 'CC-BY-4.0', 'https://advice.example.org/terms', '2026-10-12', True)
    t = [0.0]
    fetcher = m.PublicFetcher({'adv': permit}, transport, clock=clock or (lambda: t[0]))
    return fetcher, permit, t


def test_fetch_to_candidates_to_prepared_advice_keeps_provenance(port):
    HITS.clear()
    fetcher, permit, t = make(port)
    served = {}
    records = []
    for path in ('/advice/essays', '/advice/grants'):
        text = fetcher.fetch('adv', 'https://advice.example.org' + path)
        served[path] = text
        records.append({'source_id': 'adv', 'url': 'https://advice.example.org' + path, 'text': text, 'as_of': '2026-10-12'})
        t[0] += 61   # per-host interval
    units = m.TrainingUnits({'adv': permit}, policy=lambda a: None)
    t3 = units.run('T3', {'records': records})
    techs = [c['technique'] for c in t3['concept_candidates']]
    assert any('verify your claims' in x for x in techs) and any('Compare three funders' in x for x in techs)
    assert not any('evil' in x for x in techs) and not any('weather' in x.lower() for x in techs)
    for c in t3['concept_candidates']:
        assert c['status'] == 'candidate_not_installed' and c['source_url'].startswith('https://advice.example.org/advice/')
        assert c['source_sha256'] in {hashlib.sha256(s.encode()).hexdigest() for s in served.values()}
    assert t3['model_trained'] is False and 'model training' in t3['scope']['not_implemented']
    t4 = units.run('T4', {'records': records, 'task': 'plan essay', 'action': {'type': 'analyze'}})
    assert t4['status'] == 'prepared_only' and [s['stage'] for s in t4['log']] == ['advice', 'policy', 'prepared']
    assert set(HITS) == {'/robots.txt', '/advice/essays', '/advice/grants'}


def test_robots_disallowed_path_is_never_requested(port):
    HITS.clear()
    fetcher, _, _ = make(port)
    with pytest.raises(m.Refusal, match='TREND_REFUSED_SCRAPE'):
        fetcher.fetch('adv', 'https://advice.example.org/private/notes')
    assert '/private/notes' not in HITS


def test_rate_limit_refuses_second_fetch_to_same_host(port):
    fetcher, _, t = make(port)
    fetcher.fetch('adv', 'https://advice.example.org/advice/essays')
    with pytest.raises(m.Refusal, match='RATELIMIT'):
        fetcher.fetch('adv', 'https://advice.example.org/advice/grants')


def test_unpermitted_origin_and_missing_page_refused(port):
    fetcher, _, t = make(port)
    with pytest.raises(m.Refusal):
        fetcher.fetch('adv', 'https://other.example.org/advice/essays')
    with pytest.raises(m.Refusal, match='FETCH'):
        fetcher.fetch('adv', 'https://advice.example.org/advice/missing')


def test_t4_without_records_or_with_policy_denial_prepares_nothing(port):
    _, permit, _ = make(port)
    with pytest.raises(m.Refusal, match='FLEET_REFUSED_NOADVICE'):
        m.TrainingUnits({'adv': permit}, policy=lambda a: None).run('T4', {'records': [], 'action': {'type': 'analyze'}})
    rec = {'source_id': 'adv', 'url': 'https://advice.example.org/advice/essays', 'text': 'Always test.', 'as_of': '2026-10-12'}
    with pytest.raises(m.Refusal):
        m.TrainingUnits({'adv': permit}, policy=lambda a: False).run('T4', {'records': [rec], 'action': {'type': 'analyze'}})
    with pytest.raises(m.Refusal):
        m.TrainingUnits({'adv': permit}, policy=None).run('T4', {'records': [rec], 'action': {'outreach': True}})
