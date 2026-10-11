"""S4.4 journal-and-org-pitch-drafts: draft-and-queue only. Nothing here sends.

Stdlib only, no I/O, no clock, no randomness. Refusals are PitchRefusal (a ValueError). A policy
refusal's message is exactly its APPLY_REFUSED_* code; any other refusal reads "pitch_drafts:<code>".
Messages never contain input text.
"""
from __future__ import annotations

import copy
import hashlib
import json
import unicodedata

UNIT = "pitch_drafts"
SEND = "APPLY_REFUSED_SEND"
BULK = "APPLY_REFUSED_BULK"
NOSOURCE = "APPLY_REFUSED_NOSOURCE"
MAX_PITCH_WORDS = 200
MAX_JOURNAL_WORDS = 1000
MAX_BODY = 5000
MAX_SUBJECT = 300
MAX_QUEUE = 50
MAX_KEYWORDS = 50
MAX_STR = 200
MAX_SUMMARY = 1200
MAX_INT = 10 ** 7
WEIGHTS = (("scope", 3), ("length", 2), ("format", 1), ("sections", 2), ("fee", 1))
TOTAL_WEIGHT = 9
HONESTY = {"semantic_fit_judged": False, "acceptance_predicted": False, "sent": False}
_FORBIDDEN = ("Cc", "Zl", "Zp")
_TEXT_WS = "\n\r\t"
_LEAF = (str, int, bool, type(None))
_DRAFT_KEYS = ("draft_id", "kind", "status", "recipient", "subject", "body", "text_sha256",
               "sent", "target_name")
_FIT_KEYS = ("score", "verdict", "checks", "honesty", "target_name", "source_url", "as_of",
             "manuscript_sha256", "fit_sha256")


class PitchRefusal(ValueError):
    def __init__(self, message):
        super().__init__(message)
        self.code = message


def _err(code):
    return PitchRefusal("%s:%s" % (UNIT, code))


def _policy(code):
    return PitchRefusal(code)


def _bad(value, allow_ws=False):
    for c in value:
        if allow_ws and c in _TEXT_WS:
            continue
        if unicodedata.category(c) in _FORBIDDEN:
            return True
    return False


def _scan(value, field, depth=0, text_keys=()):
    if depth > 6:
        raise _err("too_deep")
    t = type(value)
    if t is dict:
        for k, v in value.items():
            if type(k) is not str:
                raise _err("bad_type:" + field)
            if _bad(k):
                raise _err("control_chars:" + field)
            if type(v) is str and k in text_keys:
                if _bad(v, True):
                    raise _err("control_chars:" + field)
            else:
                _scan(v, field, depth + 1, text_keys)
    elif t is list:
        for v in value:
            _scan(v, field, depth + 1, text_keys)
    elif t is str:
        if _bad(value):
            raise _err("control_chars:" + field)
    elif t not in _LEAF:
        raise _err("bad_type:" + field)


def _keys(d, field, allowed, required):
    if type(d) is not dict:
        raise _err("bad_type:" + field)
    _scan(d, field)
    if any(k not in allowed for k in d):
        raise _err("unknown_field:" + field)
    if any(k not in d for k in required):
        raise _err("missing_field:" + field)


def _str(d, key, field, limit=MAX_STR):
    v = d[key]
    if type(v) is not str:
        raise _err("bad_type:" + field)
    if v == "":
        raise _err("empty:" + field)
    if len(v) > limit:
        raise _err("too_long_field:" + field)
    return v


def _int(d, key, field):
    v = d[key]
    if type(v) is not int:
        raise _err("bad_type:" + field)
    if v < 0 or v > MAX_INT:
        raise _err("range:" + field)
    return v


def _strlist(d, key, field, lo, hi):
    v = d[key]
    if type(v) is not list:
        raise _err("bad_type:" + field)
    if len(v) < lo or len(v) > hi:
        raise _err("list_size:" + field)
    out = []
    for s in v:
        if type(s) is not str:
            raise _err("bad_type:" + field)
        if s == "" or len(s) > MAX_STR:
            raise _err("bad_item:" + field)
        out.append(s.lower())
    return out


def _date_ok(s):
    if len(s) != 10 or s[4] != "-" or s[7] != "-":
        return False
    y, m, d = s[0:4], s[5:7], s[8:10]
    if not (y.isascii() and m.isascii() and d.isascii() and y.isdigit() and m.isdigit() and d.isdigit()):
        return False
    yi, mi, di = int(y), int(m), int(d)
    if mi < 1 or mi > 12 or yi < 1:
        return False
    leap = yi % 4 == 0 and (yi % 100 != 0 or yi % 400 == 0)
    days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[mi - 1]
    return 1 <= di <= days


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _verdict(score, all_pass):
    if all_pass:
        return "FIT_CONDITIONS_MET"
    return "PARTIAL" if score >= 50 else "LOW_FIT"


def _manuscript(m):
    _keys(m, "manuscript", ("title", "words", "keywords", "format", "sections", "max_fee_usd"),
          ("title", "words", "keywords", "format", "sections", "max_fee_usd"))
    return {"title": _str(m, "title", "manuscript"), "words": _int(m, "words", "manuscript"),
            "keywords": _strlist(m, "keywords", "manuscript", 1, MAX_KEYWORDS),
            "format": _str(m, "format", "manuscript").lower(),
            "sections": _strlist(m, "sections", "manuscript", 0, MAX_KEYWORDS),
            "max_fee_usd": _int(m, "max_fee_usd", "manuscript")}


def _manuscript_hash(m):
    return _sha(_canon({"title": m["title"], "words": m["words"], "keywords": sorted(set(m["keywords"])),
                        "format": m["format"], "sections": sorted(set(m["sections"])),
                        "max_fee_usd": m["max_fee_usd"]}))


def score_fit(guidelines, manuscript):
    """Target-fit from supplied public submission guidelines. Computed conditions only."""
    names = ("name", "source_url", "as_of", "scope_keywords", "min_words", "max_words",
             "accepted_formats", "required_sections", "fee_usd")
    _keys(guidelines, "guidelines", names, names)
    gname = _str(guidelines, "name", "guidelines")
    url = _str(guidelines, "source_url", "guidelines")
    as_of = _str(guidelines, "as_of", "guidelines")
    if not url.startswith("https://") or len(url) <= 8 or " " in url:
        raise _policy(NOSOURCE)
    if not _date_ok(as_of):
        raise _policy(NOSOURCE)
    gk = set(_strlist(guidelines, "scope_keywords", "guidelines", 1, MAX_KEYWORDS))
    lo = _int(guidelines, "min_words", "guidelines")
    hi = _int(guidelines, "max_words", "guidelines")
    if lo > hi:
        raise _err("range:guidelines")
    fmts = _strlist(guidelines, "accepted_formats", "guidelines", 1, MAX_KEYWORDS)
    req = _strlist(guidelines, "required_sections", "guidelines", 0, MAX_KEYWORDS)
    fee = _int(guidelines, "fee_usd", "guidelines")
    m = _manuscript(manuscript)
    mk = set(m["keywords"])
    overlap = len(gk & mk)
    passes = {
        "scope": overlap > 0 and overlap >= min(2, len(mk)),
        "length": lo <= m["words"] <= hi,
        "format": m["format"] in fmts,
        "sections": all(r in m["sections"] for r in req),
        "fee": fee <= m["max_fee_usd"],
    }
    checks = []
    points = 0
    for name, weight in WEIGHTS:
        c = {"name": name, "passed": passes[name], "weight": weight}
        if name == "scope":
            c["overlap"] = overlap
        if passes[name]:
            points += weight
        checks.append(c)
    score = points * 100 // TOTAL_WEIGHT
    body = {"score": score, "verdict": _verdict(score, points == TOTAL_WEIGHT), "checks": checks,
            "target_name": gname, "source_url": url, "as_of": as_of,
            "manuscript_sha256": _manuscript_hash(m)}
    out = dict(body)
    out["honesty"] = dict(HONESTY)
    out["fit_sha256"] = _sha(_canon(body))
    return out


def _check_fit(fit, m):
    _keys(fit, "fit", _FIT_KEYS, _FIT_KEYS)
    body = {k: fit[k] for k in _FIT_KEYS if k not in ("honesty", "fit_sha256")}
    if fit["honesty"] != HONESTY or fit["fit_sha256"] != _sha(_canon(body)):
        raise _err("fit_mismatch")
    if fit["manuscript_sha256"] != _manuscript_hash(m):
        raise _err("fit_mismatch")
    checks = fit["checks"]
    if type(checks) is not list or len(checks) != len(WEIGHTS):
        raise _err("fit_mismatch")
    points = 0
    for c, (name, weight) in zip(checks, WEIGHTS):
        if type(c) is not dict or c.get("name") != name or c.get("weight") != weight \
                or type(c.get("passed")) is not bool:
            raise _err("fit_mismatch")
        if c["passed"]:
            points += weight
    score = points * 100 // TOTAL_WEIGHT
    if fit["score"] != score or fit["verdict"] != _verdict(score, points == TOTAL_WEIGHT):
        raise _err("fit_mismatch")


def _recipient(addr):
    if "," in addr or ";" in addr:
        raise _policy(BULK)
    if len(addr) > 254 or addr.count("@") != 1 or " " in addr:
        raise _err("bad_recipient")
    local, domain = addr.split("@")
    if local == "" or "." not in domain or domain.startswith(".") or domain.endswith(".") \
            or ".." in domain:
        raise _err("bad_recipient")


def _target(t):
    _keys(t, "target", ("name", "recipient"), ("name", "recipient"))
    name = _str(t, "name", "target")
    rcpt = _str(t, "recipient", "target")
    _recipient(rcpt)
    return name, rcpt


def _author(a, journal):
    allowed = ("name", "summary") + (("not_under_review_elsewhere",) if journal else ())
    _keys(a, "author", allowed, ("name", "summary"))
    flag = a.get("not_under_review_elsewhere", False)
    if type(flag) is not bool:
        raise _err("bad_type:author")
    return _str(a, "name", "author"), _str(a, "summary", "author", MAX_SUMMARY), flag


def _draft(kind, target_name, recipient, subject, body):
    text_sha = _sha(recipient + "\n" + subject + "\n" + body)
    return {"draft_id": text_sha[:16], "kind": kind, "status": "DRAFT", "recipient": recipient,
            "subject": subject, "body": body, "text_sha256": text_sha, "sent": False,
            "target_name": target_name}


def make_journal_draft(target, manuscript, author, fit):
    """Cover-letter draft. Nothing is sent; it still needs queue_add and release."""
    tname, rcpt = _target(target)
    m = _manuscript(manuscript)
    aname, summary, flag = _author(author, True)
    _check_fit(fit, m)
    if fit["target_name"] != tname:
        raise _err("fit_mismatch")
    if fit["verdict"] == "LOW_FIT":
        raise _err("low_fit")
    tail = " This manuscript is not under review elsewhere." if flag else ""
    body = ("Dear Editor,\n\nI would like to submit the manuscript \"%s\" (%d words, %s) "
            "for consideration in %s.\n\n%s%s\n\nSincerely,\n%s"
            % (m["title"], m["words"], m["format"], tname, summary, tail, aname))
    return _draft("journal", tname, rcpt, "Submission enquiry: " + m["title"], body)


def make_org_pitch_draft(target, author, ask):
    """Short pitch draft to an organisation at an owner-supplied recipient."""
    tname, rcpt = _target(target)
    aname, summary, _flag = _author(author, False)
    if type(ask) is not str:
        raise _err("bad_type:ask")
    if _bad(ask):
        raise _err("control_chars:ask")
    if ask == "" or len(ask) > MAX_STR:
        raise _err("too_long_field:ask")
    body = ("Dear %s team,\n\nMy name is %s. %s\n\nI would like to ask for %s.\n\n"
            "Thank you for your time.\n\n%s" % (tname, aname, summary, ask, aname))
    if len(body.split()) > MAX_PITCH_WORDS:
        raise _err("too_long")
    return _draft("org_pitch", tname, rcpt, "Enquiry from " + aname, body)


_QUEUED = ("QUEUED", "APPROVED_FOR_MANUAL_SEND")
_STR_FIELDS = ("draft_id", "kind", "status", "recipient", "subject", "body", "text_sha256",
               "target_name")


def _check_draft(d, statuses):
    """One complete validation for a draft, whether it came from a builder or from a caller."""
    if type(d) is not dict:
        raise _err("bad_type:queue")
    _scan(d, "queue", 0, ("body",))
    if sorted(d) != sorted(_DRAFT_KEYS):
        raise _err("bad_draft")
    for k in _STR_FIELDS:
        if type(d[k]) is not str:
            raise _err("bad_type:draft")
    if d["sent"] is not False or d["kind"] not in ("journal", "org_pitch") \
            or d["status"] not in statuses:
        raise _err("bad_draft")
    _recipient(d["recipient"])
    if len(d["recipient"]) > MAX_STR or not 0 < len(d["subject"]) <= MAX_SUBJECT \
            or not 0 < len(d["target_name"]) <= MAX_STR or not 0 < len(d["body"]) <= MAX_BODY:
        raise _err("bad_draft")
    cap = MAX_PITCH_WORDS if d["kind"] == "org_pitch" else MAX_JOURNAL_WORDS
    if len(d["body"].split()) > cap:
        raise _err("bad_draft")
    text_sha = _sha(d["recipient"] + "\n" + d["subject"] + "\n" + d["body"])
    if d["text_sha256"] != text_sha or d["draft_id"] != text_sha[:16]:
        raise _err("bad_draft")


def _queue(q):
    if type(q) is not list:
        raise _err("bad_type:queue")
    if len(q) > MAX_QUEUE:
        raise _err("queue_full")
    for d in q:
        _check_draft(d, _QUEUED)
    if len({d["draft_id"] for d in q}) != len(q):
        raise _err("bad_draft")


def queue_add(queue, draft):
    _queue(queue)
    _check_draft(draft, ("DRAFT",))
    if any(x["draft_id"] == draft["draft_id"] for x in queue):
        raise _err("duplicate")
    if len(queue) >= MAX_QUEUE:
        raise _err("queue_full")
    item = copy.deepcopy(draft)
    item["status"] = "QUEUED"
    return copy.deepcopy(queue) + [item]


def release(queue, approval):
    """Release one queued draft as a packet for the owner to send by hand. Never sends."""
    _queue(queue)
    if type(approval) is not dict or not approval:
        raise _policy(SEND)
    names = ("draft_id", "recipient", "text_sha256", "approved_by")
    _keys(approval, "approval", names, names)
    for n in names:
        if type(approval[n]) is not str:
            raise _err("bad_type:approval")
    if approval["approved_by"] != "owner":
        raise _policy(SEND)
    hit = None
    for i, x in enumerate(queue):
        if x["draft_id"] == approval["draft_id"]:
            hit = i
    if hit is None:
        raise _policy(SEND)
    item = queue[hit]
    if item["status"] != "QUEUED" or approval["recipient"] != item["recipient"] \
            or approval["text_sha256"] != item["text_sha256"]:
        raise _policy(SEND)
    out = copy.deepcopy(queue)
    out[hit]["status"] = "APPROVED_FOR_MANUAL_SEND"
    packet = {"draft_id": item["draft_id"], "kind": item["kind"], "recipient": item["recipient"],
              "subject": item["subject"], "body": item["body"], "text_sha256": item["text_sha256"],
              "sent": False, "send_instruction": "OWNER_SENDS_MANUALLY"}
    return out, packet
