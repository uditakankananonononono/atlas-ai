"""Independent gap tests (pessimistic). Real Chromium + real daemon CLICK_NAV. The site logs every raw request
(path, Cookie, Referer). SECRET is the unapproved draft; any trace of it (plain/base64/hex) in any request is a leak."""
import json, time, base64
import pytest
from test_m18_login_browser import setup, _compose_with_values  # noqa
from test_m18_login_round5 import _nav_click
SECRET = 'UNAPPROVEDSECRET'
D = "document.querySelector('#draft').value"
def hook(code):
    return f"document.querySelector('#lnk').addEventListener('click',(e)=>{{{code}}});"
def marks(blob):
    return [m for m in [SECRET, base64.b64encode(SECRET.encode()).decode().rstrip('='), SECRET.encode().hex()] if m in blob]
LATE = "<html><body><script>setTimeout(()=>{new Image().src='/late?w='+encodeURIComponent(window.name)+'&l='+encodeURIComponent(localStorage.getItem('d')||'')},3000)</script>landed</body></html>"
V = {
 # httpOnly cookie planted through the site's own endpoint (script cannot write httpOnly, the SERVER can)
 'httponly_cookie_via_fetch_in_click': hook(f"fetch('/setc?d='+btoa({D}))"),
 'httponly_cookie_via_img_in_click': hook(f"new Image().src='/setc?d='+btoa({D})"),
 'httponly_cookie_via_input_before_click': f"document.querySelector('#draft').addEventListener('input',()=>{{fetch('/setc?d='+btoa({D}))}});document.querySelector('#draft').dispatchEvent(new Event('input'));",
 # popups and targets
 'window_open_in_click': hook(f"window.open('/leak?d='+btoa({D}))"),
 'target_blank_link_added': hook(f"const a=document.createElement('a');a.href='/leak?d='+btoa({D});a.target='_blank';document.body.appendChild(a);a.click()"),
 'mutate_clicked_href': hook(f"e.currentTarget.href='/idea?page=2&d='+btoa({D})"),
 'mutate_clicked_target_blank': hook("e.currentTarget.target='_blank'"),
 # form submits
 'form_submit_get_in_click': hook(f"const f=document.createElement('form');f.method='get';f.action='/leak';const i=document.createElement('input');i.name='d';i.value={D};f.appendChild(i);document.body.appendChild(f);f.submit()"),
 'form_submit_post_blank_in_click': hook(f"const f=document.createElement('form');f.method='post';f.target='_blank';f.action='/leakpost';const i=document.createElement('input');i.name='d';i.value={D};f.appendChild(i);document.body.appendChild(f);f.submit()"),
 'real_publish_form_requestSubmit_in_click': hook("document.querySelector('form').requestSubmit()"),
 # misc channels
 'sendBeacon': hook(f"navigator.sendBeacon('/leak',{D})"),
 'xhr_sync': hook(f"const x=new XMLHttpRequest();x.open('GET','/leak?d='+btoa({D}),false);x.send()"),
 'websocket': hook(f"try{{new WebSocket('ws://'+location.host+'/ws?d='+btoa({D}))}}catch(_){{}}"),
 'window_name': hook(f"window.name={D}"),
 'localStorage': hook(f"localStorage.setItem('d',{D})"),
 'pagehide_beacon': hook(f"addEventListener('pagehide',()=>navigator.sendBeacon('/leak',{D}))"),
 'visibility_fetch_keepalive': hook(f"addEventListener('beforeunload',()=>fetch('/leak?d='+btoa({D}),{{keepalive:true}}))"),
 'serviceworker_register_with_query': hook(f"navigator.serviceWorker&&navigator.serviceWorker.register('/sw.js?d='+btoa({D}))"),
 'redirect_server_side_target': hook(f"fetch('/redir?to='+btoa({D}))"),
 'top_location_hash_then_assign': hook(f"location.hash=btoa({D})"),
 'document_domain_cookie_path': hook(f"document.cookie='d='+btoa({D})+';path=/idea'"),
}
@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(V))
async def test_gap(setup, name):
    code = V[name]
    site = setup[6]
    raw = []
    orig_get, orig_post = site.do_GET, site.do_POST
    def wrapped(self):
        raw.append((time.time(), self.command, self.path, self.headers.get('Cookie'), self.headers.get('Referer')))
        if self.path.startswith('/setc'):
            self.send_response(200); self.send_header('Set-Cookie', 'hc='+self.path.split('d=')[-1]+'; HttpOnly; Path=/'); self.end_headers(); return
        if self.path.startswith('/idea?page=2'):
            self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(LATE.encode()); return
        if self.path.startswith('/redir'):
            self.send_response(302); self.send_header('Location','/leak?r='+self.path.split('to=')[-1]); self.end_headers(); return
        if self.path.startswith('/sw.js'):
            self.send_response(200); self.send_header('Content-Type','application/javascript'); self.end_headers(); self.wfile.write(b''); return
        return orig_get(self)
    def wrapped_post(self):
        n = int(self.headers.get('Content-Length') or 0); body = self.rfile.read(n).decode() if n else ''
        raw.append((time.time(), self.command, self.path+'#'+body, self.headers.get('Cookie'), self.headers.get('Referer')))
        self.send_response(200); self.end_headers()
    site.do_GET, site.do_POST = wrapped, wrapped_post
    site.html_hook = lambda html: html.replace('<body>', '<body><a id="lnk" href="/idea?page=2">l</a>')
    try:
        page, _ = await _compose_with_values(setup)
    finally:
        site.html_hook = None
    await page.fill('#draft', SECRET)
    await page.evaluate(code if code.startswith('document') or code.startswith('const') is False else code)
    raw.clear()
    try:
        answer = await _nav_click(setup, '#lnk')
    except Exception as error:  # a refusal is a safe outcome
        answer = {'ok': False, 'error': str(error)}
    for _ in range(8):
        await page.wait_for_timeout(700)
    # also drive pages opened by the click
    for p in page.context.pages:
        try: await p.wait_for_timeout(300)
        except Exception: pass
    site.do_GET, site.do_POST = orig_get, orig_post
    blob = json.dumps([r[1:] for r in raw])
    print('RESULT', name, 'ok=', answer.get('ok'), 'leaked=', marks(blob), 'reqs=', [r[1:3] for r in raw][:6], 'pages=', len(page.context.pages))
    assert not marks(blob), (name, raw[:6])
