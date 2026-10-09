"""A16 real Chromium, intercepted fixture transport; no live site acceptance."""
import json
import shutil
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m13_browser_agent import security
from app.modules.m13_browser_agent.playwright_adapter import PlaywrightSessions
from app.modules.m13_browser_agent.service import Service
from app.modules.m13_browser_agent.store import SQLStore
from app.modules.m13_browser_agent.forms import FieldDescriptor

HTML = '''<!doctype html><html><head><title>A16 controlled fixture</title>
<style>body{font:20px sans-serif;background:#f2f5fa;margin:48px}main{padding:32px;background:white;width:620px}input{display:block;font-size:20px;margin:12px 0;padding:10px}h1{color:#204070}</style></head>
<body><main><h1>A16 browser consumer fixture</h1><label>Email<input id="email" name="email"></label><p id="state">Local fixture. No submission.</p></main></body></html>'''


class FixtureRoute:
    def __init__(self, route, seen):
        self.route, self.seen = route, seen
        self.request = route.request
    async def abort(self, reason):
        self.seen.append(('blocked', self.request.url))
        await self.route.abort(reason)
    async def continue_(self):
        # Production guard has accepted the URL. Transport is intercepted here.
        assert self.request.url.startswith('https://a16-fixture.test/')
        self.seen.append(('fulfilled', self.request.url))
        await self.route.fulfill(status=200, content_type='text/html', body=HTML)


@pytest.mark.asyncio
async def test_real_m13_chromium_dom_artifacts_tenant_isolation(tmp_path, monkeypatch):
    def fixture_dns(host, port):
        if host == 'a16-fixture.test':
            return {'93.184.216.34'}
        raise AssertionError('fixture attempted unexpected DNS')
    monkeypatch.setattr(security, '_resolve', fixture_dns)
    root = tmp_path / 'artifacts'
    sessions = PlaywrightSessions(str(root), allowed_hosts={'a16-fixture.test'}, max_sessions=2)
    engine = create_engine(f'sqlite:///{tmp_path / "audit.sqlite"}')
    Base.metadata.create_all(engine)
    store = SQLStore(sessionmaker(bind=engine, expire_on_commit=False))
    service = Service(sessions, None, store, artifact_root=str(root), allowed_hosts={'a16-fixture.test'})
    seen = []
    try:
        page_a = await sessions.page('tenant-a', 'same-session')
        page_b = await sessions.page('tenant-b', 'same-session')
        for page in (page_a, page_b):
            async def intercepted(route):
                await sessions._guard_route(FixtureRoute(route, seen))
            await page.context.route('**/*', intercepted)
        result = await service.navigate('tenant-a', 'same-session', 'https://a16-fixture.test/form')
        assert result == {'status':'ok', 'url':'https://a16-fixture.test/form', 'http_status':200}
        await service.navigate('tenant-b', 'same-session', 'https://a16-fixture.test/form')
        assert page_a.context is not page_b.context
        await page_a.context.add_cookies([{'name':'fixture', 'value':'tenant-a', 'url':'https://a16-fixture.test'}])
        assert any(c['value'] == 'tenant-a' for c in await page_a.context.cookies())
        assert await page_b.context.cookies() == []
        mapping = await service.fill('tenant-a', 'same-session', [FieldDescriptor('#email', label='Email', name='email', input_type='email')], {'email':'fixture@example.test'})
        assert mapping == {'#email':'fixture@example.test'}
        assert await service.read_values('tenant-a', 'same-session', ['#email']) == mapping
        assert await page_b.locator('#email').input_value() == ''
        assert 'A16 browser consumer fixture' in await service.extract('tenant-a', 'same-session')
        shot = await service.screenshot('tenant-a', 'same-session')
        assert Path(shot).read_bytes().startswith(b'\x89PNG')
        evidence = Path('/tmp/atlas-a16-visual.png')
        shutil.copyfile(shot, evidence)
        events = await store.audit_events('tenant-a', 'same-session')
        assert [e.action.value for e in events] == ['screenshot','extract','readback','fill','navigate']
        assert len(await store.audit_events('tenant-b', 'same-session')) == 1
        with pytest.raises(ValueError, match='persistence mode'):
            await sessions.page('tenant-a', 'same-session', persistent=True)
        with pytest.raises(RuntimeError, match='capacity'):
            await sessions.page('tenant-c', 'extra')
        with pytest.raises(security.NavigationBlocked):
            await service.navigate('tenant-a', 'same-session', 'http://127.0.0.1/private')
        # Real Chromium subresource request passes through unchanged guard and aborts.
        await page_a.evaluate("fetch('http://127.0.0.1/private').catch(() => null)")
        assert any(kind == 'blocked' and '127.0.0.1' in url for kind, url in seen)
        assert sum(kind == 'fulfilled' for kind, _ in seen) == 2
        assert await sessions.close_session('tenant-a', 'same-session') is True
        assert await sessions.close_session('tenant-a', 'same-session') is False
        har = json.loads((root / 'tenant-a' / 'same-session' / 'audit.har').read_text())
        assert har['log']['entries']
    finally:
        await sessions.close()
        service.artifacts.close()
        engine.dispose()
    assert sessions._browser is None and sessions._pw is None and sessions._sessions == {}


@pytest.mark.asyncio
@pytest.mark.parametrize('url', ['http://127.0.0.1/private', 'http://metadata.google.internal/latest', 'http://localhost/admin'])
async def test_unchanged_route_guard_aborts_forbidden_before_continue(tmp_path, url):
    sessions = PlaywrightSessions(str(tmp_path / 'root'))
    class Request:
        pass
    class Route:
        def __init__(self):
            self.request = Request()
            self.request.url = url
            self.aborts, self.continues = [], []
        async def abort(self, reason): self.aborts.append(reason)
        async def continue_(self): self.continues.append(True)
    route = Route()
    try:
        await sessions._guard_route(route)
        assert route.aborts == ['blockedbyclient'] and route.continues == []
    finally:
        await sessions.close()
