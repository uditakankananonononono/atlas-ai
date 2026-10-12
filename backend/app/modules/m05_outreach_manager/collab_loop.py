"""G113 / m05.collab_loop - approved contact-to-collaboration runtime.

Source request (instinct doc, verbatim): "reach out to people for help,
outreach, designs, collabs, ideas".

What the audit (G113) could not verify: a complete runtime from contact to
collaboration. This unit closes the loop as a real state machine:

  discovered -> researched -> drafted -> pending_approval -> approved
  -> sent -> replied -> negotiating -> collaborating   (+ lost, dormant)

Every transition is validated and recorded. Drafts are generated from
SUPPLIED evidence only - the generator refuses to draft without real
evidence fields, so personalization can never be fabricated. Approval is a
hard gate: only an owner approval token moves a draft to approved, matching
the standing rule that person-facing communications stay owner-gated. The
module never sends: mark_sent records the receipt of an external send done
through the owner's own channel. Reply classification is real keyword
scoring, follow-ups are computed against as_of, and a collaboration brief
closes the loop. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from app.modules.c30 import policy

PREFIX = "REACH"
STATES = ("discovered", "researched", "drafted", "pending_approval", "approved",
          "sent", "replied", "negotiating", "collaborating", "lost", "dormant")
TERMINAL = ("lost",)
EDGES = {
    "discovered": ("researched", "lost"),
    "researched": ("drafted", "lost"),
    "drafted": ("pending_approval", "researched", "lost"),
    "pending_approval": ("approved", "drafted", "lost"),
    "approved": ("sent", "lost"),
    "sent": ("replied", "dormant", "lost"),
    "dormant": ("sent", "lost"),
    "replied": ("negotiating", "lost", "sent"),
    "negotiating": ("collaborating", "lost", "sent"),
    "collaborating": ("lost",),
    "lost": (),
}
ASKS = ("help", "design", "collab", "idea_feedback", "intro")
EVIDENCE_REQUIRED = ("role", "recent_work", "interest")
FOLLOW_UP_DAYS = 5
MAX_TEXT = 300
MAX_MESSAGE = 4000
MAX_CONTACTS = 5000
POSITIVE = ("love", "great", "interested", "yes", "sounds good", "let's", "happy to",
            "excited", "count me in", "awesome", "glad", "thanks")
NEGATIVE = ("no thanks", "not interested", "stop", "unsubscribe", "busy", "pass",
            "don't", "do not", "remove me")
QUESTION = ("?", "how much", "what do you mean", "can you explain", "tell me more")


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _text(value, field, limit=MAX_TEXT):
    if type(value) is not str:
        _refuse("BAD_TYPE", field)
    if len(value) > limit:
        _refuse("TEXT_TOO_LONG", field)
    if not value.strip():
        _refuse("EMPTY", field)
    if any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") and c not in "\n\t"
           for c in value):
        _refuse("CONTROL_CHARS", field)
    return value


def _date(value, field):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        _refuse("BAD_TYPE", field)
    try:
        return date.fromisoformat(value)
    except ValueError:
        _refuse("BAD_TYPE", field)


def create_pipeline():
    return {"contacts": {}, "log": []}


def _contact(pipeline, cid):
    if type(pipeline) is not dict or set(pipeline) - {"contacts", "log"}:
        _refuse("BAD_TYPE", "pipeline")
    c = pipeline["contacts"].get(cid)
    if c is None:
        _refuse("NOT_FOUND", cid)
    return c


def _move(pipeline, c, new_state, as_of, note):
    if new_state not in EDGES[c["state"]]:
        _refuse("BAD_TRANSITION", "%s->%s" % (c["state"], new_state))
    c["state"] = new_state
    entry = {"contact_id": c["id"], "from": c["history"][-1]["to"] if c["history"] else None,
             "to": new_state, "as_of": as_of, "note": note}
    c["history"].append(entry)
    pipeline["log"].append(entry)
    return c


def add_contact(pipeline, cid, name, channel, org, as_of):
    _text(cid, "id", 64)
    if type(pipeline) is not dict or set(pipeline) - {"contacts", "log"}:
        _refuse("BAD_TYPE", "pipeline")
    if cid in pipeline["contacts"]:
        _refuse("DUPLICATE", cid)
    if len(pipeline["contacts"]) >= MAX_CONTACTS:
        _refuse("OVERSIZE", "contacts")
    _date(as_of, "as_of")
    c = {"id": cid, "name": _text(name, "name"), "channel": _text(channel, "channel", 64),
         "org": _text(org, "org", 128), "state": "discovered", "evidence": {},
         "drafts": [], "approval": None, "send_receipt": None, "replies": [],
         "collab": None, "history": [{"to": "discovered", "as_of": as_of, "note": "added"}]}
    pipeline["contacts"][cid] = c
    return c


def research(pipeline, cid, evidence, as_of):
    """Attach supplied evidence; all required fields must be real and non-empty."""
    c = _contact(pipeline, cid)
    _date(as_of, "as_of")
    if type(evidence) is not dict or set(evidence) - set(EVIDENCE_REQUIRED) - {"links", "notes"}:
        _refuse("UNKNOWN", "evidence")
    for field in EVIDENCE_REQUIRED:
        _text(evidence.get(field), "evidence." + field)
    c["evidence"] = {k: _text(v, "evidence." + k, 500) for k, v in evidence.items()
                     if isinstance(v, str)}
    if evidence.get("links") is not None:
        links = evidence["links"]
        if type(links) is not list or len(links) > 10:
            _refuse("BAD_TYPE", "evidence.links")
        c["evidence"]["links"] = [_text(u, "evidence.links", 300) for u in links]
    return _move(pipeline, c, "researched", as_of, "evidence attached")


def draft(pipeline, cid, ask, goal, as_of):
    """Generate a real personalized draft from the attached evidence only."""
    c = _contact(pipeline, cid)
    _date(as_of, "as_of")
    if ask not in ASKS:
        _refuse("BAD_TYPE", "ask")
    goal_text = _text(goal, "goal", 500)
    missing = [f for f in EVIDENCE_REQUIRED if not c["evidence"].get(f)]
    if missing:
        _refuse("NO_EVIDENCE", ",".join(missing))  # never fabricate personalization
    ev = c["evidence"]
    ask_line = {
        "help": "I could use your eyes on a hard problem I'm stuck on",
        "design": "I'd love your design critique on something I'm building",
        "collab": "I think there's a real collaboration between what you do and what I'm building",
        "idea_feedback": "I'd value your honest take on an idea before I commit to it",
        "intro": "I'd be grateful for an introduction if someone in your circle fits",
    }[ask]
    body = (
        "Hi {name},\n\n"
        "Your work as {role} caught my attention - specifically {recent}. "
        "Given your interest in {interest}, {ask_line}.\n\n"
        "What I'm working on: {goal}.\n\n"
        "Would a short exchange be welcome? If not, no follow-up barrage - "
        "one note, then I leave you in peace.\n\n"
        "Best,\n{{owner_name}}"
    ).format(name=c["name"].split()[0], role=ev["role"], recent=ev["recent_work"],
             interest=ev["interest"], ask_line=ask_line, goal=goal_text)
    draft_row = {"ask": ask, "goal": goal_text, "body": body, "as_of": as_of,
                 "personalization_sources": sorted(ev.keys())}
    c["drafts"].append(draft_row)
    _move(pipeline, c, "drafted", as_of, "draft generated from supplied evidence")
    return draft_row


def submit_for_approval(pipeline, cid, as_of):
    c = _contact(pipeline, cid)
    _date(as_of, "as_of")
    if not c["drafts"]:
        _refuse("EMPTY", "drafts")
    return _move(pipeline, c, "pending_approval", as_of, "awaiting owner review")


def approve(pipeline, cid, approval_token, as_of):
    """Owner gate: only a supplied owner approval token approves the exact draft."""
    c = _contact(pipeline, cid)
    _date(as_of, "as_of")
    token = _text(approval_token, "approval_token", 200)
    if c["state"] != "pending_approval":
        _refuse("BAD_TRANSITION", "%s->approved" % c["state"])
    c["approval"] = {"token": token, "as_of": as_of,
                     "draft_index": len(c["drafts"]) - 1}
    return _move(pipeline, c, "approved", as_of, "owner approved exact draft")


def mark_sent(pipeline, cid, message_id, as_of):
    """Record the receipt of a send performed externally on the owner's channel."""
    c = _contact(pipeline, cid)
    _date(as_of, "as_of")
    mid = _text(message_id, "message_id", 200)
    if c["approval"] is None:
        _refuse("NOT_APPROVED", cid)  # an unapproved message can never be marked sent
    c["send_receipt"] = {"message_id": mid, "as_of": as_of,
                         "draft_index": c["approval"]["draft_index"]}
    return _move(pipeline, c, "sent", as_of, "external send receipt recorded")


def classify_reply(text):
    """Real keyword scoring; returns positive / negative / question / neutral."""
    low = text.casefold()
    pos = sum(1 for w in POSITIVE if w in low)
    neg = sum(1 for w in NEGATIVE if w in low)
    q = sum(1 for w in QUESTION if w in low)
    if neg > pos:
        return "negative"
    if pos > 0 and q > 0:
        return "question"
    if pos > 0:
        return "positive"
    if q > 0:
        return "question"
    return "neutral"


def record_reply(pipeline, cid, text, as_of):
    c = _contact(pipeline, cid)
    _date(as_of, "as_of")
    body = _text(text, "text", MAX_MESSAGE)
    sentiment = classify_reply(body)
    c["replies"].append({"text": body, "sentiment": sentiment, "as_of": as_of})
    _move(pipeline, c, "replied", as_of, "reply recorded: " + sentiment)
    if sentiment == "negative":
        _move(pipeline, c, "lost", as_of, "negative reply - do not contact again")
    return {"sentiment": sentiment,
            "suggested_next": {"positive": "negotiate", "question": "answer_then_negotiate",
                               "neutral": "one_followup", "negative": "stop"}[sentiment]}


def negotiate(pipeline, cid, as_of, note):
    c = _contact(pipeline, cid)
    _date(as_of, "as_of")
    return _move(pipeline, c, "negotiating", as_of, _text(note, "note", 500))


def start_collaboration(pipeline, cid, details, as_of):
    """Close the loop: a real collaboration brief from supplied details."""
    c = _contact(pipeline, cid)
    _date(as_of, "as_of")
    if type(details) is not dict or set(details) - {"project", "roles", "next_steps", "check_in_days"}:
        _refuse("UNKNOWN", "details")
    project = _text(details.get("project"), "project", 300)
    roles = details.get("roles")
    if type(roles) is not dict or not roles or len(roles) > 10:
        _refuse("BAD_TYPE", "roles")
    clean_roles = {_text(k, "roles.key", 64): _text(v, "roles.value", 300) for k, v in roles.items()}
    steps = details.get("next_steps")
    if type(steps) is not list or not steps or len(steps) > 20:
        _refuse("BAD_TYPE", "next_steps")
    clean_steps = [_text(s, "next_steps", 300) for s in steps]
    check_in = details.get("check_in_days", 7)
    if type(check_in) is not int or not 1 <= check_in <= 90:
        _refuse("BAD_TYPE", "check_in_days")
    c["collab"] = {"project": project, "roles": clean_roles, "next_steps": clean_steps,
                   "check_in_days": check_in, "started": as_of}
    _move(pipeline, c, "collaborating", as_of, "collaboration started: " + project)
    return c["collab"]


def follow_ups_due(pipeline, as_of):
    """Contacts in sent/dormant whose last activity is older than FOLLOW_UP_DAYS."""
    today = _date(as_of, "as_of")
    due = []
    for c in pipeline["contacts"].values():
        if c["state"] not in ("sent", "dormant"):
            continue
        last = c["history"][-1]["as_of"]
        age = (today - date.fromisoformat(last)).days
        if age >= FOLLOW_UP_DAYS:
            due.append({"contact_id": c["id"], "state": c["state"],
                        "days_since_touch": age,
                        "action": "send_followup" if c["state"] == "sent" else "re_engage"})
    due.sort(key=lambda r: (-r["days_since_touch"], r["contact_id"]))
    return due


def report(pipeline, as_of=None):
    if type(pipeline) is not dict or set(pipeline) - {"contacts", "log"}:
        _refuse("BAD_TYPE", "pipeline")
    counts = {s: 0 for s in STATES}
    for c in pipeline["contacts"].values():
        counts[c["state"]] += 1
    contacts = pipeline["contacts"].values()
    sent = sum(1 for c in contacts if c["send_receipt"])
    replied = sum(1 for c in contacts if c["replies"])
    collab = sum(1 for c in contacts if c["collab"])
    out = {
        "counts": counts, "total": len(pipeline["contacts"]),
        "funnel": {"sent": sent, "replied": replied, "collaborating": collab,
                   "reply_rate": round(replied / sent, 6) if sent else None,
                   "collab_rate": round(collab / replied, 6) if replied else None},
        "transitions": len(pipeline["log"]),
        "scope": policy.scope(
            ["full state machine from discovered to collaborating with validated transitions",
             "drafts generated only from supplied evidence (fabrication refuses)",
             "owner approval gate before any send receipt can be recorded",
             "keyword reply classification, follow-up computation, collaboration briefs"],
            ["sending - the owner's channel sends; this runtime records receipts",
             "approval - the owner's token approves; this runtime verifies its presence",
             "sentiment beyond keyword scoring - labeled keyword scoring"],
            "supplied contacts, evidence and receipts",
            as_of if isinstance(as_of, str) else "supplied-input"),
    }
    if isinstance(as_of, str):
        out["follow_ups_due"] = follow_ups_due(pipeline, as_of)
    return out
