"""c36.agency (doc row 108): personal-brand + owner-run earning agency engine.

Closes the audit gap on row 108 ("planning/drafts/collectors; no monetized
agency outcome"): the complete agency machinery - brand kit, priced service
catalog, client pipeline CRM (lead -> qualified -> proposal -> owner-approved
-> delivered -> paid), proposal and invoice DOCUMENT generation, and a
revenue ledger that records supplied payment facts and computes totals,
receivables and per-client revenue.

Enforced money boundaries: this unit never charges, bills, spends, posts or
outreaches. Proposals and invoices are DOCUMENTS that enter owner review;
payments are RECORDED facts supplied by the owner, never executed. Any
request key naming send/outreach/post/charge/card/pay-execution refuses the
whole request. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import hashlib
import json
import re

from app.modules.c30 import policy

PREFIX = "AGENCY"
MAX_SERVICES = 100
MAX_LEADS = 1000
MAX_TEXT = 4000
PIPELINE = ("lead", "qualified", "proposal_drafted", "owner_approved",
            "delivered", "invoice_drafted", "paid")

_FORBIDDEN = (
    ("OUTREACH", frozenset({"send", "email", "smtp", "dm", "outreach", "message_client",
                            "notify"})),
    ("AUTOPOST", frozenset({"post", "publish", "schedule_post", "autopost", "upload"})),
    ("SPEND", frozenset({"spend", "buy_ads", "ads_budget", "boost"})),
    ("CHARGE", frozenset({"charge", "charge_card", "card", "stripe_charge", "auto_bill",
                          "collect_payment", "debit"})),
    ("FAKEACCT", frozenset({"fake_account", "bot", "bots", "multi_account"})),
)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

LIMITS = (
    "Documents only: proposals and invoices enter owner review; nothing is sent.",
    "Payments are owner-supplied records of fact; this unit never charges or collects.",
    "Revenue figures are sums of supplied records, not a business outcome promise.",
)


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


def _guard(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str):
                nk = k.casefold().replace("-", "_")
                for reason, keys in _FORBIDDEN:
                    if nk in keys:
                        _err(reason, nk)
            _guard(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _guard(v)


def _id(prefix, *parts):
    return prefix + "-" + hashlib.sha256(
        json.dumps(parts, sort_keys=True).encode()).hexdigest()[:10]


def brand_kit(profile):
    """Deterministic brand kit from a supplied profile."""
    _guard(profile)
    if not isinstance(profile, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:profile" % PREFIX)
    name = policy.clean_text(profile.get("name"), PREFIX, "name", 120)
    skills = profile.get("skills", [])
    if isinstance(skills, bool) or not isinstance(skills, (list, tuple)) or not skills:
        _err("EMPTY", "skills")
    skills = [policy.clean_text(s, PREFIX, "skill", 80) for s in skills[:20]]
    audience = policy.clean_text(profile.get("audience", "clients"), PREFIX, "audience", 200)
    digest = hashlib.sha256(name.encode()).hexdigest()
    palette = ["#%s" % digest[i:i + 6] for i in (0, 6, 12)]
    return {
        "brand_name": name,
        "positioning": "%s for %s, led by %s" % (skills[0], audience, name),
        "voice_rules": ["plain words", "evidence over adjectives", "short sentences"],
        "palette": palette,
        "service_seeds": skills,
        "generated_posting": False,
        "limits": list(LIMITS),
    }


def catalog(services):
    """Validate a priced service catalog."""
    _guard(services)
    if isinstance(services, bool) or not isinstance(services, (list, tuple)) \
            or not services or len(services) > MAX_SERVICES:
        raise ValueError("%s_REFUSED_BAD_TYPE:services" % PREFIX)
    out = []
    for s in services:
        if not isinstance(s, dict):
            raise ValueError("%s_REFUSED_BAD_TYPE:service" % PREFIX)
        sid = policy.clean_text(s.get("id"), PREFIX, "service.id", 64)
        name = policy.clean_text(s.get("name"), PREFIX, "service.name", 200)
        price = s.get("price_cents")
        if isinstance(price, bool) or not isinstance(price, int) or price < 0:
            raise ValueError("%s_REFUSED_BAD_TYPE:price_cents" % PREFIX)
        unit = policy.clean_text(s.get("unit", "project"), PREFIX, "service.unit", 40)
        out.append({"id": sid, "name": name, "price_cents": price, "unit": unit})
    return {"services": out, "count": len(out), "limits": list(LIMITS)}


def _store(store):
    if not isinstance(store, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:store" % PREFIX)
    store.setdefault("clients", {})
    store.setdefault("payments", [])
    if len(store["clients"]) > MAX_LEADS:
        _err("OVERSIZE")
    return store


def add_lead(store, lead):
    store = _store(store)
    _guard(lead)
    if not isinstance(lead, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:lead" % PREFIX)
    name = policy.clean_text(lead.get("name"), PREFIX, "lead.name", 200)
    need = policy.clean_text(lead.get("need"), PREFIX, "lead.need", MAX_TEXT, allow_ws=True)
    cid = _id("cli", name, need)
    store["clients"][cid] = {"id": cid, "name": name, "need": need, "state": "lead",
                             "service_id": lead.get("service_id"), "history": ["lead"]}
    return store["clients"][cid]


def _advance(store, client_id, target):
    store = _store(store)
    client = store["clients"].get(client_id)
    if not client:
        _err("NOTFOUND", client_id)
    cur = PIPELINE.index(client["state"])
    nxt = PIPELINE.index(target)
    if nxt != cur + 1:
        _err("STATE", "%s->%s" % (client["state"], target))
    client["state"] = target
    client["history"].append(target)
    return client


def qualify(store, client_id, service_id=None):
    client = _advance(store, client_id, "qualified")
    if service_id is not None:
        client["service_id"] = policy.clean_text(service_id, PREFIX, "service_id", 64)
    return client


def draft_proposal(store, client_id, scope_text, catalog_services):
    client = _advance(store, client_id, "proposal_drafted")
    _guard(scope_text)
    scope_text = policy.clean_text(scope_text, PREFIX, "scope", MAX_TEXT, allow_ws=True)
    svc = None
    for s in (catalog_services or []):
        if isinstance(s, dict) and s.get("id") == client.get("service_id"):
            svc = s
    price_line = ("%s: %d cents per %s" % (svc["name"], svc["price_cents"], svc["unit"])) \
        if svc else "pricing to be confirmed by owner"
    client["proposal"] = {
        "title": "Proposal for %s" % client["name"],
        "scope": scope_text,
        "pricing": price_line,
        "status": "awaiting_owner_approval",
        "sent": False,
        "hash": hashlib.sha256((scope_text + price_line).encode()).hexdigest(),
    }
    return client


def owner_approve(store, client_id, approver, proposal_hash):
    client = store["clients"].get(client_id) if isinstance(store, dict) else None
    if not client or "proposal" not in client:
        _err("STATE", "no-proposal")
    if not isinstance(proposal_hash, str) or proposal_hash != client["proposal"]["hash"]:
        _err("EXACT_DRAFT", "hash-mismatch")  # approve the exact reviewed draft only
    client = _advance(store, client_id, "owner_approved")
    client["proposal"]["status"] = "owner_approved"
    client["proposal"]["approved_by"] = policy.clean_text(approver, PREFIX, "approver", 120)
    return client


def mark_delivered(store, client_id, deliverable_summary):
    client = _advance(store, client_id, "delivered")
    client["deliverable"] = policy.clean_text(deliverable_summary, PREFIX, "deliverable",
                                              MAX_TEXT, allow_ws=True)
    return client


def draft_invoice(store, client_id, amount_cents, as_of):
    client = _advance(store, client_id, "invoice_drafted")
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError("%s_REFUSED_BAD_TYPE:amount_cents" % PREFIX)
    if not isinstance(as_of, str) or not _DATE.fullmatch(as_of):
        raise ValueError("%s_REFUSED_BAD_TYPE:as_of" % PREFIX)
    client["invoice"] = {
        "id": _id("inv", client_id, amount_cents, as_of),
        "amount_cents": amount_cents, "issued": as_of,
        "status": "awaiting_owner_review",
        "collection": "owner collects payment outside Atlas; Atlas never charges",
        "sent": False,
    }
    return client


def record_payment(store, client_id, payment):
    """Record an owner-supplied payment fact. payment = {"amount_cents",
    "received_date", "note"?}. This records; it never collects."""
    _guard(payment)
    store = _store(store)
    client = store["clients"].get(client_id)
    if not client:
        _err("NOTFOUND", client_id)
    if client["state"] != "invoice_drafted":
        _err("STATE", client["state"])
    if not isinstance(payment, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:payment" % PREFIX)
    amount = payment.get("amount_cents")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise ValueError("%s_REFUSED_BAD_TYPE:amount_cents" % PREFIX)
    date = payment.get("received_date")
    if not isinstance(date, str) or not _DATE.fullmatch(date):
        raise ValueError("%s_REFUSED_BAD_TYPE:received_date" % PREFIX)
    entry = {"client_id": client_id, "amount_cents": amount, "received_date": date,
             "note": payment.get("note"), "recorded_fact": True, "executed_by_atlas": False}
    store["payments"].append(entry)
    client["state"] = "paid"
    client["history"].append("paid")
    return entry


def ledger(store):
    """Revenue ledger over recorded payments: totals, receivables, per-client."""
    store = _store(store)
    per_client = {}
    for p in store["payments"]:
        per_client[p["client_id"]] = per_client.get(p["client_id"], 0) + p["amount_cents"]
    receivables = {c["id"]: c["invoice"]["amount_cents"]
                   for c in store["clients"].values()
                   if c["state"] == "invoice_drafted" and c.get("invoice")}
    return {
        "total_received_cents": sum(per_client.values()),
        "payments_recorded": len(store["payments"]),
        "per_client_cents": per_client,
        "receivables_cents": receivables,
        "clients_by_state": {s: sum(1 for c in store["clients"].values() if c["state"] == s)
                             for s in PIPELINE},
        "basis": "owner-supplied payment records only",
        "limits": list(LIMITS),
    }
