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
