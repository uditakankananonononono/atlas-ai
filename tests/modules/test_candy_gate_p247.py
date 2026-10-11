"""Unit 9 [P247|L195]: declared-input release gate (offline, stdlib only).

The module is loaded by file path and does not depend on a package marker in
backend/app/modules/instinct_doc (another unit's __init__.py may exist there and
is not asserted either way). The gate computes each gate state from
supplied observations; caller labels are refused. GREEN is not proof that work
is complete.
"""
import importlib.util
import itertools
import pathlib
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MOD_PATH = ROOT / "backend/app/modules/instinct_doc/candy_gate_p247.py"


def _load(path=MOD_PATH, name="candy_gate_p247"):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


g = _load()
NOW = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
SHA = "a" * 64
SHB = "b" * 64


def gate(gid, kind, **kw):
    return {"id": gid, "kind": kind, **kw}


def ev(gates, obs, **kw):
    return g.evaluate({"gates": gates}, obs, **kw)


def state(res, gid):
    return next(x for x in res["gates"] if x["id"] == gid)


# ---------------- release logic ----------------
def test_release_when_every_declared_gate_computed_green():
    gates = [gate("files", "all_present", required=["a", "b"]), gate("n", "count_equals", expected=3),
             gate("d", "digest_equals", expected_sha256=SHA), gate("f", "fresh_within", max_age_days=7)]
    obs = {"files": {"present": ["b", "a", "c"]}, "n": {"count": 3}, "d": {"sha256": SHA},
           "f": {"checked_at": (NOW - timedelta(days=7)).isoformat()}}
    res = ev(gates, obs, now=NOW)
    assert res["release"] is True and res["blocked_by"] == []
    assert [x["state"] for x in res["gates"]] == ["GREEN"] * 4
    assert res["counts"] == {"gates": 4, "GREEN": 4, "RED": 0, "MISSING": 0, "INVALID": 0}


def test_empty_gate_list_never_releases():
    res = ev([], {})
    assert res["release"] is False and res["blocked_by"] == [] and res["counts"]["gates"] == 0
    assert res["reason"] == "no_gates_declared"


def test_exhaustive_green_red_combinations_release_iff_all_green():
    for n in (1, 2, 3, 4):
        for flags in itertools.product([True, False], repeat=n):
            gates = [gate(f"g{i}", "count_equals", expected=5) for i in range(n)]
            obs = {f"g{i}": {"count": 5 if ok else 4} for i, ok in enumerate(flags)}
            res = ev(gates, obs)
            assert res["release"] is all(flags)
            assert res["blocked_by"] == [f"g{i}" for i, ok in enumerate(flags) if not ok]


def test_missing_observation_blocks():
    res = ev([gate("a", "count_equals", expected=1), gate("b", "count_equals", expected=1)], {"a": {"count": 1}})
    assert res["release"] is False and res["blocked_by"] == ["b"]
    assert state(res, "b") == {"id": "b", "kind": "count_equals", "state": "MISSING", "reason": "missing_observation"}


def test_one_red_among_green_blocks_and_names_it():
    res = ev([gate("a", "count_equals", expected=1), gate("b", "count_equals", expected=2)],
             {"a": {"count": 1}, "b": {"count": 3}})
    assert res["release"] is False and res["blocked_by"] == ["b"]
    assert state(res, "b")["state"] == "RED" and state(res, "b")["reason"] == "count_mismatch"


# ---------------- caller labels are not inputs ----------------
@pytest.mark.parametrize("label", ["status", "green", "done", "passed", "complete", "ok", "result", "verdict", "approved"])
def test_label_fields_in_observation_make_gate_invalid(label):
    res = ev([gate("a", "count_equals", expected=1)], {"a": {"count": 1, label: "GREEN"}})
    assert res["release"] is False
    assert state(res, "a")["state"] == "INVALID" and state(res, "a")["reason"] == f"unsupported_observation_field:{label}"


@pytest.mark.parametrize("label", ["status", "green", "done", "passed", "state", "release"])
def test_label_fields_in_spec_gate_refused(label):
    with pytest.raises(ValueError, match=rf"^gate a has unsupported field {label}$"):
        ev([{**gate("a", "count_equals", expected=1), label: "GREEN"}], {})


def test_label_only_observation_for_declared_gate_is_invalid_not_green():
    res = ev([gate("a", "count_equals", expected=1)], {"a": {"status": "GREEN"}})
    assert res["release"] is False and state(res, "a")["state"] == "INVALID"


def test_observation_for_undeclared_gate_refused():
    with pytest.raises(ValueError, match=r"^observation for unknown gate zz-fresh$"):
        ev([gate("a", "count_equals", expected=1)], {"a": {"count": 1}, "zz-fresh": {"count": 1}})


# ---------------- per-kind semantics and boundaries ----------------
def test_all_present_missing_items_listed_sorted():
    res = ev([gate("f", "all_present", required=["c", "a", "b"])], {"f": {"present": ["b"]}})
    assert state(res, "f")["state"] == "RED" and state(res, "f")["reason"] == "missing_items:a,c"


def test_all_present_extra_items_fine_and_empty_present_red():
    assert ev([gate("f", "all_present", required=["a"])], {"f": {"present": ["a", "z"]}})["release"] is True
    assert ev([gate("f", "all_present", required=["a"])], {"f": {"present": []}})["release"] is False


@pytest.mark.parametrize("bad", ["a", ["a", 1], [None], "", {"a": 1}])
def test_all_present_invalid_observation(bad):
    res = ev([gate("f", "all_present", required=["a"])], {"f": {"present": bad}})
    assert state(res, "f")["state"] == "INVALID" and state(res, "f")["reason"] == "invalid_observation:present"


def test_count_true_is_not_one():
    r = ev([gate("n", "count_equals", expected=1)], {"n": {"count": True}})
    assert r["release"] is False and state(r, "n")["state"] == "INVALID"


def test_count_exact_and_off_by_one_both_sides():
    for c, ok in [(5, True), (4, False), (6, False)]:
        assert ev([gate("n", "count_equals", expected=5)], {"n": {"count": c}})["release"] is ok
    assert ev([gate("n", "count_equals", expected=0)], {"n": {"count": 0}})["release"] is True


@pytest.mark.parametrize("bad", [True, "5", 5.0, None, -1])
def test_count_invalid_observation(bad):
    res = ev([gate("n", "count_equals", expected=5)], {"n": {"count": bad}})
    assert state(res, "n")["state"] == "INVALID" and state(res, "n")["reason"] == "invalid_observation:count"


def test_digest_match_mismatch_and_malformed():
    assert ev([gate("d", "digest_equals", expected_sha256=SHA)], {"d": {"sha256": SHA}})["release"] is True
    r = ev([gate("d", "digest_equals", expected_sha256=SHA)], {"d": {"sha256": SHB}})
    assert state(r, "d")["state"] == "RED" and state(r, "d")["reason"] == "digest_mismatch"
    for bad in ("A" * 64, "a" * 63, "a" * 65, "g" * 64, 5, None):
        r = ev([gate("d", "digest_equals", expected_sha256=SHA)], {"d": {"sha256": bad}})
        assert state(r, "d")["state"] == "INVALID" and state(r, "d")["reason"] == "invalid_observation:sha256"


def test_fresh_within_boundaries():
    mk = lambda ts: ev([gate("f", "fresh_within", max_age_days=7)], {"f": {"checked_at": ts}}, now=NOW)
    assert mk((NOW - timedelta(days=7)).isoformat())["release"] is True
    r = mk((NOW - timedelta(days=7, seconds=1)).isoformat())
    assert state(r, "f")["state"] == "RED" and state(r, "f")["reason"] == "stale"
    assert mk(NOW.isoformat())["release"] is True
    r = mk((NOW + timedelta(seconds=1)).isoformat())
    assert state(r, "f")["state"] == "RED" and state(r, "f")["reason"] == "checked_at_future"
    for bad in ("2026-10-01T00:00:00", "nope", 5, None, ""):
        r = mk(bad)
        assert state(r, "f")["state"] == "INVALID" and state(r, "f")["reason"] == "invalid_observation:checked_at"
    assert mk("2026-10-11T11:00:00Z")["release"] is True
    r = mk("2026-10-11T11:00:00")  # recent but timezone-less: never GREEN
    assert state(r, "f")["state"] == "INVALID" and r["release"] is False


def test_fresh_gate_needs_aware_now():
    with pytest.raises(ValueError, match=r"^now is required for fresh_within gates$"):
        ev([gate("f", "fresh_within", max_age_days=7)], {"f": {"checked_at": NOW.isoformat()}})
    with pytest.raises(ValueError, match=r"^now must be a timezone-aware datetime$"):
        ev([gate("f", "fresh_within", max_age_days=7)], {}, now=datetime(2026, 10, 11))
    assert ev([gate("n", "count_equals", expected=1)], {"n": {"count": 1}})["release"] is True


# ---------------- spec validation: exact errors, bounds ----------------
def test_spec_errors_exact():
    with pytest.raises(ValueError, match=r"^spec must be an object$"):
        g.evaluate([], {})
    with pytest.raises(ValueError, match=r"^spec has unsupported field release$"):
        g.evaluate({"gates": [], "release": True}, {})
    with pytest.raises(ValueError, match=r"^spec needs gates as a list$"):
        g.evaluate({"gates": "x"}, {})
    with pytest.raises(ValueError, match=r"^observations must be an object$"):
        ev([], [])
    with pytest.raises(ValueError, match=r"^gate 0 must be an object$"):
        ev([5], {})
    with pytest.raises(ValueError, match=r"^gate id must be a non-empty string$"):
        ev([{"id": " ", "kind": "count_equals", "expected": 1}], {})
    with pytest.raises(ValueError, match=r"^gate a has unknown kind magic$"):
        ev([gate("a", "magic")], {})
    with pytest.raises(ValueError, match=r"^duplicate gate id a$"):
        ev([gate("a", "count_equals", expected=1), gate("a", "count_equals", expected=1)], {})
    with pytest.raises(ValueError, match=r"^gate a needs expected$"):
        ev([gate("a", "count_equals")], {})
    for bad in (True, -1, 1.5, "1"):
        with pytest.raises(ValueError, match=r"^gate a expected must be a non-negative integer$"):
            ev([gate("a", "count_equals", expected=bad)], {})
    for bad in ([], "a", [""], ["a", "a"], [1]):
        with pytest.raises(ValueError, match=r"^gate a required must be a list of 1 to 200 unique non-empty strings$"):
            ev([gate("a", "all_present", required=bad)], {})
    with pytest.raises(ValueError, match=r"^gate a expected_sha256 must be 64 lowercase hex characters$"):
        ev([gate("a", "digest_equals", expected_sha256="A" * 64)], {})
    for bad in (0, 3651, True, "7", 1.5):
        with pytest.raises(ValueError, match=r"^gate a max_age_days must be an integer from 1 to 3650$"):
            ev([gate("a", "fresh_within", max_age_days=bad)], {}, now=NOW)
    with pytest.raises(ValueError, match=r"^gate a has unsupported field required$"):
        ev([gate("a", "count_equals", expected=1, required=["x"])], {})


def test_bounds_gates_N_and_N_plus_1():
    assert g.MAX_GATES == 50
    gates = [gate(f"g{i:02d}", "count_equals", expected=1) for i in range(50)]
    obs = {x["id"]: {"count": 1} for x in gates}
    assert ev(gates, obs)["release"] is True
    with pytest.raises(ValueError, match=r"^at most 50 gates are allowed, got 51$"):
        ev(gates + [gate("g50", "count_equals", expected=1)], obs)


def test_bounds_required_items_N_and_N_plus_1():
    assert g.MAX_REQUIRED == 200
    req = [f"r{i}" for i in range(200)]
    assert ev([gate("f", "all_present", required=req)], {"f": {"present": req}})["release"] is True
    with pytest.raises(ValueError, match=r"^gate f required must be a list of 1 to 200 unique non-empty strings$"):
        ev([gate("f", "all_present", required=req + ["r200"])], {})


def test_present_list_bound_makes_observation_invalid():
    assert g.MAX_PRESENT == 1000
    ok = [f"r{i}" for i in range(1000)]
    assert ev([gate("f", "all_present", required=["r0"])], {"f": {"present": ok}})["release"] is True
    r = ev([gate("f", "all_present", required=["r0"])], {"f": {"present": ok + ["x"]}})
    assert state(r, "f")["reason"] == "invalid_observation:present"


# ---------------- determinism, immutability, honest output ----------------
def test_unsorted_input_determinism():
    gates = [gate("c", "count_equals", expected=1), gate("a", "count_equals", expected=1), gate("b", "count_equals", expected=1)]
    obs = {"a": {"count": 1}, "b": {"count": 2}, "c": {"count": 1}}
    ref = ev(gates, obs)
    for perm in itertools.permutations(gates):
        assert ev(list(perm), dict(reversed(list(obs.items())))) == ref
    assert [x["id"] for x in ref["gates"]] == ["a", "b", "c"] and ref["blocked_by"] == ["b"]


def test_inputs_not_mutated():
    import copy
    spec = {"gates": [gate("a", "all_present", required=["x"])]}; obs = {"a": {"present": ["x", "y"]}}
    s0, o0 = copy.deepcopy(spec), copy.deepcopy(obs)
    g.evaluate(spec, obs)
    assert spec == s0 and obs == o0


def test_output_is_honest_and_has_no_send_action():
    res = ev([gate("a", "count_equals", expected=1)], {"a": {"count": 1}})
    assert res["feature"] == "candy_gate_p247" and res["source_lines"] == ["P247|L195"]
    assert "not proof" in res["method_limits"] and "declared" in res["method_limits"]
    assert res["action"] == "none" and "send" not in res
    text = MOD_PATH.read_text()
    for ch in "🍬🍭🍪🍮🎂🍩🍦🍨🍥🪄🧋🎀🍧🧁🍫💖🎉🥳":
        assert ch not in text
    for banned in ("import requests", "import httpx", "urllib.request", "socket", "subprocess", "open(", "import app", "os.environ"):
        assert banned not in text


def test_module_is_standalone_and_neutral_about_the_package_marker():
    """P247 neither relies on nor creates a package marker: it loads by file path, has no
    relative or app imports and only stdlib imports. Whether another unit's __init__.py
    exists in the directory is that unit's business and is not asserted here."""
    import ast
    tree = ast.parse(MOD_PATH.read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative import would depend on a package marker"
            roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
    assert roots <= {"__future__", "re", "datetime", "typing"}, roots
    standalone = _load(name="candy_gate_p247_standalone_probe")
    assert not standalone.__package__
    assert standalone.evaluate({"gates": []}, {})["reason"] == "no_gates_declared"


# ---------------- independent mutants ----------------
def _mutant(name, old, new):
    src = MOD_PATH.read_text()
    assert old in src, f"mutant {name}: anchor missing"
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "candy_gate_p247.py").write_text(src.replace(old, new, 1))
    return _load(d / "candy_gate_p247.py", f"cg_mut_{name}")


def _killed(m):
    def e(gates, obs, **kw):
        return m.evaluate({"gates": gates}, obs, **kw)
    def st(res, gid):
        return next(x for x in res["gates"] if x["id"] == gid)
    try:
        if e([], {})["release"] is not False: return True
        for n in (1, 2, 3):
            for flags in itertools.product([True, False], repeat=n):
                gs = [gate(f"g{i}", "count_equals", expected=5) for i in range(n)]
                ob = {f"g{i}": {"count": 5 if ok else 4} for i, ok in enumerate(flags)}
                r = e(gs, ob)
                if r["release"] is not all(flags) or r["blocked_by"] != [f"g{i}" for i, ok in enumerate(flags) if not ok]: return True
        if e([gate("a", "count_equals", expected=1), gate("b", "count_equals", expected=1)], {"a": {"count": 1}})["release"]: return True
        if e([gate("a", "count_equals", expected=1)], {"a": {"count": 1, "status": "GREEN"}})["release"]: return True
        if e([gate("a", "count_equals", expected=1)], {"a": {"status": "GREEN"}})["release"]: return True
        if e([gate("a", "count_equals", expected=5)], {"a": {"count": 6}})["release"]: return True
        if e([gate("a", "count_equals", expected=1)], {"a": {"count": True}})["release"]: return True
        if st(e([gate("a", "count_equals", expected=1)], {"a": {"count": True}}), "a")["state"] != "INVALID": return True
        if not e([gate("f", "all_present", required=["a"])], {"f": {"present": ["a", "z"]}})["release"]: return True
        if e([gate("f", "all_present", required=["a", "b"])], {"f": {"present": ["a"]}})["release"]: return True
        if e([gate("f", "all_present", required=["a"])], {"f": {"present": "a"}})["release"]: return True
        if e([gate("d", "digest_equals", expected_sha256=SHA)], {"d": {"sha256": SHB}})["release"]: return True
        if st(e([gate("d", "digest_equals", expected_sha256=SHA)], {"d": {"sha256": "A" * 64}}), "d")["state"] != "INVALID": return True
        fr = lambda ts: e([gate("f", "fresh_within", max_age_days=7)], {"f": {"checked_at": ts}}, now=NOW)["release"]
        if not fr((NOW - timedelta(days=7)).isoformat()): return True
        if fr((NOW - timedelta(days=7, seconds=1)).isoformat()): return True
        if not fr(NOW.isoformat()): return True
        if fr((NOW + timedelta(seconds=1)).isoformat()): return True
        if fr("2026-10-01T00:00:00") or fr("2026-10-11T11:00:00"): return True
        gs = [gate("c", "count_equals", expected=1), gate("a", "count_equals", expected=1)]
        if [x["id"] for x in e(gs, {"a": {"count": 1}, "c": {"count": 1}})["gates"]] != ["a", "c"]: return True
        for bad in (lambda: e([{**gate("a", "count_equals", expected=1), "status": "GREEN"}], {}),
                    lambda: e([gate("a", "count_equals", expected=1)], {"a": {"count": 1}, "zz": {"count": 1}}),
                    lambda: e([gate("a", "count_equals", expected=1), gate("a", "count_equals", expected=1)], {}),
                    lambda: e([gate(f"g{i}", "count_equals", expected=1) for i in range(51)], {}),
                    lambda: e([gate("f", "all_present", required=[f"r{i}" for i in range(201)])], {}),
                    lambda: e([gate("f", "fresh_within", max_age_days=7)], {}),
                    lambda: e([gate("a", "count_equals", expected=True)], {}),
                    lambda: e([gate("a", "digest_equals", expected_sha256="A" * 64)], {})):
            try:
                bad()
            except ValueError:
                continue
            return True
        r = e([gate("f", "all_present", required=["r0"])], {"f": {"present": [f"r{i}" for i in range(1001)]}})
        if st(r, "f")["state"] != "INVALID": return True
        return False
    except Exception:
        return True


MUTANTS = [
    ("empty_releases", "bool(results) and all(", "all("),
    ("any_instead_of_all", "release = bool(results) and all(", "release = bool(results) and any("),
    ("missing_is_green", "return 'MISSING', 'missing_observation'", "return 'GREEN', 'missing_observation'"),
    ("labels_allowed", "if k not in allowed_obs:", "if False:"),
    ("count_ge", "obs['count'] == gate['expected']", "obs['count'] >= gate['expected']"),
    ("count_bool_ok", "isinstance(c, bool) or ", ""),
    ("present_subset_reversed", "missing = sorted(set(gate['required']) - set(present))", "missing = sorted(set(present) - set(gate['required']))"),
    ("present_str_ok", "not isinstance(present, list) or ", ""),
    ("digest_mismatch_green", "obs_sha != gate['expected_sha256']", "False"),
    ("digest_format_unchecked", "not _HEX64.fullmatch(obs_sha)", "False"),
    ("stale_ge", "age > timedelta(days=gate['max_age_days'])", "age >= timedelta(days=gate['max_age_days'])"),
    ("future_ok", "if checked > now:", "if False:"),
    ("naive_ok", "dt.tzinfo is None or dt.utcoffset() is None", "False"),
    ("no_sort", "results.sort(key=lambda x: x['id'])", "pass"),
    ("spec_label_ok", "if k not in allowed:", "if False:"),
    ("unknown_obs_ok", "if oid not in ids:", "if False:"),
    ("dup_ok", "if gid in ids:", "if False:"),
    ("max_gates_off", "MAX_GATES = 50", "MAX_GATES = 51"),
    ("max_required_off", "MAX_REQUIRED = 200", "MAX_REQUIRED = 201"),
    ("max_present_off", "MAX_PRESENT = 1000", "MAX_PRESENT = 1001"),
    ("now_not_required", "if needs_now and now is None:", "if False:"),
    ("expected_bool_ok", "isinstance(e, bool) or ", ""),
]


@pytest.mark.parametrize("name,old,new", MUTANTS, ids=[m[0] for m in MUTANTS])
def test_mutant_is_killed(name, old, new):
    assert _killed(_mutant(name, old, new)), f"mutant {name} survived"


def test_negative_control_unmutated_not_killed():
    assert _killed(g) is False
