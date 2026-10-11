"""Row 1538 Measurement Systems Analysis: balanced crossed gauge R&R (ANOVA) from raw repeats."""
import importlib.util, pathlib, sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/m20_general_cognitive_worker/measurement_systems_analysis1538.py"
DOC = ROOT / "docs/M20_MEASUREMENT_SYSTEMS_ANALYSIS1538_CONTRACT.md"
P = "MEASYS1538: "


def load(source=None, name="measys1538"):
    spec = importlib.util.spec_from_file_location(name, SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if source is None:
        spec.loader.exec_module(mod)
    else:
        exec(compile(source, str(SRC), "exec"), mod.__dict__)
    return mod


MOD = load()
study = MOD.gauge_rr_study


def build(data, sid="g1"):
    """data[i][j] = list of repeat strings for part i, operator j."""
    ms = []
    for i, row in enumerate(data):
        for j, vals in enumerate(row):
            ms.append({"part": "P%d" % (i + 1), "operator": "O%d" % (j + 1), "values": list(vals)})
    return {"study_id": sid, "measurements": ms}


D1 = [[["10", "12"], ["11", "13"]], [["20", "22"], ["21", "23"]]]
D2 = [[["10", "12"], ["11", "13"]], [["20", "22"], ["25", "27"]]]
D3 = [[["5", "6", "7"], ["6", "8", "7"], ["9", "8", "10"]],
      [["15", "17", "16"], ["14", "16", "15"], ["18", "17", "19"]],
      [["25", "24", "26"], ["27", "26", "25"], ["22", "24", "23"]]]
D0 = [[["0", "0"], ["0", "0"]], [["0", "0"], ["0", "1"]]]
DP = [[["0", "0"], ["0", "3"]], [["1", "1"], ["1", "1"]]]
VC = ("repeatability", "interaction", "operator", "reproducibility", "part_to_part", "gage_rr", "total")


def refuse(payload, message):
    with pytest.raises(ValueError) as ei:
        study(payload)
    assert str(ei.value) == P + message


def comps(out):
    return out["variance_components"]


def test_exact_envelope_with_interaction_truncated():
    out = study(build(D1))
    assert out == {
        "study_id": "g1", "parts": 2, "operators": 2, "replicates": 2, "grand_mean": "16.5",
        "variance_components": {"repeatability": "2", "interaction": "0", "operator": "0.5",
                                "reproducibility": "0.5", "part_to_part": "50", "gage_rr": "2.5", "total": "52.5"},
        "standard_deviations": {"repeatability": "1.414213562", "interaction": "0", "operator": "0.707106781",
                                "reproducibility": "0.707106781", "part_to_part": "7.071067812",
                                "gage_rr": "1.58113883", "total": "7.245688373"},
        "percent_contribution": {"repeatability": "3.80952381", "reproducibility": "0.952380952",
                                 "gage_rr": "4.761904762", "part_to_part": "95.238095238"},
        "truncated_components": ["interaction"],
        "method": "balanced crossed two-factor ANOVA, variance components from mean squares",
        "gauge_approval_claimed": False, "boundary": MOD.BOUNDARY}


def test_interaction_present_nothing_truncated():
    out = study(build(D2))
    assert comps(out) == {"repeatability": "2", "interaction": "3", "operator": "2.5", "reproducibility": "5.5",
                          "part_to_part": "70", "gage_rr": "7.5", "total": "77.5"}
    assert out["truncated_components"] == [] and out["grand_mean"] == "17.5"
    assert out["standard_deviations"]["gage_rr"] == "2.738612788"
    assert out["percent_contribution"] == {"repeatability": "2.580645161", "reproducibility": "7.096774194",
                                           "gage_rr": "9.677419355", "part_to_part": "90.322580645"}


def test_three_parts_three_operators_three_repeats_operator_truncated():
    out = study(build(D3))
    assert (out["parts"], out["operators"], out["replicates"], out["grand_mean"]) == (3, 3, 3, "16.111111111")
    assert comps(out) == {"repeatability": "1", "interaction": "2.777777778", "operator": "0",
                          "reproducibility": "2.777777778", "part_to_part": "74.111111111",
                          "gage_rr": "3.777777778", "total": "77.888888889"}
    assert out["truncated_components"] == ["operator"]
    assert out["percent_contribution"]["gage_rr"] == "4.85021398"


def test_part_component_truncated():
    out = study(build(DP))
    assert out["truncated_components"] == ["part_to_part"]
    assert comps(out)["part_to_part"] == "0" and comps(out)["gage_rr"] == "1.125"
    assert out["percent_contribution"]["gage_rr"] == "100"


def test_components_exactly_zero_are_not_truncated():
    # every mean square equals the error mean square: raw components are exactly 0, not negative
    out = study(build(D0))
    assert out["truncated_components"] == []
    assert comps(out) == {"repeatability": "0.125", "interaction": "0", "operator": "0", "reproducibility": "0",
                          "part_to_part": "0", "gage_rr": "0.125", "total": "0.125"}
    assert out["percent_contribution"]["part_to_part"] == "0"


def test_unequal_parts_and_operators_three_by_two():
    d = [[["0", "1"], ["7", "5"]], [["9", "8"], ["9", "8"]], [["3", "4"], ["7", "8"]]]
    out = study(build(d))
    assert (out["parts"], out["operators"], out["replicates"], out["grand_mean"]) == (3, 2, 2, "5.75")
    assert comps(out) == {"repeatability": "0.75", "interaction": "3.666666667", "operator": "3.666666667",
                          "reproducibility": "7.333333333", "part_to_part": "4.916666667",
                          "gage_rr": "8.083333333", "total": "13"}
    assert out["standard_deviations"]["total"] == "3.605551275"
    assert out["percent_contribution"] == {"repeatability": "5.769230769", "reproducibility": "56.41025641",
                                           "gage_rr": "62.179487179", "part_to_part": "37.820512821"}
    assert out["truncated_components"] == []


def test_unequal_parts_and_operators_two_by_three():
    d = [[["8", "8"], ["9", "7"], ["5", "1"]], [["4", "0"], ["2", "6"], ["1", "4"]]]
    out = study(build(d))
    assert (out["parts"], out["operators"], out["grand_mean"]) == (2, 3, "4.583333333")
    assert comps(out) == {"repeatability": "5.083333333", "interaction": "1.333333333", "operator": "0.833333333",
                          "reproducibility": "2.166666667", "part_to_part": "4.833333333",
                          "gage_rr": "7.25", "total": "12.083333333"}
    assert out["percent_contribution"]["gage_rr"] == "60" and out["percent_contribution"]["part_to_part"] == "40"


def test_two_truncated_components_are_listed_in_fixed_order():
    d = [[["5", "2"], ["6", "0"]], [["1", "8"], ["1", "5"]], [["9", "0"], ["8", "3"]]]
    out = study(build(d))
    assert out["truncated_components"] == ["interaction", "operator"]
    assert comps(out)["part_to_part"] == "0.416666667" and comps(out)["gage_rr"] == "18"
    assert out["percent_contribution"] == {"repeatability": "97.737556561", "reproducibility": "0",
                                           "gage_rr": "97.737556561", "part_to_part": "2.262443439"}
    d = [[["0", "1"], ["6", "6"], ["1", "3"]], [["1", "8"], ["6", "0"], ["9", "1"]]]
    out = study(build(d))
    assert out["truncated_components"] == ["operator", "part_to_part"]
    assert comps(out)["interaction"] == "0.75" and comps(out)["total"] == "13.583333333"


def test_record_order_does_not_matter_parts_sorted():
    a = build(D2)
    b = build(D2)
    b["measurements"].reverse()
    assert study(a) == study(b)


def test_minimum_and_maximum_study_sizes():
    study(build(D1))  # 2 parts x 2 operators x 2 repeats is the minimum
    big = [[["1", str(2 + (i + j) % 3)] for j in range(20)] for i in range(50)]
    out = study(build(big))
    assert (out["parts"], out["operators"], out["replicates"]) == (50, 20, 2)
    rep20 = [[[str(k % 5) for k in range(20)] for _ in range(2)] for _ in range(2)]
    rep20[1][1][0] = "9"
    assert study(build(rep20))["replicates"] == 20


def test_count_bounds_n_and_n_plus_one():
    refuse({"study_id": "s", "measurements": build(D1)["measurements"][:3]}, "measurements requires a list of 4..1000 records")
    refuse({"study_id": "s", "measurements": None}, "measurements requires a list of 4..1000 records")
    refuse({"study_id": "s", "measurements": ()}, "measurements requires a list of 4..1000 records")
    big = [[["1", "2"] for _ in range(20)] for _ in range(51)]  # 1020 cells
    refuse(build(big), "measurements requires a list of 4..1000 records")
    big51 = [[["1", "2"] for _ in range(19)] for _ in range(51)]  # 969 cells, 51 parts
    refuse(build(big51), "parts requires 2..50 distinct parts")
    ops21 = [[["1", "2"] for _ in range(21)] for _ in range(2)]
    refuse(build(ops21), "operators requires 2..20 distinct operators")


def test_part_and_operator_minimums():
    refuse(build([[["1", "2"], ["2", "3"], ["3", "4"], ["4", "5"]]]), "parts requires 2..50 distinct parts")
    refuse(build([[["1", "2"]], [["2", "3"]], [["3", "4"]], [["4", "5"]]]), "operators requires 2..20 distinct operators")


def test_replicate_bounds_n_and_n_plus_one():
    for bad in ([], ["1"], ["1"] * 21, None, "12", ("1", "2")):
        p = build(D1)
        p["measurements"][0]["values"] = bad
        refuse(p, "values requires a list of 2..20 decimal strings")


def test_unbalanced_incomplete_duplicate():
    p = build(D1)
    p["measurements"][0]["values"] = ["10", "12", "11"]
    refuse(p, "unbalanced study: every cell requires the same number of values")
    p = build(D1)
    del p["measurements"][3]
    p["measurements"].append({"part": "P1", "operator": "O3", "values": ["1", "2"]})
    refuse(p, "incomplete study: every part requires every operator")
    p = build(D1)
    p["measurements"][1]["operator"] = "O1"
    refuse(p, "duplicate cell for one part and one operator")
    p = build(D1)
    p["measurements"][1]["operator"] = "SECRETOP"
    p["measurements"][0]["operator"] = "SECRETOP"
    p["measurements"][0]["part"] = "SECRETPART"
    p["measurements"][1]["part"] = "SECRETPART"
    with pytest.raises(ValueError) as ei:
        study(p)
    assert "SECRET" not in str(ei.value)


def test_record_and_field_refusals():
    refuse(None, "payload requires an object")
    refuse([], "payload requires an object")
    p = build(D1); p["x"] = 1
    refuse(p, "unknown key in payload")
    for bad in (None, "", " ", 5):
        p = build(D1); p["study_id"] = bad
        refuse(p, "invalid_study_id: study_id requires non-blank text")
    p = build(D1); p["measurements"][0] = "x"
    refuse(p, "measurement requires an object")
    p = build(D1); p["measurements"][0]["x"] = 1
    refuse(p, "unknown key in measurement")
    for f, label in (("part", "part"), ("operator", "operator")):
        for bad in (None, "", " ", 3):
            p = build(D1); p["measurements"][0][f] = bad
            refuse(p, f"invalid_{label}: {label} requires non-blank text")


SHAPE = "invalid_number: values require ASCII decimal strings such as -12.5"
LONG = "number_too_long: values require at most 80 characters"
PREC = "number_precision: values require at most 64 significant digits and 64 fraction digits"
RANGE = "number_range: values require |value| <= 1000000000000"


def with_value(v):
    p = build(D1)
    p["measurements"][0]["values"][0] = v
    return p


def test_value_bounds_n_and_n_plus_one():
    for ok in ("1000000000000", "-1000000000000", "1000000000000.0000000000"):
        study(with_value(ok))
    for bad in ("1000000000000.0000000001", "-1000000000000.1", "1000000000001", "9" * 13):
        refuse(with_value(bad), RANGE)


def test_bound_compare_is_exact_under_ambient_context():
    import decimal
    for prec in (2, 5, 28, 100):
        with decimal.localcontext() as ctx:
            ctx.prec = prec
            for bad in ("1000000000001", "1000000000000.0000000001", "-1000000000000.1"):
                refuse(with_value(bad), RANGE)
            study(with_value("1000000000000"))
            study(with_value("-1000000000000"))


def test_number_shape_refusals():
    for bad in (1, 1.5, None, True, [], {}, b"1", "abc", "", " ", "1,5", "0x10", "1e5", "1E5", "1e-999999999999999999",
                "+1", "01", "00", ".5", "5.", "-", "1_0", " 1", "1 ", "1\n", "NaN", "Infinity", "-Infinity",
                "sNaN", "1.2.3", "\u0661", "\uff11"):
        refuse(with_value(bad), SHAPE)
    study(with_value("0.5"))
    study(with_value("-0.0"))


def test_number_length_and_precision_n_and_n_plus_one():
    refuse(with_value("0." + "1" * 78), PREC)
    refuse(with_value("0." + "1" * 79), LONG)
    refuse(with_value("a" * 81), LONG)
    refuse(with_value("a" * 80), SHAPE)
    refuse(with_value("0." + "1" * 65), PREC)
    refuse(with_value("0." + "0" * 64 + "1"), PREC)
    refuse(with_value("1." + "1" * 64), PREC)
    refuse(with_value("-0." + "1" * 65), PREC)
    refuse(with_value("9" * 13 + "." + "1" * 65 + "z"), SHAPE)
    refuse(with_value("9" * 13 + "." + "1" * 65), PREC)
    refuse(with_value("9" * 90), LONG)
    study(with_value("0." + "1" * 64))
    study(with_value("-0." + "1" * 64))
    study(with_value("0." + "0" * 63 + "1"))
    study(with_value("1" * 12 + "." + "1" * 51))
    refuse(with_value("1" * 12 + "." + "1" * 53), PREC)


def test_refusal_never_echoes_input():
    for bad in ("TOPSECRET" * 20, "TOPSECRET1e5"):
        with pytest.raises(ValueError) as ei:
            study(with_value(bad))
        assert "TOPSECRET" not in str(ei.value)


def test_ambient_context_cannot_change_output():
    import decimal
    base = study(build(D3))
    base2 = study(build(D1))
    variants = [dict(prec=2), dict(prec=100), dict(rounding=decimal.ROUND_DOWN), dict(rounding=decimal.ROUND_UP),
                dict(traps=[]), dict(Emax=1, Emin=-1), dict(prec=1, rounding=decimal.ROUND_FLOOR, traps=[]),
                dict(capitals=0, clamp=1)]
    for kw in variants:
        with decimal.localcontext() as ctx:
            for k, v in kw.items():
                if k == "traps":
                    for sig in list(ctx.traps):
                        ctx.traps[sig] = False
                else:
                    setattr(ctx, k, v)
            assert study(build(D3)) == base
            assert study(build(D1)) == base2


def test_working_context_is_pinned():
    import decimal
    seen = {}
    mod = load(name="measys1538_spy")
    real = mod._out
    def spy(value):
        c = decimal.getcontext()
        seen.update(prec=c.prec, rounding=c.rounding, Emin=c.Emin, Emax=c.Emax, capitals=c.capitals, clamp=c.clamp,
                    traps=sorted(k.__name__ for k, v in c.traps.items() if v))
        return real(value)
    mod._out = spy
    mod.gauge_rr_study(build(D1))
    assert seen == {"prec": 64, "rounding": decimal.ROUND_HALF_EVEN, "Emin": -999999, "Emax": 999999,
                    "capitals": 1, "clamp": 0,
                    "traps": ["DivisionByZero", "InvalidOperation", "Overflow", "Underflow"]}


def test_arithmetic_error_is_mapped_not_raw():
    import decimal
    mod = load(name="measys1538_arith")
    mod._out = lambda value: value.quantize(decimal.Decimal("1E-9999999"))
    with pytest.raises(ValueError) as ei:
        mod.gauge_rr_study(build(D1))
    assert str(ei.value) == P + "arithmetic: computation could not complete"
    assert not isinstance(ei.value, decimal.DecimalException)


def test_text_field_rules_and_unicode():
    for field in ("study_id", "part", "operator"):
        def put(v):
            p = build(D1)
            if field == "study_id":
                p["study_id"] = v
            else:
                old = p["measurements"][0][field]
                for m in p["measurements"]:
                    if m[field] == old:
                        m[field] = v
            return p
        study(put("x" * 128))
        refuse(put("x" * 129), f"invalid_{field}: {field} exceeds 128 characters")
        refuse(put("x" * 129 + "\u202e"), f"invalid_{field}: {field} exceeds 128 characters")
        for ok in ("a b", "caf\u00e9", "\u65e5\u672c", "a\u200a", "a\u2010", "a\u202f", "a\u2065", "a\u206a",
                   "a\ufefe", "a\u00a0", "a\u3000", "\U0001f600"):
            out = study(put(ok))
            if field == "study_id":
                assert out["study_id"] == ok
        for c in ("a\x00b", "a\nb", "a\tb", "\x1fa", "a\x7f", "a\x85", "a\x9f", "a\u2028", "a\u2029",
                  "a\u202e", "a\u200b", "\ufeff", "a\u200f", "a\u202a", "a\u2066", "a\u2069", "a\u200c",
                  "a\u200d", "a\u200e", "a\u202b", "a\u202c", "a\u202d", "a\u2067", "a\u2068"):
            refuse(put(c + "SECRETTAIL"), f"invalid_{field}: {field} contains disallowed characters")


def test_unicode_doc_line():
    assert "no Unicode control, line/paragraph separator or bidi/format characters" in DOC.read_text()


def test_zero_variation_refused():
    refuse(build([[["4", "4"], ["4", "4"]], [["4", "4"], ["4", "4"]]]), "study undefined for zero observed variation")


def test_percent_contributions_add_up():
    out = study(build(D2))
    pc = out["percent_contribution"]
    assert Decimal(pc["gage_rr"]) + Decimal(pc["part_to_part"]) == Decimal("100")
    assert Decimal(pc["repeatability"]) + Decimal(pc["reproducibility"]) == Decimal(pc["gage_rr"])


from decimal import Decimal


def test_input_not_mutated_deterministic():
    import copy
    p = build(D3)
    snap = copy.deepcopy(p)
    a = study(p)
    assert p == snap and a == study(p)


def test_no_effect_surface():
    import inspect
    src = SRC.read_text()
    for w in ("import socket", "import subprocess", "import urllib", "open(", "random", "float(", "datetime", "math."):
        assert w not in src
    pub = [n for n, o in vars(MOD).items() if inspect.isfunction(o) and not n.startswith("_")
           and o.__module__ == MOD.__name__]
    assert pub == ["gauge_rr_study"]


def test_boundary_text_is_pinned():
    assert MOD.BOUNDARY == (
        'Variance components are computed from the supplied repeat measurements with a '
        'balanced crossed two-factor ANOVA; negative estimates are reported as zero and '
        'listed. Normal, independent errors are assumed and not tested. No gauge '
        'approval, acceptance threshold or capability claim is made.')


def test_contract_doc():
    t = DOC.read_text()
    for w in ("audits/additional-2000-features.json", "Measurement Systems Analysis", "title is the whole spec",
              "engineering_1510_1559.py:172", "MEASYS1538", "LIMITS", "Full test suite not run",
              "cross-account builder package, provenance held privately", "ANOVA", "Input is exact",
              "64 significant digits rounded"):
        assert w in t
    for w in ("wamid", "HBgM"):
        assert w not in t


def _peak_for(payload):
    import tracemalloc
    tracemalloc.start()
    tracemalloc.reset_peak()
    try:
        with pytest.raises(ValueError) as ei:
            study(payload)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return peak, str(ei.value)


def test_cap_is_the_first_operation_no_large_allocation():
    big = "x" * (10 * 1024 * 1024) + " "
    for field in ("study_id", "part", "operator"):
        p = build(D1)
        if field == "study_id":
            p["study_id"] = big
        else:
            p["measurements"][0][field] = big
        peak, msg = _peak_for(p)
        assert msg == P + f"invalid_{field}: {field} exceeds 128 characters"
        assert peak < 1_000_000, (field, peak)
    p = build(D1)
    p["measurements"][0]["values"][0] = "1" * (10 * 1024 * 1024)
    peak, msg = _peak_for(p)
    assert msg == P + "number_too_long: values require at most 80 characters" and peak < 1_000_000


def test_oversize_blank_text_is_reported_as_oversize():
    p = build(D1)
    p["study_id"] = " " * 129
    refuse(p, "invalid_study_id: study_id exceeds 128 characters")
    p["study_id"] = " " * 128
    refuse(p, "invalid_study_id: study_id requires non-blank text")


def test_first_operation_on_text_is_the_type_check_then_length():
    import re
    src = SRC.read_text()
    body = src[src.index("def _text"):src.index("def _value")].split("\n")
    ops = [l.strip() for l in body if l.strip().startswith(("if ", "return"))]
    assert ops[0] == "if type(value) is not str:" and ops[1] == "if len(value) > MAX_TEXT:"
    num = src[src.index("def _value"):src.index("def _series") if "def _series" in src else src.index("def gauge_rr_study")].split("\n")
    ops = [l.strip() for l in num if l.strip().startswith("if ")]
    assert ops[0] == "if type(raw) is not str:" and ops[1] == "if len(raw) > MAX_NUMBER_CHARS:"
