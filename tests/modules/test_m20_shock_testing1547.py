"""Row 1547 Shock Testing: hermetic stdlib tests, exact-value pins, row-tagged refusals. Loads the module by path."""
import importlib.util
import math
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/shock_testing1547.py"
_spec = importlib.util.spec_from_file_location("shock_testing1547", _SRC)
st = importlib.util.module_from_spec(_spec)
sys.modules["shock_testing1547"] = st
_spec.loader.exec_module(st)


def go(**over):
    d = {"profiles": [{"pulse_shape": "half_sine", "peak_acceleration_g": 100, "duration_ms": 11}],
         "specimen_count": 3, "axes": ["x"], "acceptance_criteria": ["no visible damage"]}
    d.update(over)
    return st.plan(d)


def refused(fn, word):
    with pytest.raises(st.ShockError) as e:
        fn()
    assert str(e.value).startswith("SHOCK1547: ")
    assert word in str(e.value)


def test_half_sine_delta_velocity_exact():
    r = go()
    assert r["row"] == 1547
    p = r["plan"][0]
    assert p["pulse_shape"] == "half_sine" and p["shape_factor"] == 2 / math.pi
    assert p["estimated_delta_velocity_m_per_s"] == 100 * 9.80665 * 11 / 1000 * (2 / math.pi)
    assert r["max_estimated_delta_velocity_m_per_s"] == p["estimated_delta_velocity_m_per_s"]
    assert r["test_executed"] is False and r["plan_only"] is True


def test_rectangular_and_sawtooth_factors():
    r = go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": 50, "duration_ms": 6},
                     {"pulse_shape": "terminal_peak_sawtooth", "peak_acceleration_g": 200, "duration_ms": 3}])
    assert r["plan"][0]["estimated_delta_velocity_m_per_s"] == 50 * 9.80665 * 6 / 1000
    assert r["plan"][1]["estimated_delta_velocity_m_per_s"] == 200 * 9.80665 * 3 / 1000 * 0.5
    assert r["shape_counts"] == {"rectangular": 1, "terminal_peak_sawtooth": 1}
    assert r["max_estimated_delta_velocity_m_per_s"] == max(
        p["estimated_delta_velocity_m_per_s"] for p in r["plan"])


def test_shape_counts_sorted_and_profiles_supplied():
    r = go(profiles=[{"pulse_shape": "terminal_peak_sawtooth", "peak_acceleration_g": 10, "duration_ms": 1},
                     {"pulse_shape": "half_sine", "peak_acceleration_g": 10, "duration_ms": 1},
                     {"pulse_shape": "rectangular", "peak_acceleration_g": 10, "duration_ms": 1}])
    assert list(r["shape_counts"]) == ["half_sine", "rectangular", "terminal_peak_sawtooth"]
    assert r["profiles_supplied"] == 3 and r["specimen_count"] == 3 and r["axes"] == ["x"]
    assert r["acceptance_criteria_declared"] == 1


def test_input_must_be_mapping():
    refused(lambda: st.plan([1, 2]), "mapping")


def test_missing_and_unknown_keys_refused():
    refused(lambda: st.plan({"profiles": [], "specimen_count": 1, "axes": ["x"]}), "acceptance_criteria required")
    refused(lambda: go(extra=1), "unknown key")


def test_profiles_count_bounds():
    refused(lambda: go(profiles="x"), "list")
    refused(lambda: go(profiles=[]), "1 to 20")
    refused(lambda: go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": 1, "duration_ms": 1}] * 21), "1 to 20")


def test_profile_schema_exact():
    refused(lambda: go(profiles=[{"pulse_shape": "half_sine", "peak_acceleration_g": 1}]), "duration_ms required")
    refused(lambda: go(profiles=[{"pulse_shape": "half_sine", "peak_acceleration_g": 1, "duration_ms": 1, "x": 1}]), "unknown profile key")


def test_unsupported_pulse_shape_refused_with_tag():
    refused(lambda: go(profiles=[{"pulse_shape": "trapezoidal", "peak_acceleration_g": 1, "duration_ms": 1}]), "unsupported pulse_shape")
    refused(lambda: go(profiles=[{"pulse_shape": 7, "peak_acceleration_g": 1, "duration_ms": 1}]), "unsupported pulse_shape")


def test_peak_and_duration_validation():
    for bad in (True, "100", float("nan"), float("inf"), 0, -5, 100001):
        refused(lambda bad=bad: go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": bad, "duration_ms": 1}]), "peak_acceleration_g")
    for bad in (True, "11", float("nan"), 0, -1, 60001):
        refused(lambda bad=bad: go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": 1, "duration_ms": bad}]), "duration_ms")
    r = go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": 100000, "duration_ms": 60000}])
    assert r["profiles_supplied"] == 1


def test_specimen_count_and_axes_and_criteria():
    for bad in (True, 0, -1, 1001, 2.5, "3"):
        refused(lambda bad=bad: go(specimen_count=bad), "specimen_count")
    refused(lambda: go(axes=[]), "axes")
    refused(lambda: go(axes=["x", "x"]), "duplicate axis")
    refused(lambda: go(axes=["w"]), "axes")
    refused(lambda: go(axes=["x", "y", "z", "x"]), "axes")
    refused(lambda: go(acceptance_criteria="none"), "acceptance_criteria")
    refused(lambda: go(acceptance_criteria=[" "]), "acceptance_criteria")
    refused(lambda: go(acceptance_criteria=["x" * 65]), "acceptance_criteria")
    refused(lambda: go(acceptance_criteria=["ok"] * 11), "acceptance_criteria")
    r = go(axes=["z", "y"], acceptance_criteria=[])
    assert r["axes"] == ["z", "y"] and r["acceptance_criteria_declared"] == 0


def test_limits_present_and_no_execution_claims():
    r = go()
    assert len(r["limits"]) == 3
    assert all(isinstance(s, str) for s in r["limits"])
    assert r["test_executed"] is False and r["plan_only"] is True


def test_key_count_checked_before_iteration():
    # an over-wide mapping must be refused on key count, even with valid required keys
    d = {"profiles": [{"pulse_shape": "rectangular", "peak_acceleration_g": 1, "duration_ms": 1}],
         "specimen_count": 1, "axes": ["x"], "acceptance_criteria": [], "z1": 1, "z2": 2}
    refused(lambda: st.plan(d), "unknown key")
    # an over-wide profile mapping likewise
    refused(lambda: go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": 1,
                                  "duration_ms": 1, "z1": 1, "z2": 2}]), "unknown profile key")


def test_raw_length_cap_before_strip():
    # 201 chars of spaces: raw-length refusal must win over the blank check
    refused(lambda: go(acceptance_criteria=[" " * 65]), "at most 64 characters")


def test_unicode_cc_cf_zl_zp_refused_zs_accepted():
    for bad in ("a\tb", "a­b", "a⁠b", "a b", "a\x7fb", "a​b"):
        refused(lambda bad=bad: go(profiles=[{"pulse_shape": bad, "peak_acceleration_g": 1, "duration_ms": 1}]), "unsupported pulse_shape")
        refused(lambda bad=bad: go(axes=[bad]), "Unicode")
        refused(lambda bad=bad: go(acceptance_criteria=[bad]), "Unicode")
    refused(lambda: go(acceptance_criteria=["soft­hyphen"]), "Unicode")  # U+00AD pin
    refused(lambda: go(acceptance_criteria=["word⁠joiner"]), "Unicode")  # U+2060 pin
    # Zs accepted in echoed/carried text
    r = go(acceptance_criteria=["no visible damage", "MMLU Pro pin"])
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

    refused(lambda: st.plan(OddDict({"profiles": [], "specimen_count": 1, "axes": ["x"],
                                     "acceptance_criteria": []})), "mapping")
    refused(lambda: go(profiles=OddList()), "list")
    refused(lambda: go(specimen_count=OddInt(3)), "specimen_count")
    refused(lambda: go(axes=OddList(["x"])), "axes")
    refused(lambda: go(axes=[OddStr("x")]), "axes")
    refused(lambda: go(acceptance_criteria=[OddStr("ok")]), "acceptance_criteria")
    refused(lambda: go(profiles=[{"pulse_shape": OddStr("half_sine"), "peak_acceleration_g": 1,
                                  "duration_ms": 1}]), "pulse_shape")
    refused(lambda: go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": OddInt(5),
                                  "duration_ms": 1}]), "peak_acceleration_g")
    refused(lambda: go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": 1,
                                  "duration_ms": OddInt(5)}]), "duration_ms")


def test_axes_raw_cap_before_unicode():
    refused(lambda: go(axes=["x" + "\u200b" * 8]), "axes entries must be at most 8 characters")
    refused(lambda: go(axes=["y" * 9]), "axes entries must be at most 8 characters")


def test_pulse_raw_cap_then_enum_then_unicode():
    refused(lambda: go(profiles=[{"pulse_shape": "s" * 33, "peak_acceleration_g": 1,
                                  "duration_ms": 1}]), "pulse_shape must be at most 32 characters")
    refused(lambda: go(profiles=[{"pulse_shape": "half_sine\u200b", "peak_acceleration_g": 1,
                                  "duration_ms": 1}]), "unsupported pulse_shape")


def test_strict_key_types():
    refused(lambda: st.plan({1: "x", "profiles": [], "specimen_count": 1,
                             "axes": ["x"]}), "keys must be text")
    refused(lambda: go(profiles=[{1: "x", "pulse_shape": "rectangular",
                                  "peak_acceleration_g": 1}]), "profile keys must be text")


def test_count_check_precedes_dict_iteration_setprofile():
    events = []

    def tracer(frame, event, arg):
        if event == "call" and frame.f_code.co_name == "<genexpr>":
            events.append("iterate")
        elif event == "c_call" and arg is len:
            events.append("len")
        return tracer

    valid = {"profiles": [{"pulse_shape": "rectangular", "peak_acceleration_g": 1, "duration_ms": 1}],
             "specimen_count": 1, "axes": ["x"], "acceptance_criteria": []}
    sys.setprofile(tracer)
    try:
        st.plan(valid)
    finally:
        sys.setprofile(None)
    assert "iterate" in events and "len" in events
    assert events.index("len") < events.index("iterate")


def test_huge_exact_int_is_refused_not_overflow():
    huge = 1 << 100000
    refused(lambda: go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": huge,
                                  "duration_ms": 1}]), "peak_acceleration_g")
    refused(lambda: go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": 1,
                                  "duration_ms": huge}]), "duration_ms")


def test_float_nonfinite_still_refused_after_int_guard():
    for bad in (float("nan"), float("inf"), float("-inf")):
        refused(lambda bad=bad: go(profiles=[{"pulse_shape": "rectangular",
                                              "peak_acceleration_g": bad, "duration_ms": 1}]),
                "peak_acceleration_g")


def refused_exact(fn, msg):
    with pytest.raises(st.ShockError) as e:
        fn()
    assert str(e.value) == "SHOCK1547: " + msg


def test_float_caps_validated_per_field():
    def peak(v):
        return go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": v, "duration_ms": 1}])

    def dur(v):
        return go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": 1, "duration_ms": v}])

    for bad in (0.0, -1.0, 100000.5, 1e9):
        refused(lambda bad=bad: peak(bad), "peak_acceleration_g")
    for ok in (1.0, 100000.0):
        assert peak(ok)["profiles_supplied"] == 1
    for bad in (0.0, -1.0, 60000.5, 1e9, 100000.0):
        refused(lambda bad=bad: dur(bad), "duration_ms")
    for ok in (1.0, 60000.0):
        assert dur(ok)["profiles_supplied"] == 1


def test_acceptance_cap_boundaries_accepted():
    prof = {"pulse_shape": "rectangular", "peak_acceleration_g": 1, "duration_ms": 1}
    r = st.plan({"profiles": [prof] * 20, "specimen_count": 1000, "axes": ["x", "y", "z"],
                 "acceptance_criteria": ["c" * 64] * 10})
    assert r["profiles_supplied"] == 20 and r["specimen_count"] == 1000
    assert r["axes"] == ["x", "y", "z"] and r["acceptance_criteria_declared"] == 10
    assert go(specimen_count=1)["specimen_count"] == 1


def test_axis_and_pulse_length_exact_messages():
    refused_exact(lambda: go(axes=["xxxxxxxx"]), "axes entries must be x, y or z")  # 8 chars: length check passed
    refused_exact(lambda: go(axes=["xxxxxxxxx"]), "axes entries must be at most 8 characters")  # 9 chars
    refused_exact(lambda: go(profiles=[{"pulse_shape": "s" * 32, "peak_acceleration_g": 1,
                                        "duration_ms": 1}]), "unsupported pulse_shape")  # 32 chars: length check passed
    refused_exact(lambda: go(profiles=[{"pulse_shape": "s" * 33, "peak_acceleration_g": 1,
                                        "duration_ms": 1}]), "pulse_shape must be at most 32 characters")


def test_oversized_dicts_refused_before_iteration_setprofile():
    # generator frames re-fire "call" on every resumption, so pin by source line:
    # the profile-level genexpr must never start when the profile is oversized.
    lines = _SRC.read_text().splitlines()
    outer_ln = next(i for i, l in enumerate(lines, 1) if "for k in data" in l)
    prof_ln = next(i for i, l in enumerate(lines, 1) if "for k in prof" in l)
    events = []

    def tracer(frame, event, arg):
        if event == "call" and frame.f_code.co_name == "<genexpr>":
            events.append(frame.f_code.co_firstlineno)
        return tracer

    oversized = {"profiles": [], "specimen_count": 1, "axes": ["x"],
                 "acceptance_criteria": [], "z1": 1}
    sys.setprofile(tracer)
    try:
        try:
            st.plan(oversized)
            raise AssertionError("oversized mapping accepted")
        except st.ShockError as e:
            assert "unknown key" in str(e)
        assert events == []  # length refusal precedes any generator expression
        try:
            go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": 1,
                          "duration_ms": 1, "z1": 1}])
            raise AssertionError("oversized profile accepted")
        except st.ShockError as e:
            assert "unknown profile key" in str(e)
        # the outer key-type genexpr ran; the profile-level genexpr never started
        assert outer_ln in events and prof_ln not in events
    finally:
        sys.setprofile(None)


def test_max_picks_the_largest_estimate():
    r = go(profiles=[{"pulse_shape": "rectangular", "peak_acceleration_g": 10, "duration_ms": 1},
                     {"pulse_shape": "rectangular", "peak_acceleration_g": 20, "duration_ms": 1}])
    assert r["max_estimated_delta_velocity_m_per_s"] == r["plan"][1]["estimated_delta_velocity_m_per_s"]
    assert r["max_estimated_delta_velocity_m_per_s"] > r["plan"][0]["estimated_delta_velocity_m_per_s"]
