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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
ROBOTS_OVERRIDE = {}
PAGES['/advice/big'] = 'x' * 200


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        HITS.append(self.path)
        body = (ROBOTS_OVERRIDE.get('robots', ROBOTS) if self.path == '/robots.txt' else PAGES.get(self.path))
        if self.path == '/robots.txt' and ROBOTS_OVERRIDE.get('missing'):
            body = None
        code = 200 if body is not None else 404
        b = (body or '').encode()
        self.send_response(code); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)


@pytest.fixture(scope='module')
def port():
    srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_port
    srv.shutdown(); srv.server_close()


def make(port, clock=None):
    class NoRedir(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedir)

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
    page_hash = {'https://advice.example.org' + p: hashlib.sha256(x.encode()).hexdigest() for p, x in served.items()}
    for c in t3['concept_candidates']:
        assert c['status'] == 'candidate_not_installed'
        assert c['source_sha256'] == page_hash[c['source_url']]          # bound to ITS OWN page, not just any served page
    assert sorted((c['source_url'], c['technique']) for c in t3['concept_candidates']) == sorted([
        ('https://advice.example.org/advice/essays', 'Always verify your claims with a concrete example.'),
        ('https://advice.example.org/advice/grants', 'Compare three funders before you apply.'),
        ('https://advice.example.org/advice/grants', 'Avoid generic openings.')])
    assert len(set(page_hash.values())) == 2
    assert t3['model_trained'] is False and 'model training' in t3['scope']['not_implemented']
    t4 = units.run('T4', {'records': records, 'task': 'plan essay', 'action': {'type': 'analyze'}})
    assert t4['status'] == 'prepared_only' and [s['stage'] for s in t4['log']] == ['advice', 'policy', 'prepared']
    assert HITS == ['/robots.txt', '/advice/essays', '/robots.txt', '/advice/grants']


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


def test_t4_without_records_refused(port):
    _, permit, _ = make(port)
    with pytest.raises(m.Refusal, match='FLEET_REFUSED_NOADVICE'):
        m.TrainingUnits({'adv': permit}, policy=lambda a: None).run('T4', {'records': [], 'action': {'type': 'analyze'}})


REC = {'source_id': 'adv', 'url': 'https://advice.example.org/advice/essays', 'text': 'Always test.', 'as_of': '2026-10-12'}


def test_policy_callable_denial_blocks_preparation(port):
    _, permit, _ = make(port)
    seen = []
    with pytest.raises(m.Refusal, match='FLEET_REFUSED_ACTION'):
        m.TrainingUnits({'adv': permit}, policy=lambda a: seen.append(a) or False).run('T4', {'records': [REC], 'action': {'type': 'analyze'}})
    assert seen == [{'type': 'analyze'}]        # the policy callable actually ran


def test_shared_policy_denial_is_the_denial_path_not_import_failure(port):
    _, permit, _ = make(port)
    with pytest.raises(m.Refusal) as e:
        m.TrainingUnits({'adv': permit}, policy=None).run('T4', {'records': [REC], 'action': {'outreach': True}})
    assert str(e.value) == 'FLEET_REFUSED_OUTREACH'          # from c30 policy.check, not FLEET_REFUSED_UNAVAILABLE


def test_shared_policy_unavailable_is_distinguishable(port, monkeypatch):
    _, permit, _ = make(port)
    monkeypatch.setitem(sys.modules, 'app.modules.c30.policy', None)      # makes the import raise ImportError
    with pytest.raises(m.Refusal) as e:
        m.TrainingUnits({'adv': permit}, policy=None).run('T4', {'records': [REC], 'action': {'outreach': True}})
    assert str(e.value) == 'FLEET_REFUSED_UNAVAILABLE'


def test_rate_limit_boundary_and_host_independence(port):
    t = [0.0]
    fetcher, permit, _ = make(port, clock=lambda: t[0])
    fetcher.fetch('adv', 'https://advice.example.org/advice/essays')
    t[0] = 59.9
    with pytest.raises(m.Refusal, match='RATELIMIT'):
        fetcher.fetch('adv', 'https://advice.example.org/advice/grants')
    t[0] = 60.0
    assert fetcher.fetch('adv', 'https://advice.example.org/advice/grants')


def test_robots_failures_oversize_and_crawl_delay_are_refused(port):
    fetcher, _, t = make(port)
    ROBOTS_OVERRIDE['robots'] = 'User-agent: *\nCrawl-delay: 600\n'
    try:
        with pytest.raises(m.Refusal, match='RATELIMIT'):
            fetcher.fetch('adv', 'https://advice.example.org/advice/essays')
    finally:
        ROBOTS_OVERRIDE.clear()
    t[0] += 61
    small = m.PublicFetcher(fetcher.permits, fetcher.transport, clock=lambda: t[0], limit=100)
    with pytest.raises(m.Refusal, match='OVERSIZE'):
        small.fetch('adv', 'https://advice.example.org/advice/essays')     # page larger than the 100-byte limit


def test_robots_not_200_refuses_before_page_request(port):
    HITS.clear()
    fetcher, _, _ = make(port)
    ROBOTS_OVERRIDE['missing'] = True
    try:
        with pytest.raises(m.Refusal, match='TREND_REFUSED_SCRAPE'):
            fetcher.fetch('adv', 'https://advice.example.org/advice/essays')
    finally:
        ROBOTS_OVERRIDE.clear()
    assert HITS == ['/robots.txt']
