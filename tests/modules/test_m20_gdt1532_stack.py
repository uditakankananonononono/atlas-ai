"""Stdlib-only independent endpoint oracle for bounded row 1532."""
import copy
import importlib.util
import itertools
from fractions import Fraction as F
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "backend/app/modules/m20_general_cognitive_worker/datum_stack1532.py"
spec = importlib.util.spec_from_file_location("gdt1532", CORE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
E = module.evaluate_stack


def packet():
    return {"geometry": "linear_1d", "unit": "mm",
            "datums": [{"id": "D", "offset": 7, "unit": "mm", "source_ref": "drawing:D"}],
            "components": [{"id": "b", "datum": "D", "nominal": 10, "lower": 9, "upper": 11,
                            "sign": 1, "unit": "mm", "source_ref": "drawing:b"},
                           {"id": "a", "datum": "D", "nominal": 4, "lower": 3, "upper": 5,
                            "sign": -1, "unit": "mm", "source_ref": "drawing:a"}],
            "fit_limits": [{"id": "F", "lower": 4, "upper": 8, "unit": "mm", "source_ref": "fit:F"}]}


class StackTests(unittest.TestCase):
    def error(self, data, code):
        with self.assertRaises(ValueError) as c:
            E(data)
        self.assertEqual(str(c.exception), code)

    def test_signed_analytical_and_trace(self):
        r = E(packet())
        self.assertEqual((r["nominal"], r["lower"], r["upper"]), ("6", "4", "8"))
        self.assertEqual(r["fit_status"], "guaranteed_within_declared_limits")
        self.assertEqual([x["id"] for x in r["source_trace"]], ["a", "b"])
        self.assertEqual(r["source_trace"][0], {"id": "a", "source_ref": "drawing:a", "datum": "D",
            "datum_source_ref": "drawing:D", "sign": -1, "nominal_contribution": "-11",
            "lower_contribution": "-12", "upper_contribution": "-10"})
        self.assertFalse(r["physical_inspection_claimed"])
        self.assertFalse(r["full_gdt_claimed"])

    def test_endpoint_oracle(self):
        for n in range(1, 6):
            for signs in itertools.product((-1, 1), repeat=n):
                d = packet(); d["fit_limits"] = []
                d["components"] = [dict(d["components"][0], id=str(i), sign=s,
                    nominal=i+1, lower=i, upper=i+2) for i, s in enumerate(signs)]
                values = [sum(s*(7+v) for s, v in zip(signs, point))
                    for point in itertools.product(*[(i, i+2) for i in range(n)])]
                r = E(d)
                self.assertEqual(F(r["lower"]), min(values))
                self.assertEqual(F(r["upper"]), max(values))
                self.assertEqual(r["fit_status"], "no_fit_limits_declared")

    def test_datum_translation_and_permutation(self):
        d=packet(); a=E(d); d["datums"][0]["offset"]=123
        b=E(d); self.assertEqual(tuple(a[k] for k in ("nominal","lower","upper")), tuple(b[k] for k in ("nominal","lower","upper")))
        d["components"].reverse(); self.assertEqual(b,E(d))
        d["fit_limits"] += [dict(d["fit_limits"][0], id="G", lower=2, upper=10)]
        r=E(d); d["fit_limits"].reverse(); self.assertEqual(r,E(d))

    def test_single_datum_offset_is_not_ignored(self):
        d=packet(); d["components"]=d["components"][:1]
        self.assertEqual(E(d)["nominal"], "17")
        d["datums"][0]["offset"]=8; self.assertEqual(E(d)["nominal"], "18")

    def test_exact_decimal_zero_tolerance(self):
        d=packet(); d["datums"][0]["offset"]=0; d["components"]=d["components"][:1]
        d["components"][0].update(nominal="0.1", lower="0.1", upper="0.1")
        d["fit_limits"][0].update(lower="0.1", upper="0.1")
        r=E(d); self.assertEqual(r["lower"],"1/10"); self.assertEqual(r["fit_status"],"guaranteed_within_declared_limits")

    def test_fit_intersection(self):
        d=packet(); d["fit_limits"] += [dict(d["fit_limits"][0], id="G", lower=9, upper=10)]
        self.assertEqual(E(d)["fit_status"],"no_feasible_fit")
        d["fit_limits"][1].update(lower=6,upper=10)
        self.assertEqual(E(d)["fit_intersection"], {"lower":"6", "upper":"8"})
        self.assertEqual(E(d)["fit_status"],"not_guaranteed")
        d["fit_limits"][1].update(lower=8,upper=9)
        self.assertEqual(E(d)["fit_intersection"], {"lower":"8", "upper":"8"})

    def test_refusals(self):
        for geometry in ("angular", "profile", "true_position", "rss"):
            d=packet(); d["geometry"]=geometry; self.error(d,"GDT1532:unsupported_geometry")
        d=packet(); d["rss"]=True; self.error(d,"GDT1532:unknown_fields:packet")
        d=packet(); d["components"][0]["datum"]="missing"; self.error(d,"GDT1532:unknown_datum:b")
        for collection in ("datums","components","fit_limits"):
            d=packet(); d[collection].append(copy.deepcopy(d[collection][0])); self.error(d,"GDT1532:duplicate_id:"+collection)
            d=packet(); d[collection][0]["unit"]="inch"; self.error(d,"GDT1532:unit_mismatch:"+collection)
            d=packet(); d[collection][0]["source_ref"]=""; self.error(d,"GDT1532:invalid_text:source_ref")
        d=packet(); d["components"][0]["sign"]=True; self.error(d,"GDT1532:invalid_sign:b")
        d=packet(); d["components"][0]["nominal"]=12; self.error(d,"GDT1532:nominal_outside_interval:b")
        for collection in ("components","fit_limits"):
            d=packet(); d[collection][0].update(lower=10,upper=9); self.error(d,"GDT1532:inverted_interval:"+d[collection][0]["id"])
        for v in (float("nan"),float("inf"),True,"NaN","1/2",None):
            d=packet(); d["components"][0]["lower"]=v; self.error(d,"GDT1532:invalid_number:lower")
        d=packet(); d["unit"]="degree"; self.error(d,"GDT1532:unsupported_unit")
        d=packet(); d["components"]=[]; self.error(d,"GDT1532:invalid_count:components")
        self.error([],"GDT1532:invalid_packet")

    def test_fresh_ids_multi_datum_and_no_mutation(self):
        d=packet(); d["datums"].append(dict(d["datums"][0],id="X",offset=2,source_ref="drawing:X"))
        d["components"][1]["datum"]="X"
        before=copy.deepcopy(d); r=E(d)
        self.assertEqual((r["nominal"],r["lower"],r["upper"]),("11","9","13"))
        self.assertEqual(r["fit_status"],"no_feasible_fit")
        self.assertEqual(d,before)
        d["components"][0]["id"]="fresh-42"; d["components"][0]["datum"]="missing"
        self.error(d,"GDT1532:unknown_datum:fresh-42")

    def test_decimal_and_text_precision_bounds(self):
        d=packet(); d["datums"][0]["offset"]="1000000000000.000000000000000001"
        self.error(d,"GDT1532:number_bound:offset")
        d=packet(); d["datums"][0]["offset"]="0."+"0"*17+"1"; E(d)
        d["datums"][0]["offset"]="0."+"0"*18+"1"; self.error(d,"GDT1532:number_bound:offset")
        # Decimal spelling length 64 and 65, value 1 within the magnitude bound.
        d=packet(); d["datums"][0]["offset"]="0"*63+"1"; E(d)
        d["datums"][0]["offset"]="0"*64+"1"; self.error(d,"GDT1532:invalid_number:offset")

    def test_r2_finite_float_acceptance(self):
        d=packet(); d["datums"][0]["offset"]=0.5
        d["components"]=[dict(d["components"][0],nominal=1.25,lower=1.0,upper=1.5)]
        d["fit_limits"]=[dict(d["fit_limits"][0],lower=1.0,upper=2.0)]
        r=E(d)
        self.assertEqual((r["nominal"],r["lower"],r["upper"]),("7/4","3/2","2"))
        self.assertEqual(r["fit_status"],"guaranteed_within_declared_limits")

    def test_r2_integer_magnitude_exact_bound(self):
        d=packet(); d["datums"][0]["offset"]=10**12
        d["components"]=d["components"][:1]; d["fit_limits"]=[]
        self.assertEqual(E(d)["nominal"],str(10**12+10))
        d["datums"][0]["offset"]=10**12+1
        self.error(d,"GDT1532:number_bound:offset")
        d["datums"][0]["offset"]=-(10**12); E(d)
        d["datums"][0]["offset"]=-(10**12+1)
        self.error(d,"GDT1532:number_bound:offset")

    def test_r2_record_shape_errors_all_collections(self):
        for collection in ("datums","components","fit_limits"):
            for value in (None,42,"row",[],True):
                d=packet(); d[collection][0]=value
                self.error(d,"GDT1532:invalid_record:"+collection)
            d=packet(); del d[collection][0]["source_ref"]
            self.error(d,"GDT1532:invalid_fields:"+collection)
            d=packet(); d[collection][0]["extra"]=0
            self.error(d,"GDT1532:invalid_fields:"+collection)
        d=packet(); d["datums"]=[]
        self.error(d,"GDT1532:invalid_count:datums")

    def test_r2_feature_and_all_claim_flags(self):
        r=E(packet())
        self.assertEqual(r["feature_id"],1532)
        self.assertIs(type(r["feature_id"]),int)
        for key in ("sources_verified","full_gdt_claimed","physical_inspection_claimed",
                    "release_authorized","statistical_rss_performed"):
            self.assertIs(r[key],False,key)

    def test_r2_disjoint_stack_fit_both_sides(self):
        for lower,upper in ((-2,3),(9,10)):
            d=packet(); d["fit_limits"][0].update(lower=lower,upper=upper)
            r=E(d)
            self.assertEqual((r["lower"],r["upper"]),("4","8"))
            self.assertEqual(r["fit_intersection"],{"lower":str(lower),"upper":str(upper)})
            self.assertEqual(r["fit_status"],"no_feasible_fit")

    def test_n_nplus1_bounds(self):
        for collection in ("datums","components","fit_limits"):
            d=packet(); proto=d[collection][0]
            d[collection]=[dict(proto,id=("D" if collection=="datums" and i==0 else "z"+str(i))) for i in range(64)]
            E(d)
            d[collection].append(dict(proto,id="extra")); self.error(d,"GDT1532:invalid_count:"+collection)
        d=packet(); d["components"][0]["source_ref"]="x"*128; E(d)
        d["components"][0]["source_ref"]+="x"; self.error(d,"GDT1532:invalid_text:source_ref")
        d=packet(); d["datums"][0]["offset"]="1000000000000"; E(d)
        d["datums"][0]["offset"]="1000000000001"; self.error(d,"GDT1532:number_bound:offset")

if __name__ == "__main__":
    unittest.main(verbosity=2)
