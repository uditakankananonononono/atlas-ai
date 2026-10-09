"""Prototype builder: turns a generated idea into a runnable, self-tested artifact.

For each supported lever this writes a stdlib-only Python component and its
unittest file into a directory, then RUNS the tests in a subprocess and returns
the real exit code and counts. It makes no network calls and never contacts a
brand. Supported levers: provenance, scarcity_access, ownership_care,
personalization. Other levers return an explicit unsupported entry, not a stub.
Limit: these are working reference components with synthetic fixtures, not a
production integration with any brand's systems.
"""
from __future__ import annotations
import re, subprocess, sys, textwrap
from pathlib import Path

COMPONENTS: dict[str, tuple[str, str]] = {}

COMPONENTS["provenance"] = ('''
"""Hash-chained item history: each record commits to the previous one."""
import hashlib, json

def _h(prev, body):
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True)).encode()).hexdigest()

class Passport:
    def __init__(self, item_id):
        self.item_id, self.records = item_id, []
    def add(self, event, actor, detail):
        if not event or not actor: raise ValueError("event and actor required")
        prev = self.records[-1]["hash"] if self.records else "genesis:" + self.item_id
        body = {"event": event, "actor": actor, "detail": detail, "seq": len(self.records)}
        self.records.append({**body, "hash": _h(prev, body)})
    def verify(self):
        prev = "genesis:" + self.item_id
        for i, r in enumerate(self.records):
            body = {k: r[k] for k in ("event", "actor", "detail", "seq")}
            if r["seq"] != i or r["hash"] != _h(prev, body): return False, i
            prev = r["hash"]
        return True, None
''', '''
import unittest
from provenance import Passport

class T(unittest.TestCase):
    def mk(self):
        p = Passport("A1"); p.add("crafted", "atelier", "hand finished"); p.add("sold", "boutique", "order 7"); return p
    def test_valid_chain(self): self.assertEqual(self.mk().verify(), (True, None))
    def test_tamper_detected_at_index(self):
        p = self.mk(); p.records[0]["detail"] = "forged"; self.assertEqual(p.verify(), (False, 0))
    def test_reorder_detected(self):
        p = self.mk(); p.records.reverse(); self.assertFalse(p.verify()[0])
    def test_truncated_tail_still_valid_but_shorter(self):
        p = self.mk(); p.records.pop(); self.assertEqual(p.verify(), (True, None)); self.assertEqual(len(p.records), 1)
    def test_rejects_blank(self):
        with self.assertRaises(ValueError): Passport("x").add("", "a", "d")
if __name__ == "__main__": unittest.main()
''')

COMPONENTS["scarcity_access"] = ('''
"""Auditable fair allocation: a published seed makes the draw reproducible."""
import hashlib

def _rank(seed, applicant):
    return hashlib.sha256((seed + "|" + applicant).encode()).hexdigest()

def allocate(applicants, slots, seed, priority=None):
    """Return (winners, waitlist, audit). priority maps applicant -> tier (lower first); ties broken by seeded rank."""
    if slots < 0: raise ValueError("slots must be >= 0")
    ids = list(applicants)
    if len(set(ids)) != len(ids): raise ValueError("duplicate applicant")
    pr = priority or {}
    order = sorted(ids, key=lambda a: (pr.get(a, 0), _rank(seed, a)))
    audit = [{"applicant": a, "tier": pr.get(a, 0), "rank": _rank(seed, a)} for a in order]
    return order[:slots], order[slots:], audit

def verify(winners, waitlist, audit, seed):
    order = [r["applicant"] for r in audit]
    return order == winners + waitlist and all(r["rank"] == _rank(seed, r["applicant"]) for r in audit) \\
        and order == sorted(order, key=lambda a: (next(r["tier"] for r in audit if r["applicant"] == a), _rank(seed, a)))
''', '''
import unittest
from scarcity_access import allocate, verify

class T(unittest.TestCase):
    def test_reproducible(self):
        a = allocate(["a","b","c","d"], 2, "s1"); self.assertEqual(a, allocate(["a","b","c","d"], 2, "s1"))
    def test_seed_changes_outcome_somewhere(self):
        outs = {tuple(allocate(list("abcdefgh"), 3, f"seed{i}")[0]) for i in range(20)}; self.assertGreater(len(outs), 1)
    def test_priority_tier_wins(self):
        w, _, _ = allocate(["a","b","c"], 1, "s", priority={"c": -1}); self.assertEqual(w, ["c"])
    def test_audit_verifies_and_detects_swap(self):
        w, l, au = allocate(list("abcde"), 2, "s"); self.assertTrue(verify(w, l, au, "s"))
        self.assertFalse(verify(l[:1] + w[1:], w[:1] + l[1:], au, "s"))
    def test_bad_input(self):
        with self.assertRaises(ValueError): allocate(["a","a"], 1, "s")
        with self.assertRaises(ValueError): allocate(["a"], -1, "s")
    def test_more_slots_than_applicants(self):
        w, l, _ = allocate(["a"], 5, "s"); self.assertEqual((w, l), (["a"], []))
if __name__ == "__main__": unittest.main()
''')

COMPONENTS["ownership_care"] = ('''
"""Service-due planner from an owner's service history and usage."""
from datetime import date, timedelta

def next_service(history, interval_days, interval_units, today, units_per_day=0.0):
    """history: list of {date: date, units: float}. Returns due date, reason, overdue flag."""
    if interval_days <= 0 or interval_units <= 0: raise ValueError("intervals must be positive")
    if not history: return {"due": today, "reason": "no service on record", "overdue": True}
    last = max(history, key=lambda h: h["date"])
    by_time = last["date"] + timedelta(days=interval_days)
    by_use = None
    if units_per_day > 0:
        by_use = last["date"] + timedelta(days=int(interval_units / units_per_day))
    due = min(by_time, by_use) if by_use else by_time
    reason = "usage" if by_use and by_use < by_time else "time"
    return {"due": due, "reason": reason, "overdue": due < today}

def reminders(owners, today, lead_days=14):
    out = []
    for o in owners:
        r = next_service(o["history"], o["interval_days"], o["interval_units"], today, o.get("units_per_day", 0.0))
        if r["overdue"] or (r["due"] - today).days <= lead_days:
            out.append({"owner": o["id"], **r})
    return sorted(out, key=lambda r: r["due"])
''', '''
import unittest
from datetime import date
from ownership_care import next_service, reminders

D = date
class T(unittest.TestCase):
    H = [{"date": D(2026, 1, 1), "units": 100}, {"date": D(2026, 3, 1), "units": 1000}]
    def test_time_based(self):
        r = next_service(self.H, 365, 10000, D(2026, 4, 1)); self.assertEqual((r["due"], r["reason"], r["overdue"]), (D(2027, 3, 1), "time", False))
    def test_usage_can_come_first(self):
        r = next_service(self.H, 365, 1000, D(2026, 4, 1), units_per_day=20); self.assertEqual(r["reason"], "usage"); self.assertEqual(r["due"], D(2026, 4, 20))
    def test_no_history_overdue(self): self.assertTrue(next_service([], 365, 100, D(2026, 1, 1))["overdue"])
    def test_overdue_flag(self): self.assertTrue(next_service(self.H, 30, 100, D(2026, 6, 1))["overdue"])
    def test_reminders_sorted_and_filtered(self):
        owners = [{"id": "far", "history": self.H, "interval_days": 365, "interval_units": 9999},
                  {"id": "soon", "history": self.H, "interval_days": 40, "interval_units": 9999},
                  {"id": "late", "history": self.H, "interval_days": 10, "interval_units": 9999}]
        self.assertEqual([r["owner"] for r in reminders(owners, D(2026, 4, 1))], ["late", "soon"])
    def test_bad_interval(self):
        with self.assertRaises(ValueError): next_service(self.H, 0, 1, D(2026, 1, 1))
if __name__ == "__main__": unittest.main()
''')

COMPONENTS["personalization"] = ('''
"""Consent-gated preference store that explains every recommendation."""

class Prefs:
    def __init__(self): self.data, self.consent, self.log = {}, {}, []
    def grant(self, guest, purpose): self.consent.setdefault(guest, set()).add(purpose); self.log.append(("grant", guest, purpose))
    def revoke(self, guest, purpose):
        self.consent.get(guest, set()).discard(purpose); self.log.append(("revoke", guest, purpose))
        if purpose == "personalization": self.data.pop(guest, None)   # revoking erases stored preferences
    def remember(self, guest, key, value):
        if "personalization" not in self.consent.get(guest, set()): raise PermissionError("no consent to store preferences")
        self.data.setdefault(guest, {})[key] = value
    def recommend(self, guest, catalog):
        """catalog: list of {name, tags}. Without consent returns an unpersonalized list and says why."""
        if "personalization" not in self.consent.get(guest, set()):
            return [{"name": c["name"], "why": "default order, no stored preferences"} for c in catalog]
        wants = {str(v).lower() for v in self.data.get(guest, {}).values()}
        scored = [(len(wants & {t.lower() for t in c["tags"]}), c) for c in catalog]
        scored.sort(key=lambda x: -x[0])
        return [{"name": c["name"], "why": ("matches your saved preference: " + ", ".join(sorted(wants & {t.lower() for t in c["tags"]}))) if s else "no match with your saved preferences"} for s, c in scored]
''', '''
import unittest
from personalization import Prefs

CAT = [{"name": "Spa", "tags": ["quiet", "wellness"]}, {"name": "Bar", "tags": ["lively"]}]
class T(unittest.TestCase):
    def test_no_consent_cannot_store(self):
        with self.assertRaises(PermissionError): Prefs().remember("g", "mood", "quiet")
    def test_recommend_explains_match(self):
        p = Prefs(); p.grant("g", "personalization"); p.remember("g", "mood", "Quiet")
        r = p.recommend("g", CAT); self.assertEqual(r[0]["name"], "Spa"); self.assertIn("quiet", r[0]["why"])
    def test_no_consent_default_order_with_reason(self):
        r = Prefs().recommend("g", CAT); self.assertEqual([x["name"] for x in r], ["Spa", "Bar"]); self.assertIn("no stored", r[0]["why"])
    def test_revoke_erases(self):
        p = Prefs(); p.grant("g", "personalization"); p.remember("g", "mood", "quiet"); p.revoke("g", "personalization")
        self.assertNotIn("g", p.data); self.assertIn("no stored", p.recommend("g", CAT)[0]["why"])
    def test_consent_is_per_guest(self):
        p = Prefs(); p.grant("a", "personalization")
        with self.assertRaises(PermissionError): p.remember("b", "k", "v")
if __name__ == "__main__": unittest.main()
''')

_SAFE = re.compile(r"^[a-z_]+$")

def build_prototype(idea: dict, out_dir: str | Path, timeout: int = 60) -> dict:
    """Write components for the idea's levers, run their tests, return a receipt."""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    built, unsupported = [], []
    for lever in idea["levers"]:
        if lever not in COMPONENTS or not _SAFE.match(lever):
            unsupported.append(lever); continue
        code, test = COMPONENTS[lever]
        (out / f"{lever}.py").write_text(textwrap.dedent(code).lstrip())
        (out / f"test_{lever}.py").write_text(textwrap.dedent(test).lstrip())
        built.append(lever)
    results = []
    for lever in built:
        p = subprocess.run([sys.executable, "-m", "unittest", f"test_{lever}", "-v"], cwd=out, capture_output=True, text=True, timeout=timeout)
        ran = re.search(r"Ran (\d+) tests?", p.stderr)
        results.append({"lever": lever, "returncode": p.returncode, "tests_run": int(ran.group(1)) if ran else 0,
                        "output_tail": p.stderr.strip().splitlines()[-3:]})
    (out / "README.md").write_text(
        f"# Prototype for idea `{idea['idea_id']}`\n\nMechanism: {idea['mechanism']}\n\nReference components with synthetic fixtures.\n"
        "Not affiliated with or endorsed by any brand. Run: `python -m unittest discover`.\n")
    ok = bool(results) and all(r["returncode"] == 0 and r["tests_run"] > 0 for r in results)
    return {"idea_id": idea["idea_id"], "directory": str(out), "built": built, "unsupported_levers": unsupported,
            "test_results": results, "all_tests_passed": ok,
            "limits": ["synthetic fixtures", "reference components, not a brand integration", "levers without a component are listed, not faked"]}
