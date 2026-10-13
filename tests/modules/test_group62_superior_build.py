"""Group 62 superior-build acceptance pipeline tests. Hermetic, stdlib unittest."""
import copy
import importlib.util
import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
_P = _ROOT / "backend/app/modules/instinct_doc/superior_build_g62.py"
_spec = importlib.util.spec_from_file_location("superior_build_g62", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["superior_build_g62"] = m
_spec.loader.exec_module(m)

FULL = {"subjects": [{"name": "acme",
                      "reference_capabilities": ["search", "sync"],
                      "build_capabilities": ["search", "sync"],
                      "reference_metrics": {"qps": 100,
                                            "latency_ms": {"value": 50, "direction": "lower"}},
                      "build_metrics": {"qps": 150, "latency_ms": 40}}]}


class Analyze(unittest.TestCase):
    def test_superior_happy_path(self):
        out = m.analyze(FULL)
        s = out["subjects"][0]
        self.assertEqual(s["verdict"], "SUPERIOR")
        self.assertEqual([t["verdict"] for t in s["metric_targets"]], ["superior", "superior"])
        self.assertEqual(out["tickets"], [])
        self.assertEqual(out["verdicts"], {"SUPERIOR": 1, "NOT_SUPERIOR": 0, "INCOMPLETE_EVIDENCE": 0})

    def test_missing_capability_is_not_superior_with_ticket(self):
        task = {"subjects": [{"name": "acme", "reference_capabilities": ["search", "sync"],
                              "build_capabilities": ["search"]}]}
        out = m.analyze(task)
        self.assertEqual(out["subjects"][0]["verdict"], "NOT_SUPERIOR")
        self.assertEqual(out["subjects"][0]["missing_capabilities"], ["sync"])
        self.assertEqual(len(out["tickets"]), 1)
        t = out["tickets"][0]
        self.assertEqual(t["kind"], "capability_gap")
        self.assertTrue(t["acceptance_tests_first"])
        self.assertIn("sync", t["acceptance"])

    def test_missing_build_metric_is_incomplete_not_failure(self):
        task = {"subjects": [{"name": "acme", "reference_metrics": {"qps": 100},
                              "build_metrics": {}}]}
        out = m.analyze(task)
        self.assertEqual(out["subjects"][0]["verdict"], "INCOMPLETE_EVIDENCE")
        self.assertEqual(out["subjects"][0]["metric_targets"][0]["verdict"], "unevaluable")
        self.assertEqual(out["tickets"][0]["kind"], "evidence_gap")

    def test_below_metric_names_the_measurable_bar(self):
        task = {"subjects": [{"name": "acme", "reference_metrics": {"qps": 100},
                              "build_metrics": {"qps": 90}}]}
        out = m.analyze(task)
        self.assertEqual(out["subjects"][0]["verdict"], "NOT_SUPERIOR")
        t = out["tickets"][0]
        self.assertEqual(t["kind"], "metric_gap")
        self.assertEqual(t["acceptance"], "qps > 100.0 (reference 100, margin 1.0)")

    def test_tie_is_not_superior(self):
        task = {"subjects": [{"name": "acme", "reference_metrics": {"qps": 100},
                              "build_metrics": {"qps": 100}}]}
        self.assertEqual(m.analyze(task)["subjects"][0]["verdict"], "NOT_SUPERIOR")

    def test_margin_scales_the_bar(self):
        base = {"name": "acme", "reference_metrics": {"qps": 100}, "build_metrics": {"qps": 150}}
        self.assertEqual(m.analyze({"subjects": [base], "margin": 2})["subjects"][0]["verdict"],
                         "NOT_SUPERIOR")
        self.assertEqual(m.analyze({"subjects": [base], "margin": 1.5})["subjects"][0]["verdict"],
                         "NOT_SUPERIOR")  # strict: 150 > 150 is false
        base2 = dict(base, build_metrics={"qps": 151})
        self.assertEqual(m.analyze({"subjects": [base2], "margin": 1.5})["subjects"][0]["verdict"],
                         "SUPERIOR")

    def test_lower_is_better_and_zero_reference(self):
        out = m.analyze({"subjects": [{"name": "a", "reference_metrics":
                                       {"lat": {"value": 50, "direction": "lower"}},
                                       "build_metrics": {"lat": 49}}]})
        self.assertEqual(out["subjects"][0]["verdict"], "SUPERIOR")
        out = m.analyze({"subjects": [{"name": "a", "reference_metrics":
                                       {"lat": {"value": 0, "direction": "lower"}},
                                       "build_metrics": {"lat": 0}}]})
        self.assertEqual(out["subjects"][0]["verdict"], "NOT_SUPERIOR")

    def test_empty_reference_data_is_incomplete(self):
        out = m.analyze({"subjects": [{"name": "a"}]})
        self.assertEqual(out["subjects"][0]["verdict"], "INCOMPLETE_EVIDENCE")

    def test_determinism(self):
        self.assertEqual(m.analyze(FULL), m.analyze(copy.deepcopy(FULL)))


class Refusals(unittest.TestCase):
    def test_bool_and_nonfinite_and_negative_metrics_refused(self):
        for bad in (True, float("inf"), float("nan"), -1, "fast"):
            task = {"subjects": [{"name": "a", "reference_metrics": {"qps": bad},
                                  "build_metrics": {"qps": 1}}]}
            with self.assertRaises(ValueError):
                m.analyze(task)

    def test_bad_direction_and_bad_margin_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.analyze({"subjects": [{"name": "a", "reference_metrics":
                                     {"qps": {"value": 1, "direction": "sideways"}}}]})
        self.assertIn("BAD_DIRECTION", str(cm.exception))
        for margin in (0, -1, float("inf"), 11, True, "2"):
            with self.assertRaises(ValueError):
                m.analyze({"subjects": [{"name": "a", "reference_metrics": {"qps": 1}}],
                           "margin": margin})

    def test_size_bounds_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.analyze({"subjects": []})
        self.assertIn("EMPTY", str(cm.exception))
        with self.assertRaises(ValueError):
            m.analyze({"subjects": [{"name": "a"}] * 65})
        with self.assertRaises(ValueError):
            m.analyze({"subjects": [{"name": "a", "reference_metrics": {"qps": 10 ** 18 + 1}}]})
        with self.assertRaises(ValueError):
            m.analyze({"subjects": [{"name": "a", "reference_capabilities": ["x"] * 257}]})

    def test_unknown_keys_refused(self):
        with self.assertRaises(ValueError):
            m.analyze({"subjects": [{"name": "a"}], "debug": True})
        with self.assertRaises(ValueError):
            m.analyze({"subjects": [{"name": "a", "is_superior": True}]})


class Verification(unittest.TestCase):
    def _tamper(self, fn):
        result = m.analyze(FULL)
        fn(result)
        return m.verify(FULL, result)

    def test_clean_run_verifies(self):
        out = m.run(FULL)
        self.assertEqual(out["status"], "solved")
        self.assertTrue(out["verification"]["verified"])

    def test_tampered_verdict_rejected(self):
        receipt = self._tamper(lambda r: r["subjects"][0].update(verdict="NOT_SUPERIOR"))
        self.assertFalse(receipt["verified"])
        out = m.run(FULL)
        tampered = copy.deepcopy(out["result"])
        tampered["subjects"][0]["verdict"] = "NOT_SUPERIOR"
        self.assertFalse(m.verify(FULL, tampered)["verified"])

    def test_tampered_target_rejected(self):
        receipt = self._tamper(lambda r: r["subjects"][0]["metric_targets"][0].update(target=1))
        self.assertFalse(receipt["verified"])
        self.assertIn("metric_targets", receipt["failed"])

    def test_tampered_actual_rejected(self):
        receipt = self._tamper(lambda r: r["subjects"][0]["metric_targets"][0].update(actual=10 ** 6))
        self.assertFalse(receipt["verified"])

    def test_removed_ticket_rejected(self):
        task = {"subjects": [{"name": "a", "reference_capabilities": ["x"], "build_capabilities": []}]}
        result = m.analyze(task)
        result["tickets"] = []
        result["ticket_count"] = 0
        receipt = m.verify(task, result)
        self.assertFalse(receipt["verified"])
        self.assertIn("tickets", receipt["failed"])
        self.assertIn("counts", receipt["failed"])

    def test_tampered_counts_and_margin_rejected(self):
        receipt = self._tamper(lambda r: r.update(ticket_count=99))
        self.assertFalse(receipt["verified"])
        self.assertIn("counts", receipt["failed"])
        receipt = self._tamper(lambda r: r.update(margin=2.0))
        self.assertFalse(receipt["verified"])
        self.assertIn("margin", receipt["failed"])

    def test_non_dict_result_rejected(self):
        receipt = m.verify(FULL, "junk")
        self.assertFalse(receipt["verified"])
        self.assertEqual(receipt["failed"], ["structure"])


class AuditorProbesRound2(unittest.TestCase):
    """Auditor-7 round-2: margin floor, exact result keys, capability-only
    verdicts, and a full leaf-tamper sweep."""

    def test_margin_below_one_refused(self):
        base = {"name": "x", "reference_metrics": {"v": 100}, "build_metrics": {"v": 60}}
        for margin in (0.5, 1e-320, 0, -2, 0.999999):
            with self.assertRaises(ValueError) as cm:
                m.analyze({"subjects": [base], "margin": margin})
            self.assertIn("BAD_MARGIN", str(cm.exception))

    def test_margin_one_and_bounds_still_work(self):
        base = {"name": "x", "reference_metrics": {"v": 100}, "build_metrics": {"v": 120}}
        self.assertEqual(m.analyze({"subjects": [base], "margin": 1})["subjects"][0]["verdict"],
                         "SUPERIOR")
        self.assertEqual(m.analyze({"subjects": [base], "margin": 10})["subjects"][0]["verdict"],
                         "NOT_SUPERIOR")
        with self.assertRaises(ValueError):
            m.analyze({"subjects": [base], "margin": 10.000001})

    def test_lower_direction_never_manufactures_superior(self):
        # with margin >= 1 the derived target can never exceed the reference
        base = {"name": "x",
                "reference_metrics": {"v": {"value": 100, "direction": "lower"}},
                "build_metrics": {"v": 60}}
        self.assertEqual(m.analyze({"subjects": [base], "margin": 1})["subjects"][0]["verdict"],
                         "SUPERIOR")  # genuinely better: 60 < 100
        base["build_metrics"]["v"] = 100
        self.assertEqual(m.analyze({"subjects": [base], "margin": 1})["subjects"][0]["verdict"],
                         "NOT_SUPERIOR")  # tie is not superior

    def test_unknown_top_level_result_field_rejected(self):
        result = m.analyze(FULL)
        result["extra_claim"] = "world best"
        receipt = m.verify(FULL, result)
        self.assertFalse(receipt["verified"])

    def test_missing_top_level_result_field_rejected(self):
        result = m.analyze(FULL)
        del result["tickets"]
        self.assertFalse(m.verify(FULL, result)["verified"])

    def test_capability_only_is_not_superior(self):
        task = {"subjects": [{"name": "x", "reference_capabilities": ["a", "b"],
                              "build_capabilities": ["a", "b"]}]}
        out = m.analyze(task)
        self.assertEqual(out["subjects"][0]["verdict"], "INCOMPLETE_EVIDENCE")
        # with one numeric metric genuinely beaten it becomes SUPERIOR
        task["subjects"][0]["reference_metrics"] = {"v": 10}
        task["subjects"][0]["build_metrics"] = {"v": 11}
        self.assertEqual(m.analyze(task)["subjects"][0]["verdict"], "SUPERIOR")

    def test_full_leaf_tamper_sweep(self):
        task = {"subjects": [{"name": "x", "reference_capabilities": ["a"],
                              "build_capabilities": ["a"],
                              "reference_metrics": {"v": 100},
                              "build_metrics": {"v": 120}}]}
        result = m.analyze(task)

        def leaves(x, path=()):
            if isinstance(x, dict):
                for k, v in x.items():
                    yield from leaves(v, path + (k,))
            elif isinstance(x, list):
                for i, v in enumerate(x):
                    yield from leaves(v, path + (i,))
            else:
                yield path, x

        survivors = []
        count = 0
        for path, v in leaves(result):
            c = copy.deepcopy(result)
            o = c
            for k in path[:-1]:
                o = o[k]
            o[path[-1]] = ("tampered" if isinstance(v, str)
                           else not v if isinstance(v, bool)
                           else v + 1 if isinstance(v, (int, float)) else "tampered")
            count += 1
            if m.verify(task, c)["verified"]:
                survivors.append(path)
        self.assertGreater(count, 20)
        self.assertEqual(survivors, [])


if __name__ == "__main__":
    unittest.main()
