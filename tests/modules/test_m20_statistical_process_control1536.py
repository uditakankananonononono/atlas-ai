"""Row 1536 Statistical Process Control: exact baseline individuals chart."""
import importlib.util, pathlib, sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/m20_general_cognitive_worker/statistical_process_control1536.py"
DOC = ROOT / "docs/M20_STATISTICAL_PROCESS_CONTROL1536_CONTRACT.md"
P = "SPC1536: "


def load(source=None, name="spc1536"):
    spec = importlib.util.spec_from_file_location(name, SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if source is None:
        spec.loader.exec_module(mod)
    else:
        exec(compile(source, str(SRC), "exec"), mod.__dict__)
    return mod


MOD = load()
chart = MOD.chart_baseline


def run(values, sid="s1"):
    return chart({"series_id": sid, "values": list(values)})


def refuse(payload, message):
    with pytest.raises(ValueError) as ei:
        chart(payload)
    assert str(ei.value) == P + message


def rules(out, rule):
    return [f["index"] for f in out["flags"] if f["rule"] == rule]


def test_exact_envelope():
    out = run(["10", "12", "11", "13", "12"])
    assert out == {
        "series_id": "s1", "n": 5, "center_line": "11.6", "moving_range_mean": "1.5",
        "sigma_hat": "1.329787234", "ucl": "15.589361702", "lcl": "7.610638298", "flags": [],
        "sigma_estimator": "MRbar/1.128", "baseline_only": True, "control_state_claimed": False,
        "process_intervention_advised": False, "boundary": MOD.BOUNDARY}
    assert "no process intervention is advised" in out["boundary"]
    assert "No claim is made about process control state" in out["boundary"]


def test_second_hand_computed_series():
    out = run(["5", "5", "5", "0"])
    assert (out["center_line"], out["moving_range_mean"], out["sigma_hat"], out["ucl"], out["lcl"]) == \
        ("3.75", "1.666666667", "1.477541371", "8.182624113", "-0.682624113")


def test_beyond_ucl_n_and_n_plus_one():
    # four zeros then 20 at n=5 is flagged; at n=4 the single high point is inside its own limit
    assert run(["0", "0", "0", "20"])["flags"] == []
    out = run(["0", "0", "0", "0", "20"])
    assert out["flags"] == [{"index": 4, "rule": "beyond_ucl"}]
    assert (out["center_line"], out["ucl"], out["lcl"]) == ("4", "17.29787234", "-9.29787234")
    assert run(["0", "0", "0", "0", "0", "20"])["flags"] == [{"index": 5, "rule": "beyond_ucl"}]


def test_beyond_lcl_mirror():
    out = run(["0", "0", "0", "0", "-20"])
    assert out["flags"] == [{"index": 4, "rule": "beyond_lcl"}]
    assert (out["center_line"], out["ucl"], out["lcl"]) == ("-4", "9.29787234", "-17.29787234")


def test_point_equal_to_limit_is_not_flagged():
    out = run(["7", "7", "7", "7"])
    assert (out["ucl"], out["lcl"], out["sigma_hat"], out["flags"]) == ("7", "7", "0", [])


def test_both_sides_order_and_limits():
    out = run(["1", "2", "3", "4", "5", "6", "7", "8"])
    assert out["flags"] == [{"index": 0, "rule": "beyond_lcl"}, {"index": 7, "rule": "beyond_ucl"}]
    assert (out["ucl"], out["lcl"]) == ("7.159574468", "1.840425532")
    rev = run(["8", "7", "6", "5", "4", "3", "2", "1"])
    assert rev["flags"] == [{"index": 0, "rule": "beyond_ucl"}, {"index": 7, "rule": "beyond_lcl"}]


def test_run_of_eight_above_n_and_n_minus_one():
    seq = ["0"] * 15 + ["-20"]
    out = run(seq)
    assert rules(out, "run8_above") == [7, 8, 9, 10, 11, 12, 13, 14]
    assert rules(out, "beyond_lcl") == [15]
    # seven zeros above the centre line are not a run
    short = run(["0"] * 7 + ["-20"])
    assert rules(short, "run8_above") == []


def test_run_of_eight_below():
    out = run(["0"] * 15 + ["20"])
    assert rules(out, "run8_below") == [7, 8, 9, 10, 11, 12, 13, 14]
    assert rules(out, "run8_above") == []
    assert rules(run(["0"] * 7 + ["20"]), "run8_below") == []


def test_point_on_centre_line_breaks_a_run():
    out = run(["3", "3", "3", "3", "2", "1", "1", "1", "1"])
    assert out["center_line"] == "2"
    assert rules(out, "run8_above") == [] and rules(out, "run8_below") == []
    out = run(["4", "4", "4", "4", "4", "4", "4", "2", "0", "0", "0"])
    assert rules(out, "run8_above") == []  # 7 above, then one below
    long = run(["4"] * 8 + ["0"] * 8)
    assert rules(long, "run8_above") == [7] and rules(long, "run8_below") == [15]


def test_centre_line_point_inside_an_eight_window_blocks_the_run():
    up = run(["3", "3", "3", "2", "3", "3", "3", "3"] + ["1"] * 7)
    assert up["center_line"] == "2" and rules(up, "run8_above") == []
    down = run(["1", "1", "1", "2", "1", "1", "1", "1"] + ["3"] * 7)
    assert down["center_line"] == "2" and rules(down, "run8_below") == []


def test_boundary_text_is_pinned():
    assert MOD.BOUNDARY == (
        'Baseline individuals-chart statistics over the supplied series only: '
        'sigma is MRbar/1.128 and limits are the centre line plus or minus three '
        'sigma. Flags mark points or runs relative to those baseline numbers. No '
        'claim is made about process control state, and no process intervention '
        'is advised.')


def test_window_is_exactly_eight_points():
    out = run(["5"] * 8 + ["0"] * 7 + ["5"])
    assert 7 in rules(out, "run8_above")


def test_input_formats_accepted():
    assert run(["1.50", "-0.5", "2"])["n"] == 3
    assert run(["-0", "0"])["center_line"] == "0"
    assert run([".5".lstrip("."), "0.5"])["n"] == 2


def test_count_bounds_n_and_n_plus_one():
    refuse({"series_id": "s", "values": ["1"]}, "values requires a list of 2..500 points")
    refuse({"series_id": "s", "values": []}, "values requires a list of 2..500 points")
    refuse({"series_id": "s", "values": None}, "values requires a list of 2..500 points")
    refuse({"series_id": "s", "values": ("1", "2")}, "values requires a list of 2..500 points")
    assert run(["1", "2"])["n"] == 2
    assert run(["1"] * 500)["n"] == 500
    refuse({"series_id": "s", "values": ["1"] * 501}, "values requires a list of 2..500 points")


def vals(*v):
    return {"series_id": "s", "values": list(v)}


RANGE = "number_range: values require |value| <= 1000000000000"
SHAPE = "invalid_number: values require ASCII decimal strings such as -12.5"
LONG = "number_too_long: values require at most 80 characters"
PREC = "number_precision: values require at most 64 significant digits and 64 fraction digits"


def test_value_bounds_n_and_n_plus_one():
    big = "1000000000000"
    assert run(["0", big])["n"] == 2
    assert run(["0", "-" + big])["n"] == 2
    assert run(["0", big + ".0000000000"])["n"] == 2
    refuse(vals("0", "1000000000000.0000000001"), RANGE)
    refuse(vals("0", "-1000000000000.1"), RANGE)
    refuse(vals("0", "1000000000001"), RANGE)


def test_number_shape_refusals():
    for bad in (1, 1.5, None, True, [], {}, b"1", "abc", "", " ", "1,5", "0x10", "1e5", "1E5", "1e-999999999999999999",
                "+1", "01", "00", "-01", ".5", "5.", "-", "-.5", "1.", "1_0", " 1", "1 ", "1\n", "1\t",
                "NaN", "Infinity", "-Infinity", "sNaN", "inf", "1.2.3", "--1", "\u0661", "\uff11", "1\u00a0"):
        refuse(vals("1", bad), SHAPE)
    assert run(["0", "0.5"])["n"] == 2 and run(["-0.0", "10"])["n"] == 2


def test_number_length_n_and_n_plus_one():
    n80 = "0." + "1" * 78
    assert len(n80) == 80
    refuse(vals("0", n80), PREC)  # passes the length check, stopped by the precision check
    refuse(vals("0", "0." + "1" * 79), LONG)
    refuse(vals("0", "a" * 80), SHAPE)
    refuse(vals("0", "a" * 81), LONG)
    refuse(vals("0", "1" * 100), LONG)


def test_number_precision_n_and_n_plus_one():
    assert run(["0", "0." + "1" * 64])["n"] == 2
    refuse(vals("0", "0." + "1" * 65), PREC)
    assert run(["0", "0." + "0" * 63 + "1"])["n"] == 2
    refuse(vals("0", "0." + "0" * 64 + "1"), PREC)
    refuse(vals("0", "1." + "1" * 64), PREC)
    assert run(["0", "1." + "0" * 63])["n"] == 2
    refuse(vals("0", "1." + "0" * 64 + "0"), PREC)
    refuse(vals("0", "1" * 13 + "." + "1" * 52), PREC)
    assert run(["0", "1" * 12 + "." + "1" * 51])["n"] == 2


def test_check_order_length_then_shape_then_precision_then_range():
    refuse(vals("0", "x" * 81), LONG)
    refuse(vals("0", "9" * 80 + "z"), LONG)
    refuse(vals("0", "9" * 13 + "." + "1" * 65 + "z"), SHAPE)
    refuse(vals("0", "9" * 13 + "." + "1" * 65), PREC)
    refuse(vals("0", "9" * 13), RANGE)


def test_bound_compare_is_exact_under_ambient_context():
    import decimal
    eps = "1000000000000.0000000001"
    for prec in (2, 5, 28, 100):
        with decimal.localcontext() as ctx:
            ctx.prec = prec
            refuse(vals("0", "1000000000001"), RANGE)
            refuse(vals("0", eps), RANGE)
            refuse(vals("0", "-" + eps), RANGE)
            refuse(vals("0", "-1000000000000.1"), RANGE)
            assert run(["0", "1000000000000"])["n"] == 2
            assert run(["0", "-1000000000000"])["n"] == 2


def test_series_id_rules():
    for bad in (None, "", " ", "\t\n", 3, b"x", ["s"]):
        refuse({"series_id": bad, "values": ["1", "2"]}, "invalid_series_id: series_id requires non-blank text")
    refuse({"values": ["1", "2"]}, "invalid_series_id: series_id requires non-blank text")
    assert run(["1", "2"], "x" * 128)["series_id"] == "x" * 128
    refuse({"series_id": "x" * 129, "values": ["1", "2"]}, "invalid_series_id: series_id exceeds 128 characters")
    for c in ("a\x00b", "a\nb", "a\tb", "\x1fa", "a\x7f", "a\x85", "a\x9f", "a\u2028", "a\u2029", "a\u202e",
              "a\u200b", "\ufeff", "a\u200f", "a\u202a", "a\u2066", "a\u2069", "a\u200c", "a\u200d", "a\u200e",
              "a\u202b", "a\u202c", "a\u202d", "a\u2067", "a\u2068"):
        refuse({"series_id": c, "values": ["1", "2"]}, "invalid_series_id: series_id contains disallowed characters")
    assert run(["1", "2"], "s \u00e9 1")["series_id"] == "s \u00e9 1"
    long_secret = "SECRET" * 40
    with pytest.raises(ValueError) as ei:
        chart({"series_id": long_secret, "values": ["1", "2"]})
    assert "SECRET" not in str(ei.value)


def test_refusal_never_echoes_input():
    for bad in ("TOPSECRET" * 20, "TOPSECRET1e5"):
        with pytest.raises(ValueError) as ei:
            chart(vals("1", bad))
        assert "TOPSECRET" not in str(ei.value)


def test_ambient_context_cannot_change_output():
    import decimal
    series = ["0.1", "0.2", "0.3", "0.7", "0.15", "0.33", "9.1", "0.2", "0.2", "0.21"]
    base = run(series)
    assert "beyond_ucl" in [f["rule"] for f in base["flags"]]
    assert run(["0.1", "0.2", "0.3"])["sigma_hat"] == "0.088652482"
    variants = [dict(prec=2), dict(prec=100), dict(rounding=decimal.ROUND_DOWN),
                dict(rounding=decimal.ROUND_UP), dict(traps=[]), dict(Emax=1, Emin=-1),
                dict(prec=1, rounding=decimal.ROUND_FLOOR, traps=[]), dict(capitals=0, clamp=1)]
    for kw in variants:
        with decimal.localcontext() as ctx:
            for k, v in kw.items():
                if k == "traps":
                    for sig in list(ctx.traps):
                        ctx.traps[sig] = False
                else:
                    setattr(ctx, k, v)
            assert run(series) == base
            assert run(["0.1", "0.2", "0.3"])["sigma_hat"] == "0.088652482"
    with decimal.localcontext() as ctx:
        ctx.prec = 2
        assert run(["0", "1000000000000"])["center_line"] == "500000000000"


def test_ambient_context_is_restored():
    import decimal
    before = decimal.getcontext().copy()
    run(["0.1", "0.2", "0.3"])
    after = decimal.getcontext()
    assert (before.prec, before.rounding, before.Emax, before.Emin) == (after.prec, after.rounding, after.Emax, after.Emin)
    assert not after.flags[decimal.Inexact] or before.flags[decimal.Inexact]


def test_working_context_is_pinned():
    import decimal
    seen = {}
    mod = load(name="spc1536_spy")
    real = mod._out
    def spy(value):
        c = decimal.getcontext()
        seen.update(prec=c.prec, rounding=c.rounding, Emin=c.Emin, Emax=c.Emax, capitals=c.capitals, clamp=c.clamp,
                    traps=sorted(k.__name__ for k, v in c.traps.items() if v))
        return real(value)
    mod._out = spy
    mod.chart_baseline({"series_id": "s", "values": ["1", "2"]})
    assert seen == {"prec": 64, "rounding": decimal.ROUND_HALF_EVEN, "Emin": -999999, "Emax": 999999,
                    "capitals": 1, "clamp": 0,
                    "traps": ["DivisionByZero", "InvalidOperation", "Overflow", "Underflow"]}


def test_arithmetic_error_is_mapped_not_raw():
    import decimal
    mod = load(name="spc1536_arith")
    mod.D2 = decimal.Decimal(0)
    with pytest.raises(ValueError) as ei:
        mod.chart_baseline({"series_id": "s", "values": ["1", "2"]})
    assert str(ei.value) == P + "arithmetic: computation could not complete"
    assert not isinstance(ei.value, decimal.DecimalException)


def test_payload_refusals():
    refuse(None, "payload requires an object")
    refuse([], "payload requires an object")
    refuse({"series_id": "s", "values": ["1", "2"], "x": 1}, "unknown key in payload")
    refuse({"series_id": "s"}, "values requires a list of 2..500 points")


def test_does_not_mutate_and_deterministic():
    v = ["1", "2", "3"]
    a = chart({"series_id": "s", "values": v})
    assert v == ["1", "2", "3"] and a == chart({"series_id": "s", "values": v})


def test_precision_is_exact_not_float():
    out = run(["0.1", "0.2", "0.3"])
    assert out["center_line"] == "0.2" and out["moving_range_mean"] == "0.1"
    assert out["sigma_hat"] == "0.088652482" and out["ucl"] == "0.465957447"


def test_rounding_is_half_even_nine_places():
    # centre line 0.0000000005 rounds to 0 (half even); 0.0000000015 rounds to 0.000000002
    assert run(["0", "0.000000001"])["center_line"] == "0"
    assert run(["0", "0.000000003"])["center_line"] == "0.000000002"


def test_no_effect_surface():
    import inspect
    src = SRC.read_text()
    for w in ("import socket", "import subprocess", "import urllib", "open(", "random", "float(", "datetime"):
        assert w not in src
    pub = [n for n, o in vars(MOD).items() if inspect.isfunction(o) and not n.startswith("_")
           and o.__module__ == MOD.__name__]
    assert pub == ["chart_baseline"]


def test_contract_doc():
    t = DOC.read_text()
    for w in ("audits/additional-2000-features.json", "Statistical Process Control",
              "title is the whole spec", "engineering_1510_1559.py:164", "SPC1536", "LIMITS",
              "MRbar/1.128", "Full test suite not run", "64 significant digits rounded", "Input is exact",
              "cross-account builder package, provenance held privately"):
        assert w in t
    for w in ("wamid", "HBgM"):
        assert w not in t



def test_negative_numbers_count_digits_not_the_sign():
    assert run(["0", "-0." + "1" * 64])["n"] == 2
    refuse(vals("0", "-0." + "1" * 65), PREC)
    assert run(["0", "-" + "1" * 12 + "." + "1" * 52])["n"] == 2
    refuse(vals("0", "-" + "1" * 12 + "." + "1" * 53), PREC)


def test_series_id_length_is_checked_before_controls():
    refuse({"series_id": "x" * 129 + "\x00", "values": ["1", "2"]},
           "invalid_series_id: series_id exceeds 128 characters")


def test_unicode_rule_boundaries():
    for ok in ("a b", "caf\u00e9", "\u65e5\u672c", "a\u200a", "a\u2010", "a\u202f", "a\u2065", "a\u206a",
               "a\ufefe", "a\u00a0", "a\u3000", "\U0001f600"):
        assert run(["1", "2"], ok)["series_id"] == ok
    for bad, name in (("\x85", "U+0085"), ("\u2028", "U+2028"), ("\u2029", "U+2029"), ("\u202e", "U+202E"),
                      ("\u200b", "U+200B"), ("\ufeff", "U+FEFF"), ("\x7f", "DEL")):
        with pytest.raises(ValueError) as ei:
            chart({"series_id": "a" + bad + "SECRETTAIL", "values": ["1", "2"]})
        assert str(ei.value) == P + "invalid_series_id: series_id contains disallowed characters", name
    refuse({"series_id": "a" * 129 + "\u202e", "values": ["1", "2"]}, "invalid_series_id: series_id exceeds 128 characters")


def test_unicode_doc_line():
    assert "no Unicode control, line/paragraph separator or bidi/format characters" in DOC.read_text()


def _peak_for(payload):
    import tracemalloc
    tracemalloc.start()
    tracemalloc.reset_peak()
    try:
        with pytest.raises(ValueError) as ei:
            chart(payload)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return peak, str(ei.value)


def test_cap_is_the_first_operation_no_large_allocation():
    peak, msg = _peak_for({"series_id": "x" * (10 * 1024 * 1024) + " ", "values": ["1", "2"]})
    assert msg == P + "invalid_series_id: series_id exceeds 128 characters" and peak < 1_000_000
    peak, msg = _peak_for({"series_id": "s", "values": ["0", "1" * (10 * 1024 * 1024)]})
    assert msg == P + "number_too_long: values require at most 80 characters" and peak < 1_000_000


def test_oversize_blank_series_id_is_reported_as_oversize():
    refuse({"series_id": " " * 129, "values": ["1", "2"]}, "invalid_series_id: series_id exceeds 128 characters")
    refuse({"series_id": " " * 128, "values": ["1", "2"]}, "invalid_series_id: series_id requires non-blank text")


def test_first_operations_are_type_check_then_length():
    src = SRC.read_text()
    text = src[src.index("def _series_id"):src.index("return value", src.index("def _series_id"))]
    ops = [l.strip() for l in text.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(value) is not str:" and ops[1] == "if len(value) > MAX_SERIES_ID:"
    num = src[src.index("def _value"):src.index("def _series_id") if src.index("def _series_id") > src.index("def _value") else src.index("def chart_baseline")]
    ops = [l.strip() for l in num.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(raw) is not str:" and ops[1] == "if len(raw) > MAX_NUMBER_CHARS:"
