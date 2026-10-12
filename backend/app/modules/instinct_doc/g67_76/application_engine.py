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
FEE_RE = re.compile(r"(?:fee|cost)[^\d$]{0,20}(?:USD|\$|INR|Rs\.?)\s?(\d+(?:\.\d+)?)", re.I)
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
    fee = FEE_RE.search(text)
    g, a = GRADE_RE.search(text), AGE_RE.search(text)
    return {"deadline": _date(m.group(1)) if m else None,
            "fee": float(fee.group(1)) if fee else 0.0,
            "grades": (int(g.group(1)), int(g.group(2))) if g else None,
            "ages": (int(a.group(1)), int(a.group(2))) if a else None,
            "fields": re.findall(r"(?im)^\s*(?:essay|question|prompt)\s*\d*[:.)]\s*(.+?)(?:\((\d+)\s*words?\))?\s*$", text)}


def match(opp, profile, today=None):
    today = today or date.today()
    why = []
    if opp["deadline"] and opp["deadline"] < today:
        why.append("deadline passed")
    if opp["grades"] and profile.get("grade") and not opp["grades"][0] <= profile["grade"] <= opp["grades"][1]:
        why.append("grade outside range")
    if opp["ages"] and profile.get("age") and not opp["ages"][0] <= profile["age"] <= opp["ages"][1]:
        why.append("age outside range")
    return {"eligible": not why, "reasons": why,
            "needs_owner": (["fee approval: %.2f" % opp["fee"]] if opp["fee"] else []) +
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
        nums = set(re.findall(r"\b\d[\d,.]*\b", draft)) - set(re.findall(r"\b\d[\d,.]*\b", " ".join(facts)))
        if nums:
            issues.append("numbers not in owner facts: %s" % sorted(nums))
        pkg["fields"].append({"question": q, "draft": draft, "words": words, "issues": issues})
        pkg["issues"] += issues
    pkg["ready_for_owner_review"] = not pkg["issues"]
    pkg["submit"] = "never automatic; owner approval required"
    return pkg
