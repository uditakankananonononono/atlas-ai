"""Destination binding for the generic M13 capture-bound submit (audit finding 1).

Every CLICK_SUBMIT on a paired device carries a reviewed destination preview: the
browser-resolved form facts, the submit control, and the form's complete field
set. The daemon re-checks all of it in the real browser, installs the click-time
page and network guards, and refuses a click that has no preview. This module
builds that preview for callers (M13) that only hold a selector and values.
"""
from __future__ import annotations

import hashlib
import json

from bs4 import BeautifulSoup

from .session_bridge import form_guard


def preview_digest(preview: dict) -> str:
    return hashlib.sha256(json.dumps(preview, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


async def build_binding_preview(sessions, tenant_id: str, session_id: str, selector: str,
                                values: dict[str, str]) -> dict:
    """Read the live form from the paired browser; refuse anything the daemon would refuse."""
    soup = BeautifulSoup(await sessions.extract(tenant_id, session_id), "html.parser")
    buttons = soup.select(selector)
    if len(buttons) != 1:
        raise PermissionError("submit target is not exactly one control")
    button = buttons[0]
    form = button.find_parent("form")
    if form is None:
        raise PermissionError("submit control is not inside a form")
    if any(attr in node.attrs for node in [button, *form.select("input,button")]
           for attr in form_guard.SUBMIT_OVERRIDES):
        raise PermissionError("submit control overrides the form destination")
    facts = form_guard.validate_facts(await sessions.form_facts(tenant_id, session_id, selector))
    form_guard.static_form_checks(soup, form, button)
    field_names: dict[str, str] = {}
    for value_selector in values:
        nodes = soup.select(value_selector)
        name = nodes[0].get("name") if len(nodes) == 1 else None
        if not name:
            raise PermissionError("every approved value must map to exactly one named form field")
        field_names[value_selector] = str(name)
    fields = form.select("input,textarea,select,button[name]")
    names = [node.get("name") for node in fields]
    if (soup.select("[form]") or len(set(names)) != len(names)
            or any(node.get("type", "").lower() == "password" for node in fields)
            or set(names) != set(field_names.values())):
        raise PermissionError("the form has fields that are not part of the approved values")
    return {"url": facts["url"], "form_action": facts["action"], "form_facts": facts,
            "method": form.get("method", "get"), "form_text": form.get_text(" ", strip=True),
            "submit": str(button), "values": dict(values), "field_names": field_names}
