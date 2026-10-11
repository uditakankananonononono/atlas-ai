"""Row 696 Branch by Abstraction: executable migration-state engine tests."""
import pytest

from app.modules.m20_general_cognitive_worker.branch_abstraction696 import (
    BranchAbstractionError,
    BranchByAbstraction,
)


class OldPricer:
    def price(self, qty):
        if qty < 0:
            raise ValueError("neg")
        return qty * 10

    def name(self):
        return "old"


class NewPricer:
    def price(self, qty):
        if qty < 0:
            raise ValueError("neg")
        return qty * 10

    def name(self):
        return "new"


class BuggyPricer(NewPricer):
    def price(self, qty):
        if qty < 0:
            raise ValueError("neg")
        return qty * 10 + (1 if qty > 5 else 0)


def make(new=None, **kw):
    return BranchByAbstraction("Pricer", ["price"], OldPricer(), new or NewPricer(), **kw)


def test_initial_phase_and_routes_to_old():
    b = make()
    assert b.phase == "introduce"
    assert b.call("price", 3) == 30


def test_rejects_missing_operation_on_implementation():
    class Partial:
        pass

    with pytest.raises(BranchAbstractionError, match="new.*price"):
        BranchByAbstraction("P", ["price"], OldPricer(), Partial())
    with pytest.raises(BranchAbstractionError, match="old.*price"):
        BranchByAbstraction("P", ["price"], Partial(), NewPricer())


def test_rejects_bad_inputs():
    with pytest.raises(BranchAbstractionError):
        BranchByAbstraction("", ["price"], OldPricer(), NewPricer())
    with pytest.raises(BranchAbstractionError):
        BranchByAbstraction("P", [], OldPricer(), NewPricer())
    with pytest.raises(BranchAbstractionError):
        BranchByAbstraction("P", ["price"], OldPricer(), NewPricer(), min_equivalence_cases=0)
    b = make()
    with pytest.raises(BranchAbstractionError):
        b.call("unknown", 1)
    with pytest.raises(BranchAbstractionError):
        b.set_route("bogus")
    with pytest.raises(BranchAbstractionError):
        b.set_route("canary", canary_percent=101)


def test_route_new_dispatches_to_new_implementation():
    b = make()
    b.set_route("new")
    assert b.phase == "switched"
    assert b.call("price", 2) == 20
    assert b.route_log[-1] == ("price", "new")


def test_shadow_returns_old_and_records_divergence():
    b = make(BuggyPricer())
    b.set_route("shadow")
    assert b.call("price", 9) == 90  # old result returned
    assert b.call("price", 2) == 20
    assert len(b.divergences) == 1
    d = b.divergences[0]
    assert d["operation"] == "price" and d["old"] == "90" and d["new"] == "91"
    assert b.phase == "dual_implementation"


def test_shadow_new_raising_is_a_divergence_not_a_crash():
    class Boom(NewPricer):
        def price(self, qty):
            raise RuntimeError("x")

    b = make(Boom())
    b.set_route("shadow")
    assert b.call("price", 1) == 10
    assert b.divergences[0]["new"].startswith("raises RuntimeError")


def test_canary_is_deterministic_per_key_and_percent_bounds():
    b = make()
    b.set_route("canary", canary_percent=0)
    assert all(b.route_for("k%d" % i) == "old" for i in range(50))
    b.set_route("canary", canary_percent=100)
    assert all(b.route_for("k%d" % i) == "new" for i in range(50))
    b.set_route("canary", canary_percent=50)
    first = [b.route_for("k%d" % i) for i in range(200)]
    assert first == [b.route_for("k%d" % i) for i in range(200)]
    share = first.count("new") / 200
    assert 0.35 < share < 0.65
    with pytest.raises(BranchAbstractionError, match="key"):
        b.call("price", 1)


def test_verify_equivalence_detects_divergence_and_exception_parity():
    good = make()
    r = good.verify_equivalence("price", [((0,), {}), ((3,), {}), ((-1,), {})])
    assert r["cases"] == 3 and r["matches"] == 3 and r["divergences"] == []
    bad = make(BuggyPricer())
    r = bad.verify_equivalence("price", [((1,), {}), ((9,), {})])
    assert r["matches"] == 1 and len(r["divergences"]) == 1
    assert r["divergences"][0]["case"] == 1


def test_verify_equivalence_requires_cases():
    with pytest.raises(BranchAbstractionError):
        make().verify_equivalence("price", [])


def test_scan_direct_usage_finds_real_references_via_ast():
    b = make()
    src = {
        "svc/a.py": "from legacy import OldPricer\nx = OldPricer()\n",
        "svc/b.py": "import legacy\ny = legacy.OldPricer().price(1)\n",
        "svc/c.py": "# OldPricer only in a comment\ns = 'OldPricer'\n",
        "svc/adapter.py": "from legacy import OldPricer\n",
        "svc/bad.py": "def (:\n",
    }
    f = b.scan_direct_usage(src, "OldPricer", allowed_files=["svc/adapter.py"])
    kinds = {(x["file"], x["kind"]) for x in f}
    assert ("svc/a.py", "import") in kinds and ("svc/a.py", "name") in kinds
    assert ("svc/b.py", "attribute") in kinds
    assert ("svc/bad.py", "unparseable") in kinds
    assert not any(x["file"] in ("svc/c.py", "svc/adapter.py") for x in f)


def _ready(b):
    b.register_caller("checkout")
    b.mark_caller_migrated("checkout")
    b.verify_equivalence("price", [((1,), {}), ((2,), {})])
    b.scan_direct_usage({"a.py": "x = 1\n"}, "OldPricer")
    b.set_route("new")


def test_cannot_remove_old_until_every_gate_met():
    b = make(min_equivalence_cases=2)
    ok, reasons = b.can_remove_old()
    assert not ok
    text = " ".join(reasons)
    for needle in ("route", "caller", "equivalence", "scan"):
        assert needle in text
    with pytest.raises(BranchAbstractionError):
        b.remove_old()
    _ready(b)
    assert b.can_remove_old() == (True, [])
    b.remove_old()
    assert b.phase == "old_removed"
    assert b.call("price", 4) == 40
    with pytest.raises(BranchAbstractionError):
        b.set_route("old")


def test_unmigrated_caller_divergence_and_dirty_scan_block_removal():
    b = make(min_equivalence_cases=2)
    _ready(b)
    b.register_caller("reports")
    assert any("reports" in r for r in b.can_remove_old()[1])
    b.mark_caller_migrated("reports")
    b.scan_direct_usage({"a.py": "OldPricer()\n"}, "OldPricer")
    assert any("scan" in r for r in b.can_remove_old()[1])
    b.scan_direct_usage({"a.py": "x=1\n"}, "OldPricer")
    assert b.can_remove_old()[0]
    b2 = make(BuggyPricer(), min_equivalence_cases=1)
    b2.register_caller("c"); b2.mark_caller_migrated("c")
    b2.verify_equivalence("price", [((9,), {})])
    b2.scan_direct_usage({}, "OldPricer"); b2.set_route("new")
    assert any("divergen" in r for r in b2.can_remove_old()[1])


def test_unknown_caller_and_duplicate_registration():
    b = make()
    with pytest.raises(BranchAbstractionError):
        b.mark_caller_migrated("ghost")
    b.register_caller("a")
    with pytest.raises(BranchAbstractionError):
        b.register_caller("a")


def test_rollback_restores_old_route_before_removal():
    b = make()
    b.set_route("new")
    b.rollback()
    assert b.route_for(None) == "old"
    assert b.call("price", 2) == 20 and b.route_log[-1] == ("price", "old")


def test_report_counts_name_what_they_count():
    b = make(min_equivalence_cases=2)
    _ready(b)
    r = b.report()
    assert r["phase"] == "switched"
    assert r["callers"] == {"registered": 1, "migrated": 1}
    assert r["equivalence"]["price"] == {"cases_compared": 2, "divergent_cases": 0}
    assert r["direct_usage_findings"] == 0
    assert r["can_remove_old"] is True


def test_shadow_old_raising_calls_old_once_and_propagates():
    class Counting(OldPricer):
        calls = 0

        def price(self, qty):
            Counting.calls += 1
            raise ValueError("neg")

    b = BranchByAbstraction("P", ["price"], Counting(), NewPricer())
    b.set_route("shadow")
    with pytest.raises(ValueError, match="neg"):
        b.call("price", 1)
    assert Counting.calls == 1


def test_equivalence_threshold_is_exact():
    b = make(min_equivalence_cases=3)
    b.register_caller("c"); b.mark_caller_migrated("c")
    b.verify_equivalence("price", [((1,), {}), ((2,), {})])
    b.scan_direct_usage({}, "OldPricer"); b.set_route("new")
    assert any("below 3" in r for r in b.can_remove_old()[1])
    b.verify_equivalence("price", [((3,), {})])
    assert b.can_remove_old() == (True, [])


def test_remove_old_really_drops_the_old_implementation():
    b = make()
    _ready(b)
    b.remove_old()
    with pytest.raises(BranchAbstractionError, match="removed"):
        b.verify_equivalence("price", [((1,), {})])
    assert b.can_remove_old() == (False, ["old implementation already removed"])


# ---- repair round: pins for constructs found unpinned by the audit ----------------------------
import hashlib

MSG_CANARY = "canary_percent must be an integer 0..100"


class RaisesOld:
    def price(self, qty):
        raise ValueError("old says neg")


class OkNew:
    def price(self, qty):
        return qty * 10


def test_shadow_reraises_the_old_exception_and_records_the_divergence():
    b = BranchByAbstraction("P", ["price"], RaisesOld(), OkNew())
    b.set_route("shadow")
    with pytest.raises(ValueError) as ei:
        b.call("price", 2)
    assert type(ei.value) is ValueError and str(ei.value) == "old says neg"
    assert b.divergences == [{"operation": "price", "old": "raises ValueError", "new": "20"}]
    assert b.route_log == [("price", "old")]


def test_shadow_same_exception_type_on_both_sides_is_not_a_divergence():
    class Both(RaisesOld):
        pass

    b = BranchByAbstraction("P", ["price"], RaisesOld(), Both())
    b.set_route("shadow")
    with pytest.raises(ValueError):
        b.call("price", 1)
    assert b.divergences == []


def test_shadow_logs_old_as_the_route_and_returns_old_result():
    b = make()
    b.set_route("shadow")
    assert b.call("price", 3) == 30
    assert b.call("price", 4) == 40
    assert b.route_log == [("price", "old"), ("price", "old")]


@pytest.mark.parametrize("bad", [101, 500, -1, "x", "5", 5.0, None, [5], 10**9])
def test_canary_refuses_out_of_range_and_non_integer_percent(bad):
    b = make()
    with pytest.raises(BranchAbstractionError) as ei:
        b.set_route("canary", canary_percent=bad)
    assert str(ei.value) == MSG_CANARY
    assert b.route_for("k") == "old"  # state unchanged after the refusal


@pytest.mark.parametrize("ok", [0, 1, 50, 100])
def test_canary_accepts_the_boundaries(ok):
    b = make()
    b.set_route("canary", canary_percent=ok)
    assert b.phase == "dual_implementation"


@pytest.mark.parametrize("bad", [True, False])
def test_canary_percent_refuses_booleans(bad):
    b = make()
    with pytest.raises(BranchAbstractionError):
        b.set_route("canary", canary_percent=bad)


# sha256("Pricer:<key>")[:8] as hex int, mod 100, computed with hashlib and fixed here
VECTOR = {"k0": 73, "k1": 89, "k2": 49, "k3": 91, "k4": 80, "k5": 72, "k6": 34, "k7": 89, "k8": 24, "k9": 62,
          "user-1": 35, "user-2": 76, 1: 76, 2: 15}


def test_canary_hash_vector_is_fixed():
    for key, bucket in VECTOR.items():
        digest = hashlib.sha256(f"Pricer:{key}".encode()).hexdigest()
        assert int(digest[:8], 16) % 100 == bucket  # the vector itself is right
    b = make()
    for pct in (0, 24, 25, 49, 50, 73, 74, 90, 91, 100):
        b.set_route("canary", canary_percent=pct)
        for key, bucket in VECTOR.items():
            assert b.route_for(key) == ("new" if bucket < pct else "old"), (pct, key, bucket)


def test_canary_zero_is_all_old_and_hundred_is_all_new_for_the_whole_vector():
    b = make()
    b.set_route("canary", canary_percent=0)
    assert {b.route_for(k) for k in VECTOR} == {"old"}
    b.set_route("canary", canary_percent=100)
    assert {b.route_for(k) for k in VECTOR} == {"new"}


def test_canary_is_salted_by_the_abstraction_name_and_key_is_stringified():
    a = BranchByAbstraction("Pricer", ["price"], OldPricer(), NewPricer())
    z = BranchByAbstraction("Other", ["price"], OldPricer(), NewPricer())
    a.set_route("canary", canary_percent=50)
    z.set_route("canary", canary_percent=50)
    assert [a.route_for(f"k{i}") for i in range(40)] != [z.route_for(f"k{i}") for i in range(40)]
    assert a.route_for(1) == a.route_for("1")
    a.set_route("canary", canary_percent=100)
    assert a.route_for(0) == "new"  # key 0 is a real key, not "no key"


def test_min_equivalence_cases_default_and_refusals():
    assert make().min_equivalence_cases == 1
    for bad in (0, -1, "1", 1.5, None):
        with pytest.raises(BranchAbstractionError) as ei:
            BranchByAbstraction("P", ["price"], OldPricer(), NewPricer(), min_equivalence_cases=bad)
        assert str(ei.value) == "min_equivalence_cases must be an integer >= 1"


@pytest.mark.parametrize("bad", [True, False])
def test_min_equivalence_cases_refuses_booleans(bad):
    with pytest.raises(BranchAbstractionError) as ei:
        BranchByAbstraction("P", ["price"], OldPricer(), NewPricer(), min_equivalence_cases=bad)
    assert str(ei.value) == "min_equivalence_cases must be an integer >= 1"


def test_phase_strings_in_order():
    b = make()
    assert b.phase == "introduce"
    b.register_caller("c")
    assert b.phase == "migrate_callers"
    b.verify_equivalence("price", [((1,), {})])
    assert b.phase == "dual_implementation"
    b.set_route("new")
    assert b.phase == "switched"
    assert make().phase == "introduce"
    c = make()
    c.register_caller("c")
    c.set_route("shadow")
    assert c.phase == "dual_implementation"


def test_scan_findings_have_exact_kind_and_line_numbers():
    src = {"a.py": "import OldPricer\nfrom x import OldPricer as Q\nz = a.OldPricer\nOldPricer()\n",
           "b.py": "def (:\n", "c.py": "\n\nx = (\n", "d.py": "x = 1\n"}
    f = make().scan_direct_usage(src, "OldPricer")
    assert f == [
        {"file": "a.py", "line": 1, "kind": "import"},
        {"file": "a.py", "line": 2, "kind": "import"},
        {"file": "a.py", "line": 3, "kind": "attribute"},
        {"file": "a.py", "line": 4, "kind": "name"},
        {"file": "b.py", "line": 1, "kind": "unparseable"},
        {"file": "c.py", "line": 3, "kind": "unparseable"},
    ]


def test_plain_import_of_the_old_name_is_found_by_the_scan():
    f = make().scan_direct_usage({"a.py": "import OldPricer\n"}, "OldPricer")
    assert f == [{"file": "a.py", "line": 1, "kind": "import"}]


def test_scan_import_alias_form_and_multiple_names_on_one_line():
    f = make().scan_direct_usage({"m.py": "from x import A, OldPricer, B\n"}, "OldPricer")
    assert f == [{"file": "m.py", "line": 1, "kind": "import"}]
    g = make().scan_direct_usage({"m.py": "from x import A as OldPricer\n"}, "OldPricer")
    assert g == []  # alias named like the symbol is an alias, the imported name is A


def test_files_are_scanned_in_sorted_order_and_scan_replaces_the_previous_result():
    b = make()
    f = b.scan_direct_usage({"z.py": "OldPricer\n", "a.py": "OldPricer\n"}, "OldPricer")
    assert [x["file"] for x in f] == ["a.py", "z.py"]
    assert b.report()["direct_usage_findings"] == 2
    b.scan_direct_usage({}, "OldPricer")
    assert b.report()["direct_usage_findings"] == 0


def test_removal_reasons_have_exact_text_on_a_fresh_object():
    b = make(min_equivalence_cases=2)
    ok, reasons = b.can_remove_old()
    assert ok is False and reasons == [
        "route is 'old', must be 'new'",
        "no callers registered",
        "equivalence for price below 2 cases",
        "no direct-usage scan recorded",
    ]
