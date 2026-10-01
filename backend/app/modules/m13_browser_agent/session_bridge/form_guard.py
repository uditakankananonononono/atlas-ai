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

from typing import Any
from urllib.parse import parse_qsl

DEFAULT_ENCTYPE = "application/x-www-form-urlencoded"
ALLOWED_ENCTYPES = (DEFAULT_ENCTYPE, "multipart/form-data", "text/plain")
SUBMIT_OVERRIDES = ("formaction", "formmethod", "formenctype", "formtarget", "formnovalidate")
# Seconds an approved submit stays armed with nobody clicking it.
ARM_TTL_SECONDS = 120.0

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
    if facts["enctype"] != expected_enctype:
        raise PermissionError("form enctype differs from the reviewed value")
    if facts["method"] != "post":
        raise PermissionError("approved publication must be a POST form")
    return facts


def _form_body(text: str) -> dict[str, str]:
    return {name: value.replace("\r\n", "\n") for name, value in parse_qsl(text, keep_blank_values=True)}


class NetworkGuard:
    """Route guard installed on the page for the duration of the approved click.

    Allows exactly one request: the reviewed POST to the reviewed URL whose
    urlencoded body equals the approved values. Redirect hops of that request are
    server driven and allowed. Every other navigation and every other non-GET/HEAD
    request is aborted and recorded. Plain GET subresources are left alone so the
    page still renders; that is a documented residual.
    """

    def __init__(self, page, preview: dict, expected_values: dict[str, str]):
        self.page = page
        self.action = preview["form_action"]
        self.enctype = preview["form_facts"]["enctype"]
        self.values = {selector.split('"')[1]: value.replace("\r\n", "\n") for selector, value in expected_values.items()}
        self.blocked: list[str] = []
        self.approved_post_sent = False
        self._approved_request = None
        self._handler = None

    def _root(self, request):
        while request.redirected_from is not None:
            request = request.redirected_from
        return request

    def _is_approved(self, request) -> bool:
        if self.approved_post_sent or request.method.upper() != "POST" or request.url != self.action:
            return False
        if not request.is_navigation_request() or request.frame != self.page.main_frame:
            return False
        if self.enctype == DEFAULT_ENCTYPE:
            if not (request.headers.get("content-type", "").lower().startswith(DEFAULT_ENCTYPE)):
                return False
            if _form_body(request.post_data or "") != self.values:
                return False
        return True

    async def _route(self, route, request) -> None:
        method = request.method.upper()
        if request.redirected_from is not None and self._root(request) is self._approved_request:
            await route.continue_()
            return
        if self._is_approved(request):
            self.approved_post_sent = True
            self._approved_request = request
            await route.continue_()
            return
        if method in {"GET", "HEAD"} and not request.is_navigation_request():
            await route.continue_()
            return
        self.blocked.append(f"{method} {request.url[:200]}")
        await route.abort("blockedbyclient")

    async def install(self) -> None:
        self._handler = self._route
        await self.page.route("**/*", self._handler)

    async def remove(self) -> None:
        if self._handler is not None:
            try:
                await self.page.unroute("**/*", self._handler)
            finally:
                self._handler = None

    def report(self) -> dict:
        return {"approved_post_sent": self.approved_post_sent, "blocked": list(self.blocked)}
