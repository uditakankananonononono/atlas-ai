import bz2
import gzip
import hashlib
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from warcio.warcwriter import WARCWriter
from warcio.statusandheaders import StatusAndHeaders
from app.mass_collection.engine import Collector, Source, Limits, CollectionError


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        hits = []
        def do_GET(self):
            self.hits.append((self.path, dict(self.headers)))
            bodies = {
                '/robots.txt': b'User-agent: *\nDisallow: /blocked\n',
                '/page': b'<html><script>secret()</script><h1>Hello</h1><p>World</p></html>',
                '/rows': b'{"text":"one"}\n{"text":"two"}\n{"text":"one"}\n',
                '/blocked': b'never',
                '/wiki': bz2.compress(b'<mediawiki><page><title>A</title><id>7</id><revision><id>9</id><text>Wiki text</text></revision></page></mediawiki>'),
                '/atom': b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>https://arxiv.org/abs/123</id><title>Paper</title><summary>Summary</summary></entry></feed>',
            }
            if self.path == '/redirect':
                self.send_response(302); self.send_header('Location', '/blocked'); self.end_headers(); return
            if self.path == '/challenge':
                self.send_response(403); self.end_headers(); return
            data = bodies.get(self.path, b'')
            start = int(self.headers.get('Range', 'bytes=0-').split('=')[1].split('-')[0])
            self.send_response(206 if start else 200)
            self.send_header('ETag', '"fixture-v1"')
            self.send_header('Content-Length', str(len(data)-start))
            if start: self.send_header('Content-Range', f'bytes {start}-{len(data)-1}/{len(data)}')
            self.end_headers(); self.wfile.write(data[start:])
        def log_message(self, *args): pass
    srv = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True); thread.start()
    yield f'http://127.0.0.1:{srv.server_port}', Handler
    srv.shutdown(); srv.server_close(); thread.join()


def source(url, fmt='html', **kw):
    return Source(url=url, format=fmt, license='CC-BY-4.0', terms_url=url+'/terms', terms_accepted=True, **kw)


def collector(tmp_path, **kw):
    return Collector(tmp_path, limits=Limits(request_interval=0, **kw), allow_loopback=True)


def test_real_html_resume_dedupe_manifest(tmp_path, server):
    url, handler = server
    c = collector(tmp_path, shard_records=1)
    assert c.collect(source(url+'/page'))['inserted'] == 1
    assert c.collect(source(url+'/page'))['inserted'] == 0
    assert len([h for h in handler.hits if h[0] == '/page']) == 1
    manifest = c.export()
    shard = tmp_path / manifest['shards'][0]['path']
    row = json.loads(shard.read_text())
    assert row['text'] == 'Hello\nWorld'
    assert row['license'] == 'CC-BY-4.0'
    assert row['provenance']['url'] == url+'/page'
    assert hashlib.sha256(shard.read_bytes()).hexdigest() == manifest['shards'][0]['sha256']
    assert Collector(tmp_path, allow_loopback=True).export()['records'] == 1


def test_robots_redirect_and_challenge_fail_closed(tmp_path, server):
    url, handler = server; c = collector(tmp_path)
    for path in ('/blocked', '/redirect', '/challenge'):
        with pytest.raises(CollectionError): c.collect(source(url+path))
    assert not any(h[0] == '/blocked' for h in handler.hits)


def test_stream_formats_and_content_dedupe(tmp_path, server):
    url, _ = server; c = collector(tmp_path)
    assert c.collect(source(url+'/rows', 'jsonl'))['inserted'] == 2
    assert c.collect(source(url+'/wiki', 'wikipedia'))['inserted'] == 1
    assert c.collect(source(url+'/atom', 'arxiv'))['inserted'] == 1
    assert c.export()['records'] == 4


def test_quota_and_kill(tmp_path, server):
    url, _ = server; c = collector(tmp_path, max_records=1)
    with pytest.raises(CollectionError): c.collect(source(url+'/rows', 'jsonl'))
    assert c.export()['records'] == 1
    c.stop()
    with pytest.raises(CollectionError): c.collect(source(url+'/page'))


def test_terms_and_network_boundary(tmp_path):
    c = Collector(tmp_path)
    with pytest.raises(CollectionError): c.collect(source('http://127.0.0.1/page'))
    with pytest.raises(CollectionError): c.collect(Source(url='https://example.org', format='html', license='unknown', terms_url='https://example.org/terms'))


def test_warc_real_parser(tmp_path):
    out = io.BytesIO(); writer = WARCWriter(out, gzip=True)
    headers = StatusAndHeaders('200 OK', [('Content-Type', 'text/html')], protocol='HTTP/1.0')
    record = writer.create_warc_record('https://example.org/a', 'response', payload=io.BytesIO(b'<p>Archive text</p>'), http_headers=headers)
    writer.write_record(record)
    path = tmp_path/'sample.warc.gz'; path.write_bytes(out.getvalue())
    c = collector(tmp_path/'data')
    s = source('https://data.commoncrawl.org/sample.warc.gz', 'commoncrawl')
    assert c.ingest_file(s, path)['inserted'] == 1
    m = c.export(); row = json.loads((c.root/m['shards'][0]['path']).read_text())
    assert row['text'] == 'Archive text'
    assert row['provenance']['record_url'] == 'https://example.org/a'
    assert row['training_eligible'] is False


def test_authenticated_origin_scoping(tmp_path, server):
    from app.mass_collection.credentials import CredentialStore
    url, handler = server
    store = CredentialStore(tmp_path/'credentials', 'tenant', master_secret='local-test-key')
    store.save('mine', url, 'fixture-token', owner_confirmed=True)
    assert 'fixture-token' not in (tmp_path/'credentials').read_text()
    c = collector(tmp_path/'data')
    c.credentials = store
    c.collect(source(url+'/page', credential='mine', owner_account=True))
    page = next(h for h in handler.hits if h[0]=='/page')
    assert page[1]['Authorization'] == 'Bearer fixture-token'
    assert c.export()['records'] == 1
    with pytest.raises(CollectionError): store.headers('mine', 'https://other.example/page')


def test_partial_range_resume(tmp_path, server):
    url, handler = server; c = collector(tmp_path)
    s = source(url+'/rows', 'jsonl')
    from dataclasses import asdict
    key = hashlib.sha256(json.dumps(asdict(s), sort_keys=True).encode()).hexdigest()
    (c.root/'downloads'/f'{key}.part').write_bytes(b'{"text":')
    (c.root/'downloads'/f'{key}.json').write_text(json.dumps({'url': s.url, 'etag': '"fixture-v1"'}))
    assert c.collect(s)['inserted'] == 2
    request = next(h for h in handler.hits if h[0]=='/rows')
    assert request[1]['Range'] == 'bytes=8-'
    assert request[1]['If-Range'] == '"fixture-v1"'


def test_xml_entities_rejected(tmp_path):
    path = tmp_path/'bad.xml'
    path.write_text('<!DOCTYPE mediawiki [<!ENTITY evil "payload">]><mediawiki><page><revision><text>&evil;</text></revision></page></mediawiki>')
    c = collector(tmp_path/'data')
    with pytest.raises(CollectionError): c.ingest_file(source('https://example.org/dump', 'wikipedia'), path)


def test_parquet_real_parser(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    path = tmp_path/'data.parquet'
    pq.write_table(pa.table({'text': ['First', 'Second']}), path)
    c = collector(tmp_path/'corpus')
    assert c.ingest_file(source('https://huggingface.co/datasets/example/resolve/main/train.parquet', 'parquet'), path)['inserted'] == 2


def test_all_provenance_and_review_flags(tmp_path):
    path = tmp_path/'text.txt'; path.write_text('Shared')
    c = collector(tmp_path/'data')
    c.ingest_file(source('https://example.org/a', 'text', training_reviewed=True), path)
    c.ingest_file(source('https://example.org/b', 'text'), path)
    m = c.export(); row = json.loads((c.root/m['shards'][0]['path']).read_text())
    assert len(row['provenance_all']) == 2
    assert not row['training_eligible']


def test_routes_tenant_isolation_and_stop(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.mass_collection.routes import router
    monkeypatch.setenv('ATLAS_COLLECTION_ROOT', str(tmp_path))
    app = FastAPI(); app.include_router(router)
    client = TestClient(app)
    assert client.get('/mass-collection/status', headers={'x-atlas-tenant':'a'}).json()['stopped'] is False
    assert client.post('/mass-collection/stop', headers={'x-atlas-tenant':'a'}).status_code == 200
    assert client.get('/mass-collection/status', headers={'x-atlas-tenant':'a'}).json()['stopped'] is True
    assert client.get('/mass-collection/status', headers={'x-atlas-tenant':'b'}).json()['stopped'] is False


def test_rate_limited_real_server(tmp_path, server):
    import time
    url, _ = server
    c = Collector(tmp_path, limits=Limits(request_interval=0.15), allow_loopback=True)
    start = time.monotonic(); c.collect(source(url+'/page'))
    assert time.monotonic()-start >= 0.14


def test_expanded_byte_quota(tmp_path):
    p = tmp_path/'big.jsonl.gz'; p.write_bytes(gzip.compress(b'{"text":"too large"}\n'))
    c = collector(tmp_path/'data', max_parse_bytes=10)
    with pytest.raises(CollectionError): c.ingest_file(source('https://example.org/file','jsonl'), p)
    assert c.export()['records'] == 0


def test_commoncrawl_path_manifest(tmp_path):
    from app.mass_collection.catalog import commoncrawl_sources
    p = tmp_path/'paths.gz'; p.write_bytes(gzip.compress(b'crawl-data/CC-MAIN-2026-01/segments/1/warc/a.warc.gz\n'))
    sources = commoncrawl_sources(p, terms_accepted=True, max_files=1)
    assert sources[0].url == 'https://data.commoncrawl.org/crawl-data/CC-MAIN-2026-01/segments/1/warc/a.warc.gz'
    assert sources[0].license == 'unknown-per-page'
    p.write_bytes(gzip.compress(b'https://evil.example/file\n'))
    with pytest.raises(CollectionError): commoncrawl_sources(p, terms_accepted=True, max_files=1)


def test_cli_offline_ingest_and_manifest(tmp_path, capsys):
    from app.mass_collection.__main__ import main
    config = tmp_path/'config.json'; text = tmp_path/'text'; text.write_text('Local data')
    from dataclasses import asdict
    config.write_text(json.dumps({'sources': [asdict(source('https://example.org/export','text'))]}))
    args = ['--root', str(tmp_path/'corpus'), '--tenant', 'test']
    assert main(args+['ingest', str(config), str(text)]) == 0
    assert main(args+['export']) == 0
    assert '"records": 1' in capsys.readouterr().out


def test_unknown_license_never_training_eligible(tmp_path):
    from dataclasses import replace
    path = tmp_path/'text'; path.write_text('No rights grant')
    c = collector(tmp_path/'data')
    c.ingest_file(replace(source('https://example.org/data', 'text', training_reviewed=True), license='unknown'), path)
    m = c.export(); row = json.loads((c.root/m['shards'][0]['path']).read_text())
    assert not row['training_eligible']


def test_disk_quota(tmp_path):
    path = tmp_path/'text'; path.write_text('Payload')
    c = collector(tmp_path/'data', max_disk_bytes=1)
    with pytest.raises(CollectionError): c.ingest_file(source('https://example.org/file','text'), path)


def test_parallel_writers_dedupe(tmp_path):
    import concurrent.futures
    path = tmp_path/'text'; path.write_text('Shared corpus')
    c = collector(tmp_path/'data')
    def run(_):
        return collector(tmp_path/'data').ingest_file(source('https://example.org/file','text'), path)['inserted']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(run, range(2))) == 1
    assert c.export()['records'] == 1


def test_license_normalization_blocks_lookalikes(tmp_path):
    from dataclasses import replace
    c = collector(tmp_path/'data')
    variants = (' unknown', 'unknown ', '  UNKNOWN', 'All Rights Reserved', 'all rights reserved', ' all_rights_reserved ', 'unknown_per_page')
    for i, lic in enumerate(variants):
        path = tmp_path/f'text{i}'; path.write_text(f'Payload {i}')
        c.ingest_file(replace(source(f'https://example.org/data{i}', 'text', training_reviewed=True), license=lic), path)
    m = c.export()
    assert m['records'] == len(variants)
    for shard in m['shards']:
        for line in (c.root/shard['path']).read_text().splitlines():
            row = json.loads(line)
            assert row['training_eligible'] is False, row['license']


def test_dns_pin_rejects_global_multicast_and_reserved(tmp_path, monkeypatch):
    import socket as real_socket
    from app.mass_collection import engine
    cases = ('224.0.1.1', '239.255.255.250', '240.0.0.1', '0.0.0.0')
    for address in cases:
        def fake_getaddrinfo(*args, _address=address, **kwargs):
            return [(real_socket.AF_INET, real_socket.SOCK_STREAM, 6, '', (_address, 80))]
        monkeypatch.setattr(engine.socket, 'getaddrinfo', fake_getaddrinfo)
        c = collector(tmp_path/f'data-{address.replace(".", "-")}')
        with pytest.raises(CollectionError, match='network target rejected'):
            c._pinned_url('http://example.org/page')
    monkeypatch.undo()


def test_warc_skipped_records_count_against_parse_quota(tmp_path):
    out = io.BytesIO(); writer = WARCWriter(out, gzip=True)
    headers = StatusAndHeaders('200 OK', [('Content-Type', 'application/octet-stream')], protocol='HTTP/1.0')
    big = writer.create_warc_record('https://example.org/big.bin', 'response', payload=io.BytesIO(b'x'*5000), http_headers=headers)
    writer.write_record(big)
    html_headers = StatusAndHeaders('200 OK', [('Content-Type', 'text/html')], protocol='HTTP/1.0')
    small = writer.create_warc_record('https://example.org/a', 'response', payload=io.BytesIO(b'<p>ok</p>'), http_headers=html_headers)
    writer.write_record(small)
    path = tmp_path/'sample.warc.gz'; path.write_bytes(out.getvalue())
    c = collector(tmp_path/'data', max_parse_bytes=2000)
    s = source('https://data.commoncrawl.org/sample.warc.gz', 'commoncrawl')
    with pytest.raises(CollectionError): c.ingest_file(s, path)
    assert c.export()['records'] == 0


def test_corrupted_credential_raises_collection_error(tmp_path):
    from app.mass_collection.credentials import CredentialStore
    store = CredentialStore(tmp_path/'credentials.json', 't', master_secret='local-test-key')
    store.save('mine', 'https://example.org', 'real-token', owner_confirmed=True)
    rows = json.loads((tmp_path/'credentials.json').read_text())
    rows['mine']['token'] = rows['mine']['token'][:-4] + 'AAAA'
    (tmp_path/'credentials.json').write_text(json.dumps(rows))
    with pytest.raises(CollectionError): store.headers('mine', 'https://example.org/page')


def test_missing_token_key_gives_clean_cli_message(tmp_path, monkeypatch, capsys):
    from app.mass_collection.credentials import CredentialStore
    from app.mass_collection.__main__ import main
    monkeypatch.delenv('ATLAS_TOKEN_KEY', raising=False)
    with pytest.raises(CollectionError): CredentialStore(tmp_path/'credentials.json', 't')
    monkeypatch.setattr('getpass.getpass', lambda prompt: 'tok')
    code = main(['--root', str(tmp_path/'corpus'), 'credential', 'mine', 'https://example.org', '--confirm-own-account'])
    assert code == 1
    assert 'Collection stopped: ATLAS_TOKEN_KEY is not configured' in capsys.readouterr().err


def test_broadened_sensitive_query_key_screen(tmp_path):
    from app.mass_collection.engine import origin
    for key in ('secret', 'session', 'key', 'auth', 'sig', 'token', 'access_token', 'api_key', 'password', 'signature', 'Secret', 'AUTH'):
        with pytest.raises(CollectionError): origin(f'https://example.org/page?{key}=x')
    assert origin('https://example.org/page?q=python') == 'https://example.org'


# ---- round 3 ----
def _eligibility(tmp_path, lic):
    from dataclasses import replace
    c = collector(tmp_path/'data')
    path = tmp_path/'t'; path.write_text('Payload for ' + repr(lic))
    c.ingest_file(replace(source('https://example.org/d', 'text', training_reviewed=True), license=lic), path)
    m = c.export()
    return json.loads((c.root/m['shards'][0]['path']).read_text().splitlines()[0])['training_eligible']


@pytest.mark.parametrize('lic', [
    '\uff35\uff2e\uff2b\uff2e\uff2f\uff37\uff2e', 'All Rights Reserved.', 'none', 'n/a', 'proprietary', 'unknown', 'GPL-3.0',
    'cc-by-nc-4.0', ' - ', 'm\u200bit', 'mit license', 'cc-by-4.0-extra', 'cc-by-4',
])
def test_license_allowlist_denies(tmp_path, lic):
    assert _eligibility(tmp_path, lic) is False


@pytest.mark.parametrize('lic', [' Apache-2.0 ', 'CC0-1.0', 'BSD-3-Clause', 'bsd-2-clause', 'public-domain-explicit'])
def test_license_allowlist_allows_reviewed_variants(tmp_path, lic):
    assert _eligibility(tmp_path, lic) is True


def test_license_allowlist_still_requires_review_and_not_owner_or_cc(tmp_path):
    from dataclasses import replace
    c = collector(tmp_path/'data')
    path = tmp_path/'t'; path.write_text('x')
    c.ingest_file(replace(source('https://example.org/d', 'text', training_reviewed=False), license='mit'), path)
    row = json.loads((c.root/c.export()['shards'][0]['path']).read_text().splitlines()[0])
    assert row['training_eligible'] is False


def test_warc_30mb_skipped_record_stops_at_parse_limit(tmp_path):
    out = io.BytesIO(); writer = WARCWriter(out, gzip=True)
    headers = StatusAndHeaders('200 OK', [('Content-Type', 'application/octet-stream')], protocol='HTTP/1.0')
    writer.write_record(writer.create_warc_record('https://example.org/big.bin', 'response', payload=io.BytesIO(b'x'*30_000_000), http_headers=headers))
    path = tmp_path/'big.warc.gz'; path.write_bytes(out.getvalue())
    c = collector(tmp_path/'data', max_parse_bytes=5000)
    with pytest.raises(CollectionError, match='WARC'):
        c.ingest_file(source('https://data.commoncrawl.org/big.warc.gz', 'commoncrawl'), path)
    assert c.export()['records'] == 0


def test_warc_skipped_record_drain_is_chunked_and_bounded(tmp_path, monkeypatch):
    from app.mass_collection import engine
    reads = []
    real = engine.ArchiveIterator
    class Spy:
        def __init__(self, f):
            self.it = real(f)
        def __iter__(self):
            for rec in self.it:
                stream = rec.content_stream()
                orig = stream.read
                def read(n=-1, _o=orig):
                    reads.append(n); return _o(n)
                rec.content_stream = lambda s=stream, r=read: type('S', (), {'read': staticmethod(r)})()
                yield rec
    monkeypatch.setattr(engine, 'ArchiveIterator', Spy)
    out = io.BytesIO(); writer = WARCWriter(out, gzip=True)
    headers = StatusAndHeaders('200 OK', [('Content-Type', 'application/octet-stream')], protocol='HTTP/1.0')
    writer.write_record(writer.create_warc_record('https://example.org/big.bin', 'response', payload=io.BytesIO(b'x'*3_000_000), http_headers=headers))
    path = tmp_path/'b.warc.gz'; path.write_bytes(out.getvalue())
    c = collector(tmp_path/'data', max_parse_bytes=100_000)
    with pytest.raises(CollectionError):
        c.ingest_file(source('https://data.commoncrawl.org/b.warc.gz', 'commoncrawl'), path)
    assert reads and all(n != -1 and n <= 1_048_576 for n in reads)


@pytest.mark.parametrize('payload', [
    {'mine': {'origin': 'https://example.org', 'token': 5, 'owner_confirmed': True}},
    {'mine': {'origin': 'https://example.org', 'token': None, 'owner_confirmed': True}},
    {'mine': ['https://example.org', 'x', True]},
    {'mine': 'row'},
    {'mine': None},
    ['mine'],
    None,
    'str',
    5,
])
def test_structurally_corrupt_credentials_raise_collection_error(tmp_path, payload):
    from app.mass_collection.credentials import CredentialStore
    store = CredentialStore(tmp_path/'credentials.json', 't', master_secret='local-test-key')
    (tmp_path/'credentials.json').write_text(json.dumps(payload))
    with pytest.raises(CollectionError): store.headers('mine', 'https://example.org/page')


@pytest.mark.parametrize('payload', [['x'], None, 'str'])
def test_save_over_corrupt_store_raises_collection_error(tmp_path, payload):
    from app.mass_collection.credentials import CredentialStore
    store = CredentialStore(tmp_path/'credentials.json', 't', master_secret='local-test-key')
    (tmp_path/'credentials.json').write_text(json.dumps(payload))
    with pytest.raises(CollectionError): store.save('mine', 'https://example.org', 'tok', owner_confirmed=True)


@pytest.mark.parametrize('query', ['token', 'x-API-Key=1', 'access-token=1', 'X_Auth_Token=1', 'sessionid=1', 'JWT=1', 'bearer=1', 'client_secret=1', 'credentials=1', 'passwd=1', 'pwd=1', 'sig=1', 'Authorization=1', 'q=1&token', 'apiKey=1', 'PASS=1', 'X-Amz-Signature=1'])
def test_query_key_screen_normalized_substring_and_blank(query):
    from app.mass_collection.engine import origin
    with pytest.raises(CollectionError): origin('https://example.org/page?' + query)


def test_query_key_screen_allows_benign():
    from app.mass_collection.engine import origin
    assert origin('https://example.org/p?q=python&page=2&lang=en') == 'https://example.org'


@pytest.mark.parametrize('address', [
    'fec0::1', 'febf::1' if False else 'fec0:0:0:1::5', 'feff::1', '192.0.0.9', '192.0.0.10', '192.0.0.1', '192.88.99.1', '2001:20::1', '2001:2f::1',
    '::ffff:127.0.0.1', '::ffff:10.0.0.1', '::ffff:192.0.0.9', '2002:7f00:1::1', '2002:0a00:0001::1', '2002:c000:0009::1', '64:ff9b::7f00:1', '64:ff9b::a00:1', '64:ff9b::c000:9', '64:ff9b:1::1', '::ffff:0.0.0.0',
    '2001:0:4136:e378:8000:63bf:3fff:fdd2',
])
def test_dns_pin_explicit_denylist_and_unwrap(tmp_path, monkeypatch, address):
    import socket as real_socket
    from app.mass_collection import engine
    fam = real_socket.AF_INET6 if ':' in address else real_socket.AF_INET
    monkeypatch.setattr(engine.socket, 'getaddrinfo', lambda *a, **k: [(fam, real_socket.SOCK_STREAM, 6, '', (address, 80))])
    c = Collector(tmp_path/'d', limits=Limits(request_interval=0))
    with pytest.raises(CollectionError, match='network target rejected'):
        c._pinned_url('http://example.org/page')


def test_dns_pin_allows_public_and_unwrapped_public(tmp_path, monkeypatch):
    import socket as real_socket
    from app.mass_collection import engine
    for address in ('93.184.216.34', '2606:4700:4700::1111', '::ffff:93.184.216.34', '64:ff9b::5db8:d822', '2002:5db8:d822::1'):
        fam = real_socket.AF_INET6 if ':' in address else real_socket.AF_INET
        monkeypatch.setattr(engine.socket, 'getaddrinfo', lambda *a, _f=fam, _a=address, **k: [(_f, real_socket.SOCK_STREAM, 6, '', (_a, 80))])
        c = Collector(tmp_path/'d', limits=Limits(request_interval=0))
        assert c._pinned_url('http://example.org/page')[2] == 'example.org', address


# ---- round 4 ----
def _warc(tmp_path, name='r4.warc.gz', http=None, warc=None, body=b'<p>ok</p>', gzip_=True):
    out = io.BytesIO(); writer = WARCWriter(out, gzip=gzip_)
    h = StatusAndHeaders('200 OK', [('Content-Type', 'text/html')] + list(http or []), protocol='HTTP/1.0')
    writer.write_record(writer.create_warc_record('https://example.org/a', 'response', payload=io.BytesIO(body), http_headers=h, warc_headers_dict=warc or {}))
    path = tmp_path/name; path.write_bytes(out.getvalue())
    return path


def _ingest_warc(tmp_path, path, **limits):
    c = collector(tmp_path/'data', **limits)
    return c, c.ingest_file(source('https://data.commoncrawl.org/x.warc.gz', 'commoncrawl'), path)


def test_warc_huge_http_header_line_rejected_with_default_limits(tmp_path):
    path = _warc(tmp_path, http=[('X-Big', 'a'*5_000_000)])
    with pytest.raises(CollectionError):
        _ingest_warc(tmp_path, path)


def test_warc_huge_warc_header_line_rejected_with_default_limits(tmp_path):
    path = _warc(tmp_path, warc={'X-Big': 'a'*5_000_000})
    with pytest.raises(CollectionError):
        _ingest_warc(tmp_path, path)


def test_warc_many_header_lines_rejected(tmp_path):
    path = _warc(tmp_path, http=[(f'X-{i}', 'v') for i in range(200_000)])
    with pytest.raises(CollectionError):
        _ingest_warc(tmp_path, path)


def test_warc_headers_charged_to_parse_quota(tmp_path):
    path = _warc(tmp_path, http=[(f'X-{i}', 'v'*20) for i in range(300)])
    with pytest.raises(CollectionError):
        _ingest_warc(tmp_path, path, max_parse_bytes=3000)


def test_warc_normal_still_ingests(tmp_path):
    c, r = _ingest_warc(tmp_path, _warc(tmp_path, http=[('X-A', 'b')]))
    assert r['inserted'] == 1


@pytest.mark.parametrize('data', [b'WARC/1.0\r\nbad\r\n\r\n', b'not a warc at all', b'\x1f\x8b\x08\x00garbage-gzip', b'WARC/1.0\r\nWARC-Type: response\r\nContent-Length: abc\r\n\r\n'])
def test_warc_corrupt_maps_to_collection_error(tmp_path, data):
    p = tmp_path/'bad.warc.gz'; p.write_bytes(data)
    with pytest.raises(CollectionError):
        _ingest_warc(tmp_path, p)


def test_warc_truncated_gzip_maps_to_collection_error(tmp_path):
    p = _warc(tmp_path); raw = p.read_bytes(); p.write_bytes(raw[:len(raw)//2])
    with pytest.raises(CollectionError):
        _ingest_warc(tmp_path, p)


def _cred_store(tmp_path):
    from app.mass_collection.credentials import CredentialStore
    return CredentialStore(tmp_path/'credentials.json', 't', master_secret='local-test-key')


def test_credentials_deeply_nested_json_is_collection_error(tmp_path):
    store = _cred_store(tmp_path)
    (tmp_path/'credentials.json').write_text('['*200000 + ']'*200000)
    with pytest.raises(CollectionError): store.headers('mine', 'https://example.org')
    with pytest.raises(CollectionError): store.save('mine', 'https://example.org', 'tok', owner_confirmed=True)


@pytest.mark.parametrize('flag', ['yes', 'true', 1, 'True', float('nan'), None, [], 0.5])
def test_credentials_save_requires_literal_true(tmp_path, flag):
    with pytest.raises(CollectionError):
        _cred_store(tmp_path).save('mine', 'https://example.org', 'tok', owner_confirmed=flag)


@pytest.mark.parametrize('raw', ['"yes"', 'NaN', '1', '"true"', 'null', '[]'])
def test_credentials_headers_requires_stored_true(tmp_path, raw):
    store = _cred_store(tmp_path)
    store.save('mine', 'https://example.org', 'tok', owner_confirmed=True)
    assert store.headers('mine', 'https://example.org')['Authorization'] == 'Bearer tok'
    p = tmp_path/'credentials.json'
    p.write_text(p.read_text().replace('"owner_confirmed": true', '"owner_confirmed": ' + raw))
    with pytest.raises(CollectionError): store.headers('mine', 'https://example.org')


@pytest.mark.parametrize('query', [
    'a=1&access%2Dtoken=1', 'a=1;token=1', 'a=1;api_key=2', 'tok%252Ben=1', '%2574oken=1', '%25252574oken=1', 'tok\u200ben=1', 'tok%E2%80%8Ben=1', 'tok%00en=1', 'tok\x01en=1',
    '\uff54oken=1', 'T.O.K.E.N=1', 'api key=1', 'x.secret=1', 'q=Bearer%20abcdefghijklmnopqrstuv', 'q=bearer+abcdefghijklmnopqrstuv',
    'q=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl', 'q=%65yJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2ln',
])
def test_query_key_screen_round4(query):
    from app.mass_collection.engine import origin
    with pytest.raises(CollectionError): origin('https://example.org/p?' + query)


@pytest.mark.parametrize('path', ['/token/abc', '/api/Token/abc', '/a/%74oken/b', '/api_key/x', '/a;token=1/b', '/x/eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2ln'])
def test_path_token_segments_rejected(path):
    from app.mass_collection.engine import origin
    with pytest.raises(CollectionError): origin('https://example.org' + path)


def test_query_screen_round4_allows_benign():
    from app.mass_collection.engine import origin
    assert origin('https://example.org/blog/tokenizer-notes/keyboard?q=bearer+bonds&page=2;lang=en') == 'https://example.org'


@pytest.mark.parametrize('lic', ['-mit', 'mit-', 'cc-by-4.0+', 'mit+', 'MIT.', 'MIT\u200b', 'CC-BY\u20134.0', 'CC\u2011BY-4.0', 'cc--by-4.0', 'cc_by_sa_4.0', 'cc-by\u200b-4.0', '.mit', 'apache-2.0;', '(mit)', 'mit/apache-2.0', 'mit or apache-2.0', '\uff2d\uff29\uff34', 'MIT\u00a0x'])
def test_license_exact_token_only(tmp_path, lic):
    assert _eligibility(tmp_path, lic) is False


@pytest.mark.parametrize('lic', ['MIT', ' mit ', '\tApache-2.0\n', 'CC-BY-4.0', 'cc0-1.0', 'BSD-3-Clause', 'public-domain-explicit'])
def test_license_exact_token_allowed(tmp_path, lic):
    assert _eligibility(tmp_path, lic) is True


@pytest.mark.parametrize('address', [
    '2002:5db8:d822:0:0:5efe:0a00:0001', '2002:5db8:d822::200:5efe:7f00:1', '2002:5db8:d822:1:0:5efe:c0a8:1', '2002:5db8:d822::5efe:a00:1',
    '192.31.196.1', '192.52.193.1', '192.175.48.1', '2001:1::1', '2001:1:0:1::5', '2001:3::1', '2001:4:112::1', '2001:30::1', '2001:3f::1',
])
def test_dns_pin_round4_denies(tmp_path, monkeypatch, address):
    test_dns_pin_explicit_denylist_and_unwrap(tmp_path, monkeypatch, address)


def test_dns_pin_round4_allows_public(tmp_path, monkeypatch):
    import socket as real_socket
    from app.mass_collection import engine
    for address in ('2002:5db8:d822:0:0:5efe:5db8:d822', '2002:5db8:d822::1', '192.31.195.1', '2606:4700:4700::1111'):
        fam = real_socket.AF_INET6 if ':' in address else real_socket.AF_INET
        monkeypatch.setattr(engine.socket, 'getaddrinfo', lambda *a, _f=fam, _a=address, **k: [(_f, real_socket.SOCK_STREAM, 6, '', (_a, 80))])
        c = Collector(tmp_path/'d', limits=Limits(request_interval=0))
        assert c._pinned_url('http://example.org/page')[2] == 'example.org', address
