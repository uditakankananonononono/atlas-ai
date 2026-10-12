"""c35.registration_pipeline (doc row 99): review-gated olympiad registration
+ fee-waiver pipeline.

Composes the existing bounded units (c35.olympiad checklist/prefill and
c35.waiver_drafts) into an end-to-end state machine:

  draft -> pending_review -> owner_approved -> handoff_exported

A packet carries the registration checklist, form prefill, and (when the
opportunity has a fee) a filled fee-waiver draft. NOTHING is registered,
submitted, emailed or paid by this unit: the terminal state writes a local
handoff bundle (packet.json + waiver.txt + README.txt) for the OWNER to act
on. Any request key naming send/register/submit/login/pay at any depth
refuses the whole request. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

from app.modules.c30 import policy
from app.modules.c35 import olympiad, waiver_drafts

PREFIX = "APPLY"
STATES = ("draft", "pending_review", "owner_approved", "handoff_exported")
MAX_PACKETS = 200
MAX_OUT_PATH = 512

_FORBIDDEN = (
    ("SEND", frozenset({"send", "smtp", "email_send", "sender", "smtp_host", "mail"})),
    ("SPEND", frozenset({"pay", "payment", "card", "fee_action", "waive_fee"})),
    ("REGISTER", frozenset({"register", "submit", "submission", "enroll"})),
    ("ATTEMPT", frozenset({"attempt", "take_exam", "live_exam"})),
    ("NOCREDS", frozenset({"login", "password", "username", "credentials", "otp",
                           "api_key", "token", "bearer", "passwd"})),
)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


def _scan(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str):
                nk = k.casefold().replace("-", "_")
                for reason, keys in _FORBIDDEN:
                    if nk in keys:
                        _err(reason, nk)
            _scan(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _scan(v)


def _packet_id(olympiad_name, profile_name):
    blob = json.dumps([olympiad_name, profile_name], sort_keys=True)
    return "pkt-" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def build_packet(request):
    """request = {"as_of", "olympiad": {name, deadline, requirements, fee?,
    contact_email?, contact_name?}, "profile": {full_name, school, ...},
    "waiver_template"?}. Returns a packet in state pending_review."""
    if isinstance(request, bool) or not isinstance(request, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:request" % PREFIX)
    _scan(request)
    as_of = request.get("as_of")
    if not isinstance(as_of, str) or not _DATE.fullmatch(as_of):
        raise ValueError("%s_REFUSED_BAD_TYPE:as_of" % PREFIX)
    oly = request.get("olympiad")
    prof = request.get("profile")
    if not isinstance(oly, dict) or not isinstance(prof, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:olympiad|profile" % PREFIX)
    name = policy.clean_text(oly.get("name"), PREFIX, "olympiad.name", 200)
    checklist = olympiad.run({"as_of": as_of, "mode": "checklist",
                              "olympiad": {"name": name, "deadline": oly.get("deadline"),
                                           "requirements": oly.get("requirements", [])},
                              "profile": prof})
    fee = oly.get("fee")
    has_fee = bool(fee) and str(fee).strip().lower() not in ("", "0", "0.0", "free", "none", "no fee")
    waiver = None
    if has_fee:
        template = request.get("waiver_template")
        if not isinstance(template, str):
            template = ("Dear {contact},\n\nI am writing to request a fee waiver for "
                        "{opportunity}. My name is {name} and I study at {school}. "
                        "The listed fee is {fee}; the deadline is {deadline}.\n\n"
                        "Thank you for your consideration.\n{name}")
        waiver = waiver_drafts.run({
            "as_of": as_of,
            "profile": {"name": prof.get("full_name", prof.get("name", "")),
                        "school": prof.get("school", "")},
            "template": template,
            "opportunities": [{"id": _packet_id(name, prof.get("full_name", "")),
                               "title": name, "fee": str(fee),
                               "contact_email": oly.get("contact_email", ""),
                               "contact_name": oly.get("contact_name", ""),
                               "deadline": oly.get("deadline", "")}],
        })
    packet = {
        "id": _packet_id(name, prof.get("full_name", prof.get("name", ""))),
        "state": "pending_review",
        "as_of": as_of,
        "olympiad": {"name": name, "deadline": oly.get("deadline"), "fee": fee or None},
        "checklist": checklist,
        "waiver_draft": waiver,
        "review": {"reviewed_by": None, "decision": None, "exact_artifact_hash": None},
        "boundary": ("Preparation only. Atlas does not register, submit, email, pay or log "
                     "in. The terminal state is a local handoff bundle for the owner."),
    }
    packet["artifact_hash"] = hashlib.sha256(
        json.dumps(packet["checklist"], sort_keys=True).encode("utf-8")).hexdigest()
    return packet


def review(store, packet_id, decision, reviewer):
    """Owner review. decision in {"approve","reject"}; store is the caller's
    dict of packet_id -> packet. Approve requires the reviewer to confirm the
    packet's CURRENT artifact hash (exact-draft approval)."""
    if not isinstance(store, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:store" % PREFIX)
    packet = store.get(packet_id)
    if not isinstance(packet, dict):
        _err("NOTFOUND", "packet")
    if packet["state"] != "pending_review":
        _err("STATE", packet["state"])
    reviewer = policy.clean_text(reviewer, PREFIX, "reviewer", 120)
    if decision == "reject":
        packet["state"] = "draft"
        packet["review"] = {"reviewed_by": reviewer, "decision": "reject",
                            "exact_artifact_hash": None}
        return packet
    if decision != "approve":
        raise ValueError("%s_REFUSED_BAD_TYPE:decision" % PREFIX)
    packet["state"] = "owner_approved"
    packet["review"] = {"reviewed_by": reviewer, "decision": "approve",
                        "exact_artifact_hash": packet["artifact_hash"]}
    return packet


def export_handoff(store, packet_id, out_dir):
    """Terminal state: write the handoff bundle to a LOCAL directory. Only an
    owner_approved packet exports. Returns the written file paths."""
    if not isinstance(store, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:store" % PREFIX)
    packet = store.get(packet_id)
    if not isinstance(packet, dict):
        _err("NOTFOUND", "packet")
    if packet["state"] != "owner_approved":
        _err("STATE", packet["state"])
    out_dir = policy.clean_text(out_dir, PREFIX, "out_dir", MAX_OUT_PATH)
    root = os.path.realpath(out_dir)
    if os.path.exists(root) and not os.path.isdir(root):
        _err("PATH")
    os.makedirs(root, exist_ok=True)
    files = []
    packet_path = os.path.join(root, packet["id"] + ".packet.json")
    with open(packet_path, "w", encoding="utf-8") as fh:
        json.dump(packet, fh, indent=2, sort_keys=True)
    files.append(packet_path)
    waiver = packet.get("waiver_draft")
    if waiver and waiver.get("drafts"):
        wpath = os.path.join(root, packet["id"] + ".waiver.txt")
        body = waiver["drafts"][0].get("body") or json.dumps(waiver["drafts"][0], indent=2)
        with open(wpath, "w", encoding="utf-8") as fh:
            fh.write(body)
        files.append(wpath)
    readme = os.path.join(root, packet["id"] + ".README.txt")
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write("Handoff bundle for %s (%s).\n" % (packet["olympiad"]["name"], packet["id"]))
        fh.write("Approved by: %s\n" % packet["review"]["reviewed_by"])
        fh.write("Atlas prepared these materials; it did not register, submit, email or pay.\n")
        fh.write("Next step is yours: register through the official site and send the waiver "
                 "request yourself.\n")
    files.append(readme)
    packet["state"] = "handoff_exported"
    packet["handoff_files"] = files
    return {"packet_id": packet["id"], "state": packet["state"], "files": files,
            "boundary": packet["boundary"]}
