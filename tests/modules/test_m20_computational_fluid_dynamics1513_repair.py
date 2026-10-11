"""Repair pins for row 1513 CFD: uniform numeric rule, isolation, refusals."""
import sys
from fractions import Fraction
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

import pytest

MOD_PATH = (Path(__file__).resolve().parent.parent.parent
            / "backend/app/modules/m20_general_cognitive_worker/computational_fluid_dynamics1513.py")
spec = spec_from_file_location("computational_fluid_dynamics1513", MOD_PATH)
mod = module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

PREFIX = "COMPUT1513:"


def run(data):
    return mod.evaluate_flow_balance(data)


def refusal(data):
    with pytest.raises(mod.CfdBalanceRefusal) as ei:
        run(data)
    return ei.value


def base_payload(rate="10"):
    return {"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": rate}]}


class TestNumericRulePins:
    """Mandated pins: exact acceptance/refusal list for the uniform numeric rule."""

    def test_scientific_notation_string_refused(self):
        r = refusal(base_payload("1e5"))
        assert r.code == PREFIX + "invalid_input"

    def test_underscore_string_refused(self):
        r = refusal(base_payload("1_0"))
        assert r.code == PREFIX + "invalid_input"

    def test_plus_sign_string_refused(self):
        r = refusal(base_payload("+1"))
        assert r.code == PREFIX + "invalid_input"

    def test_nan_inf_strings_refused(self):
        for bad in ("nan", "NaN", "inf", "-inf", "Infinity"):
            r = refusal(base_payload(bad))
            assert r.code == PREFIX + "invalid_input", bad

    def test_raw_length_cap_first_81_refused(self):
        r = refusal(base_payload("1" * 81))
        assert r.code == PREFIX + "resource_limit"

    def test_ten_mb_string_refused_fast(self):
        r = refusal(base_payload("1" * 10_000_000))
        assert r.code == PREFIX + "resource_limit"

    def test_eighty_chars_accepted_when_valid(self):
        s = " " * 40 + "1" + " " * 40  # 81 raw, over cap -> refused
        r = refusal(base_payload(s))
        assert r.code == PREFIX + "resource_limit"
        out = run(base_payload(" " * 39 + "1" + " " * 40))
        assert out["totals"]["mass_in_kg_per_s"] == "1"

    def test_magnitude_limit_string(self):
        r = refusal(base_payload("1e13"))
        assert r.code == PREFIX + "invalid_input"  # grammar refuses exponent
        r = refusal(base_payload("10000000000000"))
        assert r.code == PREFIX + "resource_limit"
        r = refusal(base_payload("10000000000001"))
        assert r.code == PREFIX + "resource_limit"

    def test_ascii_space_padding_passes(self):
        for s in (" 1", "1 ", "  10.5  "):
            out = run(base_payload(s))
            assert out["totals"]["mass_in_kg_per_s"] in ("1", "10.5")

    def test_non_ascii_padding_refused(self):
        for bad in ("\t1", "1\n", " 1", " 1", "\r1"):
            r = refusal(base_payload(bad))
            assert r.code == PREFIX + "invalid_input", repr(bad)

    def test_inner_space_refused(self):
        r = refusal(base_payload("1 2"))
        assert r.code == PREFIX + "invalid_input"

    def test_float_zero_point_one_is_exactly_one_tenth(self):
        out = run(base_payload(0.1))
        assert out["totals"]["mass_in_kg_per_s"] == "0.1"
        r = run({"ports": [{"id": "a", "direction": "in", "mass_flow_kg_per_s": 0.1},
                           {"id": "b", "direction": "out", "mass_flow_kg_per_s": "1/10"}]})
        assert r["mass_imbalance_percent"] == "0"

    def test_float_nan_inf_refused(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            r = refusal(base_payload(bad))
            assert r.code == PREFIX + "invalid_input"

    def test_float_grammar_not_applied_to_repr(self):
        out = run(base_payload(1e-5))  # repr "1e-05" would fail the string grammar
        assert out["totals"]["mass_in_kg_per_s"] == "0.00001"  # terminating decimal renders as decimal

    def test_fraction_strings(self):
        out = run(base_payload("1/3"))
        assert out["totals"]["mass_in_kg_per_s"] == "1/3"
        for bad in ("1/0", "1/-2", "1/02", ".5", "5.", "-", "0x10"):
            r = refusal(base_payload(bad))
            assert r.code == PREFIX + "invalid_input", bad

    def test_bool_refused(self):
        for bad in (True, False):
            r = refusal(base_payload(bad))
            assert r.code == PREFIX + "invalid_input"

    def test_digit_limit_per_part(self):
        r = refusal(base_payload("1" * 65))
        assert r.code == PREFIX + "resource_limit"
        r = refusal(base_payload("1." + "1" * 65))
        assert r.code == PREFIX + "resource_limit"
        r = refusal(base_payload("1/" + "1" * 65))
        assert r.code == PREFIX + "resource_limit"

    def test_int_bit_length_guard(self):
        big = 2 ** 213
        r = refusal(base_payload(big))
        assert r.code == PREFIX + "resource_limit"
        r = refusal(base_payload(2 ** 213 - 1))  # fits bit_length, over magnitude
        assert r.code == PREFIX + "resource_limit"


class TestIsolationAndRefusals:
    def test_boundary_conditions_list_not_aliased(self):
        bcs = ["inlet"]
        data = {"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                "boundary_conditions": bcs}
        out = run(data)
        out["boundary_conditions"].append("MUTATED")
        assert bcs == ["inlet"]

    def test_two_calls_byte_identical(self):
        data = {"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 0.1},
                          {"id": "p2", "direction": "out", "mass_flow_kg_per_s": "1/10"}],
                "boundary_conditions": ["wall"], "domain": "pipe"}
        assert run(data) == run(data)
        assert data["ports"][0]["mass_flow_kg_per_s"] == 0.1

    def test_non_json_leaf_refused_before_hashing(self):
        for bad in ({"a"}, b"x", object()):
            r = refusal({"ports": [{"id": "p1", "direction": "in",
                                    "mass_flow_kg_per_s": 1}], "domain": bad})
            assert r.code == PREFIX + "invalid_input"

    def test_unknown_top_key_code_and_message(self):
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "extra": 1})
        assert r.code == PREFIX + "invalid_input"
        assert str(r) == PREFIX + "invalid_input: unknown key at input"
        assert "extra" not in str(r)

    def test_unknown_port_key_code_and_message(self):
        r = refusal({"ports": [{"id": "p1", "direction": "in",
                                "mass_flow_kg_per_s": 1, "velocity": 2}]})
        assert r.code == PREFIX + "invalid_input"
        assert str(r) == PREFIX + "invalid_input: unknown key at ports"
        assert "velocity" not in str(r)

    def test_unicode_rule_on_text_fields(self):
        for bad in ("ab", "ab", "a b", "a b", "ab", "a​b"):
            r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                         "domain": bad})
            assert r.code == PREFIX + "invalid_input"
            assert "no Unicode control, line/paragraph separator or bidi/format characters" in str(r)

    def test_per_field_caps(self):
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "domain": "x" * 257})
        assert r.code == PREFIX + "resource_limit"
        r = refusal({"ports": [{"id": "x" * 129, "direction": "in", "mass_flow_kg_per_s": 1}]})
        assert r.code == PREFIX + "resource_limit"
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "boundary_conditions": ["x" * 257]})
        assert r.code == PREFIX + "resource_limit"
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "boundary_conditions": ["ok"] * 65})
        assert r.code == PREFIX + "resource_limit"

    def test_cap_first_order_text_field(self):
        # 257 chars including a control char: cap-first must refuse resource_limit,
        # not invalid_input (Unicode check must not run before the length cap)
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "domain": "x" * 256 + "\x00"})
        assert r.code == PREFIX + "resource_limit"

    def test_cap_first_order_numeric(self):
        # 81 raw chars with a tab inside: cap-first must refuse resource_limit
        r = refusal(base_payload("\t" + "1" * 80))
        assert r.code == PREFIX + "resource_limit"

    def test_zero_denominator_refused_by_grammar(self):
        r = refusal(base_payload("10/0"))
        assert r.code == PREFIX + "invalid_input"

    def test_negative_tolerance_and_range(self):
        payload = base_payload(1)
        payload["closure_tolerance_percent"] = 101
        r = refusal(payload)
        assert r.code == PREFIX + "invalid_input"


class TestV3ResourceOrder:
    """v3 pins: count/type caps before any iteration; no incoming copy;
    generic field-only reasons; receipt containers fresh."""

    class Bomb:
        def __deepcopy__(self, memo):
            raise RuntimeError("raw throw from custom __deepcopy__")

    class IterBombList(list):
        def __iter__(self):
            raise RuntimeError("iterated before the count cap")

    class IterBombDict(dict):
        def __iter__(self):
            raise RuntimeError("iterated before the count cap")
        def items(self):
            raise RuntimeError("iterated before the count cap")

    def test_custom_object_refused_cleanly(self):
        # no incoming deepcopy exists, so a hostile __deepcopy__ never runs
        r = refusal(self.Bomb())
        assert r.code == PREFIX + "invalid_input"
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "domain": self.Bomb()})
        assert r.code == PREFIX + "invalid_input"
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "boundary_conditions": [self.Bomb()]})
        assert r.code == PREFIX + "invalid_input"

    def test_count_cap_before_iteration_bc(self):
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "boundary_conditions": ["b"] * 65})
        assert r.code == PREFIX + "resource_limit"
        # exact type fires first: a list subclass is refused as wrong type
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "boundary_conditions": self.IterBombList(["b"] * 65)})
        assert r.code == PREFIX + "invalid_input"

    def test_count_cap_before_iteration_ports(self):
        r = refusal({"ports":
            [{"id": f"p{i}", "direction": "in", "mass_flow_kg_per_s": 1} for i in range(65)]})
        assert r.code == PREFIX + "resource_limit"
        r = refusal({"ports": self.IterBombList(
            [{"id": f"p{i}", "direction": "in", "mass_flow_kg_per_s": 1} for i in range(65)])})
        assert r.code == PREFIX + "invalid_input"  # exact type: subclass refused before len

    def test_count_cap_before_iteration_top_keys(self):
        d = self.IterBombDict({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}]})
        for i in range(5):
            d[f"extra{i}"] = i  # 6 keys > 5 allowed
        r = refusal(d)
        assert r.code == PREFIX + "invalid_input"

    def test_count_cap_before_iteration_port_object(self):
        port = self.IterBombDict({"id": "p1", "direction": "in",
                                  "mass_flow_kg_per_s": 1, "extra": 1})  # 4 keys > 3 allowed
        r = refusal({"ports": [port]})
        assert r.code == PREFIX + "invalid_input"

    def test_port_allowlist_at_exactly_cap_keys(self):
        # 3 keys (= cap), one unknown: the count cap cannot catch this; the
        # allowlist must (battery residual M1513-09)
        r = refusal({"ports": [{"id": "p1", "direction": "in", "velocity": 2}]})
        assert r.code == PREFIX + "invalid_input"
        assert "unknown key at ports" in str(r)

    def test_bc_count_cap_before_element_type(self):
        # 65 boundary conditions with a non-string first element: the count cap
        # must fire BEFORE the element-type scan (battery residual M1513v3-01)
        bcs = [123] + ["b"] * 64
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "boundary_conditions": bcs})
        assert r.code == PREFIX + "resource_limit"

    def test_bc_tuple_and_dict_refused(self):
        # deleting the BC guard would accept tuples/dicts as string iterables
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "boundary_conditions": ("wall", "inlet")})
        assert r.code == PREFIX + "invalid_input"
        r = refusal({"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                     "boundary_conditions": {"wall": 1}})
        assert r.code == PREFIX + "invalid_input"

    def test_exact_type_spies_1513(self):
        class SpyList(list):
            calls = []
            def __len__(self):
                SpyList.calls.append("len")
                raise RuntimeError("len called on subclass")
        class SpyDict(dict):
            calls = []
            def __len__(self):
                SpyDict.calls.append("len")
                raise RuntimeError("len called on subclass")
        base = {"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}]}
        for bad_input, key in ((SpyDict(base), None), (base, "ports"), (base, "boundary_conditions")):
            SpyList.calls = []
            SpyDict.calls = []
            if key is None:
                r = refusal(bad_input)
            elif key == "ports":
                r = refusal({"ports": SpyList(base["ports"])})
            else:
                r = refusal({"ports": base["ports"], "boundary_conditions": SpyList()})
            assert r.code == PREFIX + "invalid_input"
            assert SpyList.calls + SpyDict.calls == []
        # port object as dict subclass
        r = refusal({"ports": [SpyDict({"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1})]})
        assert r.code == PREFIX + "invalid_input"
        assert SpyDict.calls == []
        # tuples refuse for ports too
        r = refusal({"ports": ({"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1},)})
        assert r.code == PREFIX + "invalid_input"

    def test_detail_defaults_to_empty_dict(self):
        # public .detail must be {} on a default refusal (OR->AND mutant would make it None)
        r = refusal(base_payload("abc"))
        assert r.detail == {}

    def test_port_id_type_and_empty(self):
        # OR->AND mutant on the id guard: non-str id must refuse tagged, not pass or throw raw
        r = refusal({"ports": [{"id": 123, "direction": "in", "mass_flow_kg_per_s": 1}]})
        assert r.code == PREFIX + "invalid_input"
        r = refusal({"ports": [{"id": "", "direction": "in", "mass_flow_kg_per_s": 1}]})
        assert r.code == PREFIX + "invalid_input"
        r = refusal({"ports": [{"id": None, "direction": "in", "mass_flow_kg_per_s": 1}]})
        assert r.code == PREFIX + "invalid_input"

    def test_float_magnitude_pre_conversion(self):
        # float range check happens BEFORE Fraction conversion (EQ-unproven survivor)
        r = refusal(base_payload(1e13))
        assert r.code == PREFIX + "resource_limit"
        assert "magnitude" in str(r)
        r = refusal(base_payload(-1e13))
        assert r.code == PREFIX + "resource_limit"
        out = run(base_payload(1e12))  # at-cap passes
        assert out["totals"]["mass_in_kg_per_s"] == "1000000000000"

    def test_author_final_digit_rule(self):
        # combined significant digits <=64 AND fractional digits <=64, per token
        out = run(base_payload("999999999999." + "9" * 52))   # 12+52 = 64 sig: passes
        assert out["totals"]["mass_in_kg_per_s"].startswith("999999999999.")
        r = refusal(base_payload("999999999999." + "9" * 53))  # 65 sig: refuses
        assert r.code == PREFIX + "resource_limit"
        assert "significant digits" in str(r)
        out = run(base_payload("0." + "0" * 63 + "1"))  # 1 sig, 64 fraction: passes
        assert out["totals"]["mass_in_kg_per_s"] == "0." + "0" * 63 + "1"  # terminating decimal form
        r = refusal(base_payload("0." + "0" * 64 + "1"))  # 65 fraction: refuses
        assert r.code == PREFIX + "resource_limit"
        assert "fractional digits" in str(r)
        out = run(base_payload("1/" + "9" * 64))  # denominator token 64 sig: passes
        assert out["totals"]["mass_in_kg_per_s"] == "1/" + "9" * 64
        r = refusal(base_payload("1/" + "9" * 65))  # 65 sig: refuses
        assert r.code == PREFIX + "resource_limit"

    def test_bit_length_guard_exact(self):
        # the 213 guard is contractual: 2**213 (bit_length 214) refuses with the
        # bit-length reason BEFORE magnitude; 2**213-1 (bit_length 213) passes
        # the guard and refuses with the magnitude reason (peer ruling)
        r = refusal(base_payload(2 ** 213))
        assert r.code == PREFIX + "resource_limit"
        assert "bit length" in str(r)
        r = refusal(base_payload(2 ** 213 - 1))
        assert r.code == PREFIX + "resource_limit"
        assert "magnitude" in str(r)
        assert "bit length" not in str(r)

    def test_no_echo_duplicate_id(self):
        r = refusal({"ports": [{"id": "secret-port", "direction": "in", "mass_flow_kg_per_s": 1},
                               {"id": "secret-port", "direction": "out", "mass_flow_kg_per_s": 1}]})
        assert r.code == PREFIX + "invalid_input"
        assert "secret-port" not in str(r)

    def test_receipt_bc_list_is_fresh(self):
        data = {"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}],
                "boundary_conditions": ["wall"]}
        out = run(data)
        assert out["boundary_conditions"] is not data["boundary_conditions"]
        out["boundary_conditions"].append("MUT")
        assert data["boundary_conditions"] == ["wall"]
        data["boundary_conditions"].append("post")
        out2 = run(data)
        assert out["boundary_conditions"] == ["wall", "MUT"]  # caller mutation never reaches it
        assert out2["boundary_conditions"] == ["wall", "post"]

    def test_hash_canonical_includes_only_present_keys(self):
        import hashlib, json
        data = {"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}]}
        out = run(data)
        canon = {"ports": [{"id": "p1", "direction": "in", "mass_flow_kg_per_s": 1}]}
        assert out["provenance"]["input_sha256"] == hashlib.sha256(
            json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        data2 = dict(data, domain="pipe")
        out2 = run(data2)
        assert out2["provenance"]["input_sha256"] != out["provenance"]["input_sha256"]



class TestFloatConversionSpy:
    """Resource contract pin: an over-magnitude float is refused BEFORE any
    Fraction conversion runs. With the magnitude guard deleted the conversion
    spy fires and this pin fails."""

    def test_no_fraction_conversion_before_magnitude_refusal(self):
        calls = []
        real_fraction = mod.Fraction

        class Spy:
            def __new__(cls, *args, **kwargs):
                calls.append(args)
                return real_fraction(*args, **kwargs)

        mod.Fraction = Spy
        try:
            for value in (1e13, -1e13, 1.7976931348623157e308):
                calls.clear()
                with pytest.raises(mod.CfdBalanceRefusal) as ei:
                    mod._number(value, "probe", mod._Aggregate(), "probe")
                assert ei.value.code == PREFIX + "resource_limit"
                assert calls == [], "Fraction conversion fired before the magnitude refusal"
        finally:
            mod.Fraction = real_fraction


class TestSummaryExactCounts:
    """Summary contract pin: exact inflow/outflow counts. Direction-flip
    mutants at the summary comprehension lines give 1/1 or 2/2 and fail this."""

    def test_summary_counts_exact(self):
        data = {"ports": [
            {"id": "i1", "direction": "in", "mass_flow_kg_per_s": 1},
            {"id": "i2", "direction": "in", "mass_flow_kg_per_s": 1},
            {"id": "o1", "direction": "out", "mass_flow_kg_per_s": 2}]}
        assert run(data)["summary"] == {"port_count": 3, "inflow_count": 2, "outflow_count": 1}
