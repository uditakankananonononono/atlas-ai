"""Round 11: covert SELECTION channels over server-shipped (known) URLs. Real Chromium.
After a guarded click only the clicked link's own navigation may leave; which of N shipped URLs is
requested, and when, must not reach the server."""
import json

import pytest

from test_m18_login_browser import setup, _compose_with_values  # noqa: F401
from test_m18_login_round5 import _nav_click
from test_aud_round7 import SECRET, on_click, D

ANCHORS = ''.join(f'<a href="/k/{i}">.</a>' for i in range(256)) + '<a href="/b/0">.</a><a href="/b/1">.</a><a href="/t/0">.</a>'

V = {
    'char_per_image': on_click(f"[...{D}].forEach(c=>new Image().src='/k/'+c.charCodeAt(0))"),
    'char_per_fetch': on_click(f"[...{D}].forEach(c=>fetch('/k/'+c.charCodeAt(0)))"),
    'char_per_script_tag': on_click(f"[...{D}].forEach(c=>{{const s=document.createElement('script');s.src='/k/'+c.charCodeAt(0);document.head.appendChild(s)}})"),
    'binary_two_urls': on_click(f"[...{D}].forEach(c=>{{for(let i=0;i<8;i++)new Image().src='/b/'+((c.charCodeAt(0)>>i)&1)}})"),
    'timing_selected_single_url': on_click(f"[...{D}].forEach((c,i)=>setTimeout(()=>new Image().src='/t/0?x',i*40+c.charCodeAt(0)*20))", 0),
    'timing_selected_known_url_fetch': on_click(f"[...{D}].forEach((c,i)=>setTimeout(()=>fetch('/t/0'),300+c.charCodeAt(0)*30))", 0),
    'nav_to_selected_known_url': on_click(f"location.href='/k/'+{D}.charCodeAt(0)"),
    'nav_to_selected_known_url_timer': on_click(f"location.href='/k/'+{D}.charCodeAt(1)", 6000),
    'anchor_click_selected': on_click(f"document.querySelector('a[href=\"/k/'+{D}.charCodeAt(0)+'\"]').click()"),
    'iframe_src_selected': on_click(f"const f=document.createElement('iframe');f.src='/k/'+{D}.charCodeAt(0);document.body.appendChild(f)"),
    'link_stylesheet_selected': on_click(f"const l=document.createElement('link');l.rel='stylesheet';l.href='/k/'+{D}.charCodeAt(0);document.head.appendChild(l)"),
    'form_get_selected': on_click(f"const f=document.createElement('form');f.action='/k/'+{D}.charCodeAt(0);document.body.appendChild(f);f.submit()"),
}


@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(V))
async def test_selection_channel_over_known_urls_reaches_nothing(setup, name):
    site = setup[6]
    site.html_hook = lambda html: html.replace('<body>', '<body>' + ANCHORS)
    try:
        page, _ = await _compose_with_values(setup)
    finally:
        site.html_hook = None
    await page.fill('#draft', SECRET)
    await page.evaluate(V[name])
    site.hits.clear(); site.posts.clear(); site.post_paths.clear()
    await _nav_click(setup, '#attack')
    for _ in range(14 if 'timer' not in name else 16):
        await page.wait_for_timeout(700)
    seen = [h[2] for h in site.hits if h[2] != '/compose']
    assert not [p for p in seen if p.startswith(('/k/', '/b/', '/t/'))], (name, seen[:12])
    assert not site.posts and not site.post_paths


@pytest.mark.asyncio
async def test_the_clicked_links_own_navigation_still_works(setup):
    site = setup[6]
    site.html_hook = lambda html: html.replace('<body>', '<body><a id="lnk" href="/idea?page=2">l</a>')
    try:
        page, _ = await _compose_with_values(setup)
    finally:
        site.html_hook = None
    answer = await _nav_click(setup, '#lnk')
    assert answer['ok'] is True and answer['result']['guard']['blocked'] == [], answer
    assert page.url.endswith('/idea?page=2')


def test_launch_args_merge_existing_host_resolver_rules_instead_of_dropping_them():
    from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
    from app.modules.m13_browser_agent.pc_daemon.daemon import BrowserHandle
    args = BrowserHandle(DaemonConfig(site_hosts=['site.test'], browser_args=['--host-resolver-rules=MAP a.test 127.0.0.1', '--x'])).launch_args()
    rules = [a for a in args if a.startswith('--host-resolver-rules=')]
    assert rules == ['--host-resolver-rules=MAP a.test 127.0.0.1, MAP * ~NOTFOUND, EXCLUDE site.test'], rules


@pytest.mark.asyncio
async def test_a_browser_the_daemon_launched_without_site_hosts_refuses_guarded_sessions():
    from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
    from app.modules.m13_browser_agent.pc_daemon.daemon import BrowserHandle
    handle = BrowserHandle(DaemonConfig()); handle._launched = True
    assert 'site_hosts' in (await handle.verify_containment())
    handle.config.site_hosts = ['site.test']
    assert await handle.verify_containment() is None
