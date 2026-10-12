"""Groups 67/72: opportunity triage + layered application thinking.

Layers: (1) parse deadline/fee/eligibility from opportunity text, (2) match to
owner profile, (3) requirement checklist with gaps, (4) per-field draft via an
injected drafter, (5) critic pass over the draft.

Critic scope (token and sentence level only, not understanding): flags
over-limit drafts, numbers and content words absent from the owner's facts,
and sentences that share content words with an owner fact of opposite polarity
(negated fact vs affirmative claim, or the reverse). It cannot verify truth.
Nothing is submitted. ready_for_owner_review=True only means these checks
found nothing; the owner must still read every field.
"""
from __future__ import annotations
import re
from datetime import date, datetime

DATE_RE = re.compile(r"(?:deadline|due|closes?|by)[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})", re.I)
GRADE_RE = re.compile(r"grades?\s+(\d{1,2})\s*(?:-|to|\u2013)\s*(\d{1,2})", re.I)
AGE_RE = re.compile(r"ages?\s+(\d{1,2})\s*(?:-|to|\u2013)\s*(\d{1,2})", re.I)
KNOWN_CUR = re.compile(r"\b(USD|EUR|GBP|INR|CAD|AUD|SGD|JPY|CHF)\b|(Rs\.?)|([$\u20ac\u00a3\u20b9])", re.I)
FEE_RE = re.compile(r"\b(?:fee|cost)\b((?:[^\d\n.]|Rs\.){0,30}?)(\d[\d,]*(?:\.\d+)?)\s?([A-Za-z]{3}\b|[$\u20ac\u00a3\u20b9])?", re.I)
FREE_RE = re.compile(r"\b(no (?:application |entry |registration )?(?:fee|cost|charge)s?|free (?:to (?:enter|apply)|entry|of charge)|no charge)\b", re.I)
STOPWORDS = frozenset("that this with have from about because which their there would could should while where these those been were being into over also very than then them they what when your more most some such only just like make made much many well the and for was has had are but not never".split())
NEGATIONS = frozenset("not never no none nor without cannot didn't don't doesn't wasn't weren't isn't aren't haven't hasn't hadn't won't wouldn't can't couldn't".split())
SENT_SPLIT = re.compile(r"[.!?;\n]+")


def _date(s):
    s = s.replace(",", "")
    for f in ("%Y-%m-%d", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def parse_fee(text):
    """Returns (fee, currency, status). Collects every fee statement.
    status: free (explicit free language, no charged fee), stated, conflict
    (free language AND a charged fee, or different charged amounts; the first
    charged fee is surfaced), unknown_currency, not_stated. fee is None unless
    a charged fee with a known currency exists or the status is free."""
    free_spans = [m.span() for m in FREE_RE.finditer(text)]
    charged = []  # (amount, currency or None)
    for m in FEE_RE.finditer(text):
        if any(a <= m.start() < b for a, b in free_spans):
            continue  # the word "fee" belongs to a free phrase such as "no fee"
        gap, amt, post = m.group(1), float(m.group(2).replace(",", "")), m.group(3)
        k = KNOWN_CUR.search(gap)
        cur = k.group(0) if k else None
        if cur is None and post and KNOWN_CUR.fullmatch(post):
            cur = post
        charged.append((amt, (cur.upper() if cur and cur.isalpha() else cur)))
    known = [c for c in charged if c[1] is not None]
    if free_spans:
        if not charged:
            return 0.0, None, "free"
        return (known[0][0], known[0][1], "conflict") if known else (None, None, "conflict")
    if not charged:
        return None, None, "not_stated"
    if known:
        if len({c for c in known}) > 1:
            return known[0][0], known[0][1], "conflict"
        return known[0][0], known[0][1], "stated"
    return None, None, "unknown_currency"


def parse_opportunity(text):
    m = DATE_RE.search(text)
    fee, cur, status = parse_fee(text)
    g, a = GRADE_RE.search(text), AGE_RE.search(text)
    return {"deadline": _date(m.group(1)) if m else None,
            "fee": fee, "fee_currency": cur, "fee_status": status,
            "grades": (int(g.group(1)), int(g.group(2))) if g else None,
            "ages": (int(a.group(1)), int(a.group(2))) if a else None,
            "fields": re.findall(r"(?im)^\s*(?:essay|question|prompt)\s*\d*[:.)]\s*(.+?)(?:\((\d+)\s*words?\))?\s*$", text)}


def match(opp, profile, today=None):
    today = today or date.today()
    why = []
    if opp["deadline"] and opp["deadline"] < today:
        why.append("deadline passed")
    for key, rng in (("grade", opp["grades"]), ("age", opp["ages"])):
        if rng and not profile.get(key):
            why.append("%s required but missing from profile (ineligible pending owner)" % key)
        elif rng and not rng[0] <= profile[key] <= rng[1]:
            why.append("%s outside range" % key)
    needs = []
    if opp["fee_status"] == "stated" and opp["fee"]:
        needs.append("fee approval: %.2f %s" % (opp["fee"], opp["fee_currency"]))
    elif opp["fee_status"] == "conflict":
        shown = "%.2f %s" % (opp["fee"], opp["fee_currency"]) if opp["fee"] is not None else "unknown amount"
        needs.append("conflicting fee statements: review (charged fee surfaced: %s)" % shown)
    elif opp["fee_status"] == "unknown_currency":
        needs.append("fee currency unrecognized: review")
    elif opp["fee_status"] == "not_stated":
        needs.append("fee not stated: verify before applying")
    needs += [k for k in ("grade", "age") if (opp["grades"] if k == "grade" else opp["ages"]) and not profile.get(k)]
    return {"eligible": not why, "reasons": why, "needs_owner": needs}


def _content(sentence):
    return {w for w in re.findall(r"[a-z']{3,}", sentence.lower()) if w not in STOPWORDS and w not in NEGATIONS}


def _negated(sentence):
    return any(w in NEGATIONS for w in re.findall(r"[a-z']+", sentence.lower()))


def contradictions(draft, facts):
    """Draft sentences sharing >=2 content words (or all, if fewer) with an owner
    fact sentence of opposite polarity."""
    out = []
    fact_sents = [(s, _content(s), _negated(s)) for f in facts for s in SENT_SPLIT.split(f) if s.strip()]
    for ds in SENT_SPLIT.split(draft):
        if not ds.strip():
            continue
        dc, dn = _content(ds), _negated(ds)
        for fs, fc, fn in fact_sents:
            shared = dc & fc
            if fn != dn and shared and len(shared) >= min(2, len(fc), len(dc)):
                out.append("polarity conflict: %r vs owner fact %r" % (ds.strip(), fs.strip()))
                break
    return out


def prepare(opp, profile, drafter, facts):
    """drafter(question, word_limit, facts)->str. facts: list of owner fact strings."""
    pkg = {"fields": [], "issues": [],
           "checks": ["word limit", "numbers", "claim words", "polarity vs owner facts"]}
    for q, wl in opp["fields"]:
        limit = int(wl) if wl else None
        draft = drafter(q, limit, facts)
        words = len(draft.split())
        issues = []
        if limit and words > limit:
            issues.append("over limit %d>%d" % (words, limit))
        fact_text = " ".join(facts).lower() + " " + q.lower()
        nums = set(re.findall(r"\b\d[\d,.]*\b", draft)) - set(re.findall(r"\b\d[\d,.]*\b", fact_text))
        if nums:
            issues.append("numbers not in owner facts: %s" % sorted(nums))
        fact_words = set(re.findall(r"[a-z]{4,}", fact_text))
        unsupported = sorted({w for w in re.findall(r"[a-z]{4,}", draft.lower())
                              if w not in fact_words and w not in STOPWORDS})
        if unsupported:
            issues.append("claim words not in owner facts: %s" % unsupported)
        issues += contradictions(draft, facts)
        pkg["fields"].append({"question": q, "draft": draft, "words": words, "issues": issues})
        pkg["issues"] += issues
    pkg["ready_for_owner_review"] = not pkg["issues"]
    pkg["submit"] = "never automatic; owner approval required"
    return pkg
