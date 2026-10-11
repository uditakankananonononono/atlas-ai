"""S4.5 / c35.prefill tests. Hermetic, stdlib unittest."""
import importlib.util, json, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c35/prefill.py"
_spec = importlib.util.spec_from_file_location("c35_prefill", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c35_prefill"] = m
_spec.loader.exec_module(m)

PROFILE = {"name": "Udita Phookan", "school": "Cotton University",
           "email": "u@example.com", "gpa": "9.2"}

def opp(i, **kw):
    base = {"id": "o%d" % i, "title": "Opp %d" % i, "deadline": "2026-11-%02d" % i,
            "fields": ["name", "school"], "value": 1000 * i, "p_win": 0.10,
            "effort_hours": 5.0}
    base.update(kw)
    return base

# 15-opportunity fixture: past deadline, zero effort, missing p_win,
# missing value, missing effort, profile gaps, essay field, ranking ties.
def fixture():
    opps = [
        opp(1),                                   # baseline
        opp(2, deadline="2026-10-01"),            # expired vs as_of
        opp(3, effort_hours=0),                   # zero effort -> BAD_TYPE
        opp(4),                                   # p_win removed below
        opp(5),                                   # value removed below
        opp(6),                                   # effort removed below
        opp(7, fields=["name", "sat_score"]),     # profile gap -> missing_fields
        opp(8, fields=["name", "essay"]),         # essay stays draft_required
        opp(9, value=100, p_win=0.5, effort_hours=1.0),   # score 50
        opp(10, value=200, p_win=0.25, effort_hours=1.0), # score 50 (tie w/ 9, later deadline)
        opp(11, value=200, p_win=0.25, effort_hours=1.0, deadline="2026-11-10"), # same deadline as o10 -> id tiebreak
        opp(12, fields=[]),                       # nothing requested -> not_started
        opp(13, deadline="2026-10-11"),           # due on as_of: days_left 0, not expired
        opp(14, p_win=1.0, value=60, effort_hours=3.0),   # score 20
        opp(15, fields=["name", "GPA"]),          # exact-key match is case-sensitive -> gap
    ]
    del opps[3]["p_win"]; del opps[4]["value"]; del opps[5]["effort_hours"]
    return opps

def req(opps=None, **kw):
    r = {"as_of": "2026-10-11", "profile": dict(PROFILE),
         "opportunities": fixture() if opps is None else opps}
    r.update(kw)
    return r

class Refusals(unittest.TestCase):
    def err(self, r):
        with self.assertRaises(ValueError) as cm:
            m.run(r)
        return str(cm.exception)

    def test_no_profile(self):
        self.assertEqual(self.err(req(profile=None)), "APPLY_REFUSED_NOPROFILE")
        self.assertEqual(self.err(req(profile="x")), "APPLY_REFUSED_NOPROFILE")

    def test_bad_type_request(self):
        self.assertEqual(self.err("nope"), "APPLY_REFUSED_BAD_TYPE:request")

    def test_empty_opportunities(self):
        self.assertEqual(self.err(req(opps=[])), "APPLY_REFUSED_EMPTY:opportunities")

    def test_zero_and_negative_effort(self):
        self.assertEqual(self.err(req(opps=[opp(1, effort_hours=0)])), "APPLY_REFUSED_BAD_TYPE:effort_hours")
        self.assertEqual(self.err(req(opps=[opp(1, effort_hours=-2)])), "APPLY_REFUSED_BAD_TYPE:effort_hours")

    def test_bad_types(self):
        self.assertEqual(self.err(req(opps=[opp(1, value="lots")])), "APPLY_REFUSED_BAD_TYPE:value")
        self.assertEqual(self.err(req(opps=[opp(1, p_win=True)])), "APPLY_REFUSED_BAD_TYPE:p_win")
        self.assertEqual(self.err(req(opps=[opp(1, deadline="not-a-date")])), "APPLY_REFUSED_BAD_TYPE:deadline")
        self.assertEqual(self.err(req(opps=["x"])), "APPLY_REFUSED_BAD_TYPE:opportunity")

    def test_submit_password_login_keys_refused(self):
        for key in ("submit", "Password", "LOGIN"):
            self.assertEqual(self.err(req(opps=[opp(1, **{key: "x"})])), "APPLY_REFUSED_SUBMIT")
        self.assertEqual(self.err(req(opps=[opp(1, fields=["name", "password"])])),
                         "APPLY_REFUSED_SUBMIT")

    def test_no_action_paths(self):
        import inspect
        from app.modules.c30 import policy
        for action in ("spend", "outreach", "fakeacct", "autopost", "scrape", "trade"):
            with self.assertRaises(ValueError):
                policy.check(action, "APPLY")
        public = [n for n, f in inspect.getmembers(m, inspect.isfunction) if not n.startswith("_")]
        self.assertEqual(public, ["run"])

class Behavior(unittest.TestCase):
    def setUp(self):
        self.opps = [o for o in fixture() if o.get("effort_hours", 1) != 0]
        self.out = m.run(req(opps=self.opps))

    def test_packets_fill_and_missing(self):
        pk = {p["id"]: p for p in self.out["packets"]}
        self.assertEqual(pk["o1"]["filled"], {"name": "Udita Phookan", "school": "Cotton University"})
        self.assertEqual(pk["o1"]["missing_fields"], [])
        self.assertEqual(pk["o7"]["missing_fields"], ["sat_score"])
        self.assertEqual(pk["o15"]["missing_fields"], ["GPA"])  # exact-key match only

    def test_essay_stays_draft_required(self):
        pk = {p["id"]: p for p in self.out["packets"]}
        self.assertEqual(pk["o8"]["draft_required"], ["essay"])
        self.assertNotIn("essay", pk["o8"]["filled"])
        self.assertEqual(pk["o8"]["missing_fields"], [])

    def test_tracker_statuses(self):
        tr = {t["id"]: t["status"] for t in self.out["tracker"]}
        self.assertEqual(tr["o2"], "expired")
        self.assertEqual(tr["o7"], "needs_input")
        self.assertEqual(tr["o1"], "prefilled")
        self.assertEqual(tr["o12"], "not_started")
        self.assertEqual(tr["o13"], "prefilled")  # deadline == as_of is not expired
        self.assertEqual(tr["o8"], "prefilled")   # draft_required is not missing input

    def test_ranking_formula_and_order(self):
        ranked = self.out["ranking"]["ranked"]
        by_id = {r["id"]: r for r in ranked}
        self.assertEqual(by_id["o1"]["score"], round(1000 * 0.10 / 5.0, 6))
        self.assertEqual(by_id["o9"]["score"], 50.0)
        self.assertEqual(by_id["o14"]["score"], 20.0)
        ids = [r["id"] for r in ranked]
        self.assertLess(ids.index("o9"), ids.index("o10"))   # tie -> deadline asc
        self.assertLess(ids.index("o10"), ids.index("o11"))  # tie+deadline -> id asc
        self.assertLess(ids.index("o1"), ids.index("o14"))   # tie 20.0 -> deadline asc
        scores = [r["score"] for r in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))  # strictly descending
        self.assertEqual(ids[0], "o15")  # highest score 300.0 first
        unranked = {u["id"]: u["reason"] for u in self.out["ranking"]["unranked"]}
        self.assertEqual(unranked, {"o4": "missing p_win", "o5": "missing value",
                                    "o6": "missing effort_hours"})
        self.assertIn("o2", by_id)  # expired rows still rank; expiry is tracker status

    def test_calendar_sorted_days_left(self):
        cal = self.out["calendar"]
        self.assertEqual([c["id"] for c in cal][:3], ["o2", "o13", "o1"])
        by_id = {c["id"]: c for c in cal}
        self.assertEqual(by_id["o2"]["days_left"], -10)
        self.assertEqual(by_id["o13"]["days_left"], 0)
        self.assertEqual(by_id["o1"]["days_left"], 21)

    def test_scope_honesty_block(self):
        sc = self.out["scope"]
        self.assertIn("ranking", " ".join(sc["implemented"]))
        self.assertIn("win probability", " ".join(sc["not_implemented"]))
        self.assertEqual(sc["as_of"], "2026-10-11")

    def test_determinism_byte_identical(self):
        a = json.dumps(m.run(req(opps=self.opps)), sort_keys=True)
        b = json.dumps(m.run(req(opps=self.opps)), sort_keys=True)
        self.assertEqual(a, b)

if __name__ == "__main__":
    unittest.main()


class RepairS45(unittest.TestCase):
    def err(self, r):
        with self.assertRaises(ValueError) as cm:
            m.run(r)
        return str(cm.exception)

    # -- numeric hygiene ------------------------------------------------
    def test_nonfinite_and_out_of_range_numerics_refused(self):
        nan = float("nan"); inf = float("inf")
        self.assertEqual(self.err(req(opps=[opp(1, effort_hours=nan)])), "APPLY_REFUSED_BAD_TYPE:effort_hours")
        self.assertEqual(self.err(req(opps=[opp(1, effort_hours=inf)])), "APPLY_REFUSED_BAD_TYPE:effort_hours")
        self.assertEqual(self.err(req(opps=[opp(1, p_win=nan)])), "APPLY_REFUSED_BAD_TYPE:p_win")
        self.assertEqual(self.err(req(opps=[opp(1, value=inf)])), "APPLY_REFUSED_BAD_TYPE:value")
        self.assertEqual(self.err(req(opps=[opp(1, value=nan)])), "APPLY_REFUSED_BAD_TYPE:value")
        self.assertEqual(self.err(req(opps=[opp(1, p_win=-0.5)])), "APPLY_REFUSED_BAD_TYPE:p_win")
        self.assertEqual(self.err(req(opps=[opp(1, p_win=2)])), "APPLY_REFUSED_BAD_TYPE:p_win")

    def test_p_win_bounds_zero_one_allowed(self):
        out = m.run(req(opps=[opp(1, p_win=0), opp(2, p_win=1, deadline="2026-11-02")]))
        scores = {r["id"]: r["score"] for r in out["ranking"]["ranked"]}
        self.assertEqual(scores["o1"], 0.0)
        self.assertEqual(scores["o2"], 2000.0 / 5.0)

    def test_nonfinite_score_refused(self):
        # huge finite inputs whose product/ratio overflows to inf
        out_err = self.err(req(opps=[opp(1, value=1e308, p_win=1.0, effort_hours=1e-308)]))
        self.assertEqual(out_err, "APPLY_REFUSED_NONFINITE:score")

    def test_profile_numbers_finite(self):
        self.assertEqual(self.err(req(opps=[opp(1)], profile={"name": "x", "n": float("nan")})),
                         "APPLY_REFUSED_BAD_TYPE:profile_value")
        self.assertEqual(self.err(req(opps=[opp(1)], profile={"name": "x", "n": float("inf")})),
                         "APPLY_REFUSED_BAD_TYPE:profile_value")
        out = m.run(req(opps=[opp(1, fields=["n"])], profile={"n": 3.5}))
        self.assertEqual(out["packets"][0]["filled"], {"n": 3.5})
        with self.assertRaises(ValueError) as cm:
            m.run(req(opps=[opp(1)], profile={"flag": True}))
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:profile_value")

    # -- dates -----------------------------------------------------------
    def test_canonical_dates_only(self):
        for bad in ("20261101", "2026-W44-1", "2026-11-1", "Nov 1 2026", 20261101, True):
            self.assertEqual(self.err(req(opps=[opp(1, deadline=bad)])), "APPLY_REFUSED_BAD_TYPE:deadline")
            self.assertEqual(self.err(req(opps=[opp(1)], as_of=bad)), "APPLY_REFUSED_BAD_TYPE:as_of")
        out = m.run(req(opps=[opp(1, deadline="2026-11-01")]))
        self.assertEqual(out["calendar"][0]["days_left"], 21)

    # -- caps and shape guards ------------------------------------------
    def test_profile_cap_boundary(self):
        prof = {"k%d" % i: "v" for i in range(128)}
        self.assertEqual(m.run(req(opps=[opp(1)], profile=prof))["packets"][0]["id"], "o1")
        prof["k128"] = "v"
        self.assertEqual(self.err(req(opps=[opp(1)], profile=prof)), "APPLY_REFUSED_OVERSIZE:profile")

    def test_opportunities_cap_and_shape(self):
        opps = [opp(1)]
        for i in range(2, 513):
            opps.append(opp(i, deadline="2026-12-%02d" % (i % 28 + 1), id="o%d" % i))
        self.assertEqual(len(m.run(req(opps=opps))["packets"]), 512)
        opps.append(opp(513, deadline="2026-12-01"))
        self.assertEqual(self.err(req(opps=opps)), "APPLY_REFUSED_OVERSIZE:opportunities")
        for bad in (True, "x", 123, {"id": "o1"}):
            self.assertEqual(self.err(req(opps=bad)), "APPLY_REFUSED_BAD_TYPE:opportunities")

    def test_fields_cap_and_shape(self):
        self.assertEqual(m.run(req(opps=[opp(1, fields=["name"] * 64)]))["packets"][0]["id"], "o1")
        self.assertEqual(self.err(req(opps=[opp(1, fields=["name"] * 65)])), "APPLY_REFUSED_OVERSIZE:fields")
        for bad in (True, "name", 7):
            self.assertEqual(self.err(req(opps=[opp(1, fields=bad)])), "APPLY_REFUSED_BAD_TYPE:fields")

    def test_date_shape_bool_and_nonstr(self):
        self.assertEqual(self.err(req(opps=[opp(1, deadline=True)])), "APPLY_REFUSED_BAD_TYPE:deadline")
        self.assertEqual(self.err(req(opps=[opp(1, deadline=["2026-11-01"])])), "APPLY_REFUSED_BAD_TYPE:deadline")

    # -- blocked-token full key scope ------------------------------------
    def test_blocked_tokens_scanned_everywhere(self):
        self.assertEqual(self.err(req(opps=[opp(1)], password="hunter2")), "APPLY_REFUSED_SUBMIT")
        self.assertEqual(self.err(req(opps=[opp(1)], profile={"login_url": "x"})), "APPLY_REFUSED_SUBMIT")
        self.assertEqual(self.err(req(opps=[opp(1)], submit="now")), "APPLY_REFUSED_SUBMIT")


class RepairS45HugeInt(unittest.TestCase):
    def err(self, r):
        with self.assertRaises(ValueError) as cm:
            m.run(r)
        return str(cm.exception)

    def test_huge_int_refused_not_overflowerror(self):
        huge = 10 ** 1000
        self.assertEqual(self.err(req(opps=[opp(1, value=huge)])), "APPLY_REFUSED_BAD_TYPE:value")
        self.assertEqual(self.err(req(opps=[opp(1, p_win=huge)])), "APPLY_REFUSED_BAD_TYPE:p_win")
        self.assertEqual(self.err(req(opps=[opp(1, effort_hours=huge)])), "APPLY_REFUSED_BAD_TYPE:effort_hours")
        self.assertEqual(self.err(req(opps=[opp(1)], profile={"n": huge})),
                         "APPLY_REFUSED_BAD_TYPE:profile_value")

    def test_huge_int_score_overflow_refused(self):
        # representable int value whose division overflows during scoring
        self.assertEqual(self.err(req(opps=[opp(1, value=10 ** 300, p_win=1.0, effort_hours=1e-10)])),
                         "APPLY_REFUSED_NONFINITE:score")

    def test_large_but_representable_int_accepted(self):
        out = m.run(req(opps=[opp(1, value=10 ** 300, p_win=0.5, effort_hours=2.0)]))
        self.assertEqual(out["ranking"]["ranked"][0]["score"], round(10 ** 300 * 0.5 / 2.0, 6))
