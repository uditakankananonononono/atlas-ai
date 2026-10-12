"""Groups 67/72: opportunity triage + layered application thinking.

Layers: (1) parse deadline/fee/eligibility from opportunity text, (2) match to
owner profile, (3) requirement checklist with gaps, (4) per-field draft via an
injected drafter, (5) critic pass checking word limits and unsupported claims
against owner facts. Nothing is submitted; output is a review package and the
fields that need the owner (fees, missing facts) are flagged.
"""
from __future__ import annotations
import re
from datetime import date, datetime

DATE_RE = re.compile(r"(?:deadline|due|closes?|by)[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})", re.I)
CUR = r"(USD|EUR|GBP|INR|CAD|AUD|SGD|JPY|CHF|Rs\.?|[$\u20ac\u00a3\u20b9])"
FEE_RE = re.compile(r"(?:fee|cost)[^\d\n]{0,30}?" + CUR + r"\s?(\d[\d,]*(?:\.\d+)?)", re.I)
FEE_RE2 = re.compile(r"(?:fee|cost)[^\d\n]{0,30}?(\d[\d,]*(?:\.\d+)?)\s?" + CUR, re.I)
STOPWORDS = frozenset("that this with have from about because which their there would could should while where these those been were being into over also very than then them they what when your more most some such only just like make made much many well".split())
GRADE_RE = re.compile(r"grades?\s+(\d{1,2})\s*(?:-|to|–)\s*(\d{1,2})", re.I)
AGE_RE = re.compile(r"ages?\s+(\d{1,2})\s*(?:-|to|–)\s*(\d{1,2})", re.I)


def _date(s):
    s = s.replace(",", "")
    for f in ("%Y-%m-%d", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def parse_opportunity(text):
    m = DATE_RE.search(text)
    f1, f2 = FEE_RE.search(text), FEE_RE2.search(text)
    fee_amt, fee_cur = 0.0, None
    if f1:
        fee_cur, fee_amt = f1.group(1), float(f1.group(2).replace(",", ""))
    elif f2:
        fee_cur, fee_amt = f2.group(2), float(f2.group(1).replace(",", ""))
    g, a = GRADE_RE.search(text), AGE_RE.search(text)
    return {"deadline": _date(m.group(1)) if m else None,
            "fee": fee_amt, "fee_currency": fee_cur,
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
    return {"eligible": not why, "reasons": why,
            "needs_owner": (["fee approval: %.2f %s" % (opp["fee"], opp.get("fee_currency") or "")] if opp["fee"] else []) +
                           [k for k in ("grade", "age") if (opp["grades"] if k == "grade" else opp["ages"]) and not profile.get(k)]}


def prepare(opp, profile, drafter, facts):
    """drafter(question, word_limit, facts)->str. facts: list of owner fact strings."""
    pkg = {"fields": [], "issues": []}
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
        pkg["fields"].append({"question": q, "draft": draft, "words": words, "issues": issues})
        pkg["issues"] += issues
    pkg["ready_for_owner_review"] = not pkg["issues"]
    pkg["submit"] = "never automatic; owner approval required"
    return pkg
