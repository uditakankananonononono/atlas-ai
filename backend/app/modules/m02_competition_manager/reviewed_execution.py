"""Reviewed-execution gate for APP-PLANNER drafts: local, append-only, auditable.

Wires the landed site_application_planner draft descriptor into an explicit
human-review gate. A review record binds the exact site_url + snapshot_sha256 +
draft_sha256 of one 'draft_ready_for_review' plan; a human decision is appended
by the caller; an execution permit is issued only for an approved review whose
hashes still match the presented plan exactly, inside its validity window, and
at most once. The draft digest is recomputed from draft_values on entry, so a
tampered draft cannot ride on a stale self-declared hash; the snapshot hash is
taken on trust (the HTML is not available here). The module performs no
execution itself: no live research, no form fill or submission, no external
calls, no account use. The permit is a local record that the gate was passed -
it authorizes nothing by itself.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone

MAX_RECORDS = 512
MAX_TEXT = 256
MAX_VALID_HOURS = 720
MAX_SERIALIZED = 1_000_000

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVIEW_ID = re.compile(r"^[A-Za-z0-9._/-]{1,64}$")
_DECISIONS = ("approved", "rejected")
_OPEN_KEYS = {"kind", "review_id", "site_url", "snapshot_sha256", "draft_sha256",
              "opened_by", "opened_at", "valid_hours"}
_DECISION_KEYS = {"kind", "review_id", "decision", "reviewer", "rationale", "decided_at"}
_PERMIT_KEYS = {"kind", "review_id", "permit_id", "issued_at", "site_url",
                "snapshot_sha256", "draft_sha256"}

BOUNDARY = ("Local review gate only: records a human decision for one exact draft and refuses "
            "stale, mismatched, undecided or repeated permits. It executes nothing, submits nothing, "
            "and is not authorization for any external action.")
LIMITS = [
    "Reviewer identity is a caller-supplied label, not authentication; the module cannot know who decided.",
    "The ledger is tamper-evident (hash-chained), not tamper-proof; safe storage of the serialized ledger is the caller's job.",
    "snapshot_sha256 is taken on trust: the HTML is not available here, so only the draft digest is recomputed from draft_values; a changed live form behind an old snapshot is not detected.",
    "No execution is performed or wired: browser, m00 approval and m13 submission flows remain separate integrations.",
]


def _fail(message):
    raise ValueError("APPREX: " + message)


def _text(value, name):
    if type(value) is not str or not value.strip():
        _fail(f"{name} must be non-blank text")
    if len(value) > MAX_TEXT:
        _fail(f"{name} exceeds {MAX_TEXT} characters")
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in value):
        _fail(f"{name} contains a disallowed character (Cc, Cf, Zl or Zp)")
    return value


def _when(value, name):
    if type(value) is not str:
        _fail(f"{name} must be timezone-aware ISO text")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail(f"{name} must be timezone-aware ISO text")
    if d.tzinfo is None or d.utcoffset() is None:
        _fail(f"{name} must be timezone-aware ISO text")
    return d.astimezone(timezone.utc)


def _iso(d):
    return d.isoformat()


def _hash256(value, name):
    if type(value) is not str or not _SHA256.fullmatch(value):
        _fail(f"{name} must be 64 lowercase hex characters")
    return value


def _hash_record(seq, record, prev_hash):
    payload = json.dumps({"seq": seq, "record": record, "prev_hash": prev_hash},
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _review_id(value):
    if type(value) is not str or not _REVIEW_ID.fullmatch(value):
        _fail("review_id must be 1-64 characters of A-Za-z0-9._/-")
    return value


def _valid_hours(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= MAX_VALID_HOURS:
        _fail(f"valid_hours must be a finite number in (0, {MAX_VALID_HOURS}]")
    return value


def _deadline(opened_at, valid_hours, review_id):
    try:
        return opened_at + timedelta(hours=valid_hours)
    except OverflowError:
        _fail(f"review {review_id!r} valid_hours overflows the clock")


def _check_plan(plan):
    if type(plan) is not dict:
        _fail("plan must be the exact dict returned by plan_application")
    if plan.get("status") != "draft_ready_for_review":
        _fail("only a draft_ready_for_review plan can enter review")
    if plan.get("submission_enabled") is not False or plan.get("browser_action_performed") is not False:
        _fail("plan flags indicate execution; refusing to review")
    handoff = plan.get("handoff")
    if type(handoff) is not dict or handoff.get("requires_exact_review") is not True:
        _fail("plan handoff must require exact review")
    site_url = _text(plan.get("site_url"), "plan site_url")
    for key in ("snapshot_sha256", "draft_sha256"):
        _hash256(plan.get(key), f"plan {key}")
        if handoff.get(key) != plan[key]:
            _fail(f"plan handoff {key} does not match the plan")
    draft_values = plan.get("draft_values")
    if type(draft_values) is not dict or any(type(k) is not str or type(v) is not str
                                             for k, v in draft_values.items()):
        _fail("plan draft_values must be an exact dict of strings")
    recomputed = hashlib.sha256(json.dumps(draft_values, sort_keys=True).encode()).hexdigest()
    if recomputed != plan["draft_sha256"]:
        _fail("plan draft_sha256 does not match draft_values")
    return site_url, plan["snapshot_sha256"], plan["draft_sha256"]


def _check_fields(seq, record, keys, specs):
    if set(record) != keys:
        _fail(f"ledger entry {seq} has an unexpected record shape")
    for name, check in specs:
        try:
            check(record[name])
        except ValueError as e:
            _fail(f"ledger entry {seq} has invalid content: {e}")


def _check_ledger(ledger):
    """Structural, chain, per-kind, and per-review order validation. Returns the ledger."""
    if type(ledger) is not list or len(ledger) > MAX_RECORDS:
        _fail(f"ledger must be a list of at most {MAX_RECORDS} records")
    prev_hash = "0" * 64
    reviews = {}
    for seq, entry in enumerate(ledger):
        if type(entry) is not dict or set(entry) != {"seq", "record", "prev_hash", "record_hash"}:
            _fail(f"ledger entry {seq} has an unexpected shape")
        if type(entry["record"]) is not dict:
            _fail(f"ledger entry {seq} has an unknown record kind")
        record = entry["record"]
        kind = record.get("kind")
        if kind == "review_opened":
            _check_fields(seq, record, _OPEN_KEYS, [
                ("review_id", _review_id), ("site_url", lambda v: _text(v, "site_url")),
                ("snapshot_sha256", lambda v: _hash256(v, "snapshot_sha256")),
                ("draft_sha256", lambda v: _hash256(v, "draft_sha256")),
                ("opened_by", lambda v: _text(v, "opened_by")),
                ("opened_at", lambda v: _when(v, "opened_at")),
                ("valid_hours", _valid_hours)])
        elif kind == "review_decision":
            _check_fields(seq, record, _DECISION_KEYS, [
                ("review_id", _review_id),
                ("decision", lambda v: v if v in _DECISIONS else _fail("decision must be 'approved' or 'rejected'")),
                ("reviewer", lambda v: _text(v, "reviewer")),
                ("rationale", lambda v: _text(v, "rationale")),
                ("decided_at", lambda v: _when(v, "decided_at"))])
        elif kind == "execution_permit":
            _check_fields(seq, record, _PERMIT_KEYS, [
                ("review_id", _review_id), ("permit_id", lambda v: _text(v, "permit_id")),
                ("issued_at", lambda v: _when(v, "issued_at")),
                ("site_url", lambda v: _text(v, "site_url")),
                ("snapshot_sha256", lambda v: _hash256(v, "snapshot_sha256")),
                ("draft_sha256", lambda v: _hash256(v, "draft_sha256"))])
            if record["permit_id"] != f"PERMIT-{record['review_id']}":
                _fail(f"ledger entry {seq} permit_id does not match the review")
        else:
            _fail(f"ledger entry {seq} has an unknown record kind")
        if entry["seq"] != seq or entry["prev_hash"] != prev_hash:
            _fail(f"ledger entry {seq} breaks the sequence chain")
        if entry["record_hash"] != _hash_record(seq, record, prev_hash):
            _fail(f"ledger entry {seq} fails the integrity check")
        prev_hash = entry["record_hash"]
        rid = record["review_id"]
        state = reviews.get(rid)
        if kind == "review_opened":
            if state is not None:
                _fail(f"ledger entry {seq} reopens review {rid!r}")
            reviews[rid] = {"opened": record, "decision": None, "permit": None}
        elif kind == "review_decision":
            if state is None:
                _fail(f"ledger entry {seq} decides unopened review {rid!r}")
            if state["decision"] is not None:
                _fail(f"ledger entry {seq} has a second decision for review {rid!r}")
            if state["permit"] is not None:
                _fail(f"ledger entry {seq} decides review {rid!r} after its permit")
            if _when(record["decided_at"], "decided_at") < _when(state["opened"]["opened_at"], "opened_at"):
                _fail(f"ledger entry {seq} decision is before the review opened")
            state["decision"] = record
        else:
            if state is None:
                _fail(f"ledger entry {seq} permits unopened review {rid!r}")
            if state["decision"] is None:
                _fail(f"ledger entry {seq} permits review {rid!r} before its decision")
            if state["decision"]["decision"] != "approved":
                _fail(f"ledger entry {seq} permits rejected review {rid!r}")
            if state["permit"] is not None:
                _fail(f"ledger entry {seq} has a second permit for review {rid!r}")
            opened = state["opened"]
            if (record["site_url"] != opened["site_url"] or record["snapshot_sha256"] != opened["snapshot_sha256"]
                    or record["draft_sha256"] != opened["draft_sha256"]):
                _fail(f"ledger entry {seq} permit does not match the opened review")
            issued = _when(record["issued_at"], "issued_at")
            if issued < _when(state["decision"]["decided_at"], "decided_at"):
                _fail(f"ledger entry {seq} permit is before the decision")
            deadline = _deadline(_when(opened["opened_at"], "opened_at"), opened["valid_hours"], rid)
            if issued > deadline:
                _fail(f"ledger entry {seq} permit is outside the review validity window")
            state["permit"] = record
    return ledger


def _find_open(ledger, review_id):
    state = {}
    for entry in ledger:
        r = entry["record"]
        if r["review_id"] != review_id:
            continue
        if r["kind"] == "review_opened":
            state["opened"] = r
        elif r["kind"] == "review_decision":
            state["decision"] = r
        else:
            state["permit"] = r
    return state.get("opened"), state.get("decision"), state.get("permit")


def _append(ledger, record):
    if len(ledger) >= MAX_RECORDS:
        _fail(f"ledger exceeds {MAX_RECORDS} records")
    seq = len(ledger)
    prev_hash = ledger[-1]["record_hash"] if ledger else "0" * 64
    return ledger + [{"seq": seq, "record": record, "prev_hash": prev_hash,
                      "record_hash": _hash_record(seq, record, prev_hash)}]


def open_review(plan, *, review_id, reviewer, now, valid_hours=24, ledger=None):
    """Open a review for one exact draft plan. Returns the extended ledger (new list)."""
    review_id = _review_id(review_id)
    reviewer = _text(reviewer, "reviewer")
    opened_at = _when(now, "now")
    hours = _valid_hours(valid_hours)
    _deadline(opened_at, hours, review_id)
    site_url, snapshot, digest = _check_plan(plan)
    if ledger is None:
        ledger = []
    _check_ledger(ledger)
    if _find_open(ledger, review_id)[0] is not None:
        _fail(f"review {review_id!r} is already open")
    record = {"kind": "review_opened", "review_id": review_id, "site_url": site_url,
              "snapshot_sha256": snapshot, "draft_sha256": digest, "opened_by": reviewer,
              "opened_at": _iso(opened_at), "valid_hours": hours}
    return _append(ledger, record)


def record_decision(ledger, *, review_id, decision, reviewer, rationale, now):
    """Append the human decision for an open review. One decision per review, final."""
    _check_ledger(ledger)
    review_id = _review_id(review_id)
    if decision not in _DECISIONS:
        _fail("decision must be 'approved' or 'rejected'")
    reviewer = _text(reviewer, "reviewer")
    rationale = _text(rationale, "rationale")
    decided_at = _when(now, "now")
    opened, decided, _permit = _find_open(ledger, review_id)
    if opened is None:
        _fail(f"review {review_id!r} is not open")
    if decided is not None:
        _fail(f"review {review_id!r} already has a decision")
    if decided_at < _when(opened["opened_at"], "opened_at"):
        _fail(f"review {review_id!r} decision is before it opened")
    record = {"kind": "review_decision", "review_id": review_id, "decision": decision,
              "reviewer": reviewer, "rationale": rationale, "decided_at": _iso(decided_at)}
    return _append(ledger, record)


def issue_permit(ledger, plan, *, review_id, now):
    """Issue the single-use execution permit for an approved, unexpired, hash-exact review."""
    _check_ledger(ledger)
    review_id = _review_id(review_id)
    issued_at = _when(now, "now")
    site_url, snapshot, digest = _check_plan(plan)
    opened, decided, permit = _find_open(ledger, review_id)
    if opened is None:
        _fail(f"review {review_id!r} is not open")
    if decided is None:
        _fail(f"review {review_id!r} has no decision")
    if decided["decision"] != "approved":
        _fail(f"review {review_id!r} was rejected")
    if permit is not None:
        _fail(f"review {review_id!r} already has an execution permit")
    if opened["site_url"] != site_url or opened["snapshot_sha256"] != snapshot or opened["draft_sha256"] != digest:
        _fail("plan does not match the reviewed draft hashes")
    if issued_at < _when(decided["decided_at"], "decided_at"):
        _fail(f"review {review_id!r} permit is before the decision")
    deadline = _deadline(_when(opened["opened_at"], "opened_at"), opened["valid_hours"], review_id)
    if issued_at > deadline:
        _fail(f"review {review_id!r} validity window has expired")
    record = {"kind": "execution_permit", "review_id": review_id,
              "permit_id": f"PERMIT-{review_id}", "issued_at": _iso(issued_at),
              "site_url": site_url, "snapshot_sha256": snapshot, "draft_sha256": digest}
    new_ledger = _append(ledger, record)
    return new_ledger, {"permit_id": record["permit_id"], "review_id": review_id,
                        "site_url": site_url, "snapshot_sha256": snapshot, "draft_sha256": digest,
                        "approved_by": decided["reviewer"], "decided_at": decided["decided_at"],
                        "issued_at": record["issued_at"], "executes": False, "boundary": BOUNDARY}


def audit_state(ledger, review_id):
    """Current gate state for one review: open, approved, rejected, or permit_issued."""
    _check_ledger(ledger)
    opened, decided, permit = _find_open(ledger, _review_id(review_id))
    if opened is None:
        _fail(f"review {review_id!r} is not open")
    if permit is not None:
        return "permit_issued"
    if decided is not None:
        return decided["decision"]
    return "open"


def dumps(ledger):
    """Serialize the ledger for caller-side persistence (canonical JSON)."""
    if type(ledger) is not list:
        _fail("ledger must be a list of records")
    return json.dumps(ledger, sort_keys=True, separators=(",", ":"))


def loads(text):
    """Parse a serialized ledger, verifying the chain, record content, and review order."""
    if type(text) is not str or len(text) > MAX_SERIALIZED:
        _fail(f"serialized ledger must be text at most {MAX_SERIALIZED} characters")
    try:
        ledger = json.loads(text)
    except ValueError:
        _fail("serialized ledger is not valid JSON")
    return [dict(entry, record=dict(entry["record"])) for entry in _check_ledger(ledger)]
