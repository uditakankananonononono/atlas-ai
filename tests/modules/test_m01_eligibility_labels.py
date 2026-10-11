"""M1 eligibility label harness: recorder, gate counter, grouped split and held-out evaluation (labels supplied, nothing trained)."""
import ast
import copy
import hashlib
import pathlib
import random
import unicodedata

import pytest

from app.modules.m01_opportunity_discovery import classifier as clf
from app.modules.m01_opportunity_discovery import eligibility_labels as mod
from app.modules.m01_opportunity_discovery.eligibility_labels import (
    add_label, evaluate, gate_status, split_records)

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/m01_opportunity_discovery/eligibility_labels.py"
DOC = ROOT / "docs/M01_ELIGIBILITY_LABELS_CONTRACT.md"
LABELS = ("eligible", "ineligible", "unclear")


def rec(i, label="eligible", group=None, **over):
    base = {"record_id": "r%d" % i, "group_id": group if group is not None else "g%d" % i,
            "text": "Open to students enrolled in a degree programme.", "profile": "Second year engineering student.",
            "label": label, "label_source": "human_reviewed", "reviewer": "rev_1", "reviewed_at": "2026-10-12"}
    base.update(over)
    return base


def build(counts, group_of=None):
    out, i = [], 0
    for label, n in zip(LABELS, counts):
        for _ in range(n):
            out.append(rec(i, label, group_of(i, label) if group_of else None))
            i += 1
    return out


def code(reason, field):
    return "ELIGLAB_REFUSED_%s:%s" % (reason, field)


def err(fn, *a):
    with pytest.raises(ValueError) as e:
        fn(*a)
    return str(e.value)


# independent oracle for the split and the metrics (does not call the module)
def o_bucket(seed, group):
    return int(hashlib.sha256(("%s|%s" % (seed, group)).encode()).hexdigest(), 16) % 10000


def o_split(seed, group):
    b = o_bucket(seed, group)
    return "train" if b < 8000 else ("dev" if b < 9000 else "test")


def o_ready(counts):
    return sum(counts.values()) >= 500 and all(counts.get(k, 0) >= 100 for k in LABELS)


_FIND = {}


def group_in_bucket(seed, bucket):
    """A group name whose bucket is exactly the requested value (scanned once)."""
    key = (seed, bucket)
    if key not in _FIND:
        i = 0
        while o_bucket(seed, "q%d" % i) != bucket:
            i += 1
        _FIND[key] = "q%d" % i
    return _FIND[key]


CORPUS = build((200, 150, 150))


# ------------------------------------------------------------------ contract of record
def test_thresholds_are_the_classifier_contract():
    assert clf.MIN_FINE_TUNE_LABELS == 500 and clf.MIN_PER_CLASS == 100
    assert mod.MIN_FINE_TUNE_LABELS is clf.MIN_FINE_TUNE_LABELS and mod.MIN_PER_CLASS is clf.MIN_PER_CLASS
    assert mod.fine_tune_ready is clf.fine_tune_ready
    assert mod.LABELS == ("eligible", "ineligible", "unclear")
    assert mod.SOURCES == ("human_reviewed", "synthetic", "model_generated", "rule_derived") and mod.HUMAN == "human_reviewed"
    assert mod.SPLITS == ("train", "dev", "test") and mod.KEYS == tuple(rec(0))


def test_gate_known_answers_and_boundaries():
    g = gate_status([])
    assert g["total"] == 0 and g["ready"] is False and g["total_shortfall"] == 500
    assert g["class_shortfalls"] == {"eligible": 100, "ineligible": 100, "unclear": 100}
    assert g["required_total"] == 500 and g["required_per_class"] == 100 and g["label_source_counted"] == "human_reviewed"
    cases = {(200, 150, 150): True, (300, 100, 100): True, (299, 100, 100): False, (301, 100, 99): False,
             (100, 100, 100): False, (400, 100, 100): True, (99, 200, 201): False, (200, 200, 100): True,
             (200, 200, 99): False, (500, 0, 0): False, (0, 500, 0): False}
    for counts, ready in cases.items():
        s = gate_status(build(counts))
        assert s["ready"] is ready, counts
        assert s["counts"] == dict(zip(LABELS, counts)) and s["total"] == sum(counts)
        assert s["total_shortfall"] == max(0, 500 - sum(counts))
        assert s["class_shortfalls"] == {k: max(0, 100 - c) for k, c in zip(LABELS, counts)}


def test_gate_matches_independent_formula_over_generated_counts():
    rng = random.Random(1)
    for _ in range(60):
        c = tuple(rng.choice([0, 50, 99, 100, 101, 150, 200, 300]) for _ in LABELS)
        assert gate_status(build(c))["ready"] is o_ready(dict(zip(LABELS, c))), c


def test_the_gate_is_the_classifier_function_not_a_copy(monkeypatch):
    calls = []

    def stub(counts):
        calls.append(dict(counts))
        return stub.answer
    monkeypatch.setattr(mod, "fine_tune_ready", stub)
    stub.answer = False
    assert gate_status(CORPUS)["ready"] is False and calls[-1] == {"eligible": 200, "ineligible": 150, "unclear": 150}
    assert err(split_records, CORPUS, "s") == code("BELOW_GATE", "records")
    assert err(evaluate, CORPUS, {}, "s") == code("BELOW_GATE", "records")
    stub.answer = True
    small = build((3, 3, 3))
    assert gate_status(small)["ready"] is True
    assert sum(len(v) for v in split_records(small, "s")["splits"].values()) == 9


def test_module_imports_only_the_classifier_contract():
    tree = ast.parse(SRC.read_text())
    froms = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level == 1]
    assert [(n.module, sorted(a.name for a in n.names)) for n in froms] == [
        ("classifier", ["MIN_FINE_TUNE_LABELS", "MIN_PER_CLASS", "fine_tune_ready"])]


# ------------------------------------------------------------------ synthetic labels never count
@pytest.mark.parametrize("src", ["synthetic", "model_generated", "rule_derived"])
def test_non_human_sources_refused_everywhere(src):
    bad = rec(0, label_source=src)
    assert err(add_label, [], bad) == code("SYNTHETIC", "label_source")
    mixed = CORPUS[:5] + [bad]
    assert err(gate_status, mixed) == code("SYNTHETIC", "label_source")
    assert err(split_records, mixed, "s") == code("SYNTHETIC", "label_source")
    assert err(evaluate, mixed, {}, "s") == code("SYNTHETIC", "label_source")


def test_unknown_or_nonstring_source_is_a_value_error_not_synthetic():
    for bad in ("", "Human_Reviewed", "human", "user", "expert"):
        assert err(add_label, [], rec(0, label_source=bad)) == code("BAD_VALUE", "label_source")
    assert err(add_label, [], rec(0, label_source=None)) == code("BAD_TYPE", "label_source")
    assert err(add_label, [], rec(0, label_source=1)) == code("BAD_TYPE", "label_source")


# ------------------------------------------------------------------ recorder
def test_add_label_returns_new_list_and_never_mutates():
    base = [rec(0), rec(1, "ineligible")]
    before = copy.deepcopy(base)
    out = add_label(base, rec(2, "unclear"))
    assert base == before and out is not base and len(out) == 3 and out[:2] == before
    assert out[2] == rec(2, "unclear") and out[2] is not base
    r = rec(3)
    keep = copy.deepcopy(r)
    add_label(base, r)
    assert r == keep
    assert add_label([], rec(0)) == [rec(0)]


def test_add_label_duplicates_and_capacity():
    assert err(add_label, [rec(0)], rec(0, "unclear")) == code("DUPLICATE", "record_id")
    assert err(gate_status, [rec(0), rec(1), rec(0)]) == code("DUPLICATE", "record_id")
    full = [rec(i) for i in range(20000)]
    assert err(add_label, full, rec(20000)) == code("OVERSIZE", "records")
    assert len(add_label(full[:19999], rec(19999))) == 20000
    assert len(gate_status(full)["counts"]) == 3
    assert err(gate_status, full + [rec(20000)]) == code("OVERSIZE", "records")


def test_add_label_record_must_be_an_exact_dict():
    for bad in (None, [], "x", 5, ()):
        assert err(add_label, [], bad) == code("BAD_TYPE", "record")

    class D(dict):
        pass
    assert err(add_label, [], D(rec(0))) == code("BAD_TYPE", "record")


# ------------------------------------------------------------------ shapes, types and order
def test_records_container_types():
    for bad in (None, {}, (), "x", 5, set(), (rec(0),)):
        assert err(gate_status, bad) == code("BAD_TYPE", "records")

    class L(list):
        pass
    assert err(gate_status, L([rec(0)])) == code("BAD_TYPE", "records")
    for bad in (None, "x", 5, [], ["x"], [[]]):
        assert err(gate_status, [bad]) == code("BAD_TYPE", "records")

    class D(dict):
        pass
    assert err(gate_status, [D(rec(0))]) == code("BAD_TYPE", "records")


def test_strict_value_types():
    for f in mod.KEYS:
        for bad in (None, 1, 1.5, True, [], {}, b"x"):
            assert err(add_label, [], rec(0, **{f: bad})) == code("BAD_TYPE", f), (f, bad)

    class S(str):
        pass
    for f in mod.KEYS:
        assert err(add_label, [], rec(0, **{f: S(rec(0)[f])})) == code("BAD_TYPE", f), f
    assert err(gate_status, [{1: "x"}]) == code("BAD_TYPE", "key")
    assert err(gate_status, [{None: 1}]) == code("BAD_TYPE", "key")


def test_unknown_and_missing_keys_order():
    r = rec(0)
    assert err(add_label, [], dict(r, extra=1)) == code("OVERSIZE", "record")        # nine keys
    swapped = {x: v for x, v in r.items() if x != "reviewer"}
    swapped["extra"] = 1
    assert err(add_label, [], swapped) == code("UNKNOWN", "record")
    for k in mod.KEYS:
        d = {x: v for x, v in r.items() if x != k}
        assert err(add_label, [], d) == code("MISSING", k)
    # keys are checked across all records before any content is looked at
    assert err(gate_status, [rec(0, label="nope"), swapped]) == code("UNKNOWN", "record")
    assert err(gate_status, [rec(0, label="nope"), {k: v for k, v in rec(1).items() if k != "text"}]) == code("MISSING", "text")


def test_caps_exact_each_field():
    caps = {"record_id": 128, "group_id": 128, "reviewer": 64, "text": 8000, "profile": 4000}
    for f, cap in caps.items():
        v = "a" * cap if f not in ("text", "profile") else "a" * cap
        assert add_label([], rec(0, **{f: v}))[0][f] == v
        assert err(add_label, [], rec(0, **{f: "a" * (cap + 1)})) == code("OVERSIZE", f)
    assert err(add_label, [], rec(0, text="a" * 10001)) == code("OVERSIZE", "record")
    assert err(add_label, [], rec(0, label="x" * 17)) == code("OVERSIZE", "label")
    assert err(add_label, [], rec(0, label="x" * 16)) == code("BAD_VALUE", "label")
    assert err(add_label, [], rec(0, label_source="x" * 17)) == code("OVERSIZE", "label_source")
    assert err(add_label, [], rec(0, label_source="x" * 16)) == code("BAD_VALUE", "label_source")
    assert err(add_label, [], rec(0, reviewed_at="2026-10-12x")) == code("OVERSIZE", "reviewed_at")
    assert err(add_label, [], rec(0, reviewed_at="2026-10-1")) == code("BAD_FORMAT", "reviewed_at")


def test_preflight_fence_sizes():
    assert err(gate_status, [rec(0, text="a" * 10001)]) == code("OVERSIZE", "records")
    assert err(gate_status, [rec(0, profile="a" * 10001)]) == code("OVERSIZE", "records")
    assert err(gate_status, [rec(0, profile="a" * 10000)]) == code("OVERSIZE", "profile")
    assert err(gate_status, [rec(0, text="a" * 8001)]) == code("OVERSIZE", "text")
    assert len(rec(0)) == 8
    assert err(gate_status, [dict(rec(0), x=1)]) == code("OVERSIZE", "records")          # nine keys
    for n in (65, 64):
        r = rec(0)
        r.pop("reviewed_at")
        r["k" * n] = 1
        want = code("OVERSIZE", "records") if n == 65 else code("UNKNOWN", "record")
        assert err(gate_status, [r]) == want
    assert len(gate_status([rec(i) for i in range(20000)])["counts"]) == 3
    assert err(gate_status, [rec(i) for i in range(20001)]) == code("OVERSIZE", "records")


def test_field_caps_run_across_every_record_before_content_errors():
    assert err(gate_status, [rec(0, label="nope"), rec(1, text="a" * 4001, profile="a" * 4001)]) == code("OVERSIZE", "profile")
    assert err(gate_status, [rec(0, label_source="synthetic"), rec(1, reviewer="r" * 65)]) == code("OVERSIZE", "reviewer")
    assert err(gate_status, [rec(0, text=""), rec(1, record_id="a" * 129)]) == code("OVERSIZE", "record_id")
    # a control character inside an oversize field is an oversize error, never a content error
    assert err(add_label, [], rec(0, record_id="\x00" + "a" * 128)) == code("OVERSIZE", "record_id")
    assert err(add_label, [], rec(0, reviewer="\u200b" * 65)) == code("OVERSIZE", "reviewer")


_FIELD_CAP = {"record_id": 128, "group_id": 128, "reviewer": 64, "reviewed_at": 10, "seed": 64}


def _want(value, field):
    if len(value) > _FIELD_CAP[field]:
        return code("OVERSIZE", field)
    forbidden = any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") for c in value)
    return code("CONTROL_CHARS" if forbidden else "BAD_FORMAT", field)


def test_content_formats():
    for f in ("record_id", "group_id"):
        for bad in ("", "a b", "a/b", "\u00e9", "a\n", "x\\y", "a\u200b"):
            assert err(add_label, [], rec(0, **{f: bad})) == _want(bad, f), (f, bad)
        for ok in ("a", "A_b.c:d-1", "x" * 128):
            assert add_label([], rec(0, record_id=ok, group_id=ok))
    for bad in ("", "a b", "\u00e9", "a/b", "a\n", "a:b"):
        assert err(add_label, [], rec(0, reviewer=bad)) == _want(bad, "reviewer"), bad
    for ok in ("a", "a@b.c", "A_b-1", "x" * 64):
        assert add_label([], rec(0, reviewer=ok))
    for bad in ("", "elig", "Eligible", "ELIGIBLE", " eligible", "maybe"):
        assert err(add_label, [], rec(0, label=bad)) == code("BAD_VALUE", "label")
    for bad in ("", " ", "\n\t "):
        assert err(add_label, [], rec(0, text=bad)) == code("BAD_VALUE", "text")
        assert err(add_label, [], rec(0, profile=bad)) == code("BAD_VALUE", "profile")
    for good in ("2024-02-29", "0001-01-01", "9999-12-31"):
        assert add_label([], rec(0, reviewed_at=good))
    for bad in ("2026-02-30", "2026-13-01", "2026-00-10", "2026/10/12", "26-10-12", "2026-10-1x", "2026-10-12\n",
                "\u0662\u0660\u0662\u0666-10-12", "0000-01-01", "2026-02-29"):
        assert err(add_label, [], rec(0, reviewed_at=bad)) == _want(bad, "reviewed_at"), bad


def _cats():
    out = []
    for cp in list(range(0, 0x3000)) + [0xFEFF, 0x2028, 0x2029, 0x200B, 0x202E, 0xE0001]:
        c = chr(cp)
        if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp"):
            out.append(c)
    return out


def test_control_characters_everywhere_and_never_echoed():
    bad_chars = _cats()
    assert len(bad_chars) > 100
    for f in ("record_id", "group_id", "reviewer", "label", "label_source", "reviewed_at"):
        for ch in ("\x00", "\n", "\u200b", "\u2028", "\u2029", "\ufeff", "\x7f"):
            m = err(add_label, [], rec(0, **{f: "zq" + ch}))
            assert m.startswith("ELIGLAB_REFUSED_") and ch not in m and "zq" not in m
    for f in ("text", "profile"):
        for ch in ("\x00", "\x1b", "\x7f", "\u200b", "\u2028", "\u2029", "\ufeff", "\u202e"):
            assert err(add_label, [], rec(0, **{f: "ab" + ch})) == code("CONTROL_CHARS", f)
        for ok in ("line one\nline two", "tab\tsep", "crlf\r\nend"):
            assert add_label([], rec(0, **{f: ok}))[0][f] == ok
    # every Cc/Cf/Zl/Zp character except the three ordinary prose separators is refused in prose
    for ch in bad_chars:
        if ch in "\n\r\t":
            continue
        assert err(add_label, [], rec(0, text="a" + ch)) == code("CONTROL_CHARS", "text"), hex(ord(ch))
    for ch in ("\u00a0", "\u2003", "\u3000", "e\u0301"):
        assert add_label([], rec(0, text="a" + ch + "b"))


def test_hostile_containers_are_not_materialized():
    class Trap(list):
        touched = 0

        def __iter__(self):
            Trap.touched += 1
            return super().__iter__()

        def __len__(self):
            Trap.touched += 1
            return 1
    for fn in (lambda x: gate_status(x), lambda x: split_records(x, "s"), lambda x: evaluate(x, {}, "s"),
               lambda x: add_label(x, rec(0))):
        assert err(fn, Trap([rec(0)])) == code("BAD_TYPE", "records")
    assert Trap.touched == 0

    class Item(dict):
        touched = 0

        def items(self):
            Item.touched += 1
            return super().items()

        def __len__(self):
            Item.touched += 1
            return 1
    assert err(gate_status, [Item(rec(0))]) == code("BAD_TYPE", "records")
    assert Item.touched == 0

    class Big(list):
        pass
    assert err(gate_status, Big(range(10 ** 6))) == code("BAD_TYPE", "records")


# ------------------------------------------------------------------ split
def test_split_refuses_below_gate_and_bad_seed():
    assert err(split_records, build((200, 200, 99)), "s") == code("BELOW_GATE", "records")
    assert err(split_records, [], "s") == code("BELOW_GATE", "records")
    assert err(split_records, CORPUS, "x" * 65) == code("OVERSIZE", "seed")
    assert split_records(CORPUS, "x" * 64)["seed"] == "x" * 64
    for bad in (None, 1, b"s", ["s"], True):
        assert err(split_records, CORPUS, bad) == code("BAD_TYPE", "seed")
    for bad in ("", "a b", "a/b", "é", "a\n"):
        assert err(split_records, CORPUS, bad) == code("BAD_FORMAT", "seed")

    class S(str):
        pass
    assert err(split_records, CORPUS, S("s")) == code("BAD_TYPE", "seed")
    # seed is checked before the records
    assert err(split_records, "junk", 5) == code("BAD_TYPE", "seed")


def test_split_matches_independent_oracle_and_is_group_disjoint():
    recs = build((200, 150, 150), group_of=lambda i, lab: "grp%d" % (i // 7))
    out = split_records(recs, "seed-1")
    assert out["algorithm"] == "eligibility_label_harness_v1" and out["seed"] == "seed-1"
    want = {s: sorted(r["record_id"] for r in recs if o_split("seed-1", r["group_id"]) == s) for s in mod.SPLITS}
    assert out["splits"] == want
    by_group = {}
    for s, ids in out["splits"].items():
        for rid in ids:
            by_group.setdefault(next(r["group_id"] for r in recs if r["record_id"] == rid), set()).add(s)
    assert all(len(v) == 1 for v in by_group.values())
    allids = [i for s in mod.SPLITS for i in out["splits"][s]]
    assert sorted(allids) == sorted(r["record_id"] for r in recs) and len(set(allids)) == len(allids)
    for s in mod.SPLITS:
        c = dict.fromkeys(LABELS, 0)
        for r in recs:
            if r["record_id"] in set(out["splits"][s]):
                c[r["label"]] += 1
        assert out["counts"][s] == c
        assert out["splits"][s] == sorted(out["splits"][s])
    assert out["group_disjoint"] is True and out["model_trained"] is False and out["labels_generated"] is False
    assert set(out) == {"algorithm", "seed", "splits", "counts", "group_disjoint", "model_trained", "labels_generated"}


def test_split_fractions_seed_sensitivity_and_determinism():
    recs = build((2000, 1500, 1500))
    out = split_records(recs, "s1")
    n = len(recs)
    for s, want in (("train", 0.8), ("dev", 0.1), ("test", 0.1)):
        assert abs(len(out["splits"][s]) / n - want) < 0.02, s
    assert split_records(recs, "s1") == out
    assert split_records(recs, "s2")["splits"] != out["splits"]
    shuffled = recs[:]
    random.Random(3).shuffle(shuffled)
    assert split_records(shuffled, "s1")["splits"] == out["splits"]


def test_split_bucket_boundaries_exact():
    for bucket, want in ((7999, "train"), (8000, "dev"), (8999, "dev"), (9000, "test"), (9999, "test"), (0, "train")):
        g = group_in_bucket("bnd", bucket)
        recs = [rec(i, LABELS[i % 3], group=g if i == 0 else None) for i in range(600)]
        out = split_records(recs, "bnd")
        assert "r0" in out["splits"][want], (bucket, want)


def test_split_does_not_mutate_input():
    before = copy.deepcopy(CORPUS)
    split_records(CORPUS, "s")
    assert CORPUS == before


# ------------------------------------------------------------------ evaluate
def test_set_up_has_all_classes_in_test():
    seed = "eval-seed"
    recs = build((200, 150, 150))
    test = [r for r in recs if o_split(seed, r["group_id"]) == "test"]
    assert {r["label"] for r in test} == set(LABELS) and len(test) > 30


def metrics_oracle(gold, pred):
    from fractions import Fraction
    n = len(gold)
    out = {}
    f1s = []
    for c in LABELS:
        tp = sum(1 for k in gold if gold[k] == c and pred[k] == c)
        pc = sum(1 for k in gold if pred[k] == c)
        sc = sum(1 for k in gold if gold[k] == c)
        p = Fraction(tp, pc) if pc else Fraction(0)
        r = Fraction(tp, sc)
        f = 2 * p * r / (p + r) if p + r else Fraction(0)
        out[c] = (sc, p, r, f)
        f1s.append(f)
    acc = Fraction(sum(1 for k in gold if gold[k] == pred[k]), n)
    return out, acc, sum(f1s) / 3, Fraction(max(sum(1 for k in gold if gold[k] == c) for c in LABELS), n)


def test_evaluate_known_answers_and_oracle():
    seed = "eval-seed"
    recs = build((200, 150, 150))
    test = {r["record_id"]: r["label"] for r in recs if o_split(seed, r["group_id"]) == "test"}
    perfect = dict(test)
    r = evaluate(recs, perfect, seed)
    assert r["accuracy"] == 1.0 and r["macro_f1"] == 1.0 and r["test_records"] == len(test)
    assert all(r["per_class"][c]["precision"] == 1.0 and r["per_class"][c]["recall"] == 1.0 for c in LABELS)
    assert r["confusion"] == {g: {p: (sum(1 for k in test if test[k] == g) if g == p else 0) for p in LABELS} for g in LABELS}
    rot = {k: LABELS[(LABELS.index(v) + 1) % 3] for k, v in test.items()}
    r = evaluate(recs, rot, seed)
    assert r["accuracy"] == 0.0 and r["macro_f1"] == 0.0
    rng = random.Random(5)
    for _ in range(25):
        pred = {k: rng.choice(LABELS) if rng.random() < 0.6 else v for k, v in test.items()}
        r = evaluate(recs, pred, seed)
        per, acc, macro, maj = metrics_oracle(test, pred)
        assert r["accuracy"] == round(float(acc), 6) and r["macro_f1"] == round(float(macro), 6)
        assert r["majority_baseline_accuracy"] == round(float(maj), 6)
        for c in LABELS:
            sc, p, rc, f = per[c]
            assert r["per_class"][c] == {"support": sc, "precision": round(float(p), 6), "recall": round(float(rc), 6), "f1": round(float(f), 6)}
        for g in LABELS:
            for p_ in LABELS:
                assert r["confusion"][g][p_] == sum(1 for k in test if test[k] == g and pred[k] == p_)
    assert set(r) == {"algorithm", "seed", "test_records", "accuracy", "macro_f1", "per_class", "confusion",
                      "majority_baseline_accuracy", "model_trained", "labels_generated", "limits"}
    assert r["model_trained"] is False and r["labels_generated"] is False and r["seed"] == seed


def test_evaluate_hand_computed_case():
    seed = "hand"
    ge = [group_in_bucket(seed, 9000 + i) for i in range(6)]
    recs = build((200, 150, 150), group_of=lambda i, lab: "tr%d" % i)
    # replace six train records by test-bucket groups: 2 eligible, 2 ineligible, 2 unclear
    for slot, (idx, g) in enumerate(zip([0, 1, 200, 201, 350, 351], ge)):
        recs[idx]["group_id"] = g
    for r in recs:
        if r["group_id"].startswith("tr") and o_split(seed, r["group_id"]) == "test":
            r["group_id"] = group_in_bucket(seed, 100)
    ids = ["r0", "r1", "r200", "r201", "r350", "r351"]
    assert evaluate(recs, dict.fromkeys(ids, "eligible"), seed)["test_records"] == 6
    pred = {"r0": "eligible", "r1": "ineligible", "r200": "ineligible", "r201": "ineligible", "r350": "eligible", "r351": "unclear"}
    r = evaluate(recs, pred, seed)
    assert r["accuracy"] == round(4 / 6, 6)
    assert r["confusion"] == {"eligible": {"eligible": 1, "ineligible": 1, "unclear": 0},
                              "ineligible": {"eligible": 0, "ineligible": 2, "unclear": 0},
                              "unclear": {"eligible": 1, "ineligible": 0, "unclear": 1}}
    assert r["per_class"]["eligible"] == {"support": 2, "precision": 0.5, "recall": 0.5, "f1": 0.5}
    assert r["per_class"]["ineligible"] == {"support": 2, "precision": round(2 / 3, 6), "recall": 1.0, "f1": 0.8}
    assert r["per_class"]["unclear"] == {"support": 2, "precision": 1.0, "recall": 0.5, "f1": round(2 / 3, 6)}
    assert r["macro_f1"] == round((0.5 + 0.8 + 2 / 3) / 3, 6)
    assert r["majority_baseline_accuracy"] == round(2 / 6, 6)
    # a class never predicted has zero precision and zero f1, not an error
    allel = evaluate(recs, dict.fromkeys(ids, "eligible"), seed)
    assert allel["per_class"]["ineligible"] == {"support": 2, "precision": 0.0, "recall": 0.0, "f1": 0.0}


def test_evaluate_refusals():
    seed = "eval-seed"
    recs = build((200, 150, 150))
    test = {r["record_id"]: r["label"] for r in recs if o_split(seed, r["group_id"]) == "test"}
    assert err(evaluate, build((200, 200, 99)), {}, seed) == code("BELOW_GATE", "records")
    assert err(evaluate, recs, dict(test, zzz="eligible"), seed) == code("UNKNOWN", "predictions")
    train_id = next(r["record_id"] for r in recs if o_split(seed, r["group_id"]) != "test")
    assert err(evaluate, recs, dict(test, **{train_id: "eligible"}), seed) == code("UNKNOWN", "predictions")
    missing = dict(test)
    missing.pop(sorted(missing)[0])
    assert err(evaluate, recs, missing, seed) == code("MISSING", "predictions")
    assert err(evaluate, recs, dict(test, **{sorted(test)[0]: "maybe"}), seed) == code("BAD_VALUE", "predictions")
    for bad in (None, [], (), "x", 5, [("a", "b")]):
        assert err(evaluate, recs, bad, seed) == code("BAD_TYPE", "predictions")
    assert err(evaluate, recs, {1: "eligible"}, seed) == code("BAD_TYPE", "predictions")
    assert err(evaluate, recs, {"a": 1}, seed) == code("BAD_TYPE", "predictions")
    assert err(evaluate, recs, {"a": None}, seed) == code("BAD_TYPE", "predictions")
    assert err(evaluate, recs, {"a" * 129: "eligible"}, seed) == code("OVERSIZE", "predictions")
    assert err(evaluate, recs, {"a": "x" * 17}, seed) == code("OVERSIZE", "predictions")
    assert err(evaluate, recs, {"a": "x" * 16}, seed) == code("BAD_VALUE", "predictions")
    assert err(evaluate, recs, {"a" * 128: "eligible"}, seed) == code("UNKNOWN", "predictions")
    big = {"p%d" % i: "eligible" for i in range(20001)}
    assert err(evaluate, recs, big, seed) == code("OVERSIZE", "predictions")

    class P(dict):
        pass
    assert err(evaluate, recs, P(test), seed) == code("BAD_TYPE", "predictions")

    class S(str):
        pass
    assert err(evaluate, recs, {S("r0"): "eligible"}, seed) == code("BAD_TYPE", "predictions")
    assert err(evaluate, recs, {"r0": S("eligible")}, seed) == code("BAD_TYPE", "predictions")
    assert err(evaluate, recs, test, "bad seed") == code("BAD_FORMAT", "seed")


def test_evaluate_refuses_when_the_test_split_lacks_a_class():
    seed = "empty"
    train_group = group_in_bucket(seed, 5)
    recs = build((200, 150, 150), group_of=lambda i, lab: train_group if lab == "unclear" else "e%d" % i)
    test = {r["record_id"]: r["label"] for r in recs if o_split(seed, r["group_id"]) == "test"}
    assert "unclear" not in test.values()
    assert err(evaluate, recs, test, seed) == code("EMPTY_CLASS", "test")


def test_evaluate_is_deterministic_and_pure():
    seed = "eval-seed"
    recs = build((200, 150, 150))
    test = {r["record_id"]: r["label"] for r in recs if o_split(seed, r["group_id"]) == "test"}
    before, pbefore = copy.deepcopy(recs), copy.deepcopy(test)
    a = evaluate(recs, test, seed)
    assert evaluate(recs, test, seed) == a and recs == before and test == pbefore
    a["limits"].append("x")
    assert len(evaluate(recs, test, seed)["limits"]) == 4
    g = gate_status(recs)
    g["limits"].append("x")
    assert len(gate_status(recs)["limits"]) == 4


# ------------------------------------------------------------------ purity and docs
def test_ast_purity():
    tree = ast.parse(SRC.read_text())
    imports = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            imports.add((n.module or "").split(".")[0] if n.level == 0 else "." + (n.module or ""))
    assert imports <= {"__future__", "hashlib", "re", "unicodedata", "typing", "datetime", ".classifier"}, imports
    banned = {"open", "exec", "eval", "compile", "__import__", "input", "print", "getattr", "setattr", "globals", "locals"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            assert n.func.id not in banned, n.func.id
        if isinstance(n, ast.Attribute):
            assert n.attr not in {"system", "popen", "run", "urlopen", "read_text", "write_text", "environ"}, n.attr
    text = SRC.read_text()
    for word in ("transformers", "torch", "requests", "urllib", "socket", "subprocess", "random", "import time"):
        assert word not in text, word


def test_module_not_wired_in_this_unit():
    hits = [str(p) for p in (ROOT / "backend").rglob("*.py") if p != SRC and "eligibility_labels" in p.read_text()]
    assert hits == []


def test_doc_contract():
    doc = DOC.read_text()
    assert "ELIGLAB_REFUSED_" in doc and "fine_tune_ready" in doc and "500" in doc and "100" in doc
    for needle in ("Colab", "T4", "checkpoint", "human_reviewed", "synthetic", "INTERPRETATION CHOICE", "## LIMITS"):
        assert needle in doc, needle
    for banned in ("ledger", "integrator", "private", ".json", ".jsonl", "delivery folder"):
        assert banned not in doc.lower(), banned
    for n in ("20000", "8000", "128", "10000"):
        assert n in doc, n


# ---- pins added after the mutation battery (post-red additions, disclosed)
def test_pin_line_breaks_refused_in_non_prose_fields():
    for f, good in (("record_id", "a"), ("group_id", "a"), ("label", "eligible"), ("label_source", "human_reviewed"),
                    ("reviewer", "a"), ("reviewed_at", "2026-10-1")):
        for ch in ("\n", "\r", "\t"):
            assert err(add_label, [], rec(0, **{f: good + ch})) == code("CONTROL_CHARS", f), (f, repr(ch))
    for f in ("text", "profile"):
        for ch in ("\n", "\r", "\t"):
            assert add_label([], rec(0, **{f: "a" + ch + "b"}))[0][f] == "a" + ch + "b"


def test_pin_predictions_cap_exact():
    recs = CORPUS
    over = {"x%d" % i: "eligible" for i in range(20001)}
    assert err(evaluate, recs, over, "s") == code("OVERSIZE", "predictions")
    exact = {"x%d" % i: "eligible" for i in range(20000)}
    assert err(evaluate, recs, exact, "s") == code("UNKNOWN", "predictions")


def test_pin_gate_status_shape_and_limits_exact():
    g = gate_status(CORPUS)
    assert set(g) == {"algorithm", "total", "counts", "ready", "required_total", "required_per_class",
                      "total_shortfall", "class_shortfalls", "label_source_counted", "model_trained",
                      "labels_generated", "limits"}
    assert g["algorithm"] == "eligibility_label_harness_v1"
    assert g["model_trained"] is False and g["labels_generated"] is False
    s = split_records(CORPUS, "s")
    assert s["algorithm"] == "eligibility_label_harness_v1" and s["model_trained"] is False and s["labels_generated"] is False
    assert len(g["limits"]) == 4 and g["limits"] == list(mod.LIMITS)
    assert g["limits"][0].startswith("labels are caller-supplied: this unit does not verify that a reviewer exists")
    assert g["limits"][1].startswith("no model is trained, loaded or evaluated here: held-out metrics are computed only from")
    assert g["limits"][2].startswith("readiness is classifier.fine_tune_ready over human-reviewed labels only; synthetic")
    assert g["limits"][3].startswith("metrics describe the supplied held-out records only and say nothing about other")
    for lim in g["limits"]:
        assert lim.endswith(("took place", "supplied predictions", "are refused", "applicants"))


def test_pin_category_co_characters_are_allowed():
    # INTERPRETATION CHOICE: only Cc, Cf, Zl, Zp are refused; category Co code points are ordinary text
    assert add_label([], rec(0, text="a\ue000b"))[0]["text"] == "a\ue000b"
