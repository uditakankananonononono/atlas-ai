"""Independent R14 cookie probes (reviewer). Real Chromium, no production monkeypatches."""
import base64, json, time
import pytest
from test_m18_login_browser import setup, _compose_with_values
from test_m18_login_round5 import _nav_click

SECRET = 'UNAPPROVEDSECRET'
B64 = base64.b64encode(SECRET.encode()).decode()

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

def idea_cookie_headers(site):
    return [h for h in site.hits if h[2].startswith('/idea?page=2')]

async def jar(page):
    return sorted(await page.context.cookies(), key=lambda c: (c['name'], c['domain'], c['path'], str(c.get('partitionKey'))))

# P1 server plants a PARTITIONED cookie (CHIPS) via a script-triggered fetch
@pytest.mark.asyncio
async def test_p1_server_partitioned_cookie_refused_and_removed(setup):
    site = setup[6]; page = setup[5]; original = site.do_GET; raw = []
    def get(self):
        raw.append((self.path, self.headers.get('Cookie')))
        if self.path.startswith('/pc'):
            self.send_response(200); self.send_header('Set-Cookie', 'pc=' + B64 + '; Secure; Partitioned; Path=/; HttpOnly'); self.end_headers(); self.wfile.write(b'OK'); return
        return original(self)
    site.do_GET = get
    try:
        page = await compose(setup); await page.fill('#draft', SECRET)
        before = await jar(page)
        await page.evaluate("fetch('/pc')"); await page.wait_for_timeout(300)
        mid = await jar(page)
        print('P1 mid', mid)
        assert mid != before, 'vector ineffective (partitioned cookie not stored)'
        raw.clear(); answer = await click(setup); await page.wait_for_timeout(200)
        print('P1', answer, raw, await jar(page))
        assert not answer['ok'] and not any(r[0].startswith('/idea') for r in raw)
        assert await jar(page) == before
    finally: site.do_GET = original

# P2 baseline partitioned cookie mutated -> restored with its partition key
@pytest.mark.asyncio
async def test_p2_baseline_partitioned_cookie_value_change_restored(setup):
    page = setup[5]
    pk = setup[1].origin if hasattr(setup[1], 'origin') else 'http://127.0.0.1'
    seed = {'name': 'pbase', 'value': 'fixed', 'domain': '127.0.0.1', 'path': '/', 'secure': True, 'partitionKey': pk}
    try:
        await page.context.add_cookies([seed])
    except Exception as e:
        pytest.skip('cannot seed partitioned cookie: %s' % e)
    page = await compose(setup); await page.wait_for_timeout(150)
    before = await jar(page)
    assert any(c['name'] == 'pbase' for c in before), before
    ch = [dict(c) for c in before if c['name'] == 'pbase'][0]; ch['value'] = B64
    await page.context.add_cookies([ch])
    assert (await jar(page)) != before
    setup[6].hits.clear(); answer = await click(setup)
    after = await jar(page)
    print('P2', answer, before, after)
    assert not answer['ok']
    assert after == before

# P3 same-name partitioned and unpartitioned cookie: change only the partitioned one
@pytest.mark.asyncio
async def test_p3_same_name_partitioned_and_unpartitioned(setup):
    page = setup[5]
    try:
        await page.context.add_cookies([
            {'name': 'dup', 'value': 'a', 'domain': '127.0.0.1', 'path': '/'},
            {'name': 'dup', 'value': 'b', 'domain': '127.0.0.1', 'path': '/', 'secure': True, 'partitionKey': 'http://127.0.0.1'}])
    except Exception as e:
        pytest.skip(str(e))
    page = await compose(setup); await page.wait_for_timeout(150)
    before = await jar(page); print('P3 before', before)
    assert len([c for c in before if c['name'] == 'dup']) == 2
    pc = [dict(c) for c in before if c['name'] == 'dup' and c.get('partitionKey')][0]; pc['value'] = B64
    await page.context.add_cookies([pc])
    answer = await click(setup); after = await jar(page)
    print('P3', answer, after)
    assert not answer['ok']
    assert after == before, 'restore clobbered or lost one of the same-name cookies'

# P4 expiry clamping: baseline cookie with absurd expiry must not cause permanent false refusal (usability) and a script cookie with huge max-age must refuse
@pytest.mark.asyncio
async def test_p4a_baseline_far_future_expiry_unchanged_click_ok(setup):
    page = setup[5]
    await page.context.add_cookies([{'name': 'far', 'value': 'x', 'domain': '127.0.0.1', 'path': '/', 'expires': time.time() + 1000 * 86400}])
    page = await compose(setup); await page.wait_for_timeout(150)
    setup[6].hits.clear(); answer = await click(setup)
    print('P4a', answer, await jar(page))
    assert answer['ok'], 'false refusal with clamped expiry (fail-closed usability limit)'

@pytest.mark.asyncio
@pytest.mark.parametrize('maxage', [10**9, 10**12, 400*86400, 400*86400+1])
async def test_p4b_script_cookie_huge_maxage_refused_and_removed(setup, maxage):
    page = await compose(setup); await page.fill('#draft', SECRET)
    before = await jar(page)
    await page.evaluate("m => document.cookie = 'hm=' + btoa('%s') + '; path=/; max-age=' + m" % SECRET, maxage)
    assert await jar(page) != before
    setup[6].hits.clear(); answer = await click(setup); after = await jar(page)
    print('P4b', maxage, answer, after)
    assert not answer['ok'] and after == before and not idea_cookie_headers(setup[6])

# P5 many cookies
@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['change_one', 'add_one', 'delete_one', 'unchanged'])
async def test_p5_many_cookies(setup, mode):
    page = setup[5]
    seeds = [{'name': 'c%03d' % i, 'value': 'v%d' % i, 'domain': '127.0.0.1', 'path': '/p%d' % (i % 5), 'httpOnly': i % 2 == 0, 'sameSite': ['Lax', 'Strict', 'None'][i % 3] if i % 3 != 2 else 'Lax', 'expires': (time.time() + 3600 + i) if i % 4 == 0 else -1} for i in range(150)]
    await page.context.add_cookies(seeds)
    page = await compose(setup); await page.fill('#draft', SECRET); await page.wait_for_timeout(150)
    before = await jar(page); assert len(before) >= 150, len(before)
    if mode == 'change_one':
        c = dict([x for x in before if x['name'] == 'c077'][0]); c['value'] = B64; await page.context.add_cookies([c])
    elif mode == 'add_one':
        await page.context.add_cookies([{'name': 'extra', 'value': B64, 'domain': '127.0.0.1', 'path': '/zzz'}])
    elif mode == 'delete_one':
        await page.context.clear_cookies(name='c050')
    setup[6].hits.clear(); answer = await click(setup); after = await jar(page)
    print('P5', mode, answer, len(before), len(after))
    if mode == 'unchanged':
        assert answer['ok']
    else:
        assert not answer['ok'] and not idea_cookie_headers(setup[6])
        assert after == before, [x for x in after if x not in before][:3]

# P6 cookie set between baseline and click through different routes
@pytest.mark.asyncio
@pytest.mark.parametrize('route', ['document.cookie', 'cookieStore', 'click_handler', 'other_tab_doc_cookie', 'iframe_doc_cookie', 'subdomain_domain_attr', 'path_scoped_idea'])
async def test_p6_cookie_between_baseline_and_click(setup, route):
    page = await compose(setup); await page.fill('#draft', SECRET)
    before = await jar(page)
    js = {
      'document.cookie': "document.cookie='x='+btoa('%s')+'; path=/'" % SECRET,
      'cookieStore': "cookieStore.set({name:'x',value:btoa('%s'),path:'/'})" % SECRET,
      'click_handler': "document.querySelector('#lnk').addEventListener('click',()=>{document.cookie='x='+btoa(document.querySelector('#draft').value)+'; path=/'})",
      'iframe_doc_cookie': "(()=>{const f=document.createElement('iframe');f.src='/idea';document.body.appendChild(f);return new Promise(r=>f.onload=()=>{try{f.contentDocument.cookie='x='+btoa('%s')+'; path=/'}catch(e){};r()})})()" % SECRET,
      'subdomain_domain_attr': "document.cookie='x='+btoa('%s')+'; domain=127.0.0.1; path=/'" % SECRET,
      'path_scoped_idea': "document.cookie='x='+btoa('%s')+'; path=/idea'" % SECRET,
    }
    if route == 'other_tab_doc_cookie':
        other = await page.context.new_page(); await other.goto(setup[1].origin + '/idea')
        await other.evaluate("document.cookie='x='+btoa('%s')+'; path=/'" % SECRET)
    else:
        await page.evaluate(js[route])
    await page.wait_for_timeout(200)
    setup[6].hits.clear(); answer = await click(setup); await page.wait_for_timeout(300); after = await jar(page)
    cookies_seen = [h for h in setup[6].hits]
    print('P6', route, answer, cookies_seen, after)
    assert not answer['ok'] and not idea_cookie_headers(setup[6]), (route, answer)
    assert not any(c['name'] == 'x' for c in after), after

# P7 other subdomains / domains in the jar
@pytest.mark.asyncio
@pytest.mark.parametrize('dom', ['localhost', 'sub.example.test', '.example.test'])
async def test_p7_other_domain_cookie_changes(setup, dom):
    page = await compose(setup); await page.fill('#draft', SECRET)
    before = await jar(page)
    await page.context.add_cookies([{'name': 'o', 'value': B64, 'domain': dom, 'path': '/'}])
    mid = await jar(page); assert mid != before
    setup[6].hits.clear(); answer = await click(setup); after = await jar(page)
    print('P7', dom, answer, after)
    assert not answer['ok'] and after == before

# P8 cookie planted then expires (short max-age) before click: jar returns to baseline; click state?
@pytest.mark.asyncio
async def test_p8_cookie_planted_and_self_expired_before_click(setup):
    page = await compose(setup); await page.fill('#draft', SECRET)
    before = await jar(page)
    await page.evaluate("document.cookie='t='+btoa('%s')+'; path=/; max-age=1'" % SECRET)
    await page.wait_for_timeout(1500)
    mid = await jar(page); print('P8 mid', mid)
    setup[6].hits.clear(); answer = await click(setup)
    print('P8', answer)
    # either outcome is safe if nothing leaked; assert no leak
    assert SECRET not in json.dumps(setup[6].hits) and B64 not in json.dumps(setup[6].hits)

# P9 baseline cookie deleted by page script then click
@pytest.mark.asyncio
async def test_p9_baseline_cookie_deleted_by_script_restored(setup):
    page = setup[5]
    await page.context.add_cookies([{'name': 'keep', 'value': 'fixed', 'domain': '127.0.0.1', 'path': '/', 'expires': time.time() + 7200, 'sameSite': 'Strict'}])
    page = await compose(setup); await page.fill('#draft', SECRET); await page.wait_for_timeout(150)
    before = await jar(page)
    await page.evaluate("document.cookie='keep=; path=/; max-age=0'")
    assert await jar(page) != before
    answer = await click(setup); after = await jar(page)
    print('P9', answer, before, after)
    assert not answer['ok'] and after == before

# P10 localStorage replay variants into landed page (fetch POST, sendBeacon, cookie-less header)
@pytest.mark.asyncio
@pytest.mark.parametrize('sink', ['beacon', 'fetch_post', 'fetch_header', 'ws_free_css'])
async def test_p10_localstorage_replay_sinks(setup, sink):
    site = setup[6]; original = site.do_GET; original_post = getattr(site, 'do_POST', None); raw = []
    body = {
        'beacon': "navigator.sendBeacon('/replay',localStorage.getItem('d'))",
        'fetch_post': "fetch('/replay',{method:'POST',body:localStorage.getItem('d')})",
        'fetch_header': "fetch('/replay',{headers:{'X-D':btoa(localStorage.getItem('d'))}})",
        'ws_free_css': "document.head.appendChild(Object.assign(document.createElement('link'),{rel:'stylesheet',href:'/replay.css?d='+btoa(localStorage.getItem('d'))}))",
    }[sink]
    def get(self):
        raw.append((self.path, dict(self.headers)))
        if self.path.startswith('/idea?page=2'):
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
            self.wfile.write(("<html><body><script>setTimeout(()=>{%s},1500)</script></body></html>" % body).encode()); return
        return original(self)
    site.do_GET = get
    try:
        page = await compose(setup); await page.fill('#draft', SECRET)
        await page.evaluate("s=>localStorage.setItem('d',s)", SECRET)
        raw.clear(); answer = await click(setup); await page.wait_for_timeout(2500)
        print('P10', sink, answer, [(r[0]) for r in raw], getattr(site, 'posts', None))
        blob = json.dumps(raw) + json.dumps(getattr(site, 'posts', []), default=str) + json.dumps(getattr(site, 'post_paths', []), default=str)
        assert not any(m in blob for m in (SECRET, B64, SECRET.encode().hex()))
    finally: site.do_GET = original


# P3b mirror: change only the UNPARTITIONED same-name cookie; the partitioned one must survive the restore
@pytest.mark.asyncio
async def test_p3b_same_name_change_unpartitioned_only(setup):
    page = setup[5]
    try:
        await page.context.add_cookies([
            {'name': 'dup', 'value': 'a', 'domain': '127.0.0.1', 'path': '/'},
            {'name': 'dup', 'value': 'b', 'domain': '127.0.0.1', 'path': '/', 'secure': True, 'partitionKey': 'http://127.0.0.1'}])
    except Exception as e:
        pytest.skip(str(e))
    page = await compose(setup); await page.wait_for_timeout(150)
    before = await jar(page)
    assert len([c for c in before if c['name'] == 'dup']) == 2
    uc = [dict(c) for c in before if c['name'] == 'dup' and not c.get('partitionKey')][0]; uc['value'] = B64
    await page.context.add_cookies([uc])
    answer = await click(setup); after = await jar(page)
    assert not answer['ok']
    assert after == before
