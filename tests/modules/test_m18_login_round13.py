"""Round 13: a cookie the SERVER plants (httpOnly) from a request the page made before the click must not
ride the daemon-sent navigation. Real Chromium; asserts on the raw Cookie header."""
import time

import pytest

from test_m18_login_browser import setup, _compose_with_values  # noqa: F401
from test_m18_login_round5 import _nav_click

SECRET = 'UNAPPROVEDSECRET'
D = "document.querySelector('#draft').value"


@pytest.mark.asyncio
async def test_httponly_cookie_planted_before_the_click_never_rides_the_navigation(setup):
    site = setup[6]
    raw = []
    orig = site.do_GET

    def wrapped(self):
        raw.append((self.path, self.headers.get('Cookie'), self.headers.get('Referer')))
        if self.path.startswith('/setc'):
            self.send_response(200); self.send_header('Set-Cookie', 'hc=' + self.path.split('d=')[-1] + '; HttpOnly; Path=/'); self.end_headers(); return
        return orig(self)
    site.do_GET = wrapped
    site.html_hook = lambda html: html.replace('<body>', '<body><a id="lnk" href="/idea?page=2">l</a>')
    try:
        page, _ = await _compose_with_values(setup)
    finally:
        site.html_hook = None
    await page.fill('#draft', SECRET)
    # The page talks to its own server BEFORE the click: no guard is up yet (documented, uncontained).
    await page.evaluate(f"fetch('/setc?d='+btoa({D}))")
    await page.wait_for_timeout(500)
    assert any(c['name'] == 'hc' for c in await page.context.cookies()), 'the server planted the httpOnly cookie'
    raw.clear()
    try:
        answer = await _nav_click(setup, '#lnk')
    except Exception as error:  # noqa: BLE001 - a refusal is a safe outcome
        answer = {'ok': False, 'error': str(error)}
    for _ in range(5):
        await page.wait_for_timeout(700)
    site.do_GET = orig
    assert not [r for r in raw if r[1] and 'hc=' in r[1]], raw
    assert not [r for r in raw if r[0].startswith('/idea')], raw  # refused: nothing sent
    assert not any(c['name'] == 'hc' for c in await page.context.cookies()), 'the planted cookie is removed from the jar'
