"""S6.4 / c37.breakthroughs tests. Hermetic, stdlib unittest, no network.

HER WORDS (owner spec text, local record): "train and model the best tools
across all sectors and present breakthroughs".
"""
import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
from app.modules.c37 import breakthroughs as m  # noqa: E402

AS_OF = "2026-10-11"


def claim(etype, source, repro=None, text="c"):
    return {"text": text, "evidence_url": "https://e.example/x", "evidence_type": etype,
            "provenance": {"source": source, "independent_reproduction_url": repro}}


def metric(v, b, hib=True, name="acc"):
    return {"name": name, "value": v, "baseline_value": b, "higher_is_better": hib}


def item(i, sector="ai", published="2026-10-09", url=None, claims=None, metrics=None,
         license="MIT", kind="tool"):
    return {"id": i, "sector": sector, "title": "t-" + i, "url": url or "https://r.example/" + i,
            "published": published, "kind": kind, "license": license,
            "claims": claims if claims is not None else [], "metrics": metrics or []}


def req(items, **kw):
    r = {"as_of": AS_OF, "sectors": ["ai", "bio", "energy"], "items": items, "window_days": 14}
    r.update(kw)
    return r


def err(case, request):
    with case.assertRaises(ValueError) as cm:
        m.run(request)
    return str(cm.exception)


def by_id(rows):
    return {r["id"]: r for r in rows}


class Refusals(unittest.TestCase):
    def test_items_missing_or_wrong_type_is_bad_type(self):
        r = req([])
        del r["items"]
        self.assertEqual(err(self, r), "INTEL_REFUSED_BAD_TYPE:items")
        self.assertEqual(err(self, req("x")), "INTEL_REFUSED_BAD_TYPE:items")
        self.assertEqual(err(self, req({"a": 1})), "INTEL_REFUSED_BAD_TYPE:items")

    def test_empty_list_is_noitems(self):
        self.assertEqual(err(self, req([])), "INTEL_REFUSED_NOITEMS")

    def test_nonempty_none_usable_is_nosource(self):
        stale = item("s", published="2026-01-01")
        http = item("h", url="http://r.example/h")
        self.assertEqual(err(self, req([stale, http, "junk"])), "INTEL_REFUSED_NOSOURCE")

    def test_unrequested_sector_only_is_nosource(self):
        self.assertEqual(err(self, req([item("o", sector="space")])), "INTEL_REFUSED_NOSOURCE")

    def test_request_shape(self):
        self.assertEqual(err(self, "x"), "INTEL_REFUSED_BAD_TYPE:request")
        self.assertEqual(err(self, req([item("a")], sectors="ai")), "INTEL_REFUSED_BAD_TYPE:sectors")
        self.assertEqual(err(self, req([item("a")], sectors=[])), "INTEL_REFUSED_EMPTY:sectors")
        for bad in ([1], [""], ["  "], ["ai", None], [["ai"]], [True]):
            self.assertEqual(err(self, req([item("a")], sectors=bad)), "INTEL_REFUSED_BAD_TYPE:sectors")
        r = req([item("a")])
        del r["sectors"]
        self.assertEqual(err(self, r), "INTEL_REFUSED_BAD_TYPE:sectors")
        self.assertEqual(err(self, req([item("a")], as_of="2026-13-40")), "INTEL_REFUSED_BAD_TYPE:as_of")
        self.assertEqual(err(self, req([item("a")], as_of=5)), "INTEL_REFUSED_BAD_TYPE:as_of")
        for bad in (0, -1, True, 1.5, "7", 366):
            self.assertEqual(err(self, req([item("a")], window_days=bad)),
                             "INTEL_REFUSED_BAD_TYPE:window_days")
        for bad in (0, True, "3", 101):
            self.assertEqual(err(self, req([item("a")], top_n=bad)), "INTEL_REFUSED_BAD_TYPE:top_n")

    def test_control_chars_refused_by_real_policy(self):
        self.assertEqual(err(self, req([item("a")], sectors=["a\x00b"])),
                         "INTEL_REFUSED_CONTROL_CHARS:sector")


class Grades(unittest.TestCase):
    def grade(self, claims, metrics=None):
        out = m.run(req([item("g", claims=claims, metrics=metrics)]))
        rows = []
        for blk in out["breakthroughs_by_sector"]["ai"].values():
            rows += blk
        return rows[0]

    def test_a_peer_reviewed_journal_and_conference(self):
        for src in ("journal", "conference"):
            self.assertEqual(self.grade([claim("peer_reviewed", src)])["grade"], "A")

    def test_peer_reviewed_other_source_is_c_with_conflict(self):
        for src in ("vendor", "third_party", "unknown"):
            row = self.grade([claim("peer_reviewed", src)])
            self.assertEqual(row["grade"], "C")
            self.assertIn("label_conflict", row["flags"])

    def test_a_benchmark_with_reproduction(self):
        row = self.grade([claim("benchmark", "third_party", "https://x.example/repro")])
        self.assertEqual(row["grade"], "A")

    def test_b_needs_baseline_and_third_party(self):
        b = self.grade([claim("benchmark", "third_party")], [metric(0.9, 0.8)])
        self.assertEqual(b["grade"], "B")
        nb = self.grade([claim("benchmark", "third_party")], [metric(0.9, None)])
        self.assertEqual(nb["grade"], "C")
        self.assertEqual(nb["metrics"][0]["delta"], None)
        self.assertEqual(nb["metrics"][0]["value"], 0.9)
        self.assertNotIn("rank", nb)

    def test_vendor_benchmark_without_reproduction_is_c(self):
        row = self.grade([claim("benchmark", "vendor")], [metric(0.99, 0.5)])
        self.assertEqual(row["grade"], "C")

    def test_vendor_statement_c_none_d(self):
        self.assertEqual(self.grade([claim("vendor_statement", "vendor")])["grade"], "C")
        self.assertEqual(self.grade([claim("none", "unknown")])["grade"], "D")
        self.assertEqual(self.grade([])["grade"], "D")
        self.assertEqual(self.grade([claim("preprint", "unknown")])["grade"], "D")

    def test_best_claim_wins(self):
        row = self.grade([claim("vendor_statement", "vendor"), claim("peer_reviewed", "journal")])
        self.assertEqual(row["grade"], "A")

    def test_label_text_everywhere(self):
        row = self.grade([claim("peer_reviewed", "journal")])
        self.assertEqual(row["grade_label"], "supplied-label grade A (not verified by this unit)")


class Scoring(unittest.TestCase):
    def one(self, metrics, claims=None, published="2026-10-11", window=14):
        claims = claims or [claim("peer_reviewed", "journal")]
        out = m.run(req([item("s", published=published, claims=claims, metrics=metrics)],
                        window_days=window))
        return out["breakthroughs_by_sector"]["ai"]

    def test_higher_is_better_delta(self):
        s = self.one([metric(0.9, 0.6)])
        self.assertEqual(s["breakthroughs"][0]["metrics"][0]["delta"], 0.5)
        self.assertEqual(s["breakthroughs"][0]["score"], 0.5)

    def test_lower_is_better_delta(self):
        s = self.one([metric(50, 100, hib=False, name="latency")])
        self.assertEqual(s["breakthroughs"][0]["metrics"][0]["delta"], 0.5)
        worse = self.one([metric(150, 100, hib=False, name="latency")])
        self.assertEqual(worse["breakthroughs"], [])
        self.assertEqual(worse["notable"][0]["metrics"][0]["delta"], -0.5)

    def test_average_over_metrics(self):
        s = self.one([metric(2, 1), metric(1, 1)])
        self.assertEqual(s["breakthroughs"][0]["score"], 0.5)

    def test_weights_a_vs_b(self):
        a = self.one([metric(2, 1)])["breakthroughs"][0]["score"]
        b = self.one([metric(2, 1)], claims=[claim("benchmark", "third_party")]
                     )["breakthroughs"][0]["score"]
        self.assertEqual(a, 1.0)
        self.assertEqual(b, 0.6)

    def test_recency_linear(self):
        edge = self.one([metric(2, 1)], published="2026-09-27")["breakthroughs"][0]["score"]
        self.assertEqual(edge, 0.5)
        mid = self.one([metric(2, 1)], published="2026-10-04")["breakthroughs"][0]["score"]
        self.assertEqual(mid, 0.75)

    def test_negative_baseline_uses_abs(self):
        s = self.one([metric(0, -2)])
        self.assertEqual(s["breakthroughs"][0]["metrics"][0]["delta"], 1.0)

    def test_cut_by_top_n_listed_unranked_under_notable(self):
        items = [item("c%d" % i, claims=[claim("peer_reviewed", "journal")],
                      metrics=[metric(1 + i / 10.0, 1)]) for i in range(1, 4)]
        out = m.run(req(items, top_n=1))["breakthroughs_by_sector"]["ai"]
        self.assertEqual([r["id"] for r in out["breakthroughs"]], ["c3"])
        self.assertEqual(sorted(r["id"] for r in out["notable"]), ["c1", "c2"])
        self.assertTrue(all("rank" not in r and "score" not in r and "cut_top_n" in r["flags"]
                            for r in out["notable"]))
        self.assertEqual(m.run(req(items, top_n=1))["coverage"]["by_sector"]["ai"]["cut_top_n"], 2)

    def test_zero_baseline_not_computable(self):
        s = self.one([metric(2, 0)])
        self.assertEqual(s["breakthroughs"], [])
        row = s["notable"][0]
        self.assertNotIn("score", row)
        self.assertNotIn("rank", row)
        self.assertIn("no_positive_delta", row["flags"])
        self.assertIn("baseline_zero", row["flags"])
        self.assertIn("baseline_zero", row["metrics"][0]["flags"])
        self.assertEqual(row["metrics"][0]["value"], 2)
        self.assertIsNone(row["metrics"][0]["delta"])

    def test_zero_baseline_metric_skipped_in_average(self):
        s = self.one([metric(2, 1), metric(5, 0)])
        self.assertEqual(s["breakthroughs"][0]["score"], 1.0)
        self.assertIn("baseline_zero", s["breakthroughs"][0]["flags"])

    def test_no_metrics_notable_score_zero(self):
        s = self.one([])
        self.assertEqual(s["breakthroughs"], [])
        self.assertNotIn("score", s["notable"][0])
        self.assertIn("no_positive_delta", s["notable"][0]["flags"])

    def test_c_and_d_not_flagged_no_positive_delta(self):
        c = self.one([metric(9, 1)], claims=[claim("vendor_statement", "vendor")])
        self.assertEqual(c["notable"][0]["flags"], [])
        d = self.one([metric(9, 1)], claims=[claim("none", "unknown")])
        self.assertEqual(d["unverified"][0]["flags"], [])

    def test_regression_notable_flagged_no_score(self):
        worse = self.one([metric(150, 100, hib=False, name="latency")])
        self.assertIn("no_positive_delta", worse["notable"][0]["flags"])
        self.assertNotIn("score", worse["notable"][0])
        self.assertNotIn("rank", worse["notable"][0])

    def test_ranking_order_and_top_n(self):
        items = [item("r%d" % i, claims=[claim("peer_reviewed", "journal")],
                      metrics=[metric(1 + i / 10.0, 1)], published="2026-10-11")
                 for i in range(1, 8)]
        out = m.run(req(items, top_n=3))
        ids = [r["id"] for r in out["breakthroughs_by_sector"]["ai"]["breakthroughs"]]
        self.assertEqual(ids, ["r7", "r6", "r5"])
        self.assertEqual([r["rank"] for r in out["breakthroughs_by_sector"]["ai"]["breakthroughs"]], [1, 2, 3])
        self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_used"], 7)
        self.assertEqual(out["coverage"]["by_sector"]["ai"]["cut_top_n"], 4)
        self.assertEqual(out["coverage"]["cut_top_n"], 4)

    def test_tie_break_id_asc(self):
        items = [item(i, url="https://r.example/" + u, claims=[claim("peer_reviewed", "journal")],
                      metrics=[metric(2, 1)]) for i, u in (("b", "a"), ("a", "b"))]
        ids = [r["id"] for r in m.run(req(items))["breakthroughs_by_sector"]["ai"]["breakthroughs"]]
        self.assertEqual(ids, ["a", "b"])


class Window(unittest.TestCase):
    def reasons(self, published, window=14):
        out = m.run(req([item("w", published=published), item("keep")], window_days=window))
        return out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"]

    def test_edge_inclusive_and_outside(self):
        self.assertEqual(self.reasons("2026-09-27"), {})
        self.assertEqual(self.reasons("2026-09-26"), {"stale": 1})
        self.assertEqual(self.reasons("2026-10-11"), {})
        self.assertEqual(self.reasons("2026-10-12"), {"future_date": 1})
        self.assertEqual(self.reasons("2026-10-01", window=5), {"stale": 1})

    def test_bad_inputs_dropped_with_reason(self):
        self.assertEqual(self.reasons("nope"), {"published_invalid": 1})
        self.assertEqual(self.reasons(None), {"published_invalid": 1})
        out = m.run(req([item("k"), item("u", url="http://x.example/u"),
                         item("n", url="https://"), item("c", sector="space"), "junk",
                         item("", url="https://x.example/e")]))
        cov = out["coverage"]
        self.assertEqual(cov["by_sector"]["ai"]["items_dropped_by_reason"], {"url_not_https": 2, "id_invalid": 1})
        self.assertEqual(cov["unattributed_dropped_by_reason"], {"sector_not_requested": 2})


class Dedupe(unittest.TestCase):
    def test_normalization_cases(self):
        n = m.normalize_url
        self.assertEqual(n("HTTPS://Ex.COM/a/?utm_source=x&b=1#frag"), "https://ex.com/a?b=1")
        self.assertEqual(n("https://ex.com/a/"), "https://ex.com/a")
        self.assertEqual(n("https://ex.com/a?UTM_x=1"), "https://ex.com/a")
        self.assertEqual(n("https://ex.com/a?b=1&c=2"), "https://ex.com/a?b=1&c=2")
        self.assertEqual(n("https://ex.com/"), "https://ex.com")
        self.assertIsNone(n("http://ex.com/a"))
        self.assertIsNone(n("https://"))
        self.assertIsNone(n("https://user@ex.com/a"))
        self.assertIsNone(n("ftp://ex.com"))
        self.assertIsNone(n(5))

    def test_keep_highest_grade_then_published_then_id(self):
        u = "https://d.example/p"
        lo = item("a-lo", url=u + "/?utm_medium=z", claims=[claim("vendor_statement", "vendor")])
        hi = item("z-hi", url=u + "#x", claims=[claim("peer_reviewed", "journal")],
                  published="2026-10-01")
        out = m.run(req([lo, hi]))
        rows = by_id(out["breakthroughs_by_sector"]["ai"]["breakthroughs"] + out["breakthroughs_by_sector"]["ai"]["notable"])
        self.assertEqual(list(rows), ["z-hi"])
        self.assertEqual(out["coverage"]["duplicate_url_count"], 1)
        self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {"duplicate_url": 1})

    def test_same_grade_newer_wins_then_id(self):
        u = "https://d.example/q"
        old = item("a", url=u, published="2026-10-01")
        new = item("b", url=u, published="2026-10-05")
        out = m.run(req([old, new]))
        self.assertEqual([r["id"] for r in out["breakthroughs_by_sector"]["ai"]["notable"] + out["breakthroughs_by_sector"]["ai"]["unverified"]], ["b"])
        t1, t2 = item("y", url=u), item("x", url=u)
        out = m.run(req([t1, t2]))
        self.assertEqual([r["id"] for r in out["breakthroughs_by_sector"]["ai"]["unverified"]], ["x"])

    def test_cross_sector_counts(self):
        u = "https://d.example/cross"
        a = item("a", sector="ai", url=u, claims=[claim("peer_reviewed", "journal")])
        b = item("b", sector="bio", url=u)
        out = m.run(req([a, b]))
        self.assertEqual(out["coverage"]["duplicate_url_count"], 1)
        self.assertEqual(out["coverage"]["by_sector"]["bio"]["items_dropped_by_reason"], {"duplicate_url": 1})
        self.assertEqual(out["coverage"]["by_sector"]["bio"]["items_supplied"], 1)
        self.assertEqual(out["coverage"]["by_sector"]["bio"]["items_used"], 0)
        self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_used"], 1)


class Integration(unittest.TestCase):
    def test_license_integrable_and_candidates(self):
        items = []
        for lic in ("MIT", "Apache-2.0", "BSD", "CC0", "proprietary", "unknown", "CC-BY", "GPL-3.0"):
            items.append(item("l-" + lic, license=lic, claims=[claim("peer_reviewed", "journal")],
                              metrics=[metric(2, 1)]))
        out = m.run(req(items, top_n=100))
        rows = by_id(out["breakthroughs_by_sector"]["ai"]["breakthroughs"])
        self.assertEqual(len(rows), 8)
        flags = {k: v["integrable_open_source"] for k, v in rows.items()}
        self.assertEqual(sorted(k for k, v in flags.items() if v),
                         ["l-Apache-2.0", "l-BSD", "l-CC0", "l-MIT"])
        cands = out["integration_candidates"]
        self.assertEqual(sorted(c["id"] for c in cands), ["l-Apache-2.0", "l-BSD", "l-CC0", "l-MIT"])
        self.assertTrue(all(c["action"] == "ticket_stub_only_no_install" for c in cands))

    def test_c_grade_open_source_not_a_candidate(self):
        out = m.run(req([item("c", claims=[claim("vendor_statement", "vendor")], metrics=[metric(9, 1)])]))
        self.assertEqual(out["integration_candidates"], [])


class Fixture40(unittest.TestCase):
    """40 items, 3 sectors, planted traps."""

    @classmethod
    def build(cls):
        items = []
        for i in range(10):
            items.append(item("ai%d" % i, sector="ai", claims=[claim("peer_reviewed", "journal")],
                              metrics=[metric(1.1 + i / 20.0, 1.0)]))
        for i in range(8):
            items.append(item("bio%d" % i, sector="bio",
                              claims=[claim("benchmark", "third_party", "https://x.example/r%d" % i)],
                              metrics=[metric(1.0 + i / 40.0, 1.0)], license="proprietary"))
        for i in range(8):
            items.append(item("en%d" % i, sector="energy", claims=[claim("benchmark", "third_party")],
                              metrics=[metric(80 - i, 100, hib=False, name="latency")]))
        items.append(item("TRAP-vendor", claims=[claim("vendor_statement", "vendor")],
                          metrics=[metric(1000, 1)]))
        items.append(item("TRAP-vbench", claims=[claim("benchmark", "vendor")], metrics=[metric(500, 1)]))
        items.append(item("TRAP-stale", published="2026-06-01", claims=[claim("peer_reviewed", "journal")],
                          metrics=[metric(100, 1)]))
        items.append(item("TRAP-dup-a", url="https://dup.example/z", claims=[claim("peer_reviewed", "journal")],
                          metrics=[metric(1.2, 1)]))
        items.append(item("TRAP-dup-b", url="https://dup.example/z/?utm_x=1"))
        items.append(item("TRAP-prop", claims=[claim("peer_reviewed", "journal")], metrics=[metric(3, 1)],
                          license="proprietary"))
        items.append(item("TRAP-lat", sector="energy", claims=[claim("peer_reviewed", "journal")],
                          metrics=[metric(10, 100, hib=False, name="latency")]))
        items.append(item("TRAP-unv", sector="bio", claims=[claim("none", "unknown")], metrics=[metric(7, 1)]))
        items.append(item("TRAP-ai-pad1"))
        items.append(item("TRAP-ai-pad2"))
        items.append(item("pad-bio", sector="bio"))
        items.append(item("pad-en", sector="energy"))
        items.append(item("pad-bio2", sector="bio"))
        items.append(item("pad-en2", sector="energy"))
        return items

    def test_counts_and_traps(self):
        items = self.build()
        self.assertEqual(len(items), 40)
        out = m.run(req(items, top_n=100))
        ai = out["breakthroughs_by_sector"]["ai"]
        ids_b = [r["id"] for r in ai["breakthroughs"]]
        self.assertNotIn("TRAP-vendor", ids_b)
        self.assertNotIn("TRAP-vbench", ids_b)
        self.assertNotIn("TRAP-stale", ids_b)
        self.assertNotIn("TRAP-dup-b", ids_b)
        self.assertIn("TRAP-vendor", [r["id"] for r in ai["notable"]])
        self.assertTrue(all("rank" not in r for r in ai["notable"]))
        vb = by_id(ai["notable"])["TRAP-vbench"]
        self.assertEqual(vb["grade"], "C")
        self.assertEqual(by_id(ai["breakthroughs"])["TRAP-prop"]["integrable_open_source"], False)
        lat = by_id(out["breakthroughs_by_sector"]["energy"]["breakthroughs"])["TRAP-lat"]
        self.assertEqual(lat["metrics"][0]["delta"], 0.9)
        self.assertEqual(by_id(out["breakthroughs_by_sector"]["bio"]["unverified"])["TRAP-unv"]["grade"], "D")
        cov = out["coverage"]
        self.assertEqual(cov["duplicate_url_count"], 1)
        bs = cov["by_sector"]
        self.assertEqual(bs["ai"]["items_dropped_by_reason"], {"duplicate_url": 1, "stale": 1})
        self.assertEqual(bs["ai"]["items_supplied"] + bs["bio"]["items_supplied"]
                         + bs["energy"]["items_supplied"], 40)
        self.assertEqual(cov["sectors_covered"], ["ai", "bio", "energy"])
        self.assertIn("computed", out["scope"]["not_implemented"][0] + "computed")


class Determinism(unittest.TestCase):
    def test_byte_identical_and_input_untouched(self):
        items = Fixture40.build()
        snap = copy.deepcopy(items)
        a = json.dumps(m.run(req(items)), sort_keys=True)
        b = json.dumps(m.run(req(list(reversed(items)))), sort_keys=True)
        self.assertEqual(a, b)
        self.assertEqual(items, snap)
        self.assertEqual(m.to_json(m.run(req(items))), m.to_json(m.run(req(items))))

    def test_floats_rounded_six(self):
        out = m.run(req([item("f", claims=[claim("peer_reviewed", "journal")],
                              metrics=[metric(1.0000001234567, 0.3)])]))
        d = out["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]["metrics"][0]["delta"]
        self.assertEqual(d, round(d, 6))

    def test_scope_block_and_no_overclaim(self):
        out = m.run(req([item("a")], sectors=["ai"]))
        for k in ("implemented", "not_implemented", "data_source", "as_of"):
            self.assertIn(k, out["scope"])
        self.assertEqual(out["scope"]["as_of"], AS_OF)
        self.assertEqual(out["coverage"]["sectors_covered"], ["ai"])
        self.assertNotIn("all sectors", json.dumps(out).replace("across all sectors beyond", ""))


class SectorOrder(unittest.TestCase):
    def test_sectors_covered_sorted_under_any_hash_seed(self):
        import os, subprocess
        code = ("import sys,json;sys.path.insert(0,%r);from app.modules.c37 import breakthroughs as m;"
                "r=m.run({'as_of':'2026-10-11','sectors':['energy','bio','ai','zz','qq'],'items':[{'id':'a','sector':'ai',"
                "'title':'t','url':'https://x.example/a','published':'2026-10-10'}]});"
                "print(json.dumps(r['coverage']['sectors_covered']))" % str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
        for seed in ("1", "2", "3", "4", "5"):
            out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                 env=dict(os.environ, PYTHONHASHSEED=seed), check=True).stdout
            self.assertEqual(json.loads(out), ["ai", "bio", "energy", "qq", "zz"])

    def test_sector_match_exact_case_sensitive(self):
        out = m.run(req([item("a"), item("b", sector="AI")]))
        self.assertEqual(out["coverage"]["unattributed_dropped_by_reason"], {"sector_not_requested": 1})

    def test_license_exact_case_sensitive_no_trim(self):
        rows = []
        for lic in ("mit", " MIT", "MIT "):
            out = m.run(req([item("l", license=lic, claims=[claim("peer_reviewed", "journal")],
                                  metrics=[metric(2, 1)])]))
            rows.append(out["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]["integrable_open_source"])
        self.assertEqual(rows, [False, False, False])


class Namespace(unittest.TestCase):
    def test_by_sector_namespace_separate_from_globals(self):
        out = m.run(req([item("a")]))
        self.assertEqual(sorted(out["coverage"]), ["by_sector", "cut_top_n", "duplicate_url_count",
                                                   "metrics_dropped_by_reason", "sectors_covered",
                                                   "unattributed_dropped_by_reason"])
        self.assertEqual(sorted(out["coverage"]["by_sector"]), ["ai", "bio", "energy"])
        self.assertEqual(sorted(out["breakthroughs_by_sector"]), ["ai", "bio", "energy"])
        self.assertNotIn("sectors", out)

    def test_sector_named_like_a_global_key_is_legal(self):
        ok = lambda i: claim("peer_reviewed", "journal")
        items = [item("x%d" % i, sector="cut_top_n", claims=[ok(i)], metrics=[metric(1 + i / 10.0, 1)])
                 for i in range(1, 4)]
        items.append(item("d", sector="ai", url="https://d.example/1"))
        items.append(item("d2", sector="ai", url="https://d.example/1/"))
        out = m.run(req(items, sectors=["ai", "cut_top_n", "duplicate_url_count", "by_sector"], top_n=1))
        cov = out["coverage"]
        self.assertEqual(cov["cut_top_n"], 2)
        self.assertEqual(cov["by_sector"]["cut_top_n"]["cut_top_n"], 2)
        self.assertEqual(cov["by_sector"]["cut_top_n"]["items_used"], 3)
        self.assertEqual(cov["duplicate_url_count"], 1)
        self.assertEqual(cov["by_sector"]["duplicate_url_count"]["items_supplied"], 0)
        self.assertEqual(cov["by_sector"]["by_sector"]["items_used"], 0)
        self.assertEqual(sorted(cov["sectors_covered"]), ["ai", "by_sector", "cut_top_n", "duplicate_url_count"])
        self.assertEqual([r["id"] for r in out["breakthroughs_by_sector"]["cut_top_n"]["breakthroughs"]], ["x3"])

    def test_request_level_control_chars_refuse(self):
        self.assertEqual(err(self, req([item("a")], sectors=["a\x07"])), "INTEL_REFUSED_CONTROL_CHARS:sector")
        self.assertEqual(err(self, req([item("a")], as_of="2026-10-11\x00")), "INTEL_REFUSED_CONTROL_CHARS:as_of")
        self.assertEqual(err(self, req([item("a")], window_days="1\x00")), "INTEL_REFUSED_CONTROL_CHARS:window_days")
        self.assertEqual(err(self, req([item("a")], top_n="1\x07")), "INTEL_REFUSED_CONTROL_CHARS:top_n")

    def test_required_item_field_control_drops_item(self):
        for field, val in (("id", "b\x00c"), ("title", "t\x07"), ("url", "https://c.example/c\n"),
                           ("published", "2026-10-10\x00"), ("sector", "ai\x00")):
            bad = item("bad", url="https://c.example/bad")
            bad[field] = val
            out = m.run(req([item("ok"), bad]))
            cov = out["coverage"]
            if field == "sector":
                self.assertEqual(cov["unattributed_dropped_by_reason"], {"sector_not_requested": 1}, field)
                self.assertEqual(cov["by_sector"]["ai"]["items_dropped_by_reason"], {}, field)
            elif field == "published":
                self.assertEqual(cov["by_sector"]["ai"]["items_dropped_by_reason"], {"published_invalid": 1}, field)
            else:
                self.assertEqual(cov["by_sector"]["ai"]["items_dropped_by_reason"], {"malformed_control": 1}, field)
            self.assertEqual(cov["by_sector"]["ai"]["items_used"], 1)

    def test_optional_item_field_control_dropped_not_item(self):
        for field in ("kind", "license"):
            it = item("o", claims=[claim("peer_reviewed", "journal")], metrics=[metric(2, 1)])
            it[field] = "x\x00y"
            out = m.run(req([it]))
            row = out["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]
            self.assertIn("malformed_control_dropped", row["flags"], field)
            self.assertEqual(row[field if field == "kind" else "license"], "unknown")
            self.assertEqual(row["integrable_open_source"], field == "kind")
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {})

    def test_non_control_bad_id_is_id_invalid(self):
        out = m.run(req([item("ok"), item("", url="https://c.example/e"), item("t", url="https://c.example/t")]))
        self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {"id_invalid": 1})

    def test_rest_of_input_processed_after_control_drop(self):
        bad = item("b\x00", url="https://c.example/b")
        out = m.run(req([bad, item("ok1"), item("ok2")]))
        self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_used"], 2)


class Metrics(unittest.TestCase):
    A = [claim("peer_reviewed", "journal")]

    def named(self, name, v=2, b=1):
        mt = metric(v, b)
        if name is _MISSING:
            del mt["name"]
        else:
            mt["name"] = name
        return mt

    def test_metric_name_control_drops_metric_and_flags(self):
        out = m.run(req([item("o", claims=self.A, metrics=[self.named("a\x00"), self.named("ok", 3, 1)])]))
        row = out["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]
        self.assertEqual([x["name"] for x in row["metrics"]], ["ok"])
        self.assertIn("malformed_control_dropped", row["flags"])
        self.assertNotIn("metric_invalid", row["flags"])
        self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z(malformed_control_dropped=1))

    def test_invalid_name_drops_metric_keeps_item_flag_metric_invalid(self):
        for bad in (_MISSING, None, 5, "", "   ", ["a"], True):
            out = m.run(req([item("o", claims=self.A, metrics=[self.named(bad), self.named("ok", 3, 1)])]))
            row = out["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]
            self.assertEqual([x["name"] for x in row["metrics"]], ["ok"], repr(bad))
            self.assertIn("metric_invalid", row["flags"], repr(bad))
            self.assertNotIn("malformed_control_dropped", row["flags"])
            self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z(metric_name_invalid=1))
            self.assertEqual(row["score"], round(2.0 * (1 - 0.5 * 2 / 14), 6))

    def test_metric_name_length_limit_128(self):
        ok = m.run(req([item("o", claims=self.A, metrics=[self.named("n" * 128)])]))
        self.assertEqual(len(ok["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]["metrics"]), 1)
        long = m.run(req([item("o", claims=self.A, metrics=[self.named("n" * 129), self.named("k")])]))
        self.assertEqual(long["coverage"]["metrics_dropped_by_reason"], Z(metric_name_invalid=1))

    def test_bad_value_or_baseline_drops_metric_keeps_item(self):
        good = self.named("ok", 3, 1)
        for field, bad in (("value", True), ("value", float("nan")), ("value", "x"), ("value", None),
                           ("baseline_value", True), ("baseline_value", float("inf")), ("baseline_value", "1")):
            mt = metric(2, 1)
            mt[field] = bad
            out = m.run(req([item("o", claims=self.A, metrics=[mt, good])]))
            s = out["breakthroughs_by_sector"]["ai"]
            row = s["breakthroughs"][0]
            self.assertEqual([x["name"] for x in row["metrics"]], ["ok"], (field, bad))
            self.assertIn("metric_invalid", row["flags"])
            self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z(**{"metric_value_invalid" if field == "value" else "metric_baseline_invalid": 1}))
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {})

    def test_all_metrics_bad_value_item_notable_unranked(self):
        mt = metric(True, 1)
        out = m.run(req([item("o", claims=self.A, metrics=[mt])]))
        s = out["breakthroughs_by_sector"]["ai"]
        self.assertEqual(s["breakthroughs"], [])
        row = s["notable"][0]
        self.assertEqual(row["metrics"], [])
        self.assertIn("metric_invalid", row["flags"])
        self.assertIn("no_positive_delta", row["flags"])
        self.assertNotIn("score", row)
        self.assertNotIn("rank", row)

    def test_bad_baseline_dropped_metric_does_not_make_b(self):
        bad = metric(2, 1)
        bad["baseline_value"] = "x"
        out = m.run(req([item("o", claims=[claim("benchmark", "third_party")], metrics=[bad])]))
        self.assertEqual(out["breakthroughs_by_sector"]["ai"]["notable"][0]["grade"], "C")

    def test_bad_direction_drops_metric_keeps_item_no_default(self):
        # item 15a: higher_is_better missing/null/non-bool (including 0 and 1) -> metric dropped.
        good = self.named("ok", 3, 1)
        for bad in ("yes", None, 1, 0, 1.0, [], _MISSING):
            mt = metric(2, 1)
            if bad is _MISSING:
                del mt["higher_is_better"]
            else:
                mt["higher_is_better"] = bad
            out = m.run(req([item("o", claims=self.A, metrics=[mt, good])]))
            row = out["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]
            self.assertEqual([x["name"] for x in row["metrics"]], ["ok"], repr(bad))
            self.assertIn("metric_invalid", row["flags"])
            self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z(metric_direction_invalid=1))
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {})

    def test_all_directions_bad_item_notable_unranked(self):
        mt = metric(2, 1)
        mt["higher_is_better"] = 1
        out = m.run(req([item("o", claims=self.A, metrics=[mt])]))
        s = out["breakthroughs_by_sector"]["ai"]
        self.assertEqual(s["breakthroughs"], [])
        self.assertEqual(s["notable"][0]["metrics"], [])
        self.assertIn("metric_invalid", s["notable"][0]["flags"])

    def test_missing_or_null_baseline_is_legal_not_a_drop(self):
        a = metric(2, None)
        b = metric(2, 1)
        del b["baseline_value"]
        out = m.run(req([item("o", claims=self.A, metrics=[a, b])]))
        row = out["breakthroughs_by_sector"]["ai"]["notable"][0]
        self.assertEqual(len(row["metrics"]), 2)
        self.assertNotIn("metric_invalid", row["flags"])
        self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z())

    def test_non_object_entry_dropped_per_entry_item_kept(self):
        out = m.run(req([item("o", claims=self.A, metrics=["x", 5, None, self.named("ok", 3, 1)])]))
        row = out["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]
        self.assertEqual([x["name"] for x in row["metrics"]], ["ok"])
        self.assertIn("metric_invalid", row["flags"])
        self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z(metric_not_object=3))
        self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {})

    def test_metrics_not_a_list_item_kept_counted_once(self):
        for bad in ("x", {"a": 1}, 5, True, ("a",)):
            it = item("o", claims=self.A)
            it["metrics"] = bad
            out = m.run(req([it]))
            s = out["breakthroughs_by_sector"]["ai"]
            self.assertEqual(s["breakthroughs"], [], repr(bad))
            row = s["notable"][0]
            self.assertEqual(row["metrics"], [])
            self.assertTrue({"metric_invalid", "no_positive_delta"} <= set(row["flags"]))
            self.assertNotIn("score", row)
            self.assertNotIn("rank", row)
            self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z(metrics_not_list=1))
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {})

    def test_metrics_missing_or_null_is_empty_no_flag(self):
        a = item("a", claims=self.A)
        del a["metrics"]
        b = item("b", claims=self.A, url="https://c.example/b")
        b["metrics"] = None
        out = m.run(req([a, b]))
        rows = out["breakthroughs_by_sector"]["ai"]["notable"]
        self.assertEqual(sorted(r["id"] for r in rows), ["a", "b"])
        for r in rows:
            self.assertEqual(r["metrics"], [])
            self.assertNotIn("metric_invalid", r["flags"])
        self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z())
        self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {})

    def test_each_drop_counted_once_by_first_failure(self):
        multi = {"name": "", "value": True, "baseline_value": "x", "higher_is_better": 1}
        value_dir = {"name": "n", "value": None, "baseline_value": 1, "higher_is_better": "y"}
        ctrl_and_bad = {"name": "a\x00", "value": None, "baseline_value": "x", "higher_is_better": 1}
        out = m.run(req([item("o", claims=self.A, metrics=[multi, value_dir, ctrl_and_bad, "z"])]))
        self.assertEqual(out["coverage"]["metrics_dropped_by_reason"],
                         Z(malformed_control_dropped=1, metric_name_invalid=1, metric_value_invalid=1, metric_not_object=1))

    def test_all_seven_keys_always_present_even_with_no_metrics(self):
        for metrics in (None, [], [self.named("n")]):
            out = m.run(req([item("o", claims=self.A, metrics=metrics)] if metrics is not None else [item("o", claims=self.A)]))
            self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z())
            self.assertEqual(list(out["coverage"]["metrics_dropped_by_reason"]), sorted(_KEYS))

    def test_value_and_direction_bad_is_value_only(self):
        mt = {"name": "n", "value": None, "baseline_value": 1, "higher_is_better": "y"}
        out = m.run(req([item("o", claims=self.A, metrics=[mt])]))
        self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z(metric_value_invalid=1))

    def test_baseline_checked_before_direction(self):
        mt = {"name": "n", "value": 1, "baseline_value": "x", "higher_is_better": 1}
        out = m.run(req([item("o", claims=self.A, metrics=[mt])]))
        self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z(metric_baseline_invalid=1))

    def test_control_name_counts_control_only_with_both_flags_rules(self):
        mt = {"name": "a\x00", "value": None, "baseline_value": "x", "higher_is_better": 1}
        out = m.run(req([item("o", claims=self.A, metrics=[mt])]))
        self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z(malformed_control_dropped=1))
        row = out["breakthroughs_by_sector"]["ai"]["notable"][0]
        self.assertIn("malformed_control_dropped", row["flags"])
        self.assertNotIn("metric_invalid", row["flags"])

    def test_item_flag_generic_metric_invalid_for_all_non_control_reasons(self):
        for mt in (5, {"name": ""}, {"name": "n", "value": None}, {"name": "n", "value": 1, "baseline_value": "x",
                   "higher_is_better": True}, {"name": "n", "value": 1, "higher_is_better": 1}):
            out = m.run(req([item("o", claims=self.A, metrics=[mt])]))
            row = out["breakthroughs_by_sector"]["ai"]["notable"][0]
            self.assertIn("metric_invalid", row["flags"], repr(mt))
            self.assertNotIn("malformed_control_dropped", row["flags"], repr(mt))

    def test_no_whole_item_bad_metric_anywhere(self):
        weird = [None, 5, "x", {}, {"name": "n"}, {"name": "n", "value": 1}, [],
                 {"name": "n", "value": 1, "higher_is_better": True, "baseline_value": []}]
        for w in weird:
            out = m.run(req([item("o", claims=self.A, metrics=[w])]))
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {}, repr(w))
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_used"], 1)

    def test_all_metrics_dropped_item_unranked(self):
        out = m.run(req([item("o", claims=self.A, metrics=[self.named(None), self.named("x\x07")])]))
        s = out["breakthroughs_by_sector"]["ai"]
        self.assertEqual(s["breakthroughs"], [])
        row = s["notable"][0]
        self.assertEqual(row["metrics"], [])
        self.assertTrue({"metric_invalid", "malformed_control_dropped", "no_positive_delta"} <= set(row["flags"]))
        self.assertNotIn("score", row)
        self.assertNotIn("rank", row)
        self.assertEqual(out["coverage"]["metrics_dropped_by_reason"],
                         Z(malformed_control_dropped=1, metric_name_invalid=1))
        self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_used"], 1)

    def test_dropped_metric_baseline_does_not_make_b(self):
        mt = self.named(None)
        out = m.run(req([item("o", claims=[claim("benchmark", "third_party")], metrics=[mt, {
            "name": "nb", "value": 2, "baseline_value": None, "higher_is_better": True}])]))
        self.assertEqual(out["breakthroughs_by_sector"]["ai"]["notable"][0]["grade"], "C")

    def test_drop_counts_only_for_kept_items(self):
        u = "https://same.example/x"
        keep = item("a", url=u, claims=self.A, metrics=[self.named("n")])
        lose = item("b", url=u, metrics=[self.named(None)])
        out = m.run(req([keep, lose]))
        self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z())
        self.assertEqual(out["coverage"]["duplicate_url_count"], 1)

    def test_clean_input_has_empty_drop_counts(self):
        out = m.run(req([item("a")]))
        self.assertEqual(out["coverage"]["metrics_dropped_by_reason"], Z())


class Item21Chain(unittest.TestCase):
    """Spec 908fdf1b items 18 and 21: drop chain, allowed reasons, attribution."""
    CHAIN = ("sector_not_requested", "id_invalid", "title_invalid", "url_invalid", "url_not_https",
             "published_invalid", "future_date", "stale", "malformed_control")
    ALLOWED = set(CHAIN) | {"duplicate_url"}      # the exact 10-key set (spec item 21c, kept by item 22)

    def drops(self, **kw):
        it = item("p", url="https://p.example/p")
        for k, v in kw.items():
            if v is _MISSING:
                it.pop(k, None)
            else:
                it[k] = v
        out = m.run(req([item("good"), it]))
        c = out["coverage"]
        return c["by_sector"]["ai"]["items_dropped_by_reason"], c["unattributed_dropped_by_reason"]

    def test_url_reasons(self):
        for bad in ("http://a.example/x", "ftp://a.example/x", "https:///x", "https://", "a.example/x"):
            self.assertEqual(self.drops(url=bad), ({"url_not_https": 1}, {}), repr(bad))
        for bad in (_MISSING, None, 5, "", "   ", True, []):
            self.assertEqual(self.drops(url=bad), ({"url_invalid": 1}, {}), repr(bad))

    def test_published_reasons(self):
        for bad in (_MISSING, None, 5, "", "  ", "2026-13-45", "10/09/2026", "2026-10-9"):
            self.assertEqual(self.drops(published=bad), ({"published_invalid": 1}, {}), repr(bad))

    def test_id_title_reasons(self):
        for f, reason in (("id", "id_invalid"), ("title", "title_invalid")):
            for bad in (_MISSING, None, 5, "", "  ", "x" * (257 if f == "id" else 513), True):
                self.assertEqual(self.drops(**{f: bad}), ({reason: 1}, {}), (f, repr(bad)))
            self.assertEqual(self.drops(**{f: "x" * (256 if f == "id" else 512)}), ({}, {}))

    def test_item_sector_never_matching_is_unattributed_only(self):
        for bad in (_MISSING, None, 5, "AI", " ai", "ai\x00", "zz", [], True):
            self.assertEqual(self.drops(sector=bad), ({}, {"sector_not_requested": 1}), repr(bad))
        out = m.run(req([item("good"), item("p", sector="zz"), "junk", None, 5, [], {}]))
        c = out["coverage"]
        self.assertEqual(c["unattributed_dropped_by_reason"], {"sector_not_requested": 6})
        self.assertNotIn("sector_not_requested", c["by_sector"]["ai"]["items_dropped_by_reason"])
        self.assertEqual(sorted(c["by_sector"]), ["ai", "bio", "energy"])

    def test_chain_precedence_each_pair(self):
        good = dict(sector="ai", id="p", title="t", url="https://p.example/p", published="2026-10-09")
        bad = {"sector_not_requested": dict(sector="zz"), "id_invalid": dict(id=""), "title_invalid": dict(title=""),
               "url_invalid": dict(url=None), "url_not_https": dict(url="http://a.example/x"),
               "published_invalid": dict(published="x"), "future_date": dict(published="2026-12-01"),
               "stale": dict(published="2020-01-01"), "malformed_control": dict(title="a\x00")}
        for i, r1 in enumerate(self.CHAIN):
            for r2 in self.CHAIN[i + 1:]:
                kw = dict(bad[r2]); kw.update(bad[r1])
                if r1 == "malformed_control" or r2 == "malformed_control":
                    pass
                if (r1, r2) in (("url_invalid", "url_not_https"), ("published_invalid", "future_date"),
                                ("published_invalid", "stale"), ("future_date", "stale")):
                    continue  # same field: not both simultaneously
                d, u = self.drops(**kw)
                got = list(d) + list(u)
                self.assertEqual(got, [r1], (r1, r2, kw))

    def test_control_char_in_url_or_title_only_after_all_others(self):
        self.assertEqual(self.drops(url="https://p.example/p\n"), ({"malformed_control": 1}, {}))
        self.assertEqual(self.drops(id="a\x00b"), ({"malformed_control": 1}, {}))
        self.assertEqual(self.drops(title="a\x00", published="2020-01-01"), ({"stale": 1}, {}))
        self.assertEqual(self.drops(id="a\x00", title=""), ({"title_invalid": 1}, {}))

    def test_allowed_reason_set_pinned(self):
        its = [item("good"), item("a", url="http://x/y"), dict(item("b"), url=None), item("c", published="x"),
               item("d", published="2020-01-01"), item("e", published="2026-12-01"), item("f", sector="zz"),
               item("", url="https://e.example/e"), dict(item("g", url="https://g.example/g"), title=""),
               dict(item("h", url="https://h.example/h"), title="a\x00"), "junk",
               item("i", url="https://dup.example/i"), item("j", url="https://dup.example/i"),
               dict(item("k", url="https://k.example/k"), claims="notalist")]
        c = m.run(req(its))["coverage"]
        seen = set(c["by_sector"]["ai"]["items_dropped_by_reason"]) | set(c["unattributed_dropped_by_reason"])
        self.assertEqual(seen, self.ALLOWED)
        self.assertNotIn("malformed", seen)
        for old in ("bad_url", "bad_date", "bad_metric"):
            self.assertNotIn(old, seen)
        src = open(m.__file__).read()
        for old in ("bad_url", "bad_date", "bad_metric", "malformed"):
            self.assertNotIn('"%s"' % old, src)

    def test_unattributed_counts_never_in_by_sector(self):
        out = m.run(req([item("good"), item("p", sector="zz")]))
        for s, row in out["coverage"]["by_sector"].items():
            self.assertNotIn("sector_not_requested", row["items_dropped_by_reason"], s)
            self.assertEqual(row["items_supplied"], 1 if s == "ai" else 0)
        self.assertEqual(out["coverage"]["unattributed_dropped_by_reason"], {"sector_not_requested": 1})

    def test_dedupe_loser_in_own_sector_and_dropped_never_contests(self):
        A = [claim("benchmark", "third_party", "https://r.example/x")]
        u = "https://same.example/p"
        out = m.run(req([item("a", url=u, claims=A), item("b", sector="bio", url=u, claims=A),
                         item("c", url=u, published="2020-01-01", claims=A), item("d", sector="zz", url=u, claims=A)],
                        sectors=["ai", "bio"]))
        c = out["coverage"]
        self.assertEqual(c["duplicate_url_count"], 1)
        self.assertEqual(c["by_sector"]["bio"]["items_dropped_by_reason"], {"duplicate_url": 1})
        self.assertEqual(c["by_sector"]["ai"]["items_dropped_by_reason"], {"stale": 1})
        self.assertEqual(c["unattributed_dropped_by_reason"], {"sector_not_requested": 1})


class Item22(unittest.TestCase):
    """Spec e131ce45 item 22: no generic `malformed`; claims and kind/license keep the item."""
    A = [claim("peer_reviewed", "journal")]

    def one(self, **kw):
        it = dict(item("p", url="https://p.example/p", metrics=[metric(2, 1)], claims=self.A), **kw)
        out = m.run(req([it]))
        sec = out["breakthroughs_by_sector"]["ai"]
        row = (sec["breakthroughs"] + sec["notable"] + sec["unverified"])[0]
        return out, row

    def test_claims_not_a_list_keeps_item_flag_no_count(self):
        for bad in ({}, "x", 5, True, {"evidence_type": "peer_reviewed"}):
            out, row = self.one(claims=bad)
            self.assertIn("claims_invalid", row["flags"], repr(bad))
            self.assertEqual(row["grade"], "D")
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {})
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_used"], 1)
            self.assertEqual(out["coverage"]["unattributed_dropped_by_reason"], {})

    def test_claims_missing_or_null_is_empty_no_flag(self):
        it = item("p", url="https://p.example/p")
        del it["claims"]
        out = m.run(req([it]))
        row = out["breakthroughs_by_sector"]["ai"]["unverified"][0]
        self.assertNotIn("claims_invalid", row["flags"])
        _, row = self.one(claims=[])
        self.assertNotIn("claims_invalid", row["flags"])

    def test_non_object_claim_entry_dropped_alone_others_graded(self):
        for bad in ("x", None, 5, [], True):
            out, row = self.one(claims=[bad, claim("peer_reviewed", "journal")])
            self.assertEqual(row["grade"], "A", repr(bad))
            self.assertIn("claims_invalid", row["flags"], repr(bad))
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {})
        out, row = self.one(claims=["x"])
        self.assertEqual(row["grade"], "D")
        self.assertIn("claims_invalid", row["flags"])

    def test_claims_invalid_flag_once_and_no_other_flag_change(self):
        out, row = self.one(claims=["x", 1, None, claim("peer_reviewed", "journal")])
        self.assertEqual(row["flags"].count("claims_invalid"), 1)
        out2, row2 = self.one()
        self.assertEqual(sorted(set(row["flags"]) - {"claims_invalid"}), sorted(row2["flags"]))

    def test_kind_enum_exact_case(self):
        for k in ("tool", "paper", "model", "dataset"):
            out, row = self.one(kind=k)
            self.assertEqual(row["kind"], k)
            self.assertNotIn("kind_invalid", row["flags"])
        for k in ("Tool", "TOOL", " tool", "tool ", "software", "unknown", "x" * 65, "", "   ", 5, True, [], {}, 1.5):
            out, row = self.one(kind=k)
            self.assertEqual(row["kind"], "unknown", repr(k))
            self.assertIn("kind_invalid", row["flags"], repr(k))
            self.assertEqual(row["flags"].count("kind_invalid"), 1)
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {}, repr(k))
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_used"], 1)

    def test_kind_missing_or_null_unknown_no_flag(self):
        it = dict(item("p", url="https://p.example/p", claims=self.A, metrics=[metric(2, 1)]))
        del it["kind"]
        row = m.run(req([it]))["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]
        self.assertEqual(row["kind"], "unknown")
        self.assertNotIn("kind_invalid", row["flags"])
        out, row = self.one(kind=None)
        self.assertEqual(row["kind"], "unknown")
        self.assertNotIn("kind_invalid", row["flags"])

    def test_license_free_form_up_to_64_preserved_no_flag(self):
        for lic in ("MIT", "Apache-2.0", "CC-BY", "proprietary", "GPL-3.0", "unknown", "mit", "x" * 64, "weird license v2"):
            out, row = self.one(license=lic)
            self.assertEqual(row["license"], lic)
            self.assertNotIn("license_invalid", row["flags"], lic)
            self.assertEqual(row["integrable_open_source"], lic in m.OPEN_LICENSES)

    def test_license_bad_typed_blank_or_long_unknown_license_invalid(self):
        for lic in ("", "   ", "x" * 65, 5, True, [], {}, 1.5):
            out, row = self.one(license=lic)
            self.assertEqual(row["license"], "unknown", repr(lic))
            self.assertIn("license_invalid", row["flags"], repr(lic))
            self.assertEqual(row["flags"].count("license_invalid"), 1)
            self.assertFalse(row["integrable_open_source"])
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"], {}, repr(lic))
            self.assertEqual(out["coverage"]["by_sector"]["ai"]["items_used"], 1)

    def test_license_missing_or_null_unknown_no_flag(self):
        it = dict(item("p", url="https://p.example/p", claims=self.A, metrics=[metric(2, 1)]))
        del it["license"]
        row = m.run(req([it]))["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]
        self.assertEqual(row["license"], "unknown")
        self.assertNotIn("license_invalid", row["flags"])
        out, row = self.one(license=None)
        self.assertEqual((row["license"], "license_invalid" in row["flags"]), ("unknown", False))

    def test_both_flags_are_independent_set_members(self):
        out, row = self.one(kind="nope", license="")
        self.assertTrue({"kind_invalid", "license_invalid"} <= set(row["flags"]))
        out, row = self.one(kind="nope")
        self.assertNotIn("license_invalid", row["flags"])
        out, row = self.one(license="")
        self.assertNotIn("kind_invalid", row["flags"])

    def test_control_char_kind_license_keeps_control_flag_not_new_flags(self):
        for f in ("kind", "license"):
            out, row = self.one(**{f: "a\x00b"})
            self.assertEqual(row[f], "unknown")
            self.assertIn("malformed_control_dropped", row["flags"])
            self.assertNotIn("kind_invalid", row["flags"])
            self.assertNotIn("license_invalid", row["flags"])

    def test_non_object_item_is_unattributed_sector_not_requested(self):
        out = m.run(req([item("good"), "junk", None, 5, [], {"id": "x"}]))
        c = out["coverage"]
        self.assertEqual(c["unattributed_dropped_by_reason"], {"sector_not_requested": 5})
        self.assertEqual(c["by_sector"]["ai"]["items_supplied"], 1)
        for row in c["by_sector"].values():
            self.assertNotIn("sector_not_requested", row["items_dropped_by_reason"])
            self.assertNotIn("malformed", row["items_dropped_by_reason"])


class MatrixGaps(unittest.TestCase):
    """Matrix 77fd8d52 rows that no earlier test pinned literally. Added AFTER the
    behaviour existed, so these pass on the previous commit: no red for them."""
    A = [claim("peer_reviewed", "journal")]

    def test_window_and_top_n_literal_bad_types(self):
        for bad in (14.0, "14", False):
            self.assertEqual(err(self, req([item("a")], window_days=bad)), "INTEL_REFUSED_BAD_TYPE:window_days")
        for bad in (5.0, False, -1):
            self.assertEqual(err(self, req([item("a")], top_n=bad)), "INTEL_REFUSED_BAD_TYPE:top_n")

    def test_every_open_source_license_is_integrable(self):
        for lic in ("MIT", "Apache-2.0", "BSD", "BSD-2-Clause", "BSD-3-Clause", "CC0"):
            it = item("p", url="https://p.example/p", claims=self.A, metrics=[metric(2, 1)], license=lic)
            row = m.run(req([it]))["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]
            self.assertTrue(row["integrable_open_source"], lic)

    def test_breakthrough_entry_keys(self):
        it = item("p", url="https://p.example/p", claims=self.A, metrics=[metric(2, 1)])
        row = m.run(req([it]))["breakthroughs_by_sector"]["ai"]["breakthroughs"][0]
        for k in ("id", "title", "url", "grade", "score", "metrics", "license", "integrable_open_source", "caveats"):
            self.assertIn(k, row, k)


class PeerPins(unittest.TestCase):
    """Test-only pins for survivors of the peer's 234-operator battery (b0c9fcdc). Core bytes
    unchanged; these pass on acfc24f4 and are checked by re-applying the operators."""
    A = [claim("peer_reviewed", "journal")]
    B = [claim("benchmark", "third_party")]
    C = [claim("vendor_statement", "vendor")]
    D = [claim("none", "unknown")]

    # 1. defaults and boundaries ------------------------------------------------------
    def test_window_default_is_14_inclusive(self):
        for pub, ok in (("2026-09-27", True), ("2026-09-26", False)):    # as_of 2026-10-11: age 14 / 15
            r = req([item("good"), item("p", published=pub, url="https://p.example/p")])
            del r["window_days"]
            d = m.run(r)["coverage"]["by_sector"]["ai"]["items_dropped_by_reason"]
            self.assertEqual(d, {} if ok else {"stale": 1}, pub)

    def test_window_bounds_1_and_365_accepted(self):
        for w in (0, 366):
            self.assertEqual(err(self, req([item("good")], window_days=w)), "INTEL_REFUSED_BAD_TYPE:window_days")
        r = req([item("good", published="2026-10-10")], window_days=1)
        self.assertEqual(m.run(r)["coverage"]["by_sector"]["ai"]["items_used"], 1)
        r = req([item("good", published="2025-10-11")], window_days=365)
        self.assertEqual(m.run(r)["coverage"]["by_sector"]["ai"]["items_used"], 1)

    def test_top_n_default_is_5(self):
        its = [item("i%d" % n, url="https://r.example/%d" % n, claims=[claim("peer_reviewed", "journal")],
                    metrics=[metric(2 + n, 1)]) for n in range(7)]
        r = req(its)
        out = m.run(r)
        sec = out["breakthroughs_by_sector"]["ai"]
        self.assertEqual((len(sec["breakthroughs"]), len(sec["notable"])), (5, 2))
        self.assertEqual(out["coverage"]["by_sector"]["ai"]["cut_top_n"], 2)

    def test_sector_name_length_64_ok_65_refused(self):
        ok = "s" * 64
        out = m.run(req([item("a", sector=ok)], sectors=[ok]))
        self.assertEqual(out["coverage"]["by_sector"][ok]["items_used"], 1)
        self.assertTrue(err(self, req([item("a", sector="s" * 65)], sectors=["s" * 65])).startswith("INTEL_REFUSED_"))

    # 2. mixed claims: best grade wins in any order ----------------------------------
    def grade(self, claims):
        out = m.run(req([item("p", url="https://p.example/p", claims=claims, metrics=[metric(2, 1)])]))
        sec = out["breakthroughs_by_sector"]["ai"]
        return (sec["breakthroughs"] + sec["notable"] + sec["unverified"])[0]["grade"]

    def test_best_grade_in_every_claim_order(self):
        A = claim("peer_reviewed", "journal")
        B = claim("benchmark", "third_party")
        C = claim("vendor_statement", "vendor")
        D = claim("none", "unknown")
        for cl, want in (([D, C], "C"), ([C, D], "C"), ([C, B], "B"), ([B, C], "B"), ([B, A], "A"),
                         ([A, B], "A"), ([D, B], "B"), ([C, A], "A"), ([D, A], "A"), ([A, C, D], "A"),
                         ([D, C, B, A], "A"), ([A, B, C, D], "A")):
            self.assertEqual(self.grade(cl), want, [c["evidence_type"] for c in cl])

    def test_dedupe_prefers_higher_grade_across_adjacent_ranks(self):
        u = "https://same.example/p"
        for hi, lo, want in ((self.A, self.B, "hi"), (self.B, self.C, "hi"), (self.C, self.D, "hi")):
            out = m.run(req([item("lo", url=u, claims=lo, metrics=[metric(2, 1)]),
                             item("hi", url=u, claims=hi, metrics=[metric(2, 1)])]))
            sec = out["breakthroughs_by_sector"]["ai"]
            kept = (sec["breakthroughs"] + sec["notable"] + sec["unverified"])
            self.assertEqual([r["id"] for r in kept], ["hi"])

    # 3. URL normalization keeps blank-valued query params ----------------------------
    def test_url_query_blank_values_kept_utm_dropped(self):
        n = m.normalize_url
        self.assertEqual(n("https://X.example/p/?a=keep"), "https://x.example/p?a=keep")
        self.assertEqual(n("https://x.example/p?a=&b=1"), "https://x.example/p?a=&b=1")
        self.assertEqual(n("https://x.example/p?a"), "https://x.example/p?a=")
        self.assertEqual(n("https://x.example/p?utm_source=z&a=keep&UTM_X=1"), "https://x.example/p?a=keep")
        self.assertNotEqual(n("https://x.example/p?a="), n("https://x.example/p"))

    # 4. the exact four caveat strings -------------------------------------------------
    def caveats(self, claims, metrics):
        it = item("p", url="https://p.example/p", claims=claims, metrics=metrics)
        out = m.run(req([it]))
        sec = out["breakthroughs_by_sector"]["ai"]
        return (sec["breakthroughs"] + sec["notable"] + sec["unverified"])[0]["caveats"]

    def test_caveat_strings_exact(self):
        c_txt = "vendor-stated or label-conflicted, untested"
        d_txt = "no usable evidence label"
        lc_txt = "peer_reviewed label with non-journal/conference source"
        nd_txt = "no computable delta (missing or zero baseline)"
        self.assertEqual(self.caveats(self.C, [metric(2, 1)]), [c_txt])
        self.assertEqual(self.caveats(self.D, [metric(2, 1)]), [d_txt])
        self.assertEqual(self.caveats([claim("peer_reviewed", "vendor")], [metric(2, 1)]), [c_txt, lc_txt])
        self.assertEqual(self.caveats(self.A, [metric(2, 0)]), [nd_txt])
        self.assertEqual(self.caveats(self.A, [metric(2, None)]), [nd_txt])
        self.assertEqual(self.caveats(self.A, [metric(2, 1)]), [])
        self.assertEqual(self.caveats(self.A, []), [])
        self.assertEqual(self.caveats(self.B, [metric(2, 1)]), [])
        self.assertEqual(self.caveats(self.A, [metric(2, 0), metric(2, 1)]), [])
        self.assertEqual(self.caveats(self.C, [metric(2, 0)]), [c_txt, nd_txt])

    # 5. to_json byte serialization -----------------------------------------------------
    def test_to_json_sorted_compact_bytes(self):
        out = m.run(req([item("a", claims=self.A, metrics=[metric(2, 1)]), item("b", sector="bio", claims=self.B)]))
        s = m.to_json(out)
        self.assertEqual(s, json.dumps(json.loads(s), sort_keys=True, separators=(",", ":")))
        self.assertEqual(s, json.dumps(out, sort_keys=True, separators=(",", ":")))
        self.assertTrue(s.startswith('{"as_of":"2026-10-11","breakthroughs_by_sector":{"ai":{'))
        self.assertIn('"top_n":5,"window_days":14}', s)
        self.assertEqual(s.encode("utf-8"), m.to_json(json.loads(json.dumps(out))).encode("utf-8"))
        shuffled = {k: out[k] for k in sorted(out, reverse=True)}
        self.assertEqual(m.to_json(shuffled), s)


_MISSING = object()

_KEYS = ("malformed_control_dropped", "metric_name_invalid", "metric_value_invalid",
         "metric_baseline_invalid", "metric_direction_invalid", "metric_not_object", "metrics_not_list")


def Z(**kw):
    """All 7 per-field counter keys, always present, zeros by default (item 17)."""
    assert set(kw) <= set(_KEYS), kw
    return {k: kw.get(k, 0) for k in _KEYS}


class Offline(unittest.TestCase):
    def test_no_effect_functions_and_real_policy(self):
        public = [n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))
                  and getattr(getattr(m, n), "__module__", "") == m.__name__]
        for n in public:
            for bad in ("spend", "send", "post", "trade", "account", "email", "fetch", "scrape"):
                self.assertNotIn(bad, n)
        from app.modules.c30 import policy
        self.assertIs(m.policy, policy)
        for forbidden in ("urllib.request", "socket", "requests", "http.client"):
            with open(m.__file__) as fh:
                self.assertNotIn(forbidden, fh.read())


if __name__ == "__main__":
    unittest.main()
