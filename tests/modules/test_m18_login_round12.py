"""Round 12 (audit of round 11): the one allowed navigation must not carry data in its Cookie header,
its Referer, or its arrival time. Real Chromium. Wraps the auditor's vectors (test_zz_r11_aud.py)."""
import json
import time

import pytest

from test_m18_login_browser import setup, _compose_with_values  # noqa: F401
from test_m18_login_round5 import _nav_click
from test_zz_r11_aud import V, marks, hook, D, SECRET, LANDED_LATE


async def _run(setup, code, late=None, wait=6):
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
    try:
        answer = await _nav_click(setup, '#lnk')
    except Exception as error:  # noqa: BLE001 - a refusal is a safe outcome
        answer = {'ok': False, 'error': str(error)}
    for _ in range(wait):
        await page.wait_for_timeout(700)
    site.do_GET = orig
    return raw, t0, answer


@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(V))
async def test_allowed_navigation_carries_nothing(setup, name):
    code, late = V[name]
    raw, t0, answer = await _run(setup, code, late, 14 if late else 6)
    blob = json.dumps([r[1:] for r in raw])
    assert not marks(blob), (name, raw[:5])


@pytest.mark.asyncio
async def test_a_clean_click_still_navigates_with_the_shipped_referer_and_no_extra_cookie(setup):
    raw, t0, answer = await _run(setup, "0", None, 4)
    nav = [r for r in raw if r[1].startswith('/idea?page=2')]
    assert answer['ok'] is True and len(nav) == 1, (answer, raw)
    assert nav[0][3].endswith('/compose') and not nav[0][2]


@pytest.mark.asyncio
async def test_navigation_arrival_time_does_not_depend_on_the_pages_delay(setup):
    arrivals = []
    for delay in (0, 500):
        code = hook(f"e.preventDefault();const a=e.currentTarget;setTimeout(()=>{{location.href=a.href}},{delay})")
        raw, t0, answer = await _run(setup, code, None, 5)
        nav = [r[0] - t0 for r in raw if r[1].startswith('/idea?page=2')]
        assert len(nav) == 1, (delay, raw)
        arrivals.append(nav[0])
    assert abs(arrivals[0] - arrivals[1]) < 0.35, arrivals
    code = hook("e.preventDefault();const a=e.currentTarget;setTimeout(()=>{location.href=a.href},2500)")
    raw, t0, answer = await _run(setup, code, None, 7)
    assert not [r for r in raw if r[1].startswith('/idea?page=2')], raw  # asked too late: nothing is sent
