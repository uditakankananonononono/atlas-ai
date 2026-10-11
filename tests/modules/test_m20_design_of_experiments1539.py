"""Row 1539 Design of Experiments: two-level fractional factorial plan structure."""
import importlib.util, pathlib, sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/m20_general_cognitive_worker/design_of_experiments1539.py"
DOC = ROOT / "docs/M20_DESIGN_OF_EXPERIMENTS1539_CONTRACT.md"
P = "DESEXP1539: "


def load(source=None, name="desexp1539"):
    spec = importlib.util.spec_from_file_location(name, SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if source is None:
        spec.loader.exec_module(mod)
    else:
        exec(compile(source, str(SRC), "exec"), mod.__dict__)
    return mod


MOD = load()
plan = MOD.plan_two_level_design


def req(factors, gens=None, did="d1"):
    p = {"design_id": did, "factors": list(factors)}
    if gens is not None:
        p["generators"] = gens
    return p


def gen(f, *prod):
    return {"factor": f, "product_of": list(prod)}


NOT_LIST = "invalid_product_of: product_of requires a list"
TOO_MANY = "invalid_count: product_of exceeds 8 entries"
TOO_FEW = "invalid_count: product_of requires at least 2 entries"
NOT_TEXT = "invalid_product_of: product_of entries require text"
TOO_LONG = "invalid_product_of: product_of entries exceed 128 characters"
BAD_CHARS = "invalid_product_of: product_of entries contain disallowed characters"
NOT_DECLARED = "invalid_product_of: product_of entries require declared factors"
NOT_DISTINCT = "invalid_product_of: product_of entries require distinct factors"


def refuse(payload, message):
    with pytest.raises(ValueError) as ei:
        plan(payload)
    assert str(ei.value) == P + message


def rows(out, factors):
    return [tuple(r[f] for f in factors) for r in out["run_matrix"]]


def test_exact_envelope_half_fraction_resolution_iv():
    out = plan(req("ABCD", [gen("D", "A", "B", "C")]))
    assert out == {
        "design_id": "d1", "design_type": "two_level_fractional_factorial", "fraction": "2^(4-1)",
        "factor_count": 4, "base_factors": ["A", "B", "C"],
        "generated_factors": [{"factor": "D", "product_of": ["A", "B", "C"]}],
        "run_count": 8,
        "run_matrix": [dict(zip("ABCD", r)) for r in (
            (-1, -1, -1, -1), (1, -1, -1, 1), (-1, 1, -1, 1), (1, 1, -1, -1),
            (-1, -1, 1, 1), (1, -1, 1, -1), (-1, 1, 1, -1), (1, 1, 1, 1))],
        "defining_relation": ["A*B*C*D"], "resolution": 4,
        "alias_classes": [["A*B", "C*D"], ["A*C", "B*D"], ["A*D", "B*C"]],
        "run_order": "standard order, not randomized", "randomization_required": True,
        "experiment_executed": False, "causal_claims_made": False, "boundary": MOD.BOUNDARY}


def test_two_generators_resolution_iii_aliases():
    out = plan(req("ABCDE", [gen("D", "A", "B"), gen("E", "A", "C")]))
    assert out["fraction"] == "2^(5-2)" and out["run_count"] == 8 and out["resolution"] == 3
    assert out["base_factors"] == ["A", "B", "C"]
    assert out["defining_relation"] == ["A*B*D", "A*C*E", "B*C*D*E"]
    assert out["alias_classes"] == [["A", "B*D", "C*E"], ["B", "A*D"], ["C", "A*E"], ["D", "A*B"],
                                    ["E", "A*C"], ["B*C", "D*E"], ["B*E", "C*D"]]
    assert rows(out, "ABCDE") == [
        (-1, -1, -1, 1, 1), (1, -1, -1, -1, -1), (-1, 1, -1, -1, 1), (1, 1, -1, 1, -1),
        (-1, -1, 1, 1, -1), (1, -1, 1, -1, 1), (-1, 1, 1, -1, -1), (1, 1, 1, 1, 1)]


def test_full_factorial_without_generators():
    for payload in (req("ABC"), req("ABC", [])):
        out = plan(payload)
        assert out["design_type"] == "full_factorial" and out["fraction"] == "2^3"
        assert out["resolution"] is None and out["defining_relation"] == [] and out["alias_classes"] == []
        assert out["generated_factors"] == [] and out["base_factors"] == ["A", "B", "C"]
        assert rows(out, "ABC") == [(-1, -1, -1), (1, -1, -1), (-1, 1, -1), (1, 1, -1),
                                    (-1, -1, 1), (1, -1, 1), (-1, 1, 1), (1, 1, 1)]


def test_named_factors_and_factor_order_in_words():
    out = plan(req(["temp", "time", "press", "flow"], [gen("flow", "temp", "time")]))
    assert out["defining_relation"] == ["temp*time*flow"] and out["resolution"] == 3
    assert out["alias_classes"] == [["temp", "time*flow"], ["time", "temp*flow"], ["flow", "temp*time"]]
    assert rows(out, ["temp", "time", "press", "flow"]) == [
        (-1, -1, -1, 1), (1, -1, -1, -1), (-1, 1, -1, -1), (1, 1, -1, 1),
        (-1, -1, 1, 1), (1, -1, 1, -1), (-1, 1, 1, -1), (1, 1, 1, 1)]
    assert list(out["run_matrix"][0]) == ["temp", "time", "press", "flow"]


def test_sixteen_run_two_generator_design():
    out = plan(req("ABCDEF", [gen("E", "A", "B", "C"), gen("F", "B", "C", "D")]))
    assert out["fraction"] == "2^(6-2)" and out["run_count"] == 16 and out["resolution"] == 4
    assert out["defining_relation"] == ["A*B*C*E", "A*D*E*F", "B*C*D*F"]
    assert out["alias_classes"] == [["A*B", "C*E"], ["A*C", "B*E"], ["A*D", "E*F"], ["A*E", "B*C", "D*F"],
                                    ["A*F", "D*E"], ["B*D", "C*F"], ["B*F", "C*D"]]


def test_matrix_is_orthogonal_and_generators_hold():
    out = plan(req("ABCDEF", [gen("E", "A", "B", "C"), gen("F", "B", "C", "D")]))
    m = out["run_matrix"]
    for f in "ABCDEF":
        assert sum(r[f] for r in m) == 0 and {r[f] for r in m} == {-1, 1}
    for a, b in (("A", "B"), ("A", "E"), ("C", "F"), ("D", "E")):
        assert sum(r[a] * r[b] for r in m) == 0
    assert all(r["E"] == r["A"] * r["B"] * r["C"] and r["F"] == r["B"] * r["C"] * r["D"] for r in m)


def test_resolution_two_design_is_allowed():
    out = plan(req("ABCD", [gen("C", "A", "B"), gen("D", "A", "B")]))
    assert out["run_count"] == 4 and out["resolution"] == 2
    assert out["defining_relation"] == ["C*D", "A*B*C", "A*B*D"]


def test_factor_count_bounds():
    refuse(req("A"), "factors requires a list of 2..12 names")
    refuse(req([]), "factors requires a list of 2..12 names")
    refuse({"design_id": "d", "factors": None}, "factors requires a list of 2..12 names")
    refuse({"design_id": "d", "factors": ("A", "B")}, "factors requires a list of 2..12 names")
    refuse({"design_id": "d"}, "factors requires a list of 2..12 names")
    refuse(req("ABCDEFGHIJKLM"), "factors requires a list of 2..12 names")
    assert plan(req("AB"))["run_count"] == 4
    twelve = list("ABCDEFGHIJKL")
    gens = [gen("G", "A", "B"), gen("H", "A", "C"), gen("I", "A", "D"), gen("J", "B", "C"),
            gen("K", "B", "D"), gen("L", "C", "D")]
    out = plan(req(twelve, gens))
    assert out["run_count"] == 64 and out["fraction"] == "2^(12-6)"


def test_generator_count_bound():
    gens = [gen("C", "A", "B")] * 7
    refuse(req("ABCDEFGHIJ", gens), "generators requires a list of 0..6 records")
    refuse(req("ABC", None) | {"generators": None}, "generators requires a list of 0..6 records")
    refuse(req("ABC", None) | {"generators": "x"}, "generators requires a list of 0..6 records")


def test_base_factor_bounds():
    assert plan(req("ABCDEFGH"))["run_count"] == 256
    refuse(req("ABCDEFGHI"), "base factors require at most 8 non-generated factors")
    assert plan(req("ABCDEFGHI", [gen("I", "A", "B")]))["run_count"] == 256
    refuse(req("ABCDEFGHIJ", [gen("J", "A", "B")]), "base factors require at most 8 non-generated factors")


def test_products_may_only_use_base_factors():
    refuse(req("ABC", [gen("C", "A", "B"), gen("B", "A", "C")]), "product_of may only use base factors")
    refuse(req("ABCD", [gen("D", "A", "C"), gen("C", "A", "B")]), "product_of may only use base factors")
    refuse(req("ABC", [gen("C", "A", "C")]), "product_of may only use base factors")
    refuse(req("ABC", [gen("A", "B", "C"), gen("B", "C", "A")]), "product_of may only use base factors")


def test_generator_record_refusals():
    refuse(req("ABC", ["x"]), "generator requires an object")
    refuse(req("ABC", [{"factor": "C", "product_of": ["A", "B"], "x": 1}]), "unknown key in generator")
    refuse(req("ABC", [gen("Z", "A", "B")]), "generator factor is not a declared factor")
    refuse(req("ABC", [{"factor": 3, "product_of": ["A", "B"]}]), "generator factor is not a declared factor")
    refuse(req("ABCD", [gen("C", "A", "B"), gen("C", "A", "D")]), "duplicate generator factor")
    for bad in (None, "AB", ("A", "B")):
        refuse(req("ABC", [{"factor": "C", "product_of": bad}]), NOT_LIST)
    for bad in (["A"], []):
        refuse(req("ABC", [{"factor": "C", "product_of": bad}]), TOO_FEW)
    refuse(req("ABC", [{"factor": "C", "product_of": ["A", "A"]}]), NOT_DISTINCT)
    refuse(req("ABC", [{"factor": "C", "product_of": ["A", "Z"]}]), NOT_DECLARED)
    refuse(req("ABC", [{"factor": "C", "product_of": ["A", 1]}]), NOT_TEXT)
    refuse(req("ABC", [{"factor": "C"}]), NOT_LIST)


def test_factor_name_and_payload_refusals():
    refuse(None, "payload requires an object")
    refuse([], "payload requires an object")
    p = req("AB"); p["x"] = 1
    refuse(p, "unknown key in payload")
    for bad in (None, "", " ", 3):
        refuse({"design_id": bad, "factors": ["A", "B"]}, "invalid_design_id: design_id requires non-blank text")
    for bad in ("", " ", 3, None, "A*B"):
        refuse(req(["A", bad]), "invalid_factor: factor names require non-blank text without '*'")
    refuse(req(["A", "A"]), "duplicate factor name")


def test_input_not_mutated_and_deterministic():
    import copy
    p = req("ABCDE", [gen("D", "A", "B"), gen("E", "A", "C")])
    snap = copy.deepcopy(p)
    a = plan(p)
    assert p == snap and a == plan(p)


def test_no_effect_surface():
    import inspect
    src = SRC.read_text()
    for w in ("import socket", "import subprocess", "import urllib", "open(", "import random", "float(", "datetime", "import time"):
        assert w not in src
    pub = [n for n, o in vars(MOD).items() if inspect.isfunction(o) and not n.startswith("_")
           and o.__module__ == MOD.__name__]
    assert pub == ["plan_two_level_design"]


def test_boundary_text_is_pinned():
    assert MOD.BOUNDARY == (
        'Plan structure only: coded two-level run matrix in standard order, defining '
        'relation, resolution and alias classes derived from the supplied generators. '
        'No experiment is run or scheduled, run order is not randomized, and no effect '
        'size, significance or causal claim is made.')


def test_contract_doc():
    t = DOC.read_text()
    for w in ("audits/additional-2000-features.json", "Design of Experiments", "title is the whole spec",
              "engineering_1510_1559.py:180", "DESEXP1539", "LIMITS", "Full test suite not run", "no decimal arithmetic",
              "cross-account builder package, provenance held privately", "resolution"):
        assert w in t
    for w in ("wamid", "HBgM"):
        assert w not in t


def test_two_generators_order_and_no_empty_alias_member():
    out = plan(req("ABCDE", [gen("D", "A", "B"), gen("E", "A", "C")]))
    assert out["generated_factors"] == [{"factor": "D", "product_of": ["A", "B"]},
                                        {"factor": "E", "product_of": ["A", "C"]}]
    assert out["defining_relation"] == ["A*B*D", "A*C*E", "B*C*D*E"]
    assert out["resolution"] == 3
    assert all(m for cls in out["alias_classes"] for m in cls)
    assert ["A", "B*D"] in [c[:2] for c in out["alias_classes"]]


def test_resolution_two_has_no_empty_alias_member():
    out = plan(req("ABCDEF", [gen("E", "A", "B", "C"), gen("F", "B", "C", "D")]))
    assert out["fraction"] == "2^(6-2)" and out["run_count"] == 16 and out["resolution"] == 4
    assert out["defining_relation"] == ["A*B*C*E", "A*D*E*F", "B*C*D*F"]
    assert out["alias_classes"] == [["A*B", "C*E"], ["A*C", "B*E"], ["A*D", "E*F"], ["A*E", "B*C", "D*F"],
                                    ["A*F", "D*E"], ["B*D", "C*F"], ["B*F", "C*D"]]


def test_resolution_two_design_has_no_empty_alias_member():
    out = plan(req("ABCDEF", [gen("E", "A", "B", "C"), gen("F", "A", "B", "C")]))
    assert out["defining_relation"] == ["E*F", "A*B*C*E", "A*B*C*F"]
    assert out["resolution"] == 2
    assert all(m for cls in out["alias_classes"] for m in cls)


UNSAFE = ("a\x00b", "a\nb", "a\tb", "\x1fa", "a\x7f", "a\x85", "a\x9f", "a\u2028", "a\u2029", "a\u202e",
          "a\u200b", "\ufeff", "a\u200f", "a\u202a", "a\u2066", "a\u2069", "a\u200c", "a\u200d", "a\u200e",
          "a\u202b", "a\u202c", "a\u202d", "a\u2067", "a\u2068")
SAFE = ("a b", "caf\u00e9", "\u65e5\u672c", "a\u200a", "a\u2010", "a\u202f", "a\u2065", "a\u206a", "a\ufefe",
        "a\u00a0", "a\u3000", "\U0001f600")
FIELDS = {
    "design_id": (lambda v: req("AB", did=v), "invalid_design_id", "design_id"),
    "factor": (lambda v: req(["A", v]), "invalid_factor", "factor names"),
}


def test_text_field_rules_and_unicode():
    for name, (make, code, label) in FIELDS.items():
        verb_long = "exceeds" if name == "design_id" else "exceed"
        verb_bad = "contains" if name == "design_id" else "contain"
        plan(make("x" * 128))
        refuse(make("x" * 129), f"{code}: {label} {verb_long} 128 characters")
        refuse(make("x" * 129 + "\u202e"), f"{code}: {label} {verb_long} 128 characters")
        for ok in SAFE:
            out = plan(make(ok))
            assert (out["design_id"] == ok) if name == "design_id" else (ok in out["base_factors"])
        for c in UNSAFE:
            refuse(make(c + "SECRETTAIL"), f"{code}: {label} {verb_bad} disallowed characters")


def test_seven_named_pins_on_each_field():
    for bad in ("\x85", "\u2028", "\u2029", "\u202e", "\u200b", "\ufeff", "\x7f"):
        refuse(req("AB", did="a" + bad), "invalid_design_id: design_id contains disallowed characters")
        refuse(req(["A", "b" + bad]), "invalid_factor: factor names contain disallowed characters")


def test_refusals_never_echo_caller_text():
    secret = "TOPSECRETNAME"
    cases = [req(["A", secret, secret]), req([secret, "B"], [gen("Z" + secret, "A", "B")]),
             req(["A", "B", secret], [gen(secret, secret + "x", "A")]),
             req(["A", "B", secret], [gen(secret, "A", "B"), gen(secret, "A", "B")]),
             req(["A", "B", secret], [gen(secret, "A", secret)]),
             req(["A", "B", secret, "D"], [gen(secret, "A", "B"), gen("D", secret, "A")]),
             req(["A", secret + "*"]), req(["A", secret + "\u202e"]), req(["A", "x" * 129 + secret]),
             req("AB", did=secret + "\x00"), req("AB", did=secret * 30)]
    for c in cases:
        with pytest.raises(ValueError) as ei:
            plan(c)
        assert "TOPSECRET" not in str(ei.value)


def test_unicode_doc_line():
    assert "no Unicode control, line/paragraph separator or bidi/format characters" in DOC.read_text()


def _peak_for(payload):
    import tracemalloc
    tracemalloc.start()
    tracemalloc.reset_peak()
    try:
        with pytest.raises(ValueError) as ei:
            plan(payload)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return peak, str(ei.value)


def test_cap_is_the_first_operation_no_large_allocation():
    big = "x" * (10 * 1024 * 1024) + " "
    peak, msg = _peak_for(req("AB", did=big))
    assert msg == P + "invalid_design_id: design_id exceeds 128 characters" and peak < 1_000_000
    peak, msg = _peak_for(req(["A", big]))
    assert msg == P + "invalid_factor: factor names exceed 128 characters" and peak < 1_000_000
    peak, msg = _peak_for(req(["A", big + "*"]))
    assert msg == P + "invalid_factor: factor names exceed 128 characters" and peak < 1_000_000


def test_oversize_blank_text_is_reported_as_oversize():
    refuse(req("AB", did=" " * 129), "invalid_design_id: design_id exceeds 128 characters")
    refuse(req("AB", did=" " * 128), "invalid_design_id: design_id requires non-blank text")
    refuse(req(["A", " " * 129]), "invalid_factor: factor names exceed 128 characters")
    refuse(req(["A", "*" * 129]), "invalid_factor: factor names exceed 128 characters")
    refuse(req(["A", "*" * 128]), "invalid_factor: factor names require non-blank text without '*'")


def test_first_operations_are_type_check_then_length():
    src = SRC.read_text()
    text = src[src.index("def _text"):src.index("return value", src.index("def _text"))]
    ops = [l.strip() for l in text.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(value) is not str:" and ops[1] == "if len(value) > MAX_TEXT:"


class Boom:
    """An entry that fails loudly if anything hashes, compares, reprs, iterates or stringifies it."""
    def _no(self, *a, **k):
        raise AssertionError("entry was touched")
    __hash__ = __eq__ = __ne__ = __repr__ = __str__ = __iter__ = __len__ = __bool__ = _no


def one_gen(product, factors="ABCDEFGHIJKL"):
    return req(factors, [{"factor": factors[-1], "product_of": product}])


def test_product_of_count_cap_n_and_n_plus_one():
    assert plan(req("ABCDEFGHI", [gen("I", *"ABCDEFGH")]))["run_count"] == 256   # 8 entries valid end to end
    refuse(one_gen(list("ABCDEFGHI")), TOO_MANY)                                  # 9 refused by count
    refuse(one_gen(list("ABCDEFGHIJKL")), TOO_MANY)
    refuse(one_gen(list("ABCDEFGH") + ["A"]), TOO_MANY)


def test_product_of_cap_is_checked_before_any_entry_is_touched():
    refuse(one_gen([Boom()] * 9), TOO_MANY)
    refuse(one_gen([Boom()] * (10 ** 6)), TOO_MANY)
    refuse(one_gen([Boom()] * 8), NOT_TEXT)         # within the cap: type check only, no hash/eq/repr
    refuse(one_gen([Boom()] * 2), NOT_TEXT)
    refuse(one_gen(["A", Boom()]), NOT_TEXT)


def test_product_of_minimum_after_maximum():
    refuse(one_gen(["A"]), TOO_FEW)
    refuse(one_gen([]), TOO_FEW)
    refuse(one_gen([Boom()]), TOO_FEW)               # too few is decided from the length alone


def test_product_of_requires_an_exact_list():
    class Evil(list):
        def __iter__(self):
            raise AssertionError("iterated")
        def __len__(self):
            raise AssertionError("len called")
        __getitem__ = __contains__ = __iter__
    for bad in (None, "AB", ("A", "B"), {"A", "B"}, {"A": 1, "B": 2}, 5, 1.5, True, Evil(["A", "B"]), iter(["A", "B"])):
        refuse(one_gen(bad), NOT_LIST)


def test_product_of_entry_rules_and_order():
    refuse(one_gen(["A", 1]), NOT_TEXT)
    refuse(one_gen(["A", None]), NOT_TEXT)
    refuse(one_gen(["A", b"B"]), NOT_TEXT)
    refuse(one_gen(["A", ["B"]]), NOT_TEXT)
    refuse(one_gen(["A", "x" * 129]), TOO_LONG)
    refuse(one_gen(["A", "x" * 129 + "\u202e"]), TOO_LONG)
    refuse(one_gen(["A", "B\u202e"]), BAD_CHARS)
    refuse(one_gen(["A", "B\u200b"]), BAD_CHARS)
    refuse(one_gen(["A", "B\x00"]), BAD_CHARS)
    refuse(one_gen(["A", "Z"]), NOT_DECLARED)
    refuse(one_gen(["A", " "]), NOT_DECLARED)
    refuse(one_gen(["A", "a"]), NOT_DECLARED)        # exact string equality, no case folding
    refuse(one_gen(["A", "A"]), NOT_DISTINCT)
    refuse(one_gen(["A", "B", "A"]), NOT_DISTINCT)
    assert plan(req(["A", "B", "C"], [gen("C", "A", "B")]))["run_count"] == 4


def test_product_of_oversize_entry_is_refused_without_a_large_allocation():
    big = "x" * (10 * 1024 * 1024) + " "
    peak, msg = _peak_for(one_gen(["A", big]))
    assert msg == P + TOO_LONG and peak < 1_000_000


def test_product_of_refusals_never_echo_values_or_indexes():
    secret = "TOPSECRETENTRY"
    for payload in (one_gen(["A", secret]), one_gen(["A", secret * 20]), one_gen(["A", secret + "\u202e"]),
                    one_gen([secret, secret]), one_gen([secret] * 13)):
        with pytest.raises(ValueError) as ei:
            plan(payload)
        msg = str(ei.value)
        assert "TOPSECRET" not in msg


def test_product_of_helper_has_no_repr_and_checks_list_then_length_first():
    src = SRC.read_text()
    assert "repr" not in src
    body = src[src.index("def _product"):src.index("def _generators")]
    ops = [l.strip() for l in body.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(product) is not list:" and ops[1] == "if len(product) > MAX_PRODUCT:"


def test_product_of_entries_must_be_exact_str_and_boundary_length():
    class S(str):
        def __eq__(self, other):
            raise AssertionError("compared")
        __hash__ = __eq__
    refuse(one_gen(["A", S("B")]), NOT_TEXT)
    refuse(one_gen(["A", "x" * 128]), NOT_DECLARED)
    refuse(one_gen(["A", "x" * 129]), TOO_LONG)


def test_declared_names_are_matched_as_a_set():
    assert "declared = frozenset(factors)" in SRC.read_text()


def _refusal(product):
    with pytest.raises(ValueError) as ei:
        plan(one_gen(product))
    return str(ei.value)


def test_over_cap_refusal_never_echoes_the_count_or_entry_values():
    token = "TOKENVALUE-xyz"
    for product, count in ((list("ABCDEFGHIJKLM"), "13"), ([token] * 13, "13"),
                           ([token] * (10 ** 6), "1000000")):
        msg = _refusal(product)
        assert msg == P + TOO_MANY
        assert "invalid_count" in msg and "product_of" in msg
        assert count not in msg and "1_000_000" not in msg and token not in msg
        assert "13" not in msg and "1000000" not in msg
