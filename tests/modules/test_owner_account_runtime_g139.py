"""Offline protocol tests. MockTransport is not provider/live acceptance."""
import concurrent.futures
import threading
import httpx
import pytest
from app.integrations.owner_account_runtime_g139 import OwnerAccountRuntime as RawOwnerAccountRuntime, AccountRefusal, binding_digest


def declared_reads(tenant, url):
    from urllib.parse import urlsplit
    host=urlsplit(url).netloc
    return {'tos': {host: {'allowed_kinds':['read'], 'automation_allowed':True}},
            'rate_limits': {host: {'read': {'max':100,'window_seconds':60}}}}


def OwnerAccountRuntime(*args, **kwargs):
    kwargs.setdefault('outbound_declarations', declared_reads)
    return RawOwnerAccountRuntime(*args, **kwargs)


@pytest.fixture
def setup(tmp_path):
    calls, control = [], {'authority': True, 'read': True, 'id': 123, 'type': 'User', 'token': 'secret', 'status': 200}
    def handler(request):
        calls.append(request)
        if request.url.path in ('/user', '/v1/userinfo'):
            return httpx.Response(control['status'], json={'id': control['id'], 'type': control['type'], 'sub': control.get('sub', 'abc')})
        if control.get('fail'): raise httpx.ReadTimeout('secret provider text')
        return httpx.Response(control.get('result_status', 200), json={'ok': True})
    def factory():
        return OwnerAccountRuntime(tmp_path/'accounts.db', authority=lambda ref, digest: control['authority'],
                                   read_authority=lambda *args: control['read'], credential=lambda *args: control['token'],
                                   transport=httpx.MockTransport(handler))
    gateway = factory()
    gateway.bind('tenant1', 'github', '123', 'approval1')
    return gateway, calls, control, factory


def test_actual_dispatch_uses_same_token_and_reprobes(setup):
    gate, calls, _, _ = setup
    assert gate.get('tenant1', 'github', '/repos/a/b').status_code == 200
    assert gate.get('tenant1', 'github', '/repos/a/b').json() == {'ok': True}
    assert [r.url.path for r in calls] == ['/user','/repos/a/b','/user','/repos/a/b']
    assert all(r.headers['authorization']=='Bearer secret' for r in calls)
    assert [r['outcome'] for r in gate.receipts('tenant1')] == ['DISPATCHED', 'DISPATCHED']


@pytest.mark.parametrize('key,value', [('authority',False),('authority',1),('read',False),('read',1),('token',''),('token','bad\r\nvalue')])
def test_control_failure_never_dispatches(setup, key, value):
    gate, calls, control, _ = setup
    control[key] = value
    with pytest.raises(AccountRefusal): gate.get('tenant1','github','/repos/a/b')
    assert calls == []
    assert gate.receipts('tenant1')[-1]['outcome'] == 'REFUSED'


@pytest.mark.parametrize('key,value', [('id',456),('id',True),('id',0),('id','123'),('type','Bot'),('status',401),('status',302)])
def test_identity_failure_never_dispatches(setup,key,value):
    gate,calls,control,_ = setup
    control[key] = value
    with pytest.raises(AccountRefusal):gate.get('tenant1','github','/repos/a/b')
    assert [r.url.path for r in calls] == ['/user']
    assert gate.receipts('tenant1')[-1]['outcome'] == 'REFUSED'


def test_tenant_separation(setup):
    gate,calls,_,_ = setup
    with pytest.raises(AccountRefusal):gate.get('tenant2','github','/repos/a/b')
    assert not calls
    assert gate.receipts('tenant1') == []
    assert len(gate.receipts('tenant2')) == 1


def test_revocation_persists_across_instances(setup):
    gate,calls,_,factory = setup
    other = factory();other.revoke('tenant1','github')
    with pytest.raises(AccountRefusal):gate.get('tenant1','github','/repos/a/b')
    assert not calls


def test_replacement_requires_revoke_and_current_authority(setup):
    gate,_,control,_=setup
    with pytest.raises(AccountRefusal):gate.bind('tenant1','github','456','approval2')
    gate.revoke('tenant1','github');control['authority']=False
    with pytest.raises(AccountRefusal):gate.bind('tenant1','github','456','approval2')


@pytest.mark.parametrize('path',['//attacker.test/a','/../x','/a/../x','/%2e%2e/x','/a?token=secret','/a#x','/a\\x','http://attacker.test','/a\nX: y'])
def test_destination_injection_refused_before_network(setup,path):
    gate,calls,_,_=setup
    with pytest.raises(ValueError):gate.get('tenant1','github',path)
    assert not calls


def test_ambiguous_network_failure_persisted_no_secret(setup):
    gate,_,control,_=setup;control['fail']=True
    with pytest.raises(AccountRefusal) as error:gate.get('tenant1','github','/repos/a/b')
    assert str(error.value)=='owner-account request ambiguous'
    rows=gate.receipts('tenant1')
    assert rows[0]['outcome']=='AMBIGUOUS'
    assert 'secret' not in str(rows)


def test_http_error_is_not_semantic_success(setup):
    gate,_,control,_=setup;control['result_status']=403
    assert gate.get('tenant1','github','/repos/a/b').status_code == 403
    assert gate.receipts('tenant1')[0]['outcome']=='DISPATCHED'


def test_authority_digest_is_exact_tenant_service_subject(tmp_path):
    observed=[]
    gate=OwnerAccountRuntime(tmp_path/'db',authority=lambda ref,d:(observed.append((ref,d)) or True),
                            read_authority=lambda *a:True,credential=lambda *a:'unused')
    gate.bind('tenant','google','sub123','ref123')
    assert observed==[('ref123',binding_digest('tenant','google','sub123'))]
    assert binding_digest('other','google','sub123')!=observed[0][1]


@pytest.mark.parametrize('sub',['abc','wrong','',123,'a\n','é'])
def test_google_uses_subject_not_display_or_email(setup,sub):
    gate,calls,control,_=setup;control['sub']=sub
    gate.bind('tenant1','google','abc','approval-google')
    if sub=='abc':
        assert gate.get('tenant1','google','/drive/v3/files').status_code==200
        assert calls[-1].url.host=='www.googleapis.com'
    else:
        with pytest.raises(AccountRefusal):gate.get('tenant1','google','/drive/v3/files')
        assert len(calls)==1
    assert calls[0].url.host=='openidconnect.googleapis.com'


def test_read_authority_exact_url(tmp_path):
    observed=[]
    gate=OwnerAccountRuntime(tmp_path/'db',authority=lambda *a:True,
                            read_authority=lambda *a: (observed.append(a) or False),credential=lambda *a:'not-used')
    gate.bind('t','github','123','r')
    with pytest.raises(AccountRefusal):gate.get('t','github','/repos/a/b')
    assert observed==[('t','github','123','https://api.github.com/repos/a/b')]


def test_revoke_serializes_with_inflight_dispatch(tmp_path):
    started, release, revoked = threading.Event(), threading.Event(), threading.Event()
    def handler(request):
        if request.url.path=='/user': return httpx.Response(200,json={'id':123,'type':'User'})
        started.set();assert release.wait(5)
        return httpx.Response(200,json={})
    def factory():return OwnerAccountRuntime(tmp_path/'db',authority=lambda *a:True,read_authority=lambda *a:True,
                                             credential=lambda *a:'secret',transport=httpx.MockTransport(handler))
    gate=factory();gate.bind('t','github','123','r');other=factory()
    def revoker():other.revoke('t','github');revoked.set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(gate.get,'t','github','/repos/a/b');assert started.wait(5)
        second=pool.submit(revoker)
        assert not revoked.wait(.05)
        release.set();assert first.result().status_code==200;second.result()
    with pytest.raises(AccountRefusal):gate.get('t','github','/repos/a/b')


def test_unsupported_provider(setup):
    gate,calls,_,_=setup
    with pytest.raises(ValueError):gate.get('tenant1','unknown','/x')
    assert not calls


def test_returned_response_does_not_retain_credential(setup):
    gate,_,_,_=setup
    response=gate.get('tenant1','github','/repos/a/b')
    assert 'authorization' not in response.request.headers


@pytest.mark.parametrize('identity_large',[True,False])
def test_response_size_bounded(tmp_path,identity_large):
    def handler(request):
        if request.url.path=='/user':
            return httpx.Response(200,json={'id':123,'type':'User','extra':'x'*70000}) if identity_large else httpx.Response(200,json={'id':123,'type':'User'})
        return httpx.Response(200,content=b'x'*(10485760+1))
    gate=OwnerAccountRuntime(tmp_path/'db',authority=lambda *a:True,read_authority=lambda *a:True,
                            credential=lambda *a:'secret',transport=httpx.MockTransport(handler))
    gate.bind('t','github','123','r')
    with pytest.raises(AccountRefusal):gate.get('t','github','/repos/a/b')
    assert gate.receipts('t')[0]['outcome']==('REFUSED' if identity_large else 'AMBIGUOUS')


def test_real_http_wire_via_explicit_offline_loopback_proxy(tmp_path):
    # Production destinations stay HTTPS. This test-only transport maps them
    # to loopback HTTP, exercising sockets, header encoding and response parsing.
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
    wire=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            wire.append((self.path,self.headers.get('Authorization')))
            body=b'{"id":123,"type":"User"}' if self.path=='/user' else b'{"result":"wire"}'
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    class LoopbackTransport(httpx.BaseTransport):
        def __init__(self):self.inner=httpx.HTTPTransport()
        def handle_request(self,request):
            mapped=httpx.Request(request.method,f'http://127.0.0.1:{server.server_port}'+request.url.path,headers=request.headers)
            return self.inner.handle_request(mapped)
        def close(self):self.inner.close()
    try:
        gate=OwnerAccountRuntime(tmp_path/'db',authority=lambda *a:True,read_authority=lambda *a:True,
                                credential=lambda *a:'wire-token',transport=LoopbackTransport())
        gate.bind('t','github','123','r')
        assert gate.get('t','github','/repos/a/b').json()=={'result':'wire'}
        assert wire==[('/user','Bearer wire-token'),('/repos/a/b','Bearer wire-token')]
        assert gate.receipts('t')[0]['outcome']=='DISPATCHED'
    finally:
        server.shutdown();server.server_close();thread.join(5)


def test_atlas_runtime_dispatch_uses_context_tenant(setup):
    import asyncio
    from app.runtime.integration import AtlasRuntime, RuntimeContext, Handoff
    from app.integrations.owner_account_runtime_g139 import register_owner_account_reads
    gate,calls,_,_=setup
    runtime=AtlasRuntime();register_owner_account_reads(runtime,gate)
    handoff=Handoff(source_module=21,target_module=22,operation='owner_account_read',payload={'service':'github','path':'/repos/a/b'})
    result=asyncio.run(runtime.dispatch(RuntimeContext('tenant1','actor','c1'),handoff))
    assert result['identity_checked'] is True
    assert result['http_status']==200
    assert runtime.trace[-1]['state']=='completed'
    count=len(calls)
    with pytest.raises(AccountRefusal):asyncio.run(runtime.dispatch(RuntimeContext('other','actor','c2'),handoff))
    assert len(calls)==count
    assert runtime.trace[-1]['state']=='failed'


def test_runtime_payload_cannot_replace_authority_or_tenant(setup):
    import asyncio
    from app.runtime.integration import AtlasRuntime, RuntimeContext, Handoff
    from app.integrations.owner_account_runtime_g139 import register_owner_account_reads
    gate,calls,_,_=setup
    runtime=AtlasRuntime();register_owner_account_reads(runtime,gate)
    for key in ('tenant','subject','authority','credential'):
        payload={'service':'github','path':'/repos/a/b',key:'override'}
        with pytest.raises(ValueError):asyncio.run(runtime.dispatch(RuntimeContext('tenant1','actor','c'),
            Handoff(source_module=21,target_module=22,operation='owner_account_read',payload=payload)))
    assert calls==[]


@pytest.mark.parametrize('permission',['authority','read'])
def test_permission_revoked_during_identity_probe(tmp_path,permission):
    state={'authority':True,'read':True};calls=[]
    def handler(request):
        calls.append(request.url.path);state[permission]=False
        return httpx.Response(200,json={'id':123,'type':'User'})
    gate=OwnerAccountRuntime(tmp_path/'db',authority=lambda *a:state['authority'],read_authority=lambda *a:state['read'],
                            credential=lambda *a:'token',transport=httpx.MockTransport(handler))
    gate.bind('t','github','123','r')
    with pytest.raises(AccountRefusal):gate.get('t','github','/repos/a/b')
    assert calls==['/user']
    assert gate.receipts('t')[0]['outcome']=='REFUSED'


@pytest.mark.parametrize('subject',['é','x'*256])
def test_malformed_subject_cannot_be_accepted_even_matching_binding(setup,subject):
    gate,calls,control,_=setup;control['sub']=subject
    gate.bind('tenant1','google',subject,'r')
    with pytest.raises(AccountRefusal):gate.get('tenant1','google','/drive/v3/files')
    assert len(calls)==1


def test_operation_redirect_never_followed_and_bearer_never_leaves(tmp_path):
    calls=[]
    def handler(request):
        calls.append((str(request.url),request.headers.get('authorization')))
        if request.url.path=='/user':return httpx.Response(200,json={'id':123,'type':'User'})
        if request.url.host=='api.github.com':return httpx.Response(302,headers={'Location':'https://attacker.test/collect'})
        return httpx.Response(200,json={'leaked':True})
    gate=OwnerAccountRuntime(tmp_path/'db',authority=lambda *a:True,read_authority=lambda *a:True,
                            credential=lambda *a:'token',transport=httpx.MockTransport(handler))
    gate.bind('t','github','123','r')
    response=gate.get('t','github','/repos/a/b')
    assert response.status_code==302
    assert calls==[('https://api.github.com/user','Bearer token'),('https://api.github.com/repos/a/b','Bearer token')]


def test_proxy_environment_not_honored(tmp_path,monkeypatch):
    from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
    contacts=[]
    class Proxy(BaseHTTPRequestHandler):
        def do_CONNECT(self):
            contacts.append(self.path);self.send_response(502);self.end_headers()
        def do_GET(self):
            contacts.append(self.path);self.send_response(502);self.end_headers()
        def log_message(self,*a):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Proxy)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    proxy=f'http://127.0.0.1:{server.server_port}'
    for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):monkeypatch.setenv(key,proxy)
    for key in ('NO_PROXY','no_proxy'):monkeypatch.setenv(key,'')
    calls=[]
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200,json={'id':123,'type':'User'} if request.url.path=='/user' else {'ok':True})
    try:
        gate=OwnerAccountRuntime(tmp_path/'db',authority=lambda *a:True,read_authority=lambda *a:True,
                                credential=lambda *a:'token',transport=httpx.MockTransport(handler))
        gate.bind('t','github','123','r')
        assert gate.get('t','github','/repos/a/b').status_code==200
        assert calls==['/user','/repos/a/b']
        assert contacts==[]
    finally:
        server.shutdown();server.server_close();thread.join(5)


def test_sqlite_lock_timeout_is_sanitized_account_refusal(setup):
    import sqlite3
    gate,calls,_,_=setup
    blocker=sqlite3.connect(gate.database)
    blocker.execute('BEGIN IMMEDIATE')
    try:
        with pytest.raises(AccountRefusal,match='storage unavailable or locked'):
            gate.get('tenant1','github','/repos/a/b')
        assert calls==[]
    finally:
        blocker.rollback();blocker.close()
    # A lock refusal happens before an auditable transaction can start.
    assert gate.receipts('tenant1')==[]


def test_proxy_environment_real_socket_without_injected_transport(tmp_path,monkeypatch):
    from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
    from app.integrations import owner_account_runtime_g139 as module
    origin_calls,proxy_calls=[],[]
    class Origin(BaseHTTPRequestHandler):
        def do_GET(self):
            origin_calls.append(self.path)
            body=b'{"id":123,"type":"User"}' if self.path=='/user' else b'{"ok":true}'
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*a):pass
    class Proxy(BaseHTTPRequestHandler):
        def do_GET(self):
            proxy_calls.append((self.path,self.headers.get('Authorization')))
            self.send_response(502);self.send_header('Content-Length','0');self.end_headers()
        def log_message(self,*a):pass
    origin=ThreadingHTTPServer(('127.0.0.1',0),Origin);proxy=ThreadingHTTPServer(('127.0.0.1',0),Proxy)
    threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (origin,proxy)]
    for t in threads:t.start()
    base=f'http://127.0.0.1:{origin.server_port}'
    # Test-only fixed destination override; no external network or production TLS claim.
    monkeypatch.setitem(module.PROVIDERS,'github',(base,base+'/user'))
    for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
        monkeypatch.setenv(key,f'http://127.0.0.1:{proxy.server_port}')
    for key in ('NO_PROXY','no_proxy'):monkeypatch.setenv(key,'')
    try:
        gate=OwnerAccountRuntime(tmp_path/'db',authority=lambda *a:True,read_authority=lambda *a:True,credential=lambda *a:'token')
        gate.bind('t','github','123','r')
        assert gate.get('t','github','/repos/a/b').status_code==200
        assert origin_calls==['/user','/repos/a/b']
        assert proxy_calls==[]
    finally:
        for s in (origin,proxy):s.shutdown();s.server_close()
        for t in threads:t.join(5)


@pytest.mark.parametrize('policy',['absent','automation','rate','second_destination'])
def test_outbound_policy_refusal_before_transport(tmp_path,policy):
    calls=[]
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200,json={'id':123,'type':'User'})
    def declarations(tenant,url):
        d=declared_reads(tenant,url)
        if policy=='automation':next(iter(d['tos'].values()))['automation_allowed']=False
        if policy=='rate':d['rate_limits']={}
        if policy=='second_destination' and url.endswith('/repos/a/b'):return {'tos':{}}
        return d
    kwargs={} if policy=='absent' else {'outbound_declarations':declarations}
    gate=RawOwnerAccountRuntime(tmp_path/'db',authority=lambda *a:True,read_authority=lambda *a:True,
                               credential=lambda *a:'token',transport=httpx.MockTransport(handler),**kwargs)
    gate.bind('t','github','123','r')
    with pytest.raises(AccountRefusal):gate.get('t','github','/repos/a/b')
    assert calls==(['/user'] if policy=='second_destination' else [])


def test_outbound_rate_history_survives_restart_and_counts_both_gets(tmp_path):
    calls=[]
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200,json={'id':123,'type':'User'})
    def declarations(tenant,url):
        d=declared_reads(tenant,url)
        next(iter(d['rate_limits'].values()))['read']['max']=2
        return d
    def factory():return RawOwnerAccountRuntime(tmp_path/'db',authority=lambda *a:True,read_authority=lambda *a:True,
        credential=lambda *a:'token',transport=httpx.MockTransport(handler),outbound_declarations=declarations)
    gate=factory();gate.bind('t','github','123','r')
    assert gate.get('t','github','/repos/a/b').status_code==200
    with pytest.raises(AccountRefusal):factory().get('t','github','/repos/a/b')
    assert calls==['/user','/repos/a/b']


def test_each_get_uses_isolated_canonical_gate_destination(setup,monkeypatch):
    from app.runtime.guardrails.enforcer import GuardrailEnforcer
    original=GuardrailEnforcer.dispatch_outbound
    observed=[]
    def dispatch(self,action,declarations,**kwargs):
        observed.append(action['url'])
        # Review canonical callback routing without allowing an arbitrary host.
        effect=kwargs['effect']
        kwargs['effect']=lambda canonical:effect({**canonical,'url':canonical['url']+'/canonical'})
        return original(self,action,declarations,**kwargs)
    monkeypatch.setattr(GuardrailEnforcer,'dispatch_outbound',dispatch)
    gate,calls,_,_=setup
    with pytest.raises(AccountRefusal):gate.get('tenant1','github','/repos/a/b')
    assert observed==['https://api.github.com/user']
    assert calls[0].url.path=='/user/canonical'
