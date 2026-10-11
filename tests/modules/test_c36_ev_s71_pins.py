"""S7.1 / c36.ev pin tests added after the independent mutation list.
Test-only; the module is unchanged. Hermetic, stdlib unittest."""
import importlib.util, json, math, pathlib, sys, unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
_P = _ROOT / "backend/app/modules/c36/ev.py"
_spec = importlib.util.spec_from_file_location("c36_ev_pins", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c36_ev_pins"] = m
_spec.loader.exec_module(m)


def opp(id_, lo, base, hi, p, plo, phi, hours, deadline, cash=0, **kw):
    o = {"id": id_, "name": "Opp " + id_, "kind": "gig",
         "payoff": {"low": lo, "base": base, "high": hi, "currency": "USD"},
         "p_success": {"point": p, "low": plo, "high": phi},
         "cost": {"cash": cash, "hours": hours}, "deadline": deadline,
         "source_url": "https://example.test/" + id_}
    o.update(kw)
    return o


def req(opps, **kw):
    r = {"as_of": "2026-10-11", "hours_budget_per_week": 10, "hourly_value": 0,
         "currency": "USD", "opportunities": opps}
    r.update(kw)
    return r


def flat(id_, ev, hours=1, deadline="2026-11-01", **kw):
    """Deterministic item: p=1, payoff base=ev, low=high=ev (no spread)."""
    return opp(id_, ev, ev, ev, 1, 1, 1, hours, deadline, **kw)


def refusal(test, r, text):
    with test.assertRaises(ValueError) as cm:
        m.run(r)
    test.assertEqual(str(cm.exception), text)


class Limits(unittest.TestCase):
    def test_max_opportunities_boundary(self):
        ok = [flat("i%03d" % i, 1, hours=0) for i in range(256)]
        out = m.run(req(ok))
        self.assertEqual(len(out["ranked"]), 256)
        refusal(self, req(ok + [flat("i256", 1, hours=0)]), "MONEY_REFUSED_BAD_TYPE:opportunities")

    def test_text_limit_boundary(self):
        r = req([flat("a", 1)])
        r["opportunities"][0]["name"] = "n" * 512
        self.assertEqual(len(m.run(r)["ranked"][0]["name"]), 512)
        r["opportunities"][0]["name"] = "n" * 513
        refusal(self, r, "MONEY_REFUSED_TEXT_TOO_LONG:name")

    def test_num_maximum_branch_via_private_helper(self):
        # run() never passes a maximum; the helper's own contract is pinned directly
        self.assertEqual(m._num(5, "f", None, 5), 5)
        with self.assertRaises(ValueError) as cm:
            m._num(6, "f", None, 5)
        self.assertEqual(str(cm.exception), "MONEY_REFUSED_BAD_TYPE:f")


class Types(unittest.TestCase):
    def test_probability_bad_values_all_refused_as_badprob(self):
        for v in (True, False, "0.5", float("nan"), float("inf"), float("-inf"), [0.5], {}):
            r = req([flat("a", 1)])
            r["opportunities"][0]["p_success"]["point"] = v
            refusal(self, r, "MONEY_REFUSED_BADPROB:p_success.point")

    def test_number_bad_values_refused_as_bad_type(self):
        for v in (True, "5", float("nan"), float("inf"), [5]):
            r = req([flat("a", 1)])
            r["opportunities"][0]["cost"]["hours"] = v
            refusal(self, r, "MONEY_REFUSED_BAD_TYPE:cost.hours")

    def test_date_formats_refused(self):
        for bad in ("2026-W41-1", "2026-10-1", "2026-10-111", "20261011", "2026/10/11",
                    "abcd-ef-gh", "2026-10-1x", "2026-1-011", "          "):
            r = req([flat("a", 1)])
            r["opportunities"][0]["deadline"] = bad
            refusal(self, r, "MONEY_REFUSED_BAD_TYPE:deadline")
            r = req([flat("a", 1)])
            r["as_of"] = bad
            refusal(self, r, "MONEY_REFUSED_BAD_TYPE:as_of")

    def test_currency_codes_refused(self):
        for bad in ("U1D", "US1", "US$", "U D", "usd", "uSD", "\u00c0\u00c9\u00c8", "USDX", "US", "", 5):
            r = req([flat("a", 1)])
            r["currency"] = bad
            refusal(self, r, "MONEY_REFUSED_BAD_TYPE:currency")

    def test_payoff_equalities_allowed(self):
        for lo, ba, hi in ((5, 5, 9), (1, 9, 9), (7, 7, 7)):
            r = req([opp("a", lo, ba, hi, 1, 1, 1, 1, "2026-11-01")])
            self.assertEqual(m.run(r)["ranked"][0]["ev"], ba)


class Fx(unittest.TestCase):
    def eur(self, **kw):
        o = opp("e", 100, 1000, 2000, 0.1, 0.05, 0.2, 0, "2026-11-01")
        o["payoff"]["currency"] = "EUR"
        o.update(kw)
        return o

    def test_rates_at_and_below_one_accepted(self):
        for rate, want in ((1, 100), (0.9, 90), (0.5, 50), (1.08, 108)):
            out = m.run(req([self.eur()], fx={"as_of": "2026-10-10", "rates_to_base": {"EUR": rate}}))
            self.assertEqual(out["ranked"][0]["ev"], want, rate)

    def test_ev_low_and_high_use_the_rate_multiplicatively(self):
        out = m.run(req([self.eur()], fx={"as_of": "2026-10-10", "rates_to_base": {"EUR": 1.08}}))
        x = out["ranked"][0]
        self.assertEqual((x["ev_low"], x["ev"], x["ev_high"]), (5.4, 108, 432))  # .05*100*1.08

    def test_rate_is_exact_decimal_not_float(self):
        # a: 0.1 * 3 EUR * 1.1 = 0.33 exactly; b: 0.33 USD. Exact tie, so fewer hours wins.
        a = opp("a", 0, 3, 3, 0.1, 0.1, 0.1, 2, "2026-11-01")
        a["payoff"]["currency"] = "EUR"
        b = opp("b", 0, 1, 1, 0.33, 0.33, 0.33, 1, "2026-11-01")
        out = m.run(req([a, b], fx={"as_of": "2026-10-10", "rates_to_base": {"EUR": 1.1}}))
        self.assertEqual([x["id"] for x in out["ranked"]], ["b", "a"])


class Defaults(unittest.TestCase):
    def test_omitted_flags_default_to_not_spend_not_outreach(self):
        o = flat("a", 5)
        self.assertNotIn("requires_spend", o)
        self.assertNotIn("requires_outreach", o)
        out = m.run(req([o]))
        self.assertEqual([x["id"] for x in out["ranked"]], ["a"])
        self.assertEqual(out["ranked"][0]["flags"], [])
        self.assertEqual(out["not_actionable_without_separate_approval"], [])

    def test_explicit_true_flags_still_apply(self):
        out = m.run(req([flat("s", 5, requires_spend=True), flat("o", 4, requires_outreach=True)]))
        self.assertEqual([x["id"] for x in out["not_actionable_without_separate_approval"]], ["s"])
        self.assertEqual(out["ranked"][0]["flags"], ["draft_only_needs_approval"])

    def test_label_and_notes_echoed_only_when_supplied(self):
        out = m.run(req([flat("a", 5, label="L1", notes="N1"), flat("b", 4)]))
        a, b = out["ranked"]
        self.assertEqual((a["label"], a["notes"]), ("L1", "N1"))
        self.assertNotIn("label", b)
        self.assertNotIn("notes", b)


class Rendering(unittest.TestCase):
    def test_no_negative_zero(self):
        o = opp("a", 0, 0, 0, 1, 1, 1, 0.00001, "2026-11-01")
        out = m.run(req([o], hourly_value=0.01))
        x = out["ranked"][0]
        self.assertEqual(json.dumps([x["ev"], x["ev_low"], x["ev_high"]]), "[0.0, 0.0, 0.0]")
        self.assertEqual(math.copysign(1, x["ev"]), 1.0)

    def test_integer_originals_are_ints_fractions_are_floats(self):
        o = opp("a", 100, 1000, 2000, 0.5, 0.5, 0.5, 2.5, "2026-11-01", cash=0)
        o["payoff"]["low"] = 0.5
        x = m.run(req([o]))["ranked"][0]
        self.assertEqual(json.dumps(x["original"]),
                         '{"payoff": {"low": 0.5, "base": 1000, "high": 2000, "currency": "USD"}, '
                         '"cash": {"amount": 0, "currency": "USD"}}')
        self.assertEqual(json.dumps(x["hours"]), "2.5")
        self.assertEqual(json.dumps(m.run(req([flat("b", 5, hours=4)]))["ranked"][0]["hours"]), "4")

    def test_weeks_and_capacity_integers(self):
        out = m.run(req([flat("a", 5, hours=2)]))
        self.assertEqual(json.dumps(out["plan"]["greedy"]["usage"]),
                         '[{"deadline": "2026-11-01", "weeks_available": 3, "used_hours": 2, '
                         '"capacity_hours": 30}]')


class GreedyOrder(unittest.TestCase):
    def test_small_positive_ev_is_planned(self):
        out = m.run(req([flat("a", 0.5, hours=1)]))
        self.assertEqual(out["plan"]["greedy"]["selected"], ["a"])
        self.assertEqual(out["plan"]["brute_force"]["selected"], ["a"])
        self.assertEqual(out["plan"]["greedy"]["total_ev"], 0.5)
        self.assertEqual(out["plan"]["brute_force"]["total_ev"], 0.5)

    def test_zero_hour_items_ordered_by_higher_ev(self):
        out = m.run(req([flat("a", 5, hours=0), flat("b", 9, hours=0), flat("c", 2, hours=0)]))
        self.assertEqual(out["plan"]["greedy"]["selected"], ["b", "a", "c"])

    def test_equal_ev_per_hour_prefers_higher_ev(self):
        # A: 100 EV/10h, B: 50 EV/5h, both 10 EV per hour; budget 10h in one week
        out = m.run(req([flat("B", 50, hours=5, deadline="2026-10-18"),
                         flat("A", 100, hours=10, deadline="2026-10-18")]))
        self.assertEqual(out["plan"]["greedy"]["selected"], ["A"])
        self.assertEqual(out["plan"]["greedy"]["over_budget"], ["B"])

    def test_equal_ev_per_hour_then_id(self):
        out = m.run(req([flat("y", 50, hours=5), flat("x", 50, hours=5)]))
        self.assertEqual(out["plan"]["greedy"]["selected"], ["x", "y"])

    def test_per_hour_order_descending(self):
        out = m.run(req([flat("lo", 10, hours=5), flat("hi", 30, hours=5)]))
        self.assertEqual(out["plan"]["greedy"]["selected"], ["hi", "lo"])


class BruteForce(unittest.TestCase):
    def test_zero_ev_zero_hour_item_never_in_optimum(self):
        z = flat("0z", 0, hours=0)
        a = flat("a", 10, hours=1)
        out = m.run(req([z, a]))
        self.assertEqual(out["plan"]["brute_force"]["selected"], ["a"])
        self.assertEqual(out["plan"]["greedy"]["selected"], ["a"])

    def test_tie_on_ev_and_hours_prefers_smaller_id_list(self):
        c = flat("c", 50, hours=2)
        a = flat("a", 20, hours=1)
        b = flat("b", 30, hours=1)
        for o in (c, a, b):
            o["deadline"] = "2026-10-18"
        out = m.run(req([c, a, b], hours_budget_per_week=2))
        self.assertEqual(out["plan"]["brute_force"]["selected"], ["a", "b"])
        self.assertEqual(out["plan"]["brute_force"]["total_hours"], 2)

    def test_tie_on_ev_and_hours_same_size_first_id_wins(self):
        out = m.run(req([flat("b", 10, hours=6, deadline="2026-10-18"),
                         flat("a", 10, hours=6, deadline="2026-10-18")]))
        self.assertEqual(out["plan"]["brute_force"]["selected"], ["a"])

    def test_fewer_hours_beats_more_hours_at_equal_ev(self):
        out = m.run(req([flat("a", 10, hours=6, deadline="2026-10-18"),
                         flat("b", 10, hours=5, deadline="2026-10-18")]))
        self.assertEqual(out["plan"]["brute_force"]["selected"], ["b"])


class Warnings(unittest.TestCase):
    def spread(self, id_, ev, ev_low, ev_high):
        """p=1 item whose EV, EV_low and EV_high are exactly the arguments
        (cost c = max(0, -ev_low) hours at hourly_value 1)."""
        c = max(0, -ev_low)
        return opp(id_, ev_low + c, ev + c, ev_high + c, 1, 1, 1, c, "2026-11-01")

    def z(self, id_, ev):
        return opp(id_, ev, ev, ev, 1, 1, 1, 0, "2026-11-01")

    def w(self, *items):
        return m.run(req(list(items), hourly_value=1))["warnings"]

    def test_exactly_half_share_with_high_spread_warns(self):
        self.assertIn("single_item_dominates:a", self.w(self.spread("a", 50, 0, 300), self.z("b", 50)))

    def test_forty_percent_share_does_not_warn(self):
        self.assertNotIn("single_item_dominates:a", self.w(self.spread("a", 40, 0, 300), self.z("b", 60)))

    def test_single_positive_item_never_warns(self):
        self.assertEqual(self.w(self.spread("a", 50, 0, 300)), [])
        self.assertEqual(self.w(self.spread("a", 50, 0, 300), self.z("z", 0)), [])

    def test_small_positive_item_counts_as_positive(self):
        self.assertIn("single_item_dominates:a", self.w(self.spread("a", 100, 0, 900), self.z("b", 0.5)))

    def test_spread_must_exceed_ev_and_uses_difference(self):
        # spread 600 > ev 50 but high + low = -200 < ev
        self.assertIn("single_item_dominates:a", self.w(self.spread("a", 50, -400, 200), self.z("b", 50)))
        # narrow spread (60 - 40 = 20 <= ev 50) although high + low = 100 > ev
        self.assertNotIn("single_item_dominates:a", self.w(self.spread("a", 50, 40, 60), self.z("b", 50)))

    def test_spread_equal_to_ev_does_not_warn(self):
        self.assertNotIn("single_item_dominates:a", self.w(self.spread("a", 50, 0, 50), self.z("b", 50)))

    def test_negative_ev_warning_strictly_below_zero(self):
        self.assertEqual(self.w(self.z("z", 0)), [])
        self.assertEqual(self.w(self.z("s", 0.5)), [])
        self.assertEqual(self.w(self.spread("n", -10, -10, -10)), ["negative_ev:n"])


if __name__ == "__main__":
    unittest.main()
