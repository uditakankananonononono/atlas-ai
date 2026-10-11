"""P88|L76 deliverable 12: self-improvement hook VERIFIER. Consistency check of caller-supplied fixtures (stdlib unittest, hermetic).

Every field name, verdict and refusal code is an interpretation choice recorded in the contract doc.
"""
import ast
import copy
import itertools
import json
import pathlib
import random
import unittest

from app.modules.instinct_doc import selfimprove_verifier_p88 as mod
from app.modules.instinct_doc.selfimprove_verifier_p88 import verify

MODULE_PATH = pathlib.Path(mod.__file__)
SOURCE_LINE = "Deliverable 12: self-improvement mechanisms per tool/module,"


def task(id="t1", base=1.0, delta="d1", rescored=2.0, decision="accept", **extra):
    d = {"id": id, "baseline_score": base}
    if delta is not None:
        d["delta"] = delta
    if rescored is not None:
        d["rescored"] = rescored
    if decision is not None:
        d["decision"] = decision
    d.update(extra)
    return d


def rec(tasks=None, declared=True, hook="hooks/improve.v1", thr=1.5, minimp=0.5, id="mod-a", **extra):
    d = {"id": id, "mechanism": {"declared": declared, "hook_ref": hook}, "accept_threshold": thr, "min_improvement": minimp,
         "tasks": [task()] if tasks is None else tasks}
    d.update(extra)
    return d


class Base(unittest.TestCase):
    def refusal(self, data):
        with self.assertRaises(ValueError) as cm:
            verify(data)
        return str(cm.exception)


class Verdicts(Base):
    def test_roundtrip_consistent_known_answer(self):
        tasks = [task("a", 1.0, "d", 2.0, "accept"), task("b", 1.0, "d", 1.2, "reject"), task("c", 1.0, "d", 3.0, "accept"), task("d", 2.0, "d", 1.0, "reject")]
        r = verify(rec(tasks))
        self.assertEqual(r["verdict"], "roundtrip_consistent")
        self.assertEqual(r["reasons"], [])
        self.assertEqual([t["id"] for t in r["tasks"]], ["a", "b", "c", "d"])
        self.assertEqual([t["status"] for t in r["tasks"]], ["complete"] * 4)
        self.assertEqual([t["expected_decision"] for t in r["tasks"]], ["accept", "reject", "accept", "reject"])
        self.assertTrue(r["both_decisions_exercised"])
        self.assertEqual(r["counts"], {"tasks": 4, "complete": 4, "incomplete": 0, "inconsistent": 0})

    def test_exact_record_shape_and_honesty_fields(self):
        r = verify(rec())
        self.assertEqual(sorted(r), sorted(["contract", "id", "verdict", "registration", "tasks", "counts", "both_decisions_exercised", "reasons",
                                            "mechanism_executed", "improvement_claimed", "real_mechanism_verified", "limits"]))
        self.assertEqual(r["contract"], "P88|L76")
        self.assertEqual(r["id"], "mod-a")
        self.assertEqual(r["registration"], {"declared": True, "hook_ref": "hooks/improve.v1", "registered": True})
        self.assertEqual(r["tasks"][0], {"id": "t1", "stages": {"proposed": True, "rescored": True, "decided": True}, "delta": "d1", "baseline_score": 1.0,
                                         "rescored": 2.0, "decision": "accept", "expected_decision": "accept", "improvement_met": True, "threshold_met": True,
                                         "status": "complete"})
        self.assertIs(r["mechanism_executed"], False)
        self.assertIs(r["improvement_claimed"], False)
        self.assertIs(r["real_mechanism_verified"], False)
        text = " ".join(r["limits"]).lower()
        for word in ("fixture", "consistency", "not executed", "does not implement", "interpretation"):
            self.assertIn(word, text)

    def test_not_declared_is_no_mechanism_declared_even_with_perfect_tasks(self):
        r = verify(rec(declared=False))
        self.assertEqual(r["verdict"], "no_mechanism_declared")
        self.assertEqual(r["reasons"], ["not_declared"])
        self.assertFalse(r["registration"]["registered"])
        self.assertEqual(r["tasks"][0]["status"], "complete")

    def test_declared_without_hook_ref_is_not_registered(self):
        for hook in ("", "   "):
            r = verify(rec(hook=hook))
            self.assertEqual((r["verdict"], r["reasons"]), ("no_mechanism_declared", ["hook_ref_missing"]))
            self.assertEqual(r["registration"], {"declared": True, "hook_ref": hook, "registered": False})
        r = verify(rec(declared=False, hook=""))
        self.assertEqual(r["reasons"], ["hook_ref_missing", "not_declared"])

    def test_no_tasks_is_incomplete(self):
        r = verify(rec(tasks=[]))
        self.assertEqual((r["verdict"], r["reasons"]), ("roundtrip_incomplete", ["no_fixture_tasks"]))
        self.assertFalse(r["both_decisions_exercised"])
        r = verify(rec(tasks=[], declared=False))
        self.assertEqual(r["verdict"], "no_mechanism_declared")

    def test_missing_stages_make_incomplete_each_stage(self):
        cases = [
            (task(delta=None), {"proposed": False, "rescored": True, "decided": True}),
            (task(rescored=None), {"proposed": True, "rescored": False, "decided": True}),
            (task(decision=None), {"proposed": True, "rescored": True, "decided": False}),
            (task(delta=None, rescored=None, decision=None), {"proposed": False, "rescored": False, "decided": False}),
        ]
        for t, stages in cases:
            r = verify(rec([t]))
            self.assertEqual((r["verdict"], r["reasons"]), ("roundtrip_incomplete", ["incomplete_tasks"]), t)
            self.assertEqual((r["tasks"][0]["status"], r["tasks"][0]["stages"]), ("incomplete", stages))
            self.assertEqual(r["counts"]["incomplete"], 1)
        explicit = dict(task(), delta=None, rescored=None, decision=None)
        self.assertEqual(verify(rec([explicit]))["tasks"][0]["status"], "incomplete")  # explicit null equals absent

    def test_decision_without_rescore_has_no_expected_decision(self):
        t = verify(rec([task(rescored=None)]))["tasks"][0]
        self.assertIsNone(t["expected_decision"])
        self.assertIsNone(t["improvement_met"])
        self.assertIsNone(t["threshold_met"])
        self.assertIsNone(t["rescored"])

    def test_decision_mismatch_is_inconsistent_both_directions(self):
        for dec, rescored in (("reject", 3.0), ("accept", 1.0)):
            r = verify(rec([task(rescored=rescored, decision=dec)]))
            self.assertEqual((r["verdict"], r["reasons"]), ("decision_inconsistent", ["decision_mismatch"]))
            self.assertEqual(r["tasks"][0]["status"], "inconsistent")
            self.assertEqual(r["counts"]["inconsistent"], 1)

    def test_incomplete_takes_precedence_over_inconsistent_and_both_reasons_listed(self):
        r = verify(rec([task("a", rescored=1.0, decision="accept"), task("b", decision=None)]))
        self.assertEqual(r["verdict"], "roundtrip_incomplete")
        self.assertEqual(r["reasons"], ["decision_mismatch", "incomplete_tasks"])
        self.assertEqual(r["counts"], {"tasks": 2, "complete": 0, "incomplete": 1, "inconsistent": 1})

    def test_not_declared_takes_precedence_over_everything(self):
        r = verify(rec([task(decision=None), task("b", rescored=0.0, decision="accept")], declared=False))
        self.assertEqual(r["verdict"], "no_mechanism_declared")
        self.assertEqual(r["reasons"], ["decision_mismatch", "incomplete_tasks", "not_declared"])

    def test_accept_rule_needs_both_improvement_and_threshold(self):
        # baseline 1.0, min_improvement 0.5, threshold 1.5
        table = [(1.5, "accept", True, True), (1.25, "reject", False, False), (1.5 - 0.25, "reject", False, False)]
        for rescored, want, imp, thr in table:
            t = verify(rec([task(rescored=rescored, decision=want)]))["tasks"][0]
            self.assertEqual((t["expected_decision"], t["improvement_met"], t["threshold_met"], t["status"]), (want, imp, thr, "complete"), rescored)
        # improvement met but below threshold
        t = verify(rec([task(base=0.0, rescored=0.75, decision="reject")], thr=1.0, minimp=0.5))["tasks"][0]
        self.assertEqual((t["improvement_met"], t["threshold_met"], t["expected_decision"], t["status"]), (True, False, "reject", "complete"))
        # threshold met but improvement too small
        t = verify(rec([task(base=1.75, rescored=2.0, decision="reject")], thr=1.0, minimp=0.5))["tasks"][0]
        self.assertEqual((t["improvement_met"], t["threshold_met"], t["expected_decision"], t["status"]), (False, True, "reject", "complete"))

    def test_equality_boundaries_are_inclusive(self):
        t = verify(rec([task(base=1.0, rescored=1.5, decision="accept")], thr=1.5, minimp=0.5))["tasks"][0]
        self.assertEqual((t["improvement_met"], t["threshold_met"], t["expected_decision"]), (True, True, "accept"))
        t = verify(rec([task(base=1.0, rescored=1.5, decision="reject")], thr=1.5, minimp=0.5))["tasks"][0]
        self.assertEqual(t["status"], "inconsistent")
        t = verify(rec([task(base=1.0, rescored=1.4999999999999998, decision="reject")], thr=1.5, minimp=0.5))["tasks"][0]
        self.assertEqual((t["threshold_met"], t["status"]), (False, "complete"))
        t = verify(rec([task(base=0.0, rescored=5.0, decision="accept")], thr=1.0, minimp=0.0))["tasks"][0]
        self.assertTrue(t["improvement_met"])
        t = verify(rec([task(base=5.0, rescored=5.0, decision="accept")], thr=1.0, minimp=0.0))["tasks"][0]
        self.assertTrue(t["improvement_met"] and t["expected_decision"] == "accept")  # zero improvement meets a zero minimum
        t = verify(rec([task(base=5.0, rescored=4.0, decision="reject")], thr=1.0, minimp=0.0))["tasks"][0]
        self.assertFalse(t["improvement_met"])

    def test_exact_arithmetic_not_float_rounding(self):
        # 0.1 + 0.2 style traps: exact binary values are compared, not rounded decimals
        t = verify(rec([task(base=0.1, rescored=0.30000000000000004, decision="accept")], thr=0.3, minimp=0.2))["tasks"][0]
        self.assertTrue(t["improvement_met"])
        big = 10.0 ** 12
        t = verify(rec([task(base=big - 1, rescored=big, decision="accept")], thr=big, minimp=1))["tasks"][0]
        self.assertEqual(t["expected_decision"], "accept")
        t = verify(rec([task(base=-big, rescored=big, decision="accept")], thr=0, minimp=big))["tasks"][0]
        self.assertEqual(t["expected_decision"], "accept")

    def test_both_decisions_exercised_flag_is_informational(self):
        r = verify(rec([task("a", decision="accept"), task("b", decision="accept", rescored=3.0)]))
        self.assertEqual(r["verdict"], "roundtrip_consistent")
        self.assertFalse(r["both_decisions_exercised"])
        r = verify(rec([task("a", rescored=0.0, decision="reject")]))
        self.assertFalse(r["both_decisions_exercised"])
        r = verify(rec([task("a", rescored=0.0, decision="reject"), task("b")]))
        self.assertTrue(r["both_decisions_exercised"])
        r = verify(rec([task("a", rescored=0.0, decision="accept"), task("b", decision=None)]))
        self.assertFalse(r["both_decisions_exercised"])  # only complete consistent tasks count

    def test_tasks_returned_in_sorted_id_order_and_permutation_invariant(self):
        ts = [task("b"), task("a"), task("B", rescored=0.0, decision="reject"), task("c")]
        r = verify(rec(ts))
        self.assertEqual([t["id"] for t in r["tasks"]], ["B", "a", "b", "c"])
        for perm in itertools.permutations(ts):
            self.assertEqual(verify(rec(list(perm))), r)


class Refusals(Base):
    def test_record_level(self):
        for bad in (None, [], "x", 5):
            self.assertEqual(self.refusal(bad), "P88:bad_type:record")
        self.assertEqual(self.refusal(rec(extra=1)), "P88:unknown_fields:record")
        for k in ("id", "mechanism", "accept_threshold", "min_improvement", "tasks"):
            d = rec(); del d[k]
            self.assertEqual(self.refusal(d), f"P88:empty_field:{k}")

    def test_id_codes(self):
        for bad in ("", "  "):
            self.assertEqual(self.refusal(rec(id=bad)), "P88:empty_field:id")
        for bad in (5, None, ["a"]):
            self.assertEqual(self.refusal(rec(id=bad)), "P88:bad_type:id")
        self.assertEqual(self.refusal(rec(id="a" * 65)), "P88:text_too_long:id")
        self.assertEqual(verify(rec(id="a" * 64))["id"], "a" * 64)

    def test_mechanism_codes(self):
        d = rec(); d["mechanism"] = "yes"
        self.assertEqual(self.refusal(d), "P88:bad_type:mechanism")
        d = rec(); d["mechanism"]["extra"] = 1
        self.assertEqual(self.refusal(d), "P88:unknown_fields:mechanism")
        for k in ("declared", "hook_ref"):
            d = rec(); del d["mechanism"][k]
            self.assertEqual(self.refusal(d), f"P88:empty_field:{k}")
        for bad in (1, 0, "true", None):
            self.assertEqual(self.refusal(rec(declared=bad)), "P88:bad_type:declared")
        for bad in (5, None, ["h"]):
            self.assertEqual(self.refusal(rec(hook=bad)), "P88:bad_type:hook_ref")
        self.assertEqual(self.refusal(rec(hook="h" * 129)), "P88:text_too_long:hook_ref")
        self.assertEqual(verify(rec(hook="h" * 128))["registration"]["hook_ref"], "h" * 128)

    def test_threshold_codes(self):
        for name, key in (("accept_threshold", "thr"), ("min_improvement", "minimp")):
            for bad in ("1", None, True, [1]):
                self.assertEqual(self.refusal(rec(**{key: bad})), f"P88:bad_type:{name}")
            for bad in (float("nan"), float("inf"), float("-inf"), 1e12 + 1e5, -1e12 - 1e5):
                if name == "min_improvement" and bad < 0:
                    continue
                self.assertEqual(self.refusal(rec(**{key: bad})), f"P88:bad_value:{name}")
        self.assertEqual(self.refusal(rec(minimp=-0.25)), "P88:bad_value:min_improvement")
        verify(rec(thr=-1e12, minimp=0)); verify(rec(thr=1e12, minimp=1e12))

    def test_tasks_container_and_count_bounds(self):
        for bad in (None, "x", (task(),), {"a": 1}):
            self.assertEqual(self.refusal(dict(rec(), tasks=bad)), "P88:bad_type:tasks")
        verify(rec(tasks=[task("t%d" % i) for i in range(32)]))
        self.assertEqual(self.refusal(rec(tasks=[task("t%d" % i) for i in range(33)])), "P88:limit_exceeded:tasks")
        self.assertEqual(self.refusal(rec(tasks=[5] * 33)), "P88:limit_exceeded:tasks")

    def test_task_codes(self):
        for bad in (None, 5, "t", []):
            self.assertEqual(self.refusal(rec(tasks=[bad])), "P88:bad_type:task")
        self.assertEqual(self.refusal(rec(tasks=[task(extra=1)])), "P88:unknown_fields:task")
        t = task(); del t["id"]
        self.assertEqual(self.refusal(rec(tasks=[t])), "P88:empty_field:task_id")
        t = task(); del t["baseline_score"]
        self.assertEqual(self.refusal(rec(tasks=[t])), "P88:empty_field:baseline_score")
        for bad in ("", "  "):
            self.assertEqual(self.refusal(rec(tasks=[task(id=bad)])), "P88:empty_field:task_id")
        for bad in (5, None, ["a"]):
            self.assertEqual(self.refusal(rec(tasks=[dict(task(), id=bad)])), "P88:bad_type:task_id")
        self.assertEqual(self.refusal(rec(tasks=[task(id="a" * 65)])), "P88:text_too_long:task_id")
        verify(rec(tasks=[task(id="a" * 64)]))

    def test_task_score_codes(self):
        for field in ("baseline_score", "rescored"):
            for bad in ("1", True, [1], {"a": 1}):
                t = task(); t[field] = bad
                self.assertEqual(self.refusal(rec(tasks=[t])), f"P88:bad_type:{field}")
            for bad in (float("nan"), float("inf"), -float("inf"), 1e12 + 1e5, -1e12 - 1e5):
                t = task(); t[field] = bad
                self.assertEqual(self.refusal(rec(tasks=[t])), f"P88:bad_value:{field}")
            t = task(); t[field] = 1e12
            verify(rec(tasks=[t]))

    def test_task_delta_and_decision_codes(self):
        for bad in ("", "  "):
            self.assertEqual(self.refusal(rec(tasks=[task(delta=bad)])), "P88:empty_field:delta")
        for bad in (5, True, ["d"]):
            self.assertEqual(self.refusal(rec(tasks=[task(delta=bad)])), "P88:bad_type:delta")
        self.assertEqual(self.refusal(rec(tasks=[task(delta="d" * 129)])), "P88:text_too_long:delta")
        verify(rec(tasks=[task(delta="d" * 128)]))
        for bad in ("Accept", "ACCEPT", "approve", "", "accepted"):
            self.assertEqual(self.refusal(rec(tasks=[task(decision=bad)])), "P88:bad_value:decision")
        for bad in (True, 1, ["accept"]):
            self.assertEqual(self.refusal(rec(tasks=[task(decision=bad)])), "P88:bad_type:decision")

    def test_duplicate_task_ids(self):
        self.assertEqual(self.refusal(rec(tasks=[task("d"), task("d")])), "P88:duplicate_task_id:d")
        self.assertEqual(self.refusal(rec(tasks=[task("d"), task("e", decision="zzz"), task("d")])), "P88:duplicate_task_id:d")

    def test_competing_bad_tasks_follow_sorted_ids_and_not_input_order(self):
        ts = [task("z", decision="bad1"), task("a", decision="bad2"), task("m", rescored="x")]
        self.assertEqual(self.refusal(rec(tasks=ts)), "P88:bad_value:decision")
        self.assertEqual(self.refusal(rec(tasks=list(reversed(ts)))), "P88:bad_value:decision")
        ts = [task("b", rescored="x"), task("a", extra=1)]
        self.assertEqual(self.refusal(rec(tasks=ts)), "P88:unknown_fields:task")
        self.assertEqual(self.refusal(rec(tasks=[5, task("a", decision="q")])), "P88:bad_value:decision")
        self.assertEqual(self.refusal(rec(tasks=[5, task("a")])), "P88:bad_type:task")

    def test_check_order_across_record(self):
        d = {"id": "", "mechanism": 5, "accept_threshold": "x", "min_improvement": None, "tasks": 3}
        self.assertEqual(self.refusal(d), "P88:empty_field:id")
        d["id"] = "ok"
        self.assertEqual(self.refusal(d), "P88:bad_type:mechanism")
        d["mechanism"] = {"declared": True, "hook_ref": "h"}
        self.assertEqual(self.refusal(d), "P88:bad_type:accept_threshold")
        d["accept_threshold"] = 1
        self.assertEqual(self.refusal(d), "P88:bad_type:min_improvement")
        d["min_improvement"] = 1
        self.assertEqual(self.refusal(d), "P88:bad_type:tasks")
        self.assertEqual(self.refusal(dict(d, extra=1)), "P88:unknown_fields:record")

    def test_strict_types_subclasses_refused(self):
        class S(str):
            pass

        class F(float):
            pass

        class D(dict):
            pass
        self.assertEqual(self.refusal(rec(id=S("a"))), "P88:bad_type:id")
        self.assertEqual(self.refusal(rec(thr=F(1.0))), "P88:bad_type:accept_threshold")
        self.assertEqual(self.refusal(D(rec())), "P88:bad_type:record")
        self.assertEqual(self.refusal(rec(tasks=[task(decision=S("accept"))])), "P88:bad_type:decision")

    def test_ints_and_floats_both_accepted(self):
        r = verify(rec([task(base=1, rescored=2, decision="accept")], thr=1, minimp=1))
        self.assertEqual(r["tasks"][0]["expected_decision"], "accept")
        self.assertEqual(r["tasks"][0]["baseline_score"], 1)
        self.assertIs(type(r["tasks"][0]["baseline_score"]), int)
        self.assertIs(type(r["tasks"][0]["rescored"]), int)
        r = verify(rec([task(base=1.5, rescored=2, decision="accept")], thr=1, minimp=0))
        self.assertIs(type(r["tasks"][0]["baseline_score"]), float)

    def test_bounds_are_exact_for_integers(self):
        for bad in (10 ** 12 + 1, -10 ** 12 - 1):
            self.assertEqual(self.refusal(rec(thr=bad)), "P88:bad_value:accept_threshold")
            t = task(); t["rescored"] = bad
            self.assertEqual(self.refusal(rec(tasks=[t])), "P88:bad_value:rescored")
        self.assertEqual(self.refusal(rec(minimp=10 ** 12 + 1)), "P88:bad_value:min_improvement")
        verify(rec(thr=10 ** 12, minimp=10 ** 12)); verify(rec(thr=-10 ** 12))

    def test_task_dict_subclass_and_inconsistent_decision_echoed(self):
        class D(dict):
            pass
        self.assertEqual(self.refusal(rec(tasks=[D(task())])), "P88:bad_type:task")
        t = verify(rec([task(rescored=3.0, decision="reject")]))["tasks"][0]
        self.assertEqual((t["decision"], t["expected_decision"], t["status"]), ("reject", "accept", "inconsistent"))


class Hygiene(Base):
    def test_input_not_mutated_and_output_independent(self):
        d = rec([task("b"), task("a", delta=None)])
        before = copy.deepcopy(d)
        r = verify(d)
        self.assertEqual(d, before)
        r["tasks"].append(1); r["limits"].append("x"); r["reasons"].append("y")
        r2 = verify(d)
        self.assertEqual(len(r2["tasks"]), 2)
        self.assertNotIn("x", r2["limits"])
        self.assertNotIn("x", mod.LIMITS)
        json.dumps(r2)

    def test_deterministic_repeat(self):
        d = rec([task("b", rescored=0.0, decision="reject"), task("a")])
        self.assertEqual(json.dumps(verify(d), sort_keys=True), json.dumps(verify(copy.deepcopy(d)), sort_keys=True))

    def test_generated_corpus_matches_independent_integer_oracle(self):
        """Scores are multiples of 0.25, so the oracle works in exact integer quarter-units."""
        rng = random.Random(8876)
        checked = {"accept": 0, "reject": 0, "incomplete": 0, "inconsistent": 0, "none": 0}
        for _ in range(600):
            thr_q, min_q = rng.randrange(-8, 17), rng.randrange(0, 9)
            declared, hook = rng.random() > 0.15, rng.choice(["h", "h", ""])
            tasks, oracle_tasks = [], []
            for i in range(rng.randrange(0, 6)):
                base_q = rng.randrange(-8, 17)
                has = [rng.random() > 0.15 for _ in range(3)]
                resc_q = rng.randrange(-8, 25)
                exp = "accept" if (resc_q - base_q >= min_q and resc_q >= thr_q) else "reject"
                dec = rng.choice(["accept", "reject", exp, exp])
                t = {"id": "t%02d" % i, "baseline_score": base_q / 4}
                if has[0]:
                    t["delta"] = "d"
                if has[1]:
                    t["rescored"] = resc_q / 4
                if has[2]:
                    t["decision"] = dec
                tasks.append(t)
                if not all(has):
                    oracle_tasks.append("incomplete")
                else:
                    oracle_tasks.append("complete" if dec == exp else "inconsistent")
            rng.shuffle(tasks)
            r = verify({"id": "m", "mechanism": {"declared": declared, "hook_ref": hook}, "accept_threshold": thr_q / 4,
                        "min_improvement": min_q / 4, "tasks": tasks})
            statuses = {t["id"]: t["status"] for t in r["tasks"]}
            for i, want in enumerate(oracle_tasks):
                self.assertEqual(statuses["t%02d" % i], want)
            if not declared or not hook.strip():
                want_v = "no_mechanism_declared"
            elif not tasks or "incomplete" in oracle_tasks:
                want_v = "roundtrip_incomplete"
            elif "inconsistent" in oracle_tasks:
                want_v = "decision_inconsistent"
            else:
                want_v = "roundtrip_consistent"
            self.assertEqual(r["verdict"], want_v)
            checked[{"no_mechanism_declared": "none", "roundtrip_incomplete": "incomplete", "decision_inconsistent": "inconsistent",
                     "roundtrip_consistent": "accept"}[want_v]] += 1
        for k in ("none", "incomplete", "inconsistent", "accept"):
            self.assertGreater(checked[k], 20, k)

    def test_source_line_in_contract_doc_and_interpretation_tag(self):
        doc = (MODULE_PATH.parents[4] / "docs" / "INSTINCT_P88_L76_SELFIMPROVE_VERIFIER_CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn(SOURCE_LINE, doc)
        self.assertIn("P88|L76", doc)
        self.assertGreaterEqual(doc.count("INTERPRETATION CHOICE"), 6)
        self.assertIn("P61", doc)

    def test_module_is_pure_stdlib_no_io_no_clock_no_execution(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imported |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                imported.add((n.module or "").split(".")[0])
        self.assertLessEqual(imported, {"__future__", "fractions", "math", "typing"})
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for banned in ("open", "eval", "exec", "compile", "__import__", "input", "print", "time", "random", "os", "socket", "importlib", "subprocess", "getattr"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
