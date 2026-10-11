"""Row 1545 Environmental Testing: hermetic stdlib tests, exact-value pins, row-tagged refusals. Loads the module by path."""
import importlib.util
import math
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/environmental_testing1545.py"
_spec = importlib.util.spec_from_file_location("environmental_testing1545", _SRC)
et = importlib.util.module_from_spec(_spec)
sys.modules["environmental_testing1545"] = et
_spec.loader.exec_module(et)

_PROF = {"condition": "temperature", "setpoint": 85, "unit": "celsius", "dwell_hours": 2.5}


def go(**over):
    d = {"profiles": [dict(_PROF)], "specimen_count": 3, "preconditioning": ["visual inspection"],
         "measurements": ["resistance"], "acceptance_criteria": ["no visible damage"]}
    d.update(over)
    return et.plan(d)


def refused(fn, word):
    with pytest.raises(et.EnvError) as e:
        fn()
    assert str(e.value).startswith("ENV1545: ")
    assert word in str(e.value)


def test_happy_path_exact():
    r = go()
    assert r["row"] == 1545 and r["test_type"] == "environmental"
    assert r["plan"] == [{"index": 0, "condition": "temperature", "unit": "celsius",
                          "setpoint": 85, "dwell_hours": 2.5}]
    assert r["total_dwell_hours"] == 2.5 and r["max_dwell_hours"] == 2.5
    assert r["condition_counts"] == {"temperature": 1}
    assert r["specimen_count"] == 3 and r["preconditioning_declared"] == 1
    assert r["measurements_declared"] == 1 and r["acceptance_criteria_declared"] == 1
    assert r["test_executed"] is False and r["plan_only"] is True
    assert len(r["limits"]) == 3


def test_condition_counts_sorted_and_dwell_sum():
    r = go(profiles=[{"condition": "humidity", "setpoint": 85, "unit": "percent_rh", "dwell_hours": 1.5},
                     dict(_PROF),
                     {"condition": "temperature", "setpoint": -40.0, "unit": "celsius", "dwell_hours": 2}])
    assert list(r["condition_counts"]) == ["humidity", "temperature"]
    assert r["condition_counts"] == {"humidity": 1, "temperature": 2}
    assert r["total_dwell_hours"] == math.fsum([1.5, 2.5, 2])
    assert r["max_dwell_hours"] == 2.5
    assert r["plan"][2]["setpoint"] == -40.0


def test_input_must_be_mapping():
    refused(lambda: et.plan([1, 2]), "mapping")


def test_missing_and_unknown_keys_refused():
    refused(lambda: et.plan({"profiles": [], "specimen_count": 1, "preconditioning": [],
                             "measurements": ["m"]}), "acceptance_criteria required")
    refused(lambda: go(extra=1), "unknown key")


def test_profiles_count_bounds():
    refused(lambda: go(profiles="x"), "list")
    refused(lambda: go(profiles=[]), "1 to 20")
    refused(lambda: go(profiles=[dict(_PROF)] * 21), "1 to 20")


def test_profile_schema_exact():
    refused(lambda: go(profiles=[{"condition": "temperature", "setpoint": 1, "unit": "celsius"}]), "dwell_hours required")
    refused(lambda: go(profiles=[dict(_PROF, x=1)]), "unknown profile key")


def test_condition_and_unit_enums():
    refused(lambda: go(profiles=[dict(_PROF, condition="vibration")]), "unsupported condition")
    refused(lambda: go(profiles=[dict(_PROF, condition=7)]), "unsupported condition")
    refused(lambda: go(profiles=[dict(_PROF, unit="psi")]), "unsupported unit")
    refused(lambda: go(profiles=[dict(_PROF, condition="humidity", unit="celsius")]), "unsupported unit")
    refused(lambda: go(profiles=[dict(_PROF, unit=3)]), "unsupported unit")
    for cond, unit, sp in (("humidity", "percent_rh", 85), ("pressure", "kpa", 0.5),
                           ("salt_fog", "percent", 5), ("dust", "g_per_m3", 10),
                           ("solar", "w_per_m2", 1120), ("temperature", "kelvin", 300),
                           ("temperature", "fahrenheit", 185)):
        assert go(profiles=[{"condition": cond, "setpoint": sp, "unit": unit, "dwell_hours": 1}])["profiles_supplied"] == 1


def test_setpoint_bounds_and_dwell():
    for bad in (True, "85", float("nan"), float("inf"), -273.16, 1001):
        refused(lambda bad=bad: go(profiles=[dict(_PROF, setpoint=bad)]), "setpoint")
    refused(lambda: go(profiles=[{"condition": "humidity", "setpoint": 101, "unit": "percent_rh", "dwell_hours": 1}]), "setpoint")
    refused(lambda: go(profiles=[{"condition": "humidity", "setpoint": -1, "unit": "percent_rh", "dwell_hours": 1}]), "setpoint")
    for bad in (True, "1", float("nan"), 0, -1, 100001):
        refused(lambda bad=bad: go(profiles=[dict(_PROF, dwell_hours=bad)]), "dwell_hours")
    r = go(profiles=[dict(_PROF, setpoint=-273.15, dwell_hours=100000)])
    assert r["profiles_supplied"] == 1


def test_specimen_and_text_lists():
    for bad in (True, 0, -1, 1001, 2.5, "3"):
        refused(lambda bad=bad: go(specimen_count=bad), "specimen_count")
    refused(lambda: go(measurements=[]), "measurements")
    refused(lambda: go(measurements=["m"] * 21), "measurements")
    refused(lambda: go(measurements=[" "]), "measurements")
    refused(lambda: go(measurements=["x" * 65]), "measurements")
    refused(lambda: go(measurements="visual"), "measurements")
    refused(lambda: go(preconditioning=["p"] * 11), "preconditioning")
    refused(lambda: go(acceptance_criteria=["c"] * 11), "acceptance_criteria")
    refused(lambda: go(acceptance_criteria=[7]), "acceptance_criteria")
    r = go(preconditioning=[], acceptance_criteria=[], measurements=["m"] * 20)
    assert r["preconditioning_declared"] == 0 and r["measurements_declared"] == 20


def test_raw_length_cap_before_strip():
    refused(lambda: go(acceptance_criteria=[" " * 65]), "at most 64 characters")


def test_unicode_cc_cf_zl_zp_refused_zs_accepted():
    for bad in ("a\tb", "a\xadb", "a\u2060b", "a\u2028b", "a\x7fb", "a\u200bb"):
        refused(lambda bad=bad: go(measurements=[bad]), "Unicode")
        refused(lambda bad=bad: go(preconditioning=[bad]), "Unicode")
        refused(lambda bad=bad: go(acceptance_criteria=[bad]), "Unicode")
    refused(lambda: go(acceptance_criteria=["soft\xad hyphen"]), "Unicode")  # U+00AD pin
    refused(lambda: go(acceptance_criteria=["word\u2060joiner"]), "Unicode")  # U+2060 pin
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

    refused(lambda: et.plan(OddDict({"profiles": [], "specimen_count": 1, "preconditioning": [],
                                     "measurements": [], "acceptance_criteria": []})), "mapping")
    refused(lambda: go(profiles=OddList()), "list")
    refused(lambda: go(specimen_count=OddInt(3)), "specimen_count")
    refused(lambda: go(measurements=OddList(["m"])), "measurements")
    refused(lambda: go(measurements=[OddStr("m")]), "measurements")
    refused(lambda: go(profiles=[dict(_PROF, condition=OddStr("temperature"))]), "condition")
    refused(lambda: go(profiles=[dict(_PROF, unit=OddStr("celsius"))]), "unit")
    refused(lambda: go(profiles=[dict(_PROF, setpoint=OddInt(85))]), "setpoint")
    refused(lambda: go(profiles=[dict(_PROF, dwell_hours=OddInt(2))]), "dwell_hours")


def test_condition_and_unit_raw_cap_then_enum():
    refused(lambda: go(profiles=[dict(_PROF, condition="c" * 33)]), "condition must be at most 32 characters")
    refused(lambda: go(profiles=[dict(_PROF, condition="temperature⁠")]), "unsupported condition")
    refused(lambda: go(profiles=[dict(_PROF, unit="u" * 33)]), "unit must be at most 32 characters")
    refused(lambda: go(profiles=[dict(_PROF, unit="celsius⁠")]), "unsupported unit")


def test_strict_key_types():
    refused(lambda: et.plan({1: "x", "profiles": [], "specimen_count": 1,
                             "preconditioning": [], "measurements": []}), "keys must be text")
    refused(lambda: go(profiles=[{1: "x", "condition": "temperature",
                                  "setpoint": 1, "unit": "celsius"}]), "profile keys must be text")


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
    refused(lambda: go(profiles=[dict(_PROF, setpoint=huge)]), "setpoint")
    refused(lambda: go(profiles=[dict(_PROF, dwell_hours=huge)]), "dwell_hours")


def test_cap_boundaries_accepted():
    r = et.plan({"profiles": [dict(_PROF)] * 20, "specimen_count": 1000,
                 "preconditioning": ["p" * 64] * 10, "measurements": ["m" * 64] * 20,
                 "acceptance_criteria": ["c" * 64] * 10})
    assert r["profiles_supplied"] == 20 and r["specimen_count"] == 1000
    assert r["preconditioning_declared"] == 10 and r["acceptance_criteria_declared"] == 10
    assert go(specimen_count=1)["specimen_count"] == 1


def test_oversized_dicts_refused_before_iteration_setprofile():
    lines = _SRC.read_text().splitlines()
    outer_ln = next(i for i, l in enumerate(lines, 1) if "for k in data" in l)
    prof_ln = next(i for i, l in enumerate(lines, 1) if "for k in prof" in l)
    events = []

    def tracer(frame, event, arg):
        if event == "call" and frame.f_code.co_name == "<genexpr>":
            events.append(frame.f_code.co_firstlineno)
        return tracer

    oversized = {"profiles": [], "specimen_count": 1, "preconditioning": [],
                 "measurements": [], "acceptance_criteria": [], "z1": 1}
    sys.setprofile(tracer)
    try:
        try:
            et.plan(oversized)
            raise AssertionError("oversized mapping accepted")
        except et.EnvError as e:
            assert "unknown key" in str(e)
        assert events == []
        try:
            go(profiles=[dict(_PROF, z1=1)])
            raise AssertionError("oversized profile accepted")
        except et.EnvError as e:
            assert "unknown profile key" in str(e)
        assert outer_ln in events and prof_ln not in events
    finally:
        sys.setprofile(None)


def test_max_dwell_picks_the_largest():
    r = go(profiles=[dict(_PROF, dwell_hours=1),
                     dict(_PROF, dwell_hours=9)])
    assert r["max_dwell_hours"] == 9
    assert r["total_dwell_hours"] == 10


def test_dict_subclass_profile_refused():
    # strict guard: a dict SUBCLASS profile must refuse with the baseline EnvError
    # (kills the guard-deletion mutant at the "each profile must be a mapping" check)
    class Sneaky(dict):
        pass
    prof = Sneaky(_PROF)
    assert isinstance(prof, dict) and type(prof) is not dict
    refused(lambda: go(profiles=[prof]), "mapping")
