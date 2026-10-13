"""Group 8 independently-checked benchmark program tests. Hermetic, stdlib unittest."""
import copy
import importlib.util
import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
_P = _ROOT / "backend/app/modules/instinct_doc/benchmark_program_g8.py"
_spec = importlib.util.spec_from_file_location("benchmark_program_g8", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["benchmark_program_g8"] = m
_spec.loader.exec_module(m)

B1 = {"benchmark": "swe", "metric": "resolved", "name": "lead", "value": 50,
      "source_url": "https://a.example/x", "reported_date": "2026-09-01"}
B2 = dict(B1, value=51, source_url="https://b.example/y", reported_date="2026-09-02")
R1 = {"project": "atlas", "benchmark": "swe", "metric": "resolved",
      "higher_is_better": True, "value": 60, "run_id": "r1", "run_date": "2026-10-01"}
TASK = {"as_of": "2026-10-13", "projects": ["atlas", "sugar"],
        "runs": [R1], "baselines": [B1, B2]}


class Analyze(unittest.TestCase):
    def test_cross_checked_ahead_and_unmeasured_coverage(self):
        out = m.analyze(TASK)
        chk = out["baseline_checks"][0]
        self.assertEqual(chk["status"], "cross_checked")
        self.assertEqual(chk["value"], 50.5)  # median of the two domain values
        self.assertEqual(chk["source_count"], 2)
        comp = out["comparisons"][0]
        self.assertEqual(comp["verdict"], "ahead")
        self.assertEqual(comp["margin"], 9.5)
        self.assertEqual(comp["relative_margin"], round(9.5 / 50.5, 6))
        ledger = {l["project"]: l["verdict"] for l in out["project_ledger"]}
        self.assertEqual(ledger, {"atlas": "AHEAD", "sugar": "UNMEASURED"})
        self.assertEqual(out["summary"]["coverage"], 0.5)

    def test_single_source_never_supports_a_verdict(self):
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [R1], "baselines": [B1]})
        self.assertEqual(out["baseline_checks"][0]["status"], "single_source")
        self.assertEqual(out["comparisons"][0]["baseline_status"], "single_source")
        self.assertEqual(out["project_ledger"][0]["verdict"], "MEASURED_UNVERIFIED")
        self.assertEqual(out["summary"]["single_source_baselines"], 1)

    def test_conflicting_sources_disqualify_the_comparison(self):
        bad = dict(B2, value=80)  # 80 vs 50 disagrees beyond 5%
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [R1], "baselines": [B1, bad]})
        self.assertEqual(out["baseline_checks"][0]["status"], "conflicting")
        self.assertEqual(out["comparisons"][0]["verdict"], "unchecked_conflict")
        self.assertIsNone(out["comparisons"][0]["margin"])
        self.assertEqual(out["project_ledger"][0]["verdict"], "MEASURED_UNVERIFIED")
        self.assertEqual(out["summary"]["conflicting_baselines"], 1)

    def test_tolerance_boundary(self):
        ok = dict(B2, value=52.5)   # |50-52.5| = 2.5 <= 0.05 * 52.5 = 2.625
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [R1], "baselines": [B1, ok]})
        self.assertEqual(out["baseline_checks"][0]["status"], "cross_checked")
        over = dict(B2, value=53.0)  # 3.0 > 2.65
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [R1], "baselines": [B1, over]})
        self.assertEqual(out["baseline_checks"][0]["status"], "conflicting")

    def test_same_domain_twice_is_still_single_source(self):
        dup = dict(B1, source_url="https://a.example/other", reported_date="2026-09-03")
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [R1], "baselines": [B1, dup]})
        self.assertEqual(out["baseline_checks"][0]["status"], "single_source")
        self.assertEqual(out["baseline_checks"][0]["source_count"], 1)

    def test_latest_per_domain_is_the_representative(self):
        older = dict(B1, value=40, reported_date="2026-08-01")
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [R1], "baselines": [B1, older, B2]})
        chk = out["baseline_checks"][0]
        self.assertEqual(chk["values"], [50, 51])  # a.example keeps 50 (2026-09-01), not 40

    def test_behind_and_tied_verdicts(self):
        behind_run = dict(R1, value=40)
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [behind_run], "baselines": [B1, B2]})
        self.assertEqual(out["project_ledger"][0]["verdict"], "BEHIND")
        tied_run = dict(R1, value=50.5)
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [tied_run], "baselines": [B1, B2]})
        self.assertEqual(out["project_ledger"][0]["verdict"], "TIED")

    def test_lower_is_better(self):
        run = dict(R1, metric="latency", higher_is_better=False, value=40)
        b1 = dict(B1, metric="latency", value=50)
        b2 = dict(B2, metric="latency", value=50.5)
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [run], "baselines": [b1, b2]})
        self.assertEqual(out["comparisons"][0]["verdict"], "ahead")
        self.assertEqual(out["comparisons"][0]["margin"], 10.25)

    def test_median_aggregation_even_and_odd(self):
        runs = [dict(R1, run_id="r1", value=10), dict(R1, run_id="r2", value=20),
                dict(R1, run_id="r3", value=30)]
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": runs, "baselines": []})
        self.assertEqual(out["aggregates"][0]["value"], 20)
        self.assertEqual(out["aggregates"][0]["run_count"], 3)
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": runs + [dict(R1, run_id="r4", value=40)], "baselines": []})
        self.assertEqual(out["aggregates"][0]["value"], 25)

    def test_future_baseline_dropped_and_counted(self):
        future = dict(B2, reported_date="2027-01-01")
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [R1], "baselines": [B1, future]})
        self.assertEqual(out["summary"]["future_baselines_dropped"], 1)
        self.assertEqual(out["baseline_checks"][0]["status"], "single_source")

    def test_zero_baseline_relative_margin_none(self):
        z1 = dict(B1, value=0)
        z2 = dict(B2, value=0)
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [R1], "baselines": [z1, z2]})
        self.assertIsNone(out["comparisons"][0]["relative_margin"])
        self.assertEqual(out["comparisons"][0]["verdict"], "ahead")

    def test_determinism(self):
        self.assertEqual(m.analyze(TASK), m.analyze(copy.deepcopy(TASK)))


class Auditor8Round(unittest.TestCase):
    """Auditor-8: order-independent agreement, registrable-domain grouping."""

    def test_agreement_order_independent_permutations(self):
        import itertools
        sources = [("https://a.example/1", 100), ("https://b.example/2", 98),
                   ("https://c.example/3", 102)]
        statuses = set()
        for perm in itertools.permutations(sources):
            baselines = [dict(B1, source_url=u, value=v, reported_date="2026-09-0%d" % (i + 1))
                         for i, (u, v) in enumerate(perm)]
            out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                             "runs": [R1], "baselines": baselines})
            statuses.add(out["baseline_checks"][0]["status"])
        self.assertEqual(statuses, {"cross_checked"})

    def test_spread_beyond_tolerance_conflicting_in_every_order(self):
        import itertools
        sources = [("https://a.example/1", 100), ("https://b.example/2", 95),
                   ("https://c.example/3", 105)]
        statuses = set()
        for perm in itertools.permutations(sources):
            baselines = [dict(B1, source_url=u, value=v, reported_date="2026-09-0%d" % (i + 1))
                         for i, (u, v) in enumerate(perm)]
            out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                             "runs": [R1], "baselines": baselines})
            statuses.add(out["baseline_checks"][0]["status"])
        self.assertEqual(statuses, {"conflicting"})

    def test_subdomains_of_one_registrable_domain_are_one_source(self):
        b1 = dict(B1, source_url="https://www.vendor.com/report", value=50)
        b2 = dict(B2, source_url="https://blog.vendor.com/notes", value=51)
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [R1], "baselines": [b1, b2]})
        chk = out["baseline_checks"][0]
        self.assertEqual(chk["status"], "single_source")
        self.assertEqual(chk["source_count"], 1)
        self.assertEqual(chk["domains"], ["vendor.com"])

    def test_distinct_registrable_domains_count(self):
        b1 = dict(B1, source_url="https://www.alpha.com/x", value=50)
        b2 = dict(B2, source_url="https://beta.co.uk/y", value=51)
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [R1], "baselines": [b1, b2]})
        chk = out["baseline_checks"][0]
        self.assertEqual(chk["status"], "cross_checked")
        self.assertEqual(chk["source_count"], 2)
        self.assertEqual(chk["domains"], ["alpha.com", "beta.co.uk"])

    def test_common_second_level_suffixes(self):
        # small stated approximation: co.uk/org.uk/com.au/... count as one label
        b1 = dict(B1, source_url="https://a.vendor.co.uk/x", value=50)
        b2 = dict(B2, source_url="https://b.vendor.co.uk/y", value=51)
        out = m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                         "runs": [R1], "baselines": [b1, b2]})
        self.assertEqual(out["baseline_checks"][0]["status"], "single_source")


class Refusals(unittest.TestCase):
    def test_unregistered_project_refused(self):
        bad = dict(R1, project="ghost")
        with self.assertRaises(ValueError) as cm:
            m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                       "runs": [bad], "baselines": []})
        self.assertIn("UNREGISTERED", str(cm.exception))

    def test_bad_dates_urls_keys_refused(self):
        with self.assertRaises(ValueError):
            m.analyze({"as_of": "2026-13-01", "projects": ["a"], "runs": [], "baselines": []})
        with self.assertRaises(ValueError):
            m.analyze({"as_of": "2026-10-13", "projects": ["atlas"], "runs": [R1],
                       "baselines": [dict(B1, source_url="http://a.example/x")]})
        with self.assertRaises(ValueError):
            m.analyze({"as_of": "2026-10-13", "projects": ["a"], "runs": [], "baselines": [],
                       "debug": True})
        with self.assertRaises(ValueError):
            m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                       "runs": [dict(R1, run_date="2027-01-01")], "baselines": []})

    def test_bad_numbers_and_tolerance_refused(self):
        for bad in (True, float("nan"), float("inf"), 10 ** 19, "fast"):
            with self.assertRaises(ValueError):
                m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                           "runs": [dict(R1, value=bad)], "baselines": []})
        for tol in (0, -0.1, 0.6, float("inf"), True, "0.05"):
            with self.assertRaises(ValueError):
                m.analyze({"as_of": "2026-10-13", "projects": ["a"], "runs": [],
                           "baselines": [], "tolerance": tol})

    def test_duplicates_and_size_bounds_refused(self):
        with self.assertRaises(ValueError):
            m.analyze({"as_of": "2026-10-13", "projects": ["a", "a"], "runs": [], "baselines": []})
        with self.assertRaises(ValueError):
            m.analyze({"as_of": "2026-10-13", "projects": ["atlas"],
                       "runs": [R1, R1], "baselines": []})
        with self.assertRaises(ValueError):
            m.analyze({"as_of": "2026-10-13", "projects": ["a"] * 257, "runs": [], "baselines": []})


class Verification(unittest.TestCase):
    def test_clean_run_verifies(self):
        out = m.run(TASK)
        self.assertEqual(out["status"], "solved")
        self.assertTrue(out["verification"]["verified"])

    def _tamper(self, fn):
        result = m.analyze(TASK)
        fn(result)
        return m.verify(TASK, result)

    def test_tampered_verdict_rejected(self):
        receipt = self._tamper(lambda r: r["comparisons"][0].update(verdict="behind"))
        self.assertFalse(receipt["verified"])
        self.assertIn("comparisons", receipt["failed"])

    def test_tampered_median_rejected(self):
        receipt = self._tamper(lambda r: r["aggregates"][0].update(value=999))
        self.assertFalse(receipt["verified"])
        self.assertIn("aggregates", receipt["failed"])

    def test_tampered_baseline_status_rejected(self):
        receipt = self._tamper(lambda r: r["baseline_checks"][0].update(status="single_source"))
        self.assertFalse(receipt["verified"])
        self.assertIn("baseline_checks", receipt["failed"])

    def test_tampered_ledger_and_summary_rejected(self):
        receipt = self._tamper(lambda r: r["project_ledger"][1].update(verdict="AHEAD"))
        self.assertFalse(receipt["verified"])
        self.assertIn("project_ledger", receipt["failed"])
        receipt = self._tamper(lambda r: r["summary"].update(coverage=1.0))
        self.assertFalse(receipt["verified"])
        self.assertIn("summary", receipt["failed"])

    def test_unmeasured_project_hidden_rejected(self):
        receipt = self._tamper(lambda r: r["project_ledger"].pop())
        self.assertFalse(receipt["verified"])
        self.assertIn("project_ledger", receipt["failed"])

    def test_non_dict_result_rejected(self):
        self.assertEqual(m.verify(TASK, None)["failed"], ["structure"])

    def test_unknown_top_level_result_field_rejected(self):
        result = m.analyze(TASK)
        result["extra_claim"] = "world class"
        self.assertFalse(m.verify(TASK, result)["verified"])

    def test_missing_top_level_result_field_rejected(self):
        result = m.analyze(TASK)
        del result["comparisons"]
        self.assertFalse(m.verify(TASK, result)["verified"])

    def test_full_leaf_tamper_sweep(self):
        result = m.analyze(TASK)

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
            if m.verify(TASK, c)["verified"]:
                survivors.append(path)
        self.assertGreater(count, 30)
        self.assertEqual(survivors, [])



if __name__ == "__main__":
    unittest.main()
