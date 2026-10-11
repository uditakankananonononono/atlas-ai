"""Row 1537 Process Capability: exact Cp/Cpk (within) and Pp/Ppk (overall) over supplied data."""
import importlib.util, pathlib, sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/m20_general_cognitive_worker/process_capability1537.py"
DOC = ROOT / "docs/M20_PROCESS_CAPABILITY1537_CONTRACT.md"
P = "PROCAP1537: "


def load(source=None, name="procap1537"):
    spec = importlib.util.spec_from_file_location(name, SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if source is None:
        spec.loader.exec_module(mod)
    else:
        exec(compile(source, str(SRC), "exec"), mod.__dict__)
    return mod


MOD = load()
cap = MOD.capability_indices
A = ["9", "10", "11", "10", "10"]
B = ["10", "12", "11", "13", "12"]
KEYS = ("n", "mean", "sigma_within", "sigma_overall", "cp", "cpu", "cpl", "cpk", "pp", "ppu", "ppl", "ppk")


def run(values, lo="7", hi="13", sid="st1"):
    p = {"study_id": sid, "values": list(values)}
    if lo is not None: p["lower_spec"] = lo
    if hi is not None: p["upper_spec"] = hi
    return cap(p)


def pick(out):
    return {k: out[k] for k in KEYS}


def refuse(payload, message):
    with pytest.raises(ValueError) as ei:
        cap(payload)
    assert str(ei.value) == P + message


def test_exact_envelope_two_sided():
    out = run(A)
    assert out == {
        "study_id": "st1", "n": 5, "mean": "10", "sigma_within": "0.664893617", "sigma_overall": "0.707106781",
        "cp": "1.504", "cpu": "1.504", "cpl": "1.504", "cpk": "1.504",
        "pp": "1.414213562", "ppu": "1.414213562", "ppl": "1.414213562", "ppk": "1.414213562",
        "within_sigma_estimator": "MRbar/1.128", "overall_sigma_estimator": "sample standard deviation (n-1)",
        "normality_assumed": True, "stability_established": False, "process_acceptance_claimed": False,
        "boundary": MOD.BOUNDARY}


def test_asymmetric_two_sided():
    assert pick(run(B, "8", "16")) == {
        "n": 5, "mean": "11.6", "sigma_within": "1.329787234", "sigma_overall": "1.140175425",
        "cp": "1.002666667", "cpu": "1.102933333", "cpl": "0.9024", "cpk": "0.9024",
        "pp": "1.169410692", "ppu": "1.286351762", "ppl": "1.052469623", "ppk": "1.052469623"}


def test_upper_only():
    o = pick(run(B, None, "16"))
    assert (o["cp"], o["cpl"], o["cpu"], o["cpk"]) == (None, None, "1.102933333", "1.102933333")
    assert (o["pp"], o["ppl"], o["ppu"], o["ppk"]) == (None, None, "1.286351762", "1.286351762")


def test_lower_only():
    o = pick(run(B, "8", None))
    assert (o["cp"], o["cpu"], o["cpl"], o["cpk"]) == (None, None, "0.9024", "0.9024")
    assert (o["pp"], o["ppu"], o["ppl"], o["ppk"]) == (None, None, "1.052469623", "1.052469623")


def test_mean_on_spec_limit_gives_zero_and_just_past_gives_negative():
    on = pick(run(A, "7", "10"))
    assert (on["cpu"], on["cpk"], on["cp"], on["ppu"], on["ppk"], on["pp"]) == \
        ("0", "0", "0.752", "0", "0", "0.707106781")
    past = pick(run(A, "7", "9.9"))
    assert (past["cpu"], past["cpk"], past["cp"], past["ppu"], past["ppk"]) == \
        ("-0.050133333", "-0.050133333", "0.726933333", "-0.047140452", "-0.047140452")
    low = pick(run(A, "10.1", "13"))
    assert (low["cpl"], low["cpk"], low["ppl"], low["ppk"]) == \
        ("-0.050133333", "-0.050133333", "-0.047140452", "-0.047140452")


def test_two_points_is_the_minimum_study():
    o = pick(run(["1", "2"], "0", "3"))
    assert (o["n"], o["sigma_within"], o["sigma_overall"], o["cpk"], o["ppk"]) == \
        (2, "0.886524823", "0.707106781", "0.564", "0.707106781")


def test_count_bounds_n_and_n_plus_one():
    refuse({"study_id": "s", "values": ["1"], "upper_spec": "5"}, "values requires a list of 2..500 points")
    refuse({"study_id": "s", "values": None, "upper_spec": "5"}, "values requires a list of 2..500 points")
    refuse({"study_id": "s", "values": ("1", "2"), "upper_spec": "5"}, "values requires a list of 2..500 points")
    vals = [str(i % 7) for i in range(500)]
    assert run(vals, "-10", "20")["n"] == 500
    refuse({"study_id": "s", "values": vals + ["1"], "upper_spec": "20"}, "values requires a list of 2..500 points")


def sub(label):
    return "values require" if label == "values" else label + " requires"


def M(label, kind):
    sp = "values require" if label == "values" else label + " requires"
    one = "ASCII decimal strings" if label == "values" else "an ASCII decimal string"
    return {"shape": f"invalid_number: {sp} {one} such as -12.5",
            "long": f"number_too_long: {sp} at most 80 characters",
            "prec": f"number_precision: {sp} at most 64 significant digits and 64 fraction digits",
            "range": f"number_range: {sp} |value| <= 1000000000000"}[kind]


def with_field(label, text, other=None):
    if label == "values":
        return {"study_id": "s", "values": ["0", text], "upper_spec": "5"}
    return {"study_id": "s", "values": ["0", "1"], label: text}


LABELS = ("values", "lower_spec", "upper_spec")


def test_value_and_spec_bounds_both_sides():
    big = "1000000000000"
    assert run(["0", "1"], "-" + big, big)["n"] == 2
    for label in LABELS:
        refuse(with_field(label, "1000000000000.0000000001"), M(label, "range"))
        refuse(with_field(label, "-1000000000000.1"), M(label, "range"))
        refuse(with_field(label, "1000000000001"), M(label, "range"))


def test_bound_compare_is_exact_under_ambient_context():
    import decimal
    for prec in (2, 5, 28, 100):
        with decimal.localcontext() as ctx:
            ctx.prec = prec
            for label in LABELS:
                refuse(with_field(label, "1000000000001"), M(label, "range"))
                refuse(with_field(label, "1000000000000.0000000001"), M(label, "range"))
                refuse(with_field(label, "-1000000000000.1"), M(label, "range"))
            assert run(["0", "1"], "-1000000000000", "1000000000000")["n"] == 2


def test_number_shape_refusals_all_fields():
    for label in LABELS:
        for bad in (1, 1.5, None if label == "values" else 7, True, [], {}, b"1", "abc", "", " ", "1,5", "0x10", "1e5",
                    "1E5", "1e-999999999999999999", "+1", "01", "00", ".5", "5.", "-", "1_0", " 1", "1 ", "1\n",
                    "NaN", "Infinity", "-Infinity", "sNaN", "1.2.3", "\u0661", "\uff11"):
            refuse(with_field(label, bad), M(label, "shape"))
    assert run(["0", "0.5"], "-0.5", "10")["n"] == 2


def test_number_length_and_precision_n_and_n_plus_one():
    for label in LABELS:
        refuse(with_field(label, "0." + "1" * 78), M(label, "prec"))     # 80 chars passes length check
        refuse(with_field(label, "0." + "1" * 79), M(label, "long"))     # 81 chars
        refuse(with_field(label, "a" * 81), M(label, "long"))
        refuse(with_field(label, "a" * 80), M(label, "shape"))
        refuse(with_field(label, "0." + "1" * 65), M(label, "prec"))
        refuse(with_field(label, "0." + "0" * 64 + "1"), M(label, "prec"))
        refuse(with_field(label, "1." + "1" * 64), M(label, "prec"))
        refuse(with_field(label, "-0." + "1" * 65), M(label, "prec"))
        refuse(with_field(label, "9" * 13 + "." + "1" * 65 + "z"), M(label, "shape"))
        refuse(with_field(label, "9" * 13 + "." + "1" * 65), M(label, "prec"))
        refuse(with_field(label, "9" * 13), M(label, "range"))
        refuse(with_field(label, "9" * 90), M(label, "long"))
    assert run(["0", "0." + "1" * 64], "-1", "5")["n"] == 2
    assert run(["0", "-0." + "1" * 64], "-1", "5")["n"] == 2
    assert run(["0", "0." + "0" * 19 + "1"], "-1", "5")["n"] == 2
    assert run(["0", "1" * 12 + "." + "1" * 51], "-1", "1000000000000")["n"] == 2
    refuse(with_field("values", "1" * 12 + "." + "1" * 53), M("values", "prec"))
    assert cap({"study_id": "s", "values": ["0", "1"], "upper_spec": "0." + "1" * 64})["n"] == 2


def test_refusal_never_echoes_input():
    for bad in ("TOPSECRET" * 20, "TOPSECRET1e5"):
        for label in LABELS:
            with pytest.raises(ValueError) as ei:
                cap(with_field(label, bad))
            assert "TOPSECRET" not in str(ei.value)


def test_ambient_context_cannot_change_output():
    import decimal
    base = run(B, "8", "16")
    base2 = run(["0.1", "0.2", "0.35", "0.7", "0.15"], "-1", "3")
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
            assert run(B, "8", "16") == base
            assert run(["0.1", "0.2", "0.35", "0.7", "0.15"], "-1", "3") == base2


def test_working_context_is_pinned():
    import decimal
    seen = {}
    mod = load(name="procap1537_spy")
    real = mod._out
    def spy(value):
        c = decimal.getcontext()
        seen.update(prec=c.prec, rounding=c.rounding, Emin=c.Emin, Emax=c.Emax, capitals=c.capitals, clamp=c.clamp,
                    traps=sorted(k.__name__ for k, v in c.traps.items() if v))
        return real(value)
    mod._out = spy
    mod.capability_indices({"study_id": "s", "values": ["1", "2", "4"], "upper_spec": "9"})
    assert seen == {"prec": 64, "rounding": decimal.ROUND_HALF_EVEN, "Emin": -999999, "Emax": 999999,
                    "capitals": 1, "clamp": 0,
                    "traps": ["DivisionByZero", "InvalidOperation", "Overflow", "Underflow"]}


def test_arithmetic_error_is_mapped_not_raw():
    import decimal
    mod = load(name="procap1537_arith")
    mod.D2 = decimal.Decimal(0)
    with pytest.raises(ValueError) as ei:
        mod.capability_indices({"study_id": "s", "values": ["1", "2", "4"], "upper_spec": "9"})
    assert str(ei.value) == P + "arithmetic: computation could not complete"
    assert not isinstance(ei.value, decimal.DecimalException)


def test_bounded_domain_zero_variation_equivalence():
    # inside the bounded grammar, distinct values give both sigmas > 0: the zero-variation refusal never fires
    # for them (an index too large to quantize is the mapped arithmetic refusal instead).
    out = run(["0", "0." + "0" * 19 + "1"], "-1", "1")
    assert out["sigma_within"] == "0" and out["sigma_overall"] == "0" and out["cp"] is not None
    for pair in (["0", "0." + "0" * 63 + "1"], ["1" * 12 + "." + "1" * 51, "1" * 12 + "." + "1" * 50 + "2"]):
        with pytest.raises(ValueError) as ei:
            run(pair, "-1000000000000", "1000000000000")
        assert str(ei.value) == P + "arithmetic: computation could not complete"
    refuse({"study_id": "s", "values": ["4", "4", "4"], "upper_spec": "9"},
           "capability undefined for zero observed variation")
    refuse({"study_id": "s", "values": ["-0", "0", "0.0"], "upper_spec": "9"},
           "capability undefined for zero observed variation")


def test_extreme_index_is_a_mapped_refusal_not_a_raw_decimal_error():
    # Cp for a 1e-64 sigma over a 1e12 spec window exceeds what 64 digits can quantize: mapped, never raw
    tiny = "0." + "0" * 63 + "1"
    with pytest.raises(ValueError) as ei:
        cap({"study_id": "s", "values": ["0", tiny], "lower_spec": "-1000000000000", "upper_spec": "1000000000000"})
    assert str(ei.value) == P + "arithmetic: computation could not complete"


def test_study_id_rules():
    for bad in (None, "", " ", "\t\n", 3, b"x", ["s"]):
        refuse({"study_id": bad, "values": ["1", "2"], "upper_spec": "9"}, "invalid_study_id: study_id requires non-blank text")
    refuse({"values": ["1", "2"], "upper_spec": "9"}, "invalid_study_id: study_id requires non-blank text")
    assert run(["1", "2"], sid="x" * 128)["study_id"] == "x" * 128
    refuse({"study_id": "x" * 129, "values": ["1", "2"], "upper_spec": "9"}, "invalid_study_id: study_id exceeds 128 characters")
    refuse({"study_id": "x" * 129 + "\x00", "values": ["1", "2"], "upper_spec": "9"}, "invalid_study_id: study_id exceeds 128 characters")
    for c in ("a\x00b", "a\nb", "a\tb", "\x1fa", "a\x7f", "a\x85", "a\x9f", "a\u2028", "a\u2029", "a\u202e",
              "a\u200b", "\ufeff", "a\u200f", "a\u202a", "a\u2066", "a\u2069", "a\u200c", "a\u200d", "a\u200e",
              "a\u202b", "a\u202c", "a\u202d", "a\u2067", "a\u2068"):
        refuse({"study_id": c, "values": ["1", "2"], "upper_spec": "9"}, "invalid_study_id: study_id contains disallowed characters")
    assert run(["1", "2"], sid="s \u00e9 1")["study_id"] == "s \u00e9 1"
    with pytest.raises(ValueError) as ei:
        cap({"study_id": "SECRET" * 40, "values": ["1", "2"], "upper_spec": "9"})
    assert "SECRET" not in str(ei.value)


def test_spec_order_n_and_n_plus_one():
    refuse({"study_id": "s", "values": ["0", "1"], "lower_spec": "5", "upper_spec": "5"},
           "lower_spec requires lower_spec < upper_spec")
    refuse({"study_id": "s", "values": ["0", "1"], "lower_spec": "5.1", "upper_spec": "5"},
           "lower_spec requires lower_spec < upper_spec")
    assert run(["0", "1"], "4.999999", "5")["n"] == 2


def test_at_least_one_spec():
    refuse({"study_id": "s", "values": ["0", "1"]}, "at least one of lower_spec, upper_spec is required")
    refuse({"study_id": "s", "values": ["0", "1"], "lower_spec": None, "upper_spec": None},
           "at least one of lower_spec, upper_spec is required")


def test_zero_variation_refused():
    refuse({"study_id": "s", "values": ["4", "4", "4"], "upper_spec": "9"},
           "capability undefined for zero observed variation")


def test_payload_refusals():
    refuse(None, "payload requires an object")
    refuse([], "payload requires an object")
    refuse({"study_id": "s", "values": ["1", "2"], "upper_spec": "9", "x": 1}, "unknown key in payload")


def test_input_not_mutated_deterministic():
    v = list(B)
    p = {"study_id": "s", "values": v, "lower_spec": "8", "upper_spec": "16"}
    a = cap(p)
    assert v == B and a == cap(p) and p == {"study_id": "s", "values": B, "lower_spec": "8", "upper_spec": "16"}


def test_within_vs_overall_differ_by_design():
    o = run(B, "8", "16")
    assert o["sigma_within"] != o["sigma_overall"] and o["cp"] != o["pp"]


def test_no_effect_surface():
    import inspect
    src = SRC.read_text()
    for w in ("import socket", "import subprocess", "import urllib", "open(", "random", "float(", "datetime", "math."):
        assert w not in src
    pub = [n for n, o in vars(MOD).items() if inspect.isfunction(o) and not n.startswith("_")
           and o.__module__ == MOD.__name__]
    assert pub == ["capability_indices"]


def test_boundary_text_is_pinned():
    assert MOD.BOUNDARY == (
        'Capability indices computed over the supplied series and specification limits '
        'only. Within-sigma is MRbar/1.128; overall sigma is the sample standard '
        'deviation. Both assume an approximately normal, stable process, which is '
        'neither tested nor established here. No process-acceptance or '
        'qualification claim is made.')


def test_contract_doc():
    t = DOC.read_text()
    for w in ("audits/additional-2000-features.json", "Process Capability", "title is the whole spec",
              "engineering_1510_1559.py:167", "PROCAP1537", "LIMITS", "Full test suite not run",
              "cross-account builder package, provenance held privately", "normality", "Input is exact", "64 significant digits rounded"):
        assert w in t
    for w in ("wamid", "HBgM"):
        assert w not in t


def test_unicode_rule_boundaries():
    # allowed: ordinary spaces and printable non-ASCII, and neighbours just outside the rejected ranges
    for ok in ("a b", "caf\u00e9", "\u65e5\u672c", "a\u200a", "a\u2010", "a\u2029".replace("\u2029", "\u202f"),
               "a\u2065", "a\u206a", "a\ufefe", "a\u00a0", "a\u3000", "\U0001f600"):
        assert run(["1", "2"], sid=ok)["study_id"] == ok
    for bad, name in (("\x85", "U+0085"), ("\u2028", "U+2028"), ("\u2029", "U+2029"), ("\u202e", "U+202E"),
                      ("\u200b", "U+200B"), ("\ufeff", "U+FEFF"), ("\x7f", "DEL")):
        with pytest.raises(ValueError) as ei:
            cap({"study_id": "a" + bad + "SECRETTAIL", "values": ["1", "2"], "upper_spec": "9"})
        assert str(ei.value) == P + "invalid_study_id: study_id contains disallowed characters", name
    refuse({"study_id": "a" * 129 + "\u202e", "values": ["1", "2"], "upper_spec": "9"},
           "invalid_study_id: study_id exceeds 128 characters")


def test_unicode_doc_line():
    assert "no Unicode control, line/paragraph separator or bidi/format characters" in DOC.read_text()


def _peak_for(payload):
    import tracemalloc
    tracemalloc.start()
    tracemalloc.reset_peak()
    try:
        with pytest.raises(ValueError) as ei:
            cap(payload)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return peak, str(ei.value)


def test_cap_is_the_first_operation_no_large_allocation():
    big = 10 * 1024 * 1024
    peak, msg = _peak_for({"study_id": "x" * big + " ", "values": ["1", "2"], "upper_spec": "9"})
    assert msg == P + "invalid_study_id: study_id exceeds 128 characters" and peak < 1_000_000
    for label in LABELS:
        peak, msg = _peak_for(with_field(label, "1" * big))
        assert msg == P + M(label, "long") and peak < 1_000_000, label


def test_oversize_blank_study_id_is_reported_as_oversize():
    refuse({"study_id": " " * 129, "values": ["1", "2"], "upper_spec": "9"}, "invalid_study_id: study_id exceeds 128 characters")
    refuse({"study_id": " " * 128, "values": ["1", "2"], "upper_spec": "9"}, "invalid_study_id: study_id requires non-blank text")


def test_first_operations_are_type_check_then_length():
    src = SRC.read_text()
    text = src[src.index("def _study_id"):src.index("return value", src.index("def _study_id"))]
    ops = [l.strip() for l in text.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(value) is not str:" and ops[1] == "if len(value) > MAX_STUDY_ID:"
    num = src[src.index("def _parse"):src.index("def _study_id")]
    ops = [l.strip() for l in num.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(raw) is not str:" and ops[1] == "if len(raw) > MAX_NUMBER_CHARS:"
