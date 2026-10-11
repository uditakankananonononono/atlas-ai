"""Row709 Linting: audit of a supplied lint report against a supplied ruleset."""
import ast
import copy
import json
import pathlib
import random
import unicodedata

import pytest

from app.modules.m20_general_cognitive_worker import lint_audit709 as mod
from app.modules.m20_general_cognitive_worker.lint_audit709 import audit

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/m20_general_cognitive_worker/lint_audit709.py"
DOC = ROOT / "docs/M20_LINT709_CONTRACT.md"


def R(rid, sev="error"):
    return {"rule_id": rid, "severity": sev}


def F(rid, sev="error", path="a/b.py", line=1, sup=None):
    return {"rule_id": rid, "severity": sev, "path": path, "line": line,
            "suppression": None if sup is None else {"reason": sup}}


_U = object()


def D(rules=_U, findings=_U, ruleset="rs-1"):
    return {"ruleset": ruleset, "rules": [R("E1"), R("W1", "warning"), R("I1", "info")] if rules is _U else rules,
            "findings": [] if findings is _U else findings}


def err(d):
    with pytest.raises(ValueError) as e:
        audit(d)
    return str(e.value)


def code(reason, field):
    return "LINT709_REFUSED_%s:%s" % (reason, field)


# ------------------------------------------------------------------ known answers
def test_clean_empty_findings():
    out = audit(D())
    assert out["status"] == "clean" and out["finding_count"] == 0 and out["rule_count"] == 3
    assert out["counts_by_severity"] == {"error": 0, "warning": 0, "info": 0}
    assert out["blocking"] == [] and out["violations"] == [] and out["suppressed_errors"] == []
    assert out["rules_without_findings"] == ["E1", "I1", "W1"]


def test_known_answer_blocked():
    d = D(findings=[F("E1", path="x.py", line=3), F("W1", "warning", "y.py", 9), F("I1", "info", "z.py", 2),
                    F("E1", path="q.py", line=7, sup="legacy"), F("W1", "warning", "y.py", 10)])
    out = audit(d)
    assert out["status"] == "blocked" and out["finding_count"] == 5
    assert out["counts_by_severity"] == {"error": 2, "warning": 2, "info": 1}
    assert out["blocking"] == [{"index": 1, "rule_id": "E1", "path": "x.py", "line": 3}]
    assert out["suppressed_errors"] == [{"index": 4, "rule_id": "E1", "path": "q.py", "line": 7}]
    assert out["violations"] == [] and out["rules_without_findings"] == []
    assert out["ruleset"] == "rs-1" and out["algorithm"] == "lint_report_audit_v1"


def test_warnings_only_clean():
    out = audit(D(findings=[F("W1", "warning"), F("I1", "info", line=2)]))
    assert out["status"] == "clean" and out["rules_without_findings"] == ["E1"]


def test_blank_suppression_does_not_unblock():
    for reason in ("", "   ", "\u3000"):
        out = audit(D(findings=[F("E1", sup=reason)]))
        assert out["status"] == "blocked" and out["blocking"][0]["index"] == 1
        assert out["violations"] == [{"index": 1, "code": "suppression_reason_blank"}]
        assert out["suppressed_errors"] == []
    out = audit(D(findings=[F("W1", "warning", sup="")]))
    assert out["status"] == "report_inconsistent"
    assert out["violations"] == [{"index": 1, "code": "suppression_reason_blank"}]


def test_unknown_rule_and_severity_mismatch():
    out = audit(D(findings=[F("NOPE", "warning")]))
    assert out["status"] == "report_inconsistent" and out["violations"] == [{"index": 1, "code": "unknown_rule"}]
    out = audit(D(findings=[F("NOPE", "error")]))
    assert out["status"] == "blocked" and out["violations"] == [{"index": 1, "code": "unknown_rule"}]
    # reported warning on an error rule still blocks (declared severity is checked too)
    out = audit(D(findings=[F("E1", "warning")]))
    assert out["status"] == "blocked" and out["violations"] == [{"index": 1, "code": "severity_mismatch"}]
    assert out["counts_by_severity"]["warning"] == 1
    # reported error on a warning rule blocks
    out = audit(D(findings=[F("W1", "error")]))
    assert out["status"] == "blocked" and out["violations"] == [{"index": 1, "code": "severity_mismatch"}]
    out = audit(D(findings=[F("I1", "warning")]))
    assert out["status"] == "report_inconsistent"


def test_duplicate_findings():
    out = audit(D(findings=[F("W1", "warning"), F("W1", "warning"), F("W1", "warning", line=2),
                            F("W1", "warning", path="c.py")]))
    assert out["violations"] == [{"index": 2, "code": "duplicate_finding"}]
    assert out["counts_by_severity"]["warning"] == 4 and out["status"] == "report_inconsistent"


def test_violations_sorted_and_multiple_codes():
    out = audit(D(findings=[F("W1", "warning"), F("NOPE", "info", sup=""), F("NOPE", "info", sup="")]))
    assert out["violations"] == [{"index": 2, "code": "suppression_reason_blank"}, {"index": 2, "code": "unknown_rule"},
                                 {"index": 3, "code": "duplicate_finding"}, {"index": 3, "code": "suppression_reason_blank"},
                                 {"index": 3, "code": "unknown_rule"}]


def test_honesty_flags_and_limits():
    out = audit(D())
    for k in ("linter_executed", "source_scanned", "findings_verified", "completeness_assessed"):
        assert out[k] is False
    assert out["suppression_requires_reason"] is True
    assert len(out["limits"]) == 5 and all(type(x) is str for x in out["limits"])
    out["limits"].append("x")
    assert len(audit(D())["limits"]) == 5


# ------------------------------------------------------------------ independent oracle over a generated corpus
def oracle(d):
    decl = {r["rule_id"]: r["severity"] for r in d["rules"]}
    blocking, supp, viol = [], [], []
    seen = set()
    counts = dict.fromkeys(("error", "warning", "info"), 0)
    for i, f in enumerate(d["findings"]):
        n = i + 1
        counts[f["severity"]] += 1
        s = f["suppression"]
        valid = s is not None and s["reason"].strip() != ""
        if f["rule_id"] not in decl:
            viol.append((n, "unknown_rule"))
        elif decl[f["rule_id"]] != f["severity"]:
            viol.append((n, "severity_mismatch"))
        if s is not None and not valid:
            viol.append((n, "suppression_reason_blank"))
        k = (f["rule_id"], f["path"], f["line"])
        if k in seen:
            viol.append((n, "duplicate_finding"))
        seen.add(k)
        if "error" in (f["severity"], decl.get(f["rule_id"])):
            (supp if valid else blocking).append(n)
    viol.sort()
    st = "blocked" if blocking else ("report_inconsistent" if viol else "clean")
    return st, counts, blocking, supp, viol


def gen(rng):
    ids = ["A", "B", "C", "D", "E"]
    rules = [R(i, rng.choice(["error", "warning", "info"])) for i in rng.sample(ids, rng.randint(1, 5))]
    fs = []
    for _ in range(rng.randint(0, 12)):
        fs.append(F(rng.choice(ids), rng.choice(["error", "warning", "info"]), rng.choice(["a.py", "b/c.py"]),
                    rng.randint(1, 3), rng.choice([None, None, "", " ", "why"])))
    return {"ruleset": "rs", "rules": rules, "findings": fs}


def test_generated_corpus_matches_oracle():
    rng = random.Random(709)
    seen_status = set()
    for _ in range(600):
        d = gen(rng)
        out = audit(copy.deepcopy(d))
        st, counts, blk, sup, viol = oracle(d)
        seen_status.add(st)
        assert out["status"] == st and out["counts_by_severity"] == counts
        assert [b["index"] for b in out["blocking"]] == blk
        assert [b["index"] for b in out["suppressed_errors"]] == sup
        assert [(v["index"], v["code"]) for v in out["violations"]] == viol
        assert out["finding_count"] == len(d["findings"]) == sum(counts.values())
    assert seen_status == {"blocked", "report_inconsistent", "clean"}


# ------------------------------------------------------------------ refusals: shape, order, codes
def test_not_dict():
    for bad in (None, [], "x", 5, (), True, set()):
        assert err(bad) == code("BAD_TYPE", "input")


def test_keys_unknown_missing_nonstr():
    assert err(dict(D(), extra=1)) == code("UNKNOWN", "input")
    for k in ("ruleset", "rules", "findings"):
        d = D()
        del d[k]
        assert err(d) == code("MISSING", k)
    assert err({1: 2}) == code("BAD_TYPE", "key")
    d = D(findings=[F("E1")])
    d["findings"][0][5] = 1
    assert err(d) == code("BAD_TYPE", "key")
    assert err(D(findings=[dict(F("E1"), z=1)])) == code("UNKNOWN", "findings")
    assert err(D(rules=[dict(R("E1"), z=1)])) == code("UNKNOWN", "rules")
    d = D(findings=[F("E1")])
    d["findings"][0]["suppression"] = {"reason": "x", "z": 1}
    assert err(d) == code("UNKNOWN", "suppression")
    d["findings"][0]["suppression"] = {}
    assert err(d) == code("MISSING", "reason")
    for f in ("rule_id", "severity", "path", "line", "suppression"):
        x = F("E1")
        del x[f]
        assert err(D(findings=[x])) == code("MISSING", f)
    for f in ("rule_id", "severity"):
        x = R("E1")
        del x[f]
        assert err(D(rules=[x])) == code("MISSING", f)


def test_types():
    for bad in (None, "x", (), {}, 5):
        assert err(D(rules=bad)) == code("BAD_TYPE", "rules")
        assert err(D(findings=bad)) == code("BAD_TYPE", "findings")
    assert err(D(rules=[])) == code("EMPTY", "rules")
    assert err(D(rules=["x"])) == code("BAD_TYPE", "rules")
    assert err(D(findings=["x"])) == code("BAD_TYPE", "findings")
    for bad in (None, 5, True, b"x", ["x"]):
        assert err(D(ruleset=bad)) == code("BAD_TYPE", "ruleset")
        assert err(D(rules=[R(bad)])) in (code("BAD_TYPE", "rule_id"), code("BAD_TYPE", "rules"))
    assert err(D(rules=[R(5)])) == code("BAD_TYPE", "rule_id")
    assert err(D(rules=[R("E1", 5)])) == code("BAD_TYPE", "severity")
    assert err(D(findings=[F("E1", path=5)])) == code("BAD_TYPE", "path")
    for bad in ("1", 1.0, True, False, None, [1]):
        assert err(D(findings=[dict(F("E1"), line=bad)])) == code("BAD_TYPE", "line")
    for bad in (0, -1, 1000001):
        assert err(D(findings=[F("E1", line=bad)])) == code("BAD_VALUE", "line")
    for ok in (1, 1000000):
        audit(D(findings=[F("E1", line=ok)]))
    for bad in (5, True, ["x"], "x"):
        x = F("E1")
        x["suppression"] = bad
        assert err(D(findings=[x])) == code("BAD_TYPE", "suppression")
    x = F("E1")
    x["suppression"] = {"reason": 5}
    assert err(D(findings=[x])) == code("BAD_TYPE", "reason")


def test_strict_subclasses():
    class S(str):
        pass

    class I(int):
        pass
    assert err(D(ruleset=S("rs"))) == code("BAD_TYPE", "ruleset")
    assert err(D(rules=[R(S("E1"))])) == code("BAD_TYPE", "rule_id")
    assert err(D(findings=[F("E1", path=S("a.py"))])) == code("BAD_TYPE", "path")
    assert err(D(findings=[dict(F("E1"), line=I(3))])) == code("BAD_TYPE", "line")
    x = F("E1")
    x["suppression"] = {"reason": S("r")}
    assert err(D(findings=[x])) == code("BAD_TYPE", "reason")


def test_format_and_value():
    for bad in ("", "a b", "a/b", "é", "x" * 0, "a\\b"):
        assert err(D(ruleset=bad)) == code("BAD_FORMAT", "ruleset")
        assert err(D(rules=[R(bad)])) == code("BAD_FORMAT", "rule_id")
    for ok in ("a", "A_b.c:d-1", "x" * 64):
        audit(D(ruleset=ok))
    for bad in ("", "Error", "fatal", " error", "ERROR"):
        assert err(D(rules=[R("E1", bad)])) == code("BAD_VALUE", "severity")
        assert err(D(findings=[F("E1", bad)])) == code("BAD_VALUE", "severity")
    for bad in ("", "/a", "a/", "a//b", "./a", "a/..", "a/./b", "../x", "a b", "é.py", "a\\b.py"):
        assert err(D(findings=[F("E1", path=bad)])) == code("BAD_FORMAT", "path")
    for ok in ("a", "a/b/c.py", ".hidden", "a..b", "a-b_c.d/e"):
        audit(D(findings=[F("E1", path=ok)]))


def test_duplicate_rule_ids_refused():
    assert err(D(rules=[R("E1"), R("E1", "warning")])) == code("DUPLICATE", "rules")
    audit(D(rules=[R("E1"), R("e1")]))


def test_validation_order_first_failure():
    assert err(D(rules=[R("A", "bad"), R("B b")])) == code("BAD_VALUE", "severity")
    assert err(D(rules=[R("B b"), R("A", "bad")])) == code("BAD_FORMAT", "rule_id")
    f1, f2 = F("E1", path="a b"), F("E1", line=0)
    assert err(D(findings=[f1, f2])) == code("BAD_FORMAT", "path")
    assert err(D(findings=[f2, f1])) == code("BAD_VALUE", "line")
    assert err(D(rules=[], findings=[F("E1", path="a b")])) == code("EMPTY", "rules")
    assert err(D(rules=[R("E1"), R("E1")], findings=[F("E1", path="a b")])) == code("DUPLICATE", "rules")
    assert err(dict(D(), extra=1, rules=5)) == code("UNKNOWN", "input")


# ------------------------------------------------------------------ caps: N accepted, N+1 refused
def test_caps_exact():
    audit(D(ruleset="r" * 64))
    assert err(D(ruleset="r" * 65)) == code("OVERSIZE", "ruleset")
    audit(D(rules=[R("i" * 64)]))
    assert err(D(rules=[R("i" * 65)])) == code("OVERSIZE", "rule_id")
    assert err(D(findings=[F("E1", "e" * 17)])) == code("OVERSIZE", "severity")
    assert err(D(rules=[R("E1", "e" * 17)])) == code("OVERSIZE", "severity")
    audit(D(findings=[F("E1", path="p" * 128)]))
    assert err(D(findings=[F("E1", path="p" * 129)])) == code("OVERSIZE", "path")
    audit(D(findings=[F("E1", sup="r" * 200)]))
    assert err(D(findings=[F("E1", sup="r" * 201)])) == code("OVERSIZE", "reason")
    rules = [R("r%d" % i, "info") for i in range(64)]
    assert audit(D(rules=rules))["rule_count"] == 64
    assert err(D(rules=rules + [R("r64")])) == code("OVERSIZE", "rules")
    fs = [F("E1", "error", "a.py", i + 1, "why") for i in range(256)]
    assert audit(D(findings=fs))["finding_count"] == 256
    assert err(D(findings=fs + [F("E1", line=999)])) == code("OVERSIZE", "findings")


def test_max_report_uses_579_containers_and_is_accepted():
    rules = [R("r%d" % i, "info") for i in range(64)]
    fs = [F("r1", "info", "a.py", i + 1, "why") for i in range(256)]
    out = audit(D(rules=rules, findings=fs))
    assert out["finding_count"] == 256 and out["status"] == "clean"


def test_field_cap_beats_content_errors():
    ctl = "\x00"
    assert err(D(ruleset=ctl + "r" * 64)) == code("OVERSIZE", "ruleset")
    assert err(D(rules=[R(" " * 65)])) == code("OVERSIZE", "rule_id")
    assert err(D(findings=[F("E1", path="\u200b" * 129)])) == code("OVERSIZE", "path")
    assert err(D(findings=[F("E1", sup="\u2028" * 201)])) == code("OVERSIZE", "reason")
    assert err(D(findings=[F("E1", "\x00" * 17)])) == code("OVERSIZE", "severity")
    # caps run across every item before any item is validated
    assert err(D(findings=[F("E1", line=0), F("E1", path="p" * 129)])) == code("OVERSIZE", "path")
    assert err(D(rules=[R("a b"), R("c" * 65)])) == code("OVERSIZE", "rule_id")


# ------------------------------------------------------------------ preflight fence
def nest(n, as_dict=False):
    node = {} if as_dict else []
    for _ in range(n - 1):
        node = {"a": node} if as_dict else [node]
    return node


def test_string_fence_everywhere():
    big = "z" * 10001
    assert err(dict(D(), x=big)) == code("OVERSIZE", "input")
    assert err(dict(D(), fetch=big)) == code("OVERSIZE", "input")
    assert err(D(findings=[dict(F("E1"), z=big)])) == code("OVERSIZE", "findings")
    x = F("E1")
    x["suppression"] = {"reason": big}
    assert err(D(findings=[x])) == code("OVERSIZE", "suppression")
    assert err(D(ruleset=big)) == code("OVERSIZE", "input")
    assert err(dict(D(), x="z" * 10000)) == code("UNKNOWN", "input")


def test_key_and_dict_fences():
    assert err(dict(D(), **{"k" * 65: 1})) == code("OVERSIZE", "input")
    assert err(dict(D(), **{"k" * 64: 1})) == code("UNKNOWN", "input")
    assert err(D(findings=[dict(F("E1"), **{"k" * 65: 1})])) == code("OVERSIZE", "findings")
    d = D()
    for i in range(5):
        d["x%d" % i] = 1
    assert err(d) == code("UNKNOWN", "input")          # 8 keys
    d["x5"] = 1
    assert err(d) == code("OVERSIZE", "input")
    assert err(dict(D(), x=[0] * 65)) == code("OVERSIZE", "input")
    assert err(dict(D(), x=[0] * 64)) == code("UNKNOWN", "input")
    assert err(dict(D(), x={"k%d" % i: 1 for i in range(9)})) == code("OVERSIZE", "input")
    assert err(dict(D(), x={"k%d" % i: 1 for i in range(8)})) == code("UNKNOWN", "input")


def test_depth_boundaries_each_path():
    for as_dict in (False, True):
        assert err(dict(D(), x=nest(5, as_dict))) == code("UNKNOWN", "input")
        assert err(dict(D(), x=nest(6, as_dict))) == code("OVERSIZE", "input")
    assert err(D(rules=[nest(4)])) == code("BAD_TYPE", "rules")
    assert err(D(rules=[nest(5)])) == code("OVERSIZE", "rules")
    assert err(D(findings=[nest(4)])) == code("BAD_TYPE", "findings")
    assert err(D(findings=[nest(5)])) == code("OVERSIZE", "findings")
    assert err(D(findings=[dict(F("E1"), z=nest(3))])) == code("UNKNOWN", "findings")
    assert err(D(findings=[dict(F("E1"), z=nest(4))])) == code("OVERSIZE", "findings")
    assert err(D(findings=[dict(F("E1"), z=nest(3, True))])) == code("UNKNOWN", "findings")
    assert err(D(findings=[dict(F("E1"), z=nest(4, True))])) == code("OVERSIZE", "findings")
    x = F("E1")
    x["suppression"] = {"reason": "r", "z": nest(2)}
    assert err(D(findings=[x])) == code("UNKNOWN", "suppression")
    x["suppression"] = {"reason": "r", "z": nest(3)}
    assert err(D(findings=[x])) == code("OVERSIZE", "suppression")
    x["suppression"] = {"reason": "r", "z": nest(2, True)}
    assert err(D(findings=[x])) == code("UNKNOWN", "suppression")
    x["suppression"] = {"reason": "r", "z": nest(3, True)}
    assert err(D(findings=[x])) == code("OVERSIZE", "suppression")
    cyc = []
    cyc.append(cyc)
    assert err(dict(D(), x=cyc)) == code("OVERSIZE", "input")


def blob(n):
    root, n = [], n - 1
    while n > 0 and len(root) < 64:
        g = min(n - 1, 63)
        root.append([[] for _ in range(g)])
        n -= 1 + g
    return root


def cc(x):
    return 1 + sum(cc(c) for c in x) if isinstance(x, list) else 1


def test_container_budget_exact_on_both_admission_paths():
    rules = [R("r%d" % i, "info") for i in range(64)]
    fs = [F("r1", "info", "a.py", i + 1, "why") for i in range(256)]
    base = D(rules=rules, findings=fs)                    # 579 containers
    assert audit(base)["finding_count"] == 256
    assert err(dict(base, x=[])) == code("UNKNOWN", "input")                   # exactly 580
    assert err(dict(base, x=[[]])).startswith("LINT709_REFUSED_OVERSIZE:")      # 581
    # finding dicts admitted last: no suppression key, so 1 + 2 + 64 + 256 + blobs
    bare = [{k: v for k, v in F("r1", "info", "a.py", i + 1).items() if k != "suppression"} for i in range(256)]
    b = blob(257)
    assert cc(b) == 257
    def ordered(x):      # findings admitted first so the finding dicts are the last containers counted
        return {"ruleset": "rs-1", "findings": bare, "rules": rules, "x": x}
    assert err(ordered(b)) == code("UNKNOWN", "input")    # 3 + 64 + 256 + 257 = 580
    assert cc(blob(258)) == 258
    assert err(ordered(blob(258))) == code("OVERSIZE", "findings")


class Trap:
    touched = 0

    def _t(self, *a, **k):
        Trap.touched += 1
        raise AssertionError("touched")
    __len__ = __iter__ = __getitem__ = __eq__ = __hash__ = __bool__ = __str__ = __repr__ = _t
    __contains__ = __getattr__ = _t


class SpyList(list):
    def _t(self, *a, **k):
        Trap.touched += 1
        raise AssertionError("iterated")
    __iter__ = __len__ = __getitem__ = __contains__ = _t


class SpyDict(dict):
    def _t(self, *a, **k):
        Trap.touched += 1
        raise AssertionError("touched")
    __iter__ = __len__ = keys = items = values = get = __getitem__ = __contains__ = _t


def test_subclass_containers_refused_untouched():
    Trap.touched = 0
    d = D()
    d["rules"] = SpyList()
    assert err(d) == code("BAD_TYPE", "rules")
    d = D()
    d["findings"] = SpyList()
    assert err(d) == code("BAD_TYPE", "findings")
    d = D(findings=[F("E1")])
    d["findings"][0]["suppression"] = SpyDict()
    assert err(d) == code("BAD_TYPE", "suppression")
    assert err(D(findings=[SpyDict()])) == code("BAD_TYPE", "findings")
    assert err(D(rules=[SpyDict()])) == code("BAD_TYPE", "rules")
    assert err(SpyDict()) == code("BAD_TYPE", "input")
    d = D()
    d["x"] = SpyList()
    assert err(d) == code("BAD_TYPE", "input")
    assert Trap.touched == 0


def test_oversize_containers_never_touch_elements():
    Trap.touched = 0
    t = Trap()
    d = D()
    d["rules"] = [t] * 65
    assert err(d) == code("OVERSIZE", "rules")
    d = D()
    d["findings"] = [t] * 257
    assert err(d) == code("OVERSIZE", "findings")
    assert err(dict(D(), x=[t] * 65)) == code("OVERSIZE", "input")
    assert err(dict(D(), x={"k%d" % i: Trap() for i in range(9)})) == code("OVERSIZE", "input")
    assert err(D(findings=[dict(F("E1"), **{"k%d" % i: Trap() for i in range(9)})])) == code("OVERSIZE", "findings")
    assert Trap.touched == 0


def test_fence_beats_forbidden_content_and_types():
    assert err(dict(D(rules=5), x=[0] * 65)) == code("OVERSIZE", "input")
    assert err(D(findings=[F("E1", path="a b"), dict(F("E1"), z="z" * 10001)])) == code("OVERSIZE", "findings")


# ------------------------------------------------------------------ control characters
@pytest.mark.parametrize("ch", ["\x00", "\n", "\t", "\u200b", "\u2028", "\u2029", "\u202e", "\u00ad", "\x85"])
def test_forbidden_chars_all_fields_never_echoed(ch):
    secret = "AB" + ch + "CD"
    cases = [(D(ruleset=secret), "ruleset"), (D(rules=[R(secret)]), "rule_id"),
             (D(rules=[R("E1", secret)]), "severity"), (D(findings=[F("E1", path=secret)]), "path"),
             (D(findings=[F("E1", "error", "a.py", 1, secret)]), "reason"),
             (D(findings=[F("E1", secret)]), "severity")]
    for d, field in cases:
        m = err(d)
        assert m == code("CONTROL_CHARS", field)
        assert "AB" not in m and ch not in m


def test_char_sweep_matches_category_rule():
    for cp in list(range(0x300)) + [0x2028, 0x2029, 0x200b, 0x200d, 0x2060, 0xfeff, 0x202e, 0xe000, 0x1f600]:
        ch = chr(cp)
        bad = unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp")
        d = D(findings=[F("E1", sup="a" + ch + "b")])
        if bad:
            assert err(d) == code("CONTROL_CHARS", "reason"), hex(cp)
        else:
            audit(d)


def test_reason_prose_allows_ordinary_text():
    out = audit(D(findings=[F("E1", sup="Generated code, see ticket #12: (ok) \u00e9")]))
    assert out["suppressed_errors"][0]["index"] == 1 and out["status"] == "clean"


def test_key_with_control_chars_is_unknown_not_echoed():
    m = err(dict(D(), **{"a\x00b": 1}))
    assert m == code("UNKNOWN", "input") and "\x00" not in m


# ------------------------------------------------------------------ determinism, immutability, purity
def test_deterministic_immutable_no_alias():
    d = D(findings=[F("E1"), F("W1", "warning", sup="x"), F("E1", line=2, sup="ok")])
    snap = copy.deepcopy(d)
    a = json.dumps(audit(d), sort_keys=True)
    assert d == snap
    assert a == json.dumps(audit(copy.deepcopy(d)), sort_keys=True)
    assert json.dumps(audit(d)) == json.dumps(audit(copy.deepcopy(d)))
    out = audit(d)
    out["blocking"].append(1)
    out["counts_by_severity"]["error"] = 99
    assert audit(d)["blocking"] != out["blocking"] and audit(d)["counts_by_severity"]["error"] == 2
    shuffled = copy.deepcopy(d)
    shuffled["rules"].reverse()
    assert audit(shuffled)["rules_without_findings"] == audit(d)["rules_without_findings"]


def test_ast_purity():
    tree = ast.parse(SRC.read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add(n.module)
    assert mods <= {"__future__", "re", "unicodedata", "typing"}, mods
    nm = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    for banned in ("open", "eval", "exec", "compile", "__import__", "input", "getattr", "setattr", "globals",
                   "os", "sys", "subprocess", "socket", "time", "random"):
        assert banned not in nm, banned
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for banned in ("system", "popen", "write", "write_text", "read_text", "now", "today", "urlopen"):
        assert banned not in attrs, banned
    assert not any(isinstance(n, ast.Constant) and isinstance(n.value, float) for n in ast.walk(tree))
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for bad in ("lint", "run", "scan", "fix", "execute", "fetch", "send", "write", "apply"):
        assert bad not in fns, bad
    assert mod.ALGORITHM == "lint_report_audit_v1"


def test_module_not_wired_in_this_unit():
    for p in (ROOT / "backend/app").rglob("*.py"):
        if p == SRC:
            continue
        t = p.read_text()
        assert "lint_audit709" not in t, p


def test_doc_contract():
    d = DOC.read_text()
    low = d.lower()
    for need in ("LIMITS", "INTERPRETATION CHOICE", "LINT709_REFUSED_", "report_inconsistent", "blocked", "clean",
                 "severity_mismatch", "suppression_reason_blank", "unknown_rule", "duplicate_finding",
                 "stale `.pyc`", "void", "Linting", "Catches issues"):
        assert need in d, need
    for bad in (".jsonl", ".json", "delivery folder", "invalid_run", "mutation_run", "private", "ledger", "integrator",
                "doc hygiene", "main said", "adopt"):
        assert bad not in low, bad


# ------------------------------------------------------------------ survivor pins (added after the first battery)
def test_pin_limits_text_and_list_caps():
    import backend.app.modules.m20_general_cognitive_worker.lint_audit709 as m
    out = audit(D())["limits"]
    assert out[0].endswith("not verified or authenticated")
    assert out[1].endswith("not checked against any file or ruleset source")
    assert out[2].endswith("not that the code is clean")
    assert out[3].endswith("are invisible here")
    assert out[4].endswith("not for being true or adequate")
    assert m._LIST_CAPS == {"rules": 64, "findings": 256}


def test_pin_caps_run_across_every_item_for_each_field():
    assert err(D(findings=[F("E1", line=0), F("E1", "e" * 17)])) == code("OVERSIZE", "severity")
    assert err(D(findings=[F("E1", line=0), F("i" * 65)])) == code("OVERSIZE", "rule_id")
    assert err(D(findings=[F("E1", line=0), F("E1", sup="r" * 201)])) == code("OVERSIZE", "reason")
    assert err(D(rules=[R("a b"), R("E1", "e" * 17)])) == code("OVERSIZE", "severity")


def test_pin_field_labels_in_content_errors():
    assert err(D(findings=[F("a b")])) == code("BAD_FORMAT", "rule_id")
    fat = {"x%d" % i: 1 for i in range(9)}
    assert err(D(findings=[dict(F("E1"), suppression=fat)])) == code("OVERSIZE", "suppression")
    assert err(D(rules=[dict(R("E1"), suppression={"x%d" % i: 1 for i in range(9)})])) == code("OVERSIZE", "rules")


def test_pin_container_budget_boundary_on_the_generic_admission_path():
    rules = [R("r%d" % i, "info") for i in range(64)]
    bare = [{k: v for k, v in F("r1", "info", "a.py", i + 1).items() if k != "suppression"} for i in range(256)]
    def first(x):        # x listed first is processed last, so its containers are the last counted
        return {"x": x, "ruleset": "rs-1", "findings": bare, "rules": rules}
    assert cc(blob(257)) == 257
    assert err(first(blob(257))) == code("UNKNOWN", "input")          # exactly 580
    assert err(first(blob(258))).startswith("LINT709_REFUSED_OVERSIZE:")   # 581


def test_pin_severity_cap_boundary_pair():
    for s in ("x" * 16,):
        assert err(D(rules=[R("E1", s)])) == code("BAD_VALUE", "severity")
        assert err(D(findings=[F("E1", s)])) == code("BAD_VALUE", "severity")
    for s in ("x" * 17,):
        assert err(D(rules=[R("E1", s)])) == code("OVERSIZE", "severity")
        assert err(D(findings=[F("E1", s)])) == code("OVERSIZE", "severity")
    assert mod.MAX_SEVERITY == 16
