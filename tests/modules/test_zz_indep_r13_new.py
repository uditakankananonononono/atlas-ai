"""Independent R13 probes. Local real Chromium/daemon, no production monkeypatches.
Cookie-attribute assertions test the documented any-difference/restore contract.
Other cases watch raw outgoing paths, Cookie, Referer and bodies after CLICK_NAV.
"""
import base64
import json
import time
import pytest
from test_m18_login_browser import setup, _compose_with_values
from test_m18_login_round5 import _nav_click

SECRET = 'UNAPPROVEDSECRET'
B64 = base64.b64encode(SECRET.encode()).decode()
ATTRS = {
    'sameSite': ('Lax', 'Strict'),
    'expires': (-1, int(time.time()) + 3600),
    'secure': (False, True),
}

async def compose(setup):
    site = setup[6]
    site.html_hook = lambda html: html.replace('<body>', '<body><a id="lnk" href="/idea?page=2">go</a>')
    try:
        return (await _compose_with_values(setup))[0]
    finally:
        site.html_hook = None

async def click(setup):
    try:
        return await _nav_click(setup, '#lnk')
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}

@pytest.mark.asyncio
@pytest.mark.parametrize('attr', sorted(ATTRS))
async def test_any_cookie_attribute_difference_refuses_and_restores(setup, attr):
    page = setup[5]
    before, after = ATTRS[attr]
    seed = {'name': 'baseline', 'value': 'fixed', 'domain': '127.0.0.1', 'path': '/', attr: before}
    await page.context.add_cookies([seed])
    page = await compose(setup)
    await page.wait_for_timeout(150)
    snapshot = [c for c in await page.context.cookies() if c['name'] == 'baseline'][0]
    changed = dict(snapshot); changed[attr] = after
    await page.context.add_cookies([changed])
    assert [c for c in await page.context.cookies() if c['name']=='baseline'][0][attr] == after
    setup[6].hits.clear()
    answer = await click(setup)
    current = [c for c in await page.context.cookies() if c['name']=='baseline'][0]
    print('ATTRIBUTE', attr, 'answer', answer, 'before', snapshot, 'after', current, 'hits', setup[6].hits)
    assert not answer['ok'], (attr, 'documented any-difference refusal failed', answer)
    assert current[attr] == snapshot[attr], (attr, 'not restored', current)

PRE = {
    'httponly_path_idea': ('fetch', 'hc='+B64+'; HttpOnly; Path=/idea', None),
    'httponly_domain_scoped': ('fetch', 'hc='+B64+'; HttpOnly; Domain=127.0.0.1; Path=/', None),
    'httponly_strict': ('fetch', 'hc='+B64+'; HttpOnly; SameSite=Strict; Path=/', None),
    'httponly_secure': ('fetch', 'hc='+B64+'; HttpOnly; Secure; Path=/', None),
    'httponly_redirect_response': ('redirect', 'hc='+B64+'; HttpOnly; Path=/', None),
    'httponly_image_subresource': ('image', 'hc='+B64+'; HttpOnly; Path=/', None),
    'httponly_existing_cookie_overwrite': ('fetch', 'baseline='+B64+'; HttpOnly; Path=/', 'fixed'),
    'httponly_existing_cookie_delete': ('fetch', 'baseline=gone; HttpOnly; Max-Age=0; Path=/', 'fixed'),
    'httponly_other_tab_response': ('other', 'hc='+B64+'; HttpOnly; Path=/', None),
}

@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(PRE))
async def test_server_cookie_sources_refuse_and_restore(setup, name):
    kind, header, existing = PRE[name]
    site = setup[6]; page = setup[5]; raw = []; original = site.do_GET
    if existing:
        await page.context.add_cookies([{'name':'baseline','value':existing,'domain':'127.0.0.1','path':'/','httpOnly':True}])
    def get(self):
        raw.append((self.path, self.headers.get('Cookie'), self.headers.get('Referer')))
        if self.path.startswith('/cookie-source'):
            self.send_response(302 if kind=='redirect' else 200)
            self.send_header('Set-Cookie', header)
            if kind=='redirect': self.send_header('Location', '/cookie-end')
            self.end_headers(); self.wfile.write(b'OK'); return
        return original(self)
    site.do_GET = get
    try:
        page = await compose(setup); await page.fill('#draft', SECRET)
        before = await page.context.cookies()
        if kind=='image': await page.evaluate("new Image().src='/cookie-source'")
        elif kind=='other':
            other = await page.context.new_page(); await other.goto(setup[1].origin+'/cookie-source')
        else: await page.evaluate("fetch('/cookie-source')")
        await page.wait_for_timeout(300)
        assert await page.context.cookies() != before, 'vector did not change jar'
        raw.clear(); answer = await click(setup); await page.wait_for_timeout(250)
        after = await page.context.cookies()
        print('COOKIE_SOURCE', name, 'answer', answer, 'raw', raw, 'jar', after)
        assert not answer['ok'] and not any(r[0].startswith('/idea') for r in raw)
        assert after == before, (name, 'jar not restored', before, after)
    finally:
        site.do_GET = original

@pytest.mark.asyncio
@pytest.mark.parametrize('channel', ['localStorage', 'sessionStorage', 'windowName'])
async def test_replay_into_landed_page_is_blocked(setup, channel):
    site=setup[6]; original=site.do_GET; raw=[]
    source = {'localStorage': "localStorage.getItem('d')", 'sessionStorage': "sessionStorage.getItem('d')", 'windowName':'window.name'}[channel]
    def get(self):
        raw.append((self.path,self.headers.get('Cookie'),self.headers.get('Referer')))
        if self.path.startswith('/idea?page=2'):
            self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers()
            self.wfile.write(("<html><body><script>setTimeout(()=>{new Image().src='/replay?d='+btoa("+source+"||'')},2000)</script></body></html>").encode()); return
        return original(self)
    site.do_GET=get
    try:
        page=await compose(setup); await page.fill('#draft',SECRET)
        await page.evaluate("s => {"+ ('window.name=s' if channel=='windowName' else channel+".setItem('d',s)")+"}",SECRET)
        raw.clear(); answer=await click(setup); await page.wait_for_timeout(2600)
        print('LANDED_REPLAY',channel,answer,raw)
        assert not any(m in json.dumps(raw) for m in (SECRET,B64,SECRET.encode().hex()))
    finally: site.do_GET=original

@pytest.mark.asyncio
async def test_documented_navigation_presence_bit_still_exists(setup):
    page=await compose(setup); site=setup[6]
    await page.fill('#draft','1')
    await page.evaluate("document.querySelector('#lnk').addEventListener('click',e=>{if(document.querySelector('#draft').value==='1')e.preventDefault()})")
    site.hits.clear(); await click(setup)
    absent=not any(h[2].startswith('/idea?page=2') for h in site.hits)
    await page.fill('#draft','0'); site.hits.clear(); await click(setup)
    present=any(h[2].startswith('/idea?page=2') for h in site.hits)
    print('DOCUMENTED_PRESENCE_BIT',absent,present)
    assert absent and present
