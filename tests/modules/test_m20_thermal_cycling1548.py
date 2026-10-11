"""Row 1548 Thermal Cycling: hermetic stdlib tests, exact-value pins, row-tagged refusals. Loads the module by path."""
import importlib.util
import math
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/thermal_cycling1548.py"
_spec = importlib.util.spec_from_file_location("thermal_cycling1548", _SRC)
tc = importlib.util.module_from_spec(_spec)
sys.modules["thermal_cycling1548"] = tc
_spec.loader.exec_module(tc)

_PROF = {"low_temperature_c": -40, "high_temperature_c": 85, "ramp_rate_c_per_min": 10,
         "dwell_low_min": 15, "dwell_high_min": 15}


def go(**over):
    d = {"profile": dict(_PROF), "cycles": 100, "specimen_count": 2,
         "preconditioning": ["visual inspection"], "measurements": ["resistance"],
         "acceptance_criteria": ["no visible damage"]}
    d.update(over)
    return tc.plan(d)


def refused(fn, word):
    with pytest.raises(tc.ThermError) as e:
        fn()
    assert str(e.value).startswith("THERM1548: ")
    assert word in str(e.value)


def test_happy_path_exact_arithmetic():
    r = go()
    assert r["row"] == 1548 and r["test_type"] == "thermal_cycling"
    assert len(r["plan"]) == 1
    entry = r["plan"][0]
    assert entry["temperature_swing_c"] == 125
    assert entry["estimated_cycle_time_min"] == 15 + 15 + 2 * 125 / 10
    assert r["estimated_cycle_time_min"] == 55.0
    assert r["estimated_total_time_min"] == 55.0 * 100
    assert r["cycles"] == 100 and r["specimen_count"] == 2
    assert r["preconditioning_declared"] == 1 and r["measurements_declared"] == 1
    assert r["acceptance_criteria_declared"] == 1
    assert r["test_executed"] is False and r["plan_only"] is True
    assert len(r["limits"]) == 3


def test_zero_dwells_and_float_rate():
    r = go(profile={"low_temperature_c": 0.0, "high_temperature_c": 50.0,
                    "ramp_rate_c_per_min": 2.5, "dwell_low_min": 0, "dwell_high_min": 0})
    assert r["estimated_cycle_time_min"] == 2 * 50.0 / 2.5
    assert r["plan"][0]["temperature_swing_c"] == 50.0


def test_input_must_be_mapping():
    refused(lambda: tc.plan([1, 2]), "mapping")


def test_missing_and_unknown_keys_refused():
    refused(lambda: tc.plan({"profile": dict(_PROF), "cycles": 1, "specimen_count": 1,
                             "preconditioning": [], "measurements": ["m"]}), "acceptance_criteria required")
    refused(lambda: go(extra=1), "unknown key")


def test_profile_schema_exact():
    refused(lambda: go(profile="x"), "mapping")
    refused(lambda: go(profile={"low_temperature_c": -40, "high_temperature_c": 85,
                                "ramp_rate_c_per_min": 10, "dwell_low_min": 15}), "dwell_high_min required")
    refused(lambda: go(profile=dict(_PROF, x=1)), "unknown profile key")


def test_temperature_bounds_and_order():
    for bad in (True, "-40", float("nan"), float("inf"), -273.16, 1001):
        refused(lambda bad=bad: go(profile=dict(_PROF, low_temperature_c=bad)), "low_temperature_c")
        refused(lambda bad=bad: go(profile=dict(_PROF, high_temperature_c=bad)), "high_temperature_c")
    refused(lambda: go(profile=dict(_PROF, low_temperature_c=85, high_temperature_c=85)), "below")
    refused(lambda: go(profile=dict(_PROF, low_temperature_c=86)), "below")
    r = go(profile=dict(_PROF, low_temperature_c=-273.15, high_temperature_c=1000))
    assert r["plan"][0]["temperature_swing_c"] == 1273.15


def test_ramp_and_dwell_bounds():
    for bad in (True, "10", float("nan"), 0, -5, 1001):
        refused(lambda bad=bad: go(profile=dict(_PROF, ramp_rate_c_per_min=bad)), "ramp_rate_c_per_min")
    for bad in (True, "15", float("nan"), -1, 100001):
        refused(lambda bad=bad: go(profile=dict(_PROF, dwell_low_min=bad)), "dwell_low_min")
        refused(lambda bad=bad: go(profile=dict(_PROF, dwell_high_min=bad)), "dwell_high_min")
    r = go(profile=dict(_PROF, ramp_rate_c_per_min=1000, dwell_low_min=100000, dwell_high_min=100000))
    assert r["estimated_cycle_time_min"] == 100000 + 100000 + 2 * 125 / 1000


def test_cycles_and_specimen():
    for bad in (True, 0, -1, 100001, 2.5, "100"):
        refused(lambda bad=bad: go(cycles=bad), "cycles")
    for bad in (True, 0, -1, 1001, 2.5, "2"):
        refused(lambda bad=bad: go(specimen_count=bad), "specimen_count")
    assert go(cycles=1)["cycles"] == 1
    assert go(cycles=100000)["estimated_total_time_min"] == 55.0 * 100000
    assert go(specimen_count=1)["specimen_count"] == 1
    assert go(specimen_count=1000)["specimen_count"] == 1000


def test_text_lists():
    refused(lambda: go(measurements=[]), "measurements")
    refused(lambda: go(measurements=["m"] * 21), "measurements")
    refused(lambda: go(measurements=[" "]), "measurements")
    refused(lambda: go(measurements=["x" * 65]), "measurements")
    refused(lambda: go(measurements="visual"), "measurements")
    refused(lambda: go(measurements=[7]), "measurements")
    refused(lambda: go(preconditioning=["p"] * 11), "preconditioning")
    refused(lambda: go(acceptance_criteria=["c"] * 11), "acceptance_criteria")
    refused(lambda: go(acceptance_criteria="none"), "acceptance_criteria")
    r = go(preconditioning=[], acceptance_criteria=[], measurements=["m"] * 20)
    assert r["preconditioning_declared"] == 0 and r["measurements_declared"] == 20


def test_raw_length_cap_before_strip():
    refused(lambda: go(acceptance_criteria=[" " * 65]), "at most 64 characters")


def test_unicode_cc_cf_zl_zp_refused_zs_accepted():
    for bad in ("a\tb", "a\xadb", "a⁠b", "a b", "a\x7fb", "a​b"):
        refused(lambda bad=bad: go(measurements=[bad]), "Unicode")
        refused(lambda bad=bad: go(preconditioning=[bad]), "Unicode")
        refused(lambda bad=bad: go(acceptance_criteria=[bad]), "Unicode")
    refused(lambda: go(acceptance_criteria=["soft\xadhyphen"]), "Unicode")  # U+00AD pin
    refused(lambda: go(acceptance_criteria=["word⁠joiner"]), "Unicode")  # U+2060 pin
    r = go(acceptance_criteria=["no visible damage", "MMLU Pro pin"])
    assert r["acceptance_criteria_declared"] == 2


def test_strict_builtin_types_only():
    class OddInt(int):
        pass

    class OddStr(str):
        pass

    class OddDict(dict):
        pass

    class OddList(list):
        pass

    refused(lambda: tc.plan(OddDict({"profile": dict(_PROF), "cycles": 1, "specimen_count": 1,
                                     "preconditioning": [], "measurements": ["m"],
                                     "acceptance_criteria": []})), "mapping")
    refused(lambda: go(profile=OddDict(_PROF)), "mapping")
    refused(lambda: go(cycles=OddInt(100)), "cycles")
    refused(lambda: go(specimen_count=OddInt(2)), "specimen_count")
    refused(lambda: go(measurements=OddList(["m"])), "measurements")
    refused(lambda: go(measurements=[OddStr("m")]), "measurements")
    refused(lambda: go(profile=dict(_PROF, low_temperature_c=OddInt(-40))), "low_temperature_c")
    refused(lambda: go(profile=dict(_PROF, ramp_rate_c_per_min=OddInt(10))), "ramp_rate_c_per_min")
    refused(lambda: go(profile=dict(_PROF, dwell_low_min=OddInt(15))), "dwell_low_min")


def test_strict_key_types():
    refused(lambda: tc.plan({1: "x", "profile": dict(_PROF), "cycles": 1,
                             "specimen_count": 1, "preconditioning": []}), "keys must be text")
    refused(lambda: go(profile={1: "x", "low_temperature_c": -40, "high_temperature_c": 85,
                                "ramp_rate_c_per_min": 10}), "profile keys must be text")


def test_count_check_precedes_dict_iteration_setprofile():
    events = []

    def tracer(frame, event, arg):
        if event == "call" and frame.f_code.co_name == "<genexpr>":
            events.append("iterate")
        elif event == "c_call" and arg is len:
            events.append("len")
        return tracer

    sys.setprofile(tracer)
    try:
        go()
    finally:
        sys.setprofile(None)
    assert "iterate" in events and "len" in events
    assert events.index("len") < events.index("iterate")


def test_huge_exact_int_is_refused_not_overflow():
    huge = 1 << 100000
    refused(lambda: go(profile=dict(_PROF, low_temperature_c=huge)), "low_temperature_c")
    refused(lambda: go(profile=dict(_PROF, ramp_rate_c_per_min=huge)), "ramp_rate_c_per_min")
    refused(lambda: go(cycles=huge), "cycles")


def test_cap_boundaries_accepted():
    r = tc.plan({"profile": dict(_PROF), "cycles": 100000, "specimen_count": 1000,
                 "preconditioning": ["p" * 64] * 10, "measurements": ["m" * 64] * 20,
                 "acceptance_criteria": ["c" * 64] * 10})
    assert r["preconditioning_declared"] == 10 and r["measurements_declared"] == 20
    assert r["acceptance_criteria_declared"] == 10


def test_oversized_dicts_refused_before_iteration_setprofile():
    lines = _SRC.read_text().splitlines()
    outer_ln = next(i for i, l in enumerate(lines, 1) if "for k in data" in l)
    prof_ln = next(i for i, l in enumerate(lines, 1) if "for k in prof" in l)
    events = []

    def tracer(frame, event, arg):
        if event == "call" and frame.f_code.co_name == "<genexpr>":
            events.append(frame.f_code.co_firstlineno)
        return tracer

    oversized = {"profile": dict(_PROF), "cycles": 1, "specimen_count": 1,
                 "preconditioning": [], "measurements": [], "acceptance_criteria": [], "z1": 1}
    sys.setprofile(tracer)
    try:
        try:
            tc.plan(oversized)
            raise AssertionError("oversized mapping accepted")
        except tc.ThermError as e:
            assert "unknown key" in str(e)
        assert events == []
        try:
            go(profile=dict(_PROF, z1=1))
            raise AssertionError("oversized profile accepted")
        except tc.ThermError as e:
            assert "unknown profile key" in str(e)
        assert outer_ln in events and prof_ln not in events
    finally:
        sys.setprofile(None)


def test_total_scales_with_cycles():
    assert go(cycles=2)["estimated_total_time_min"] == 2 * go(cycles=1)["estimated_total_time_min"]


def test_least_positive_float_ramp_refused():
    # least positive float (subnormal): any finite positive ramp stays admitted,
    # but the derived per-cycle time must be finite
    tiny = float.fromhex("0x0.0000000000001p-1022")
    assert 0 < tiny < 1e-300
    with pytest.raises(tc.ThermError) as e:
        go(profile={"low_temperature_c": 0, "high_temperature_c": 100,
                    "ramp_rate_c_per_min": tiny, "dwell_low_min": 0, "dwell_high_min": 0})
    assert str(e.value) == "THERM1548: derived cycle time is not finite"


def test_total_overflow_refused():
    # per-cycle is finite (2e306) but the 100000-cycle total overflows
    with pytest.raises(tc.ThermError) as e:
        go(cycles=100000,
           profile={"low_temperature_c": 0, "high_temperature_c": 100,
                    "ramp_rate_c_per_min": 1e-304, "dwell_low_min": 0, "dwell_high_min": 0})
    assert str(e.value) == "THERM1548: derived total time is not finite"


def test_extreme_but_finite_results_still_admitted():
    # no arbitrary minimum on ramp: a subnormal ramp with a matching subnormal swing
    # yields an exactly finite plan and stays admitted
    tiny = float.fromhex("0x0.0000000000001p-1022")
    r = go(cycles=1, profile={"low_temperature_c": 0, "high_temperature_c": tiny,
                              "ramp_rate_c_per_min": tiny, "dwell_low_min": 0, "dwell_high_min": 0})
    assert r["estimated_cycle_time_min"] == 2.0
    assert r["estimated_total_time_min"] == 2.0
    # a very small normal ramp with a large-but-finite result (2e307) also stays admitted
    small = 1e-305
    r2 = go(cycles=1, profile={"low_temperature_c": 0, "high_temperature_c": 100,
                               "ramp_rate_c_per_min": small, "dwell_low_min": 0, "dwell_high_min": 0})
    assert r2["estimated_cycle_time_min"] == 200 / small == 2e307
    assert math.isfinite(r2["estimated_cycle_time_min"])
    assert math.isfinite(r2["estimated_total_time_min"])
    # the top of the admitted ramp range is untouched
    r3 = go(cycles=1, profile={"low_temperature_c": -40, "high_temperature_c": 85,
                               "ramp_rate_c_per_min": 1000, "dwell_low_min": 15, "dwell_high_min": 15})
    assert r3["estimated_cycle_time_min"] == 15 + 15 + 2 * 125 / 1000


def test_high_temperature_negative_and_zero_accepted():
    # boundary accepts: high_temperature_c of -1 and 0 are valid (bounds are
    # -273.15..1000 with positive=False); kills the positive=False->True mutant
    # on the high call, which would refuse a valid -1
    for high in (-1, 0):
        r = go(cycles=1, profile={"low_temperature_c": -100, "high_temperature_c": high,
                                  "ramp_rate_c_per_min": 5, "dwell_low_min": 0, "dwell_high_min": 0})
        swing = high - (-100)
        assert r["plan"][0]["high_temperature_c"] == high
        assert r["plan"][0]["temperature_swing_c"] == swing
        assert r["estimated_cycle_time_min"] == 2 * swing / 5
        assert r["estimated_total_time_min"] == r["estimated_cycle_time_min"]
