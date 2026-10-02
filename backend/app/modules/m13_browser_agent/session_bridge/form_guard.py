"""Browser-resolved form binding and the approved-click network guard.

Why this exists: Python ``urljoin(page.url, action)`` is not what Chromium does.
A ``<base href>`` (static or injected later), the form's ``enctype``/``target``/
``novalidate``, and inline ``on*`` handlers all change where or how a form is
submitted. The facts below are read from the real DOM through the
``HTMLFormElement.prototype`` accessors (immune to DOM clobbering such as an
``<input name="action">``) so the reviewed destination is the one the browser
will actually use.

Residual limits are documented in docs/M18_LOGIN_EXPERIMENTS.md. In short: a
page script that already runs on the paired browser can still do anything the
network guard does not observe (service workers, websockets, GET side effects to
other URLs, requests the browser makes outside this page's route).
"""
from __future__ import annotations

import time

from typing import Any
from urllib.parse import unquote, parse_qsl, urljoin, urlsplit

DEFAULT_ENCTYPE = "application/x-www-form-urlencoded"
# Only urlencoded bodies can be compared with the approved values at click time.
# multipart/form-data and text/plain recipes are refused (audit finding 4).
ALLOWED_ENCTYPES = (DEFAULT_ENCTYPE,)
SUBMIT_OVERRIDES = ("formaction", "formmethod", "formenctype", "formtarget", "formnovalidate")
# Seconds an approved submit stays armed with nobody clicking it.
ARM_TTL_SECONDS = 120.0
# Content-Security-Policy applied to the document a guarded click works on (as a <meta>) and to the
# document a guarded click navigates to (as a response header). connect-src 'none' covers fetch, XHR,
# WebSocket, EventSource, sendBeacon and a[ping]; default-src 'self' covers prefetch, images, frames.
GUARD_CSP = ("default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
             "connect-src 'none'; form-action 'none'; frame-src 'none'; object-src 'none'; base-uri 'self'")
# Header-only addition (not valid in <meta>): no popups, no form submission, no top navigation by script.
GUARD_CSP_HEADER = GUARD_CSP + "; sandbox allow-scripts allow-same-origin"
MAX_COOKIE_LIFETIME = 400 * 86400.0
TAINT_MIN_LEN = 4  # shorter form values are too common to treat as data in a URL
QUIET_SECONDS = 2.5  # how long the baseline guard outlives the last page activity

# True when clicking the element would submit a form: a submit-type button or input
# (including the implicit type of a bare <button> inside a form, the form= attribute
# and a <label> that activates such a control). Used by CLICK_NAV and generic clicks.
SUBMIT_CONTROL_JS = """
(el) => {
  const isSubmit = (node) => {
    if (!node) return false;
    const tag = node.tagName;
    if (tag === 'BUTTON') return node.form !== null && node.type === 'submit';
    if (tag === 'INPUT') return node.form !== null && (node.type === 'submit' || node.type === 'image');
    return false;
  };
  const control = el.closest('button,input,label');
  if (!control) return false;
  if (control.tagName === 'LABEL') return isSubmit(control.control);
  return isSubmit(control);
}
"""

# (selector) -> facts. Read with prototype getters, never form.action directly.
FORM_FACTS_JS = """
(selector) => {
  const buttons = document.querySelectorAll(selector);
  if (buttons.length !== 1) return {error: 'submit target count ' + buttons.length};
  const button = buttons[0];
  const form = Element.prototype.closest.call(button, 'form');
  if (!form) return {error: 'submit control is not inside a form'};
  const getter = (name) => Object.getOwnPropertyDescriptor(HTMLFormElement.prototype, name).get;
  const attrNames = (el) => Array.from(el.attributes).map((a) => a.name.toLowerCase());
  const scope = [form, ...form.querySelectorAll('*')];
  const chain = [];
  for (let el = form.parentElement; el; el = el.parentElement) chain.push(el);
  const on = [];
  for (const el of [...scope, ...chain]) {
    for (const n of attrNames(el)) if (n.startsWith('on')) on.push(el.tagName.toLowerCase() + '@' + n);
  }
  const handlerProps = ['onsubmit', 'onclick', 'onformdata', 'onmousedown', 'onmouseup', 'onpointerdown',
                        'onpointerup', 'onkeydown', 'onkeyup', 'onkeypress', 'onreset', 'onbeforeunload'];
  for (const [label, target] of [['form', form], ['button', button], ['window', window], ['document', document],
                                 ['html', document.documentElement], ['body', document.body]]) {
    if (!target) continue;
    for (const prop of handlerProps) if (target[prop] !== null && target[prop] !== undefined) on.push('prop:' + label + '.' + prop);
  }
  const overrides = [];
  for (const el of [button, ...form.querySelectorAll('input,button')]) {
    for (const n of attrNames(el)) if (%OVERRIDES%.includes(n)) overrides.push(n);
  }
  return {
    url: location.href,
    base_uri: document.baseURI,
    base_count: document.getElementsByTagName('base').length,
    action: getter('action').call(form),
    method: getter('method').call(form),
    enctype: getter('enctype').call(form),
    target: form.getAttribute('target') || '',
    accept_charset: form.getAttribute('accept-charset') || '',
    no_validate: form.hasAttribute('novalidate'),
    on_attrs: on.sort(),
    overrides: overrides.sort(),
    external_controls: document.querySelectorAll('[form]').length,
  };
}
""".replace("%OVERRIDES%", repr(list(SUBMIT_OVERRIDES)))

# Capturing submit guard for the approved click. Mitigation only: a script that
# registered earlier with stopImmediatePropagation, or that rewrites the form in
# a later bubble-phase listener, is caught by the network guard instead.
GUARD_JS = """
({selector, expected}) => {
  if (window.__atlasGuard) window.__atlasGuard.remove();
  const button = document.querySelector(selector);
  const form = button && Element.prototype.closest.call(button, 'form');
  const getter = (name) => Object.getOwnPropertyDescriptor(HTMLFormElement.prototype, name).get;
  const blocked = [];
  const handler = (event) => {
    const problems = [];
    if (event.target !== form) problems.push('other form');
    if (event.submitter !== button) problems.push('other submitter');
    if (document.getElementsByTagName('base').length) problems.push('base element');
    if (getter('action').call(form) !== expected.action) problems.push('action');
    if (getter('method').call(form) !== expected.method) problems.push('method');
    if (getter('enctype').call(form) !== expected.enctype) problems.push('enctype');
    if (form.getAttribute('target')) problems.push('target');
    if (problems.length) {
      blocked.push(problems.join(','));
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  };
  window.addEventListener('submit', handler, true);
  window.__atlasGuard = {blocked, remove: () => window.removeEventListener('submit', handler, true)};
  return true;
}
"""
# Audit finding 5 (not fixed, documented): window.__atlasGuard lives in the page's own
# JS world, so a hostile page can overwrite or clear it and hide what the page guard
# blocked. The page guard is advisory. The authoritative report is NetworkGuard.report(),
# which lives in the daemon process and is not readable or writable by page scripts.
# Baseline page guard for daemon-driven clicks that are not the armed submit. Advisory
# like GUARD_JS: it stops declarative and scripted submits from running at all. The
# authoritative control is NetworkGuard (baseline mode) in the daemon process.
NAV_GUARD_JS_TEMPLATE = """
(reporter) => {
  if (window.__atlasGuard) window.__atlasGuard.remove();
  const blocked = [];
  try {
    const meta = document.createElement('meta');
    meta.httpEquiv = 'Content-Security-Policy';
    meta.content = %CSP%;
    (document.head || document.documentElement).appendChild(meta);
  } catch (e) {}
  const note = (what) => {
    blocked.push(what);
    try { window[reporter](what); } catch (e) {}
    try { const k = '__atlasBlocked'; const l = JSON.parse(sessionStorage.getItem(k) || '[]'); l.push(what); sessionStorage.setItem(k, JSON.stringify(l)); } catch (e) {}
  };
  const handler = (event) => {
    note('submit event');
    event.preventDefault();
    event.stopImmediatePropagation();
  };
  window.addEventListener('submit', handler, true);
  const cspHandler = (e) => note('csp ' + e.violatedDirective + ' ' + String(e.blockedURI).slice(0, 60));
  document.addEventListener('securitypolicyviolation', cspHandler, true);
  // Script-level wrappers. They exist because a keepalive request issued while the page unloads
  // is not visible to the network route. They only cover code that calls these globals after this
  // point; anything that cached the originals earlier, or borrows an iframe's, is not stopped here.
  const orig = {fetch: window.fetch, send: XMLHttpRequest.prototype.send, open: XMLHttpRequest.prototype.open,
                beacon: navigator.sendBeacon, submit: HTMLFormElement.prototype.submit,
                requestSubmit: HTMLFormElement.prototype.requestSubmit};
  const safe = (m) => ['GET', 'HEAD'].includes(String(m || 'GET').toUpperCase());
  window.fetch = function(input, init) {
    const method = (init && init.method) || (input && input.method) || 'GET';
    if (!safe(method)) { note('script fetch ' + method); return Promise.reject(new TypeError('blocked by Atlas guard')); }
    return orig.fetch.apply(this, arguments);
  };
  XMLHttpRequest.prototype.open = function(method) { this.__atlasMethod = method; return orig.open.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function() {
    if (!safe(this.__atlasMethod)) { note('script xhr ' + this.__atlasMethod); throw new DOMException('blocked by Atlas guard', 'NetworkError'); }
    return orig.send.apply(this, arguments);
  };
  navigator.sendBeacon = function() { note('script sendBeacon'); return false; };
  const origRTC = window.RTCPeerConnection, origWRTC = window.webkitRTCPeerConnection;
  const origBC = window.BroadcastChannel, origSW = window.SharedWorker;
  const deny = (name) => function() { note('script ' + name); throw new DOMException('blocked by Atlas guard', 'SecurityError'); };
  if (origRTC) window.RTCPeerConnection = deny('RTCPeerConnection');
  if (origWRTC) window.webkitRTCPeerConnection = deny('webkitRTCPeerConnection');
  const origBCpost = origBC ? origBC.prototype.postMessage : null;
  if (origBC) origBC.prototype.postMessage = function() { note('script BroadcastChannel.postMessage'); };
  if (origBC) window.BroadcastChannel = deny('BroadcastChannel');
  if (origSW) window.SharedWorker = deny('SharedWorker');
  const origOpen = window.open;
  window.open = function() { note('script window.open'); return null; };
  const OrigWS = window.WebSocket, OrigES = window.EventSource;
  window.WebSocket = function() { note('script WebSocket'); throw new DOMException('blocked by Atlas guard', 'SecurityError'); };
  if (OrigES) window.EventSource = function() { note('script EventSource'); throw new DOMException('blocked by Atlas guard', 'SecurityError'); };
  HTMLFormElement.prototype.submit = function() { note('script form.submit'); };
  HTMLFormElement.prototype.requestSubmit = function() { note('script form.requestSubmit'); };
  window.__atlasGuard = {blocked, remove: () => {
    window.removeEventListener('submit', handler, true);
    document.removeEventListener('securitypolicyviolation', cspHandler, true);
    window.fetch = orig.fetch; XMLHttpRequest.prototype.send = orig.send; XMLHttpRequest.prototype.open = orig.open;
    navigator.sendBeacon = orig.beacon; window.open = origOpen; if (origRTC) window.RTCPeerConnection = origRTC; if (origWRTC) window.webkitRTCPeerConnection = origWRTC; if (origBC) { window.BroadcastChannel = origBC; origBC.prototype.postMessage = origBCpost; } if (origSW) window.SharedWorker = origSW; window.WebSocket = OrigWS; if (OrigES) window.EventSource = OrigES;
    HTMLFormElement.prototype.submit = orig.submit;
    HTMLFormElement.prototype.requestSubmit = orig.requestSubmit;
  }};
  return true;
}
"""
FRAME_DENY_JS = """
(() => {
  for (const name of ['RTCPeerConnection', 'webkitRTCPeerConnection', 'RTCDataChannel', 'WebTransport',
                      'BroadcastChannel', 'SharedWorker']) {
    if (!(name in window)) continue;
    try {
      Object.defineProperty(window, name, {configurable: false, writable: false,
        value: function() { throw new DOMException('blocked by Atlas guard', 'SecurityError'); }});
    } catch (e) {}
  }
})();
"""
NAV_GUARD_JS = NAV_GUARD_JS_TEMPLATE.replace("%CSP%", repr(GUARD_CSP))
# Same-origin fallback for a report made while the document unloads (the binding call can be lost).
NAV_RECALL_JS = "() => { try { const k='__atlasBlocked'; const l=JSON.parse(sessionStorage.getItem(k)||'[]'); sessionStorage.removeItem(k); return l; } catch (e) { return []; } }"
KNOWN_URLS_JS = """
() => [...new Set([
  ...performance.getEntriesByType('resource').map(e => e.name),
  ...[...document.querySelectorAll('[src],[href],[action]')].flatMap(e => [e.src, e.href, e.action]).filter(Boolean),
])].slice(0, 2000)
"""
TAINT_JS = """
() => [...new Set([...document.querySelectorAll('input,textarea,select')]
  .map(e => e.value).filter(v => v && v.length >= %d))].slice(0, 200)
""" % TAINT_MIN_LEN
GUARD_STATE_JS = "() => window.__atlasGuard ? window.__atlasGuard.blocked.slice() : null"
GUARD_REMOVE_JS = "() => { if (window.__atlasGuard) { window.__atlasGuard.remove(); } return true; }"


def static_form_checks(soup, form, button, expected_enctype: str = DEFAULT_ENCTYPE) -> None:
    """Server/daemon HTML-level rejections. Cheap and DOM-independent."""
    if soup.find("base") is not None:
        raise PermissionError("<base> element on the page can divert the approved form")
    scope = [form, *form.find_all(True)]
    for ancestor in form.parents:
        if getattr(ancestor, "attrs", None) is not None and ancestor.name != "[document]":
            scope.append(ancestor)
    for node in scope:
        if any(str(name).lower().startswith("on") for name in node.attrs):
            raise PermissionError("inline event handlers on the form, its controls or ancestors are not allowed")
    if "accept-charset" in form.attrs:
        raise PermissionError("form accept-charset is not allowed")
    if "novalidate" in form.attrs:
        raise PermissionError("novalidate forms are not allowed")
    if "target" in form.attrs and str(form.get("target")).strip():
        raise PermissionError("form target is not allowed")
    enctype = form.get("enctype")
    if enctype is not None and str(enctype).strip().lower() != expected_enctype:
        raise PermissionError("form enctype differs from the reviewed value")
    if "enctype" in form.attrs and form.get("enctype") is None:
        raise PermissionError("form enctype differs from the reviewed value")


def validate_facts(facts: Any, expected_enctype: str = DEFAULT_ENCTYPE) -> dict:
    """Reject any browser-observed form state outside the narrow reviewed shape."""
    if not isinstance(facts, dict) or facts.get("error"):
        raise PermissionError(f"browser form facts unavailable: {facts.get('error') if isinstance(facts, dict) else 'bad reply'}")
    required = {"url", "base_uri", "base_count", "action", "method", "enctype", "target", "no_validate",
                "on_attrs", "overrides", "external_controls", "accept_charset"}
    if not required <= set(facts):
        raise PermissionError("browser form facts incomplete")
    if facts["base_count"] != 0 or facts["base_uri"] != facts["url"]:
        raise PermissionError("<base> changes how the browser resolves the form destination")
    if facts["on_attrs"]:
        raise PermissionError("inline event handlers are present on the form, its controls or ancestors")
    if facts["no_validate"] or facts["target"] or facts["accept_charset"]:
        raise PermissionError("form novalidate/target/accept-charset is not allowed")
    if facts["overrides"] or facts["external_controls"]:
        raise PermissionError("submit control overrides or external form controls are not allowed")
    if expected_enctype != DEFAULT_ENCTYPE or facts["enctype"] != DEFAULT_ENCTYPE:
        raise PermissionError("only urlencoded forms can be body-bound; multipart and text/plain are refused")
    if facts["method"] != "post":
        raise PermissionError("approved publication must be a POST form")
    return facts


def _form_body(text: str) -> dict[str, str]:
    return {name: value.replace("\r\n", "\n") for name, value in parse_qsl(text, keep_blank_values=True)}


def field_name_map(preview: dict) -> dict[str, str]:
    """selector -> form field name. M13 previews carry it; M18 selectors are [name="x"]."""
    mapped = preview.get("field_names")
    if isinstance(mapped, dict):
        return {str(k): str(v) for k, v in mapped.items()}
    return {selector: selector.split('"')[1] for selector in preview.get("values", {})}


REDIRECT_STATUSES = (301, 302, 303, 307, 308)
MAX_GUARDED_HOPS = 5


def _origin(url: str) -> tuple[str, str, int | None]:
    parts = urlsplit(url)
    return (parts.scheme.lower(), (parts.hostname or "").lower(), parts.port or {"http": 80, "https": 443}.get(parts.scheme.lower()))


def _taint_forms(value: str) -> set[str]:
    low = value.lower()
    squeezed = "".join(ch for ch in low if ch.isalnum())
    forms = {low, low[::-1], squeezed, squeezed[::-1]}
    return {f for f in forms if len(f) >= TAINT_MIN_LEN}


def url_carries_taint(url: str, taint) -> bool:
    """Does the URL carry any filled value in a form a script could build: raw, percent-encoded twice,
    reversed, with separators between chunks, base64 (standard or urlsafe, any alignment of the token)
    or hex? Not a proof of absence: a keyed or compressed encoding passes. Callers also refuse URLs the
    page did not ship (see known_urls) and long opaque path or query tokens."""
    import base64 as _b64
    import binascii
    import re as _re
    from urllib.parse import unquote_plus
    if not taint:
        return False
    decoded = unquote_plus(unquote_plus(url))
    haystacks = [decoded.lower()]
    for token in _re.findall(r"[A-Za-z0-9_\-+/=]{6,}", decoded):
        for variant in {token, token.replace("-", "+").replace("_", "/")}:
            core = variant.strip("=")
            for shift in range(4):  # a secret may start at any offset of the encoded token
                chunk = core[shift:]
                chunk = chunk[: len(chunk) // 4 * 4]
                if not chunk:
                    continue
                try:
                    haystacks.append(_b64.b64decode(chunk + "==", validate=False).decode("latin-1").lower())
                except (binascii.Error, ValueError):
                    pass
        hexish = _re.sub(r"[^0-9a-fA-F]", "", token)
        if len(hexish) >= 8 and len(hexish) % 2 == 0:
            try:
                haystacks.append(bytes.fromhex(hexish).decode("latin-1").lower())
            except ValueError:
                pass
    squeezed = ["".join(ch for ch in h if ch.isalnum()) for h in haystacks]
    for value in taint:
        for form in _taint_forms(str(value)):
            if any(form in h for h in haystacks) or any(form in h for h in squeezed):
                return True
    return False


OPAQUE_TOKEN = __import__("re").compile(r"[A-Za-z0-9_\-+=]{16,}")


def looks_opaque(url: str) -> bool:
    """A long unbroken token in the path or query: how data usually rides in a URL."""
    parts = urlsplit(url)
    return bool(OPAQUE_TOKEN.search(unquote(parts.path)) or OPAQUE_TOKEN.search(unquote(parts.query)))


def markup_urls(html: str, base: str) -> set[str]:
    """Absolute URLs a document's own markup refers to (src, href, action, poster, srcset, url())."""
    import re as _re
    found = set()
    for value in _re.findall(r"""(?:src|href|action|poster|data)\s*=\s*["']([^"']+)["']""", html, _re.I):
        found.add(urljoin(base, value.strip()))
    for value in _re.findall(r"""srcset\s*=\s*["']([^"']+)["']""", html, _re.I):
        for part in value.split(","):
            if part.strip():
                found.add(urljoin(base, part.strip().split()[0]))
    for value in _re.findall(r"url\(\s*['\"]?([^'\")]+)", html, _re.I):
        found.add(urljoin(base, value.strip()))
    return found


def _is_secure_context(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" or (parts.hostname or "") in {"localhost", "127.0.0.1", "::1"}


def parse_set_cookie(url: str, raw: str, now: float | None = None, top_site: str = "") -> dict | None:
    """One Set-Cookie header value -> {'set': playwright cookie} | {'delete': filter} | None (rejected).

    Follows RFC 6265bis closely enough for this guard: no comma splitting (a header is one cookie),
    values kept verbatim (quotes included), Max-Age beats Expires, a past Expires or Max-Age <= 0
    deletes, Domain must domain-match the host, Secure needs a secure context, __Secure-/__Host-
    prefixes and SameSite=None need Secure, Partitioned becomes a partition key.
    """
    from email.utils import parsedate_to_datetime
    now = time.time() if now is None else now
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    pieces = raw.split(";")
    name, sep, value = pieces[0].partition("=")
    if not sep:  # RFC 6265bis: no "=" means an empty name and the whole string as the value
        name, value = "", name
    name, value = name.strip(), value.strip()
    if (not name and not value) or any(ord(ch) < 32 or ord(ch) == 127 for ch in name + value):
        return None
    attrs: dict[str, str | bool] = {}
    for piece in pieces[1:]:
        key, _, val = piece.partition("=")
        key = key.strip().lower()
        if key:
            attrs[key] = val.strip() if _ else True
    domain_attr = str(attrs.get("domain", "")).lstrip(".").lower() if isinstance(attrs.get("domain"), str) else ""
    if domain_attr and not (host == domain_attr or host.endswith("." + domain_attr)):
        return None
    path_attr = attrs.get("path")
    path = path_attr if isinstance(path_attr, str) and path_attr.startswith("/") else (
        parts.path.rsplit("/", 1)[0] or "/")
    secure = "secure" in attrs
    if secure and not _is_secure_context(url):
        return None
    if name.startswith("__Secure-") and not secure:
        return None
    if name.startswith("__Host-") and not (secure and path == "/" and not domain_attr):
        return None
    same_site = str(attrs.get("samesite", "")).capitalize() if isinstance(attrs.get("samesite"), str) else ""
    if same_site == "None" and not secure:
        return None
    expires = None
    if isinstance(attrs.get("max-age"), str):
        import re as _re
        if _re.fullmatch(r"[+-]?[0-9]+", str(attrs["max-age"])):  # ASCII digits only, like Chromium
            seconds = int(str(attrs["max-age"]))
            expires = now + seconds if seconds > 0 else 0.0
    if expires is None and isinstance(attrs.get("expires"), str):
        try:
            expires = parsedate_to_datetime(str(attrs["expires"])).timestamp()
        except (TypeError, ValueError):
            expires = None
    domain = ("." + domain_attr) if domain_attr else host
    if expires is not None and expires > now + MAX_COOKIE_LIFETIME:
        expires = now + MAX_COOKIE_LIFETIME  # browsers cap lifetime (Chromium: 400 days); huge values break add_cookies
    if expires is not None and expires <= now:
        return {"delete": {"name": name, "domain": domain if domain_attr else host, "path": path}}
    cookie = {"name": name, "value": value, "domain": domain, "path": path,
              "httpOnly": "httponly" in attrs, "secure": secure}
    if same_site in {"Strict", "Lax", "None"}:
        cookie["sameSite"] = same_site
    if expires is not None:
        cookie["expires"] = expires
    if "partitioned" in attrs:
        if not secure:
            return None
        cookie["partitionKey"] = top_site or f"{parts.scheme}://{host}"
    return {"set": cookie}


class NetworkGuard:
    """Route guard installed on the page for the duration of the approved click.

    Allows exactly one request: the reviewed POST to the reviewed URL whose
    urlencoded body equals the approved values. Redirect hops of that request are
    followed only when the hop stays on the previous hop's origin, or when the
    previous response was a 303 and the browser turned the hop into a GET. Any
    other hop (for example a 307/308 that would replay the approved body to
    another origin) is aborted and reported. Every other navigation and every
    other non-GET/HEAD request is aborted and recorded. Plain GET subresources are
    left alone so the page still renders; that is a documented residual.
    Non-urlencoded enctypes have no body check, so nothing is ever approved for them.
    """

    def __init__(self, page, preview: dict | None = None, expected_values: dict[str, str] | None = None,
                 *, taint=(), allowed_href: str = "", known_urls=()):
        """With a preview this is the armed-submit guard. With none it is the baseline guard
        for every other daemon-driven click: nothing is ever approved, so every non-GET/HEAD
        request and every navigation that carries a body is aborted and reported."""
        self.page = page
        self.context = page.context
        self.taint = {v for v in (taint or ()) if len(v) >= TAINT_MIN_LEN}
        self.allowed_href = allowed_href
        self.known_urls = set(known_urls)
        self.nav_seen = False
        self.nav_requested = False   # the page asked for the allowed link; the daemon issues it, not the page
        self.daemon_nav_ok = False
        self.shipped_url = None
        self.cookie_baseline = None
        self.doc_urls: set[str] = set()
        self.isolated = False
        self.window_open = False
        self.start_origin = _origin(page.url)
        self.popups: list = []
        self._known_pages: list = []
        self._page_handler = None
        if preview is None:
            self.action = None
            self.enctype = None
            self.values = {}
        else:
            self.action = preview["form_action"]
            self.enctype = preview["form_facts"]["enctype"]
            names = field_name_map(preview)
            self.values = {names[selector]: value.replace("\r\n", "\n")
                           for selector, value in (expected_values or {}).items()}
        self.blocked: list[str] = []
        self.approved_post_sent = False
        self._approved_request = None
        self._handler = None

    def _root(self, request):
        while request.redirected_from is not None:
            request = request.redirected_from
        return request

    def _is_approved(self, request) -> bool:
        if (self.action is None or self.approved_post_sent or request.method.upper() != "POST"
                or request.url != self.action):
            return False
        if not request.is_navigation_request() or request.frame != self.page.main_frame:
            return False
        if self.enctype != DEFAULT_ENCTYPE:
            return False  # fail closed: no click-time body check exists for this encoding
        if not (request.headers.get("content-type", "").lower().startswith(DEFAULT_ENCTYPE)):
            return False
        return _form_body(request.post_data or "") == self.values

    @staticmethod
    def _fetch_headers(original: dict, url: str, method: str, origin_of_page: tuple) -> dict:
        """Headers for a guard-issued fetch, copied from the browser's own request where visible.

        route.fetch is not the browser network stack, so Sec-Fetch-* and Content-Type
        are copied from the original request (the raw header set Chromium produced) and
        adjusted per hop: a hop converted to GET drops the body headers, and
        Sec-Fetch-Site is recomputed against the page that started the navigation.
        Residual differences from a real navigation: header order and casing, the
        connection (a Playwright client, not Chromium's network stack), and the Sec-Fetch
        values are synthesized for a user-activated main-frame form navigation because
        Playwright does not expose Chromium's own.
        """
        keep = {"accept", "accept-language", "accept-encoding", "upgrade-insecure-requests", "referer",
                "origin", "content-type", "user-agent"}
        headers = {k: v for k, v in original.items()
                   if k.lower() in keep or k.lower().startswith("sec-ch-")}
        if method != "POST":
            for name in [k for k in headers if k.lower() in {"content-type", "origin"}]:
                del headers[name]
        target = _origin(url)
        site = "same-origin" if target == origin_of_page else (
            "same-site" if target[1] == origin_of_page[1] else "cross-site")
        # Playwright hides Sec-Fetch-* from routed requests (the network stack adds them
        # later), so they are rebuilt for a main-frame form navigation started by the
        # approved user-activated click.
        headers.update({"sec-fetch-mode": "navigate", "sec-fetch-dest": "document",
                        "sec-fetch-user": "?1", "sec-fetch-site": site})
        return headers

    async def _persist_cookies(self, url: str, response) -> None:
        """Store every Set-Cookie of a guard-resolved hop in the browser context.

        route.fetch shares the context cookie jar for plain cookies, but expiry, deletion and
        partitioning are not reliably applied, so each header is parsed and applied explicitly.
        """
        try:
            top_site = ""
            for item in response.headers_array:
                if item["name"].lower() != "set-cookie":
                    continue
                parsed = parse_set_cookie(url, item["value"], top_site=top_site)
                if parsed is None:
                    self.blocked.append(f"set-cookie rejected for {url[:100]}")
                elif "delete" in parsed:
                    await self.context.clear_cookies(**parsed["delete"])
                else:
                    await self.context.add_cookies([parsed["set"]])
        except Exception as error:  # noqa: BLE001 - a bad cookie must not strand the routed request
            self.blocked.append(f"cookie not stored for {url[:100]}: {str(error)[:100]}")

    async def _send_approved(self, route, request) -> None:
        """Send the approved POST and judge every redirect hop before the browser sees it.

        Chromium follows redirects inside the network stack and never calls the route
        handler for the hops, so this guard resolves the entire chain itself with
        redirects disabled and hands the browser only the final non-redirect response.
        Hop rules, applied to every hop:
          * 307/308 replay the method and body and are allowed only same-origin;
          * 301/302 turn the POST into a GET and are allowed only same-origin;
          * a 303 straight out of the approved POST may go anywhere (it becomes a bodyless
            GET, the one hop that cannot carry the approved body); every hop after any
            GET has been issued must stay on the origin of the hop before it;
          * more than MAX_GUARDED_HOPS hops, a missing Location, or a loop is blocked.
        A blocked hop is reported and the request aborted, so nothing past it is fetched.
        The browser's URL stays the form action (documented residual).
        """
        url = request.url
        method = "POST"
        body = request.post_data_buffer
        page_origin = _origin(self.page.url)
        original = await request.all_headers()
        response = await route.fetch(max_redirects=0, headers=self._fetch_headers(original, url, "POST", page_origin))
        await self._persist_cookies(url, response)
        seen = {url}
        hops = 0
        while response.status in REDIRECT_STATUSES:
            location = response.headers.get("location")
            target = urljoin(url, location) if location else None
            same = target is not None and _origin(target) == _origin(url)
            first_303 = response.status == 303 and method == "POST"
            if (target is None or hops >= MAX_GUARDED_HOPS or target in seen
                    or not (same or first_303)
                    or urlsplit(target).scheme.lower() not in {"http", "https"}):
                self.blocked.append(f"redirect {response.status} {url[:100]} -> {str(target)[:100]}")
                await route.abort("blockedbyclient")
                return
            if response.status in (301, 302, 303) and method != "GET":
                method, body = "GET", None
            hops += 1
            seen.add(target)
            url = target
            options = {"url": target, "method": method, "max_redirects": 0,
                       "headers": self._fetch_headers(original, target, method, page_origin)}
            if body is not None:
                options["post_data"] = body
            response = await route.fetch(**options)
            await self._persist_cookies(target, response)
        await route.fulfill(response=response)

    def _tainted(self, url: str) -> bool:
        return url_carries_taint(url, self.taint)

    ASSET_TYPES = {"stylesheet", "script", "image", "font", "media"}
    NEVER_TYPES = {"websocket", "eventsource", "ping", "beacon", "csp_report", "texttrack"}

    def _guarded_pages(self) -> list:
        return [self.page, *self.popups]

    async def _owns(self, request) -> bool:
        """Does this request belong to the guarded page, or to a page it opened? A popup's first
        request can arrive before the popup event does, so the opener is asked directly. Other tabs
        of the shared browser are not ours."""
        try:
            frame = request.frame
            page = frame.page
        except Exception:  # noqa: BLE001 - service-worker requests have no frame
            return False
        if page in self._guarded_pages():
            return True
        if self.window_open and page not in self._known_pages:
            # A page that did not exist when the click started, seen during the click window: treat as
            # a popup of this click (this also guards a tab the owner happens to open in those seconds).
            await self._watch_popup(page)
            return True
        try:
            opener = await page.opener()
        except Exception:  # noqa: BLE001
            return False
        if opener is not None and opener in self._guarded_pages():
            if page not in self.popups:
                await self._watch_popup(page)
            return True
        return False

    async def _route(self, route, request) -> None:
        method = request.method.upper()
        try:
            from_worker = request.service_worker is not None
        except Exception:  # noqa: BLE001
            from_worker = False
        if from_worker and self.action is None:
            self.blocked.append(f"service worker request {method} {request.url[:100]}")
            await route.abort("blockedbyclient")
            return
        if not from_worker:
            try:
                request.frame
            except Exception:  # noqa: BLE001
                # A navigation whose frame does not exist yet is the first request of a brand-new page
                # (a popup). During the click window that is the click's popup: abort it. Afterwards it
                # cannot be told apart from a tab the owner opened, so it is left alone unless the session runs in
                # its own isolated context (then there are no owner tabs and it is always aborted).
                if (self.window_open or self.isolated) and request.is_navigation_request() and self.action is None:
                    self.blocked.append(f"popup navigation {method} {request.url[:100]}")
                    await route.abort("blockedbyclient")
                else:
                    await route.fallback()
                return
        if not from_worker and not await self._owns(request):
            await route.fallback()  # another tab of the shared browser: not this guard's business
            return
        if self._is_approved(request):
            self.approved_post_sent = True
            self._approved_request = request
            await self._send_approved(route, request)
            return
        if method in {"GET", "HEAD"}:
            if request.resource_type in self.NEVER_TYPES:
                self.blocked.append(f"{request.resource_type} {request.url[:120]}")
                await route.abort("blockedbyclient")
                return
            if self._tainted(request.url):
                self.blocked.append(f"{method} carrying form data {request.url[:120]}")
                await route.abort("blockedbyclient")
                return
            if self.action is None:
                top = request.is_navigation_request() and request.frame == self.page.main_frame
                if top and not self.daemon_nav_ok and not self.nav_seen and self.allowed_href \
                        and request.url == self.allowed_href:
                    # The page's own navigation is never sent. Remember that it asked; the daemon sends
                    # the request itself at a fixed time (no timing channel beyond whether it asked).
                    self.nav_requested = True
                    self.url_at_request = self.page.url
                    await route.abort("blockedbyclient")
                    return
                if self._baseline_allows(request):
                    if request.is_navigation_request() and request.frame == self.page.main_frame:
                        await self._fulfill_with_csp(route, request.url)
                    else:
                        await route.continue_()
                else:
                    self.blocked.append(f"{method} not part of the click {request.url[:120]}")
                    await route.abort("blockedbyclient")
                return
            if not request.is_navigation_request():
                await route.continue_()
                return
        self.blocked.append(f"{method} {request.url[:200]}")
        await route.abort("blockedbyclient")

    async def _fulfill_with_csp(self, route, request_url: str) -> None:
        """Top-level document the click navigated to: deliver it with GUARD_CSP so its scripts cannot
        open connections. Redirects are handed back unfollowed so every hop is judged again."""
        response = await route.fetch(max_redirects=0)
        if response.status in REDIRECT_STATUSES:
            await route.fulfill(response=response)
            return
        try:
            body = (await response.body()).decode("utf-8", "replace")
            self.doc_urls = markup_urls(body, request_url)
        except Exception:  # noqa: BLE001 - no markup, so no subresource is pre-approved
            self.doc_urls = set()
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-security-policy"}
        if "html" in headers.get("content-type", "html").lower():
            headers["content-security-policy"] = GUARD_CSP_HEADER
        await route.fulfill(response=response, headers=headers)

    def _baseline_allows(self, request) -> bool:
        """Baseline (non-approved) policy after a guarded click: exactly ONE request may leave, the
        clicked link's own top-level navigation, to the exact href the click targets (and that the
        server shipped). Nothing else, known or not: no subresource, fetch, image or other navigation.
        Why not "known URLs": which of N shipped URLs a script requests is itself a channel (256 anchors
        /k/0../k/255 and Image().src='/k/'+charCode leaks the draft one character at a time). With one
        allowed request there is no selection left except whether and when that single navigation
        happens (see the docs: a timing/1-bit channel remains)."""
        url = request.url
        top_nav = request.is_navigation_request() and request.frame == self.page.main_frame
        if not top_nav or self.nav_seen or not self.allowed_href:
            return False
        if url != self.allowed_href or self._tainted(url):
            return False
        self.nav_seen = True
        self.start_origin = _origin(url)
        return True

    async def pre_nav_problem(self) -> str | None:
        """Why the daemon must NOT send the allowed navigation: the URL the Referer would carry is not
        the server's, or a script-writable cookie differs from the load-time baseline (the Cookie header
        would carry it). None means it is clean. Fails closed when there is no baseline."""
        if self.shipped_url is None or self.cookie_baseline is None:
            return "no load-time snapshot of the page, so its URL and cookies cannot be vouched for"
        if getattr(self, "url_at_request", self.page.url).split("#")[0] != self.shipped_url:
            return "page URL changed after load (it would ride in Referer)"
        now = {}
        for cookie in await self.context.cookies():
            if not cookie.get("httpOnly"):
                now[(cookie["name"], cookie["domain"], cookie["path"])] = cookie["value"]
        if now != self.cookie_baseline:
            # Put the jar back so nothing a script wrote can ride a later request either.
            for key in set(now) - set(self.cookie_baseline):
                try:
                    await self.context.clear_cookies(name=key[0], domain=key[1], path=key[2])
                except Exception:  # noqa: BLE001
                    pass
            return "a script-writable cookie changed during the click (it would ride in Cookie)"
        return None

    async def expose_reporter(self) -> str:
        """A page binding that survives navigation, so a report made just before unload still arrives."""
        import secrets
        name = f"__atlasReport_{secrets.token_hex(6)}"
        self.page_reports: list[str] = []
        await self.page.expose_function(name, lambda what: self.page_reports.append(str(what)[:100]))
        return name

    async def _watch_popup(self, popup) -> None:
        self.popups.append(popup)
        popup.on("popup", lambda p: __import__("asyncio").ensure_future(self._watch_popup(p)))
        await self._block_websockets(popup)

    async def _block_websockets(self, page) -> None:
        async def refuse(ws):
            self.blocked.append(f"websocket {ws.url[:100]}")
            await ws.close(code=1008, reason="blocked by Atlas guard")
        try:
            await page.route_web_socket("**/*", refuse)
        except Exception as error:  # noqa: BLE001 - reported, the HTTP guard still runs
            self.blocked.append(f"websocket guard unavailable: {str(error)[:80]}")

    async def _stop_service_workers(self) -> None:
        """Unregister and stop service workers for the page: a worker is a second network client
        that can be driven by postMessage. Best effort; requests a worker still sends are aborted
        by the route when Playwright reports them with a service_worker."""
        try:
            await self.page.evaluate("() => navigator.serviceWorker ? navigator.serviceWorker.getRegistrations()"
                                     ".then(rs => Promise.all(rs.map(r => r.unregister()))): 0")
        except Exception:  # noqa: BLE001
            pass
        try:
            cdp = await self.context.new_cdp_session(self.page)
            await cdp.send("ServiceWorker.enable")
            await cdp.send("ServiceWorker.stopAllWorkers")
            await cdp.detach()
        except Exception:  # noqa: BLE001 - not every browser exposes CDP
            pass

    async def install(self) -> None:
        """Route at CONTEXT level so popups are guarded; foreign tabs fall through untouched."""
        import asyncio
        self._handler = self._route
        self._known_pages = list(self.context.pages)
        self.window_open = True
        self._popup_listener = lambda p: asyncio.ensure_future(self._watch_popup(p))
        self.page.on("popup", self._popup_listener)
        await self.context.route("**/*", self._handler)
        await self._block_websockets(self.page)
        if self.action is None:
            await self._stop_service_workers()

    async def close_popups(self) -> None:
        """Close and report popups now, leaving the guard itself installed."""
        self.window_open = False
        for popup in self.popups:
            try:
                self.blocked.append(f"popup opened {popup.url[:100]}")
                await popup.close()
            except Exception:  # noqa: BLE001 - already closed
                pass
        self.popups = []

    async def settle(self, quiet: float = QUIET_SECONDS) -> None:
        """Keep the guard up until the page is idle plus a quiet period (late timers, keepalives)."""
        import asyncio
        for page in [self.page, *self.popups]:
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:  # noqa: BLE001 - best effort; the quiet period still runs
                pass
        await asyncio.sleep(quiet)
        self.window_open = False

    async def remove(self) -> None:
        listener = getattr(self, "_popup_listener", None)
        if listener is not None:
            try:
                self.page.remove_listener("popup", listener)
            except Exception:  # noqa: BLE001
                pass
            self._popup_listener = None
        if self._handler is not None:
            try:
                await self.context.unroute("**/*", self._handler)
            finally:
                self._handler = None
        for page in self._guarded_pages():
            try:
                await page.unroute_all(behavior="ignoreErrors")
            except Exception:  # noqa: BLE001
                pass
        for popup in self.popups:
            try:
                self.blocked.append(f"popup opened {popup.url[:100]}")
                await popup.close()
            except Exception:  # noqa: BLE001 - already closed
                pass
        self.popups = []

    def report(self) -> dict:
        return {"approved_post_sent": self.approved_post_sent,
                "blocked": [*self.blocked, *[f"page-guard: {item}" for item in getattr(self, "page_reports", [])]]}

    @staticmethod
    async def collect_known_urls(page) -> list[str]:
        """URLs the SERVER's response for this document shipped (snapshot taken at load, before anything
        was filled). The live DOM is not trusted: a script can add a link whose URL encodes the draft and
        the click-time DOM would then list it. No snapshot (document not seen as a response) means nothing
        is pre-approved."""
        snapshot = getattr(page, "_atlas_doc_urls", None)
        if snapshot is None or snapshot[0] != page.url.split("#")[0]:
            return [page.url]
        return sorted(snapshot[1]) + [page.url]

    @staticmethod
    async def shipped_href(page, href: str) -> str:
        """The clicked link's target, kept only if the server shipped it."""
        snapshot = getattr(page, "_atlas_doc_urls", None)
        if not href or snapshot is None or snapshot[0] != page.url.split("#")[0] or href not in snapshot[1]:
            return ""
        return href

    @staticmethod
    async def collect_taint(page) -> list[str]:
        """Every non-trivial value currently in the page's form controls (data that must not leave)."""
        values = await page.evaluate(TAINT_JS)
        return [v for v in values if isinstance(v, str)]
