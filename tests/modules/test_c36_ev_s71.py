"""S7.1 / c36.ev tests. Hermetic, stdlib unittest. Offline, no network."""
import ast, copy, importlib.util, json, pathlib, sys, unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
_P = _ROOT / "backend/app/modules/c36/ev.py"
_spec = importlib.util.spec_from_file_location("c36_ev", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c36_ev"] = m
_spec.loader.exec_module(m)


def opp(id_, lo, base, hi, p, plo, phi, hours, deadline, cash=0, **kw):
    o = {"id": id_, "name": "Opp " + id_, "kind": "gig",
         "payoff": {"low": lo, "base": base, "high": hi, "currency": "USD"},
         "p_success": {"point": p, "low": plo, "high": phi},
         "cost": {"cash": cash, "hours": hours}, "deadline": deadline,
         "requires_spend": False, "requires_outreach": False,
         "source_url": "https://example.test/" + id_}
    o.update(kw)
    return o


def req(opps, **kw):
    r = {"as_of": "2026-10-11", "hours_budget_per_week": 10, "hourly_value": 10,
         "currency": "USD", "opportunities": opps}
    r.update(kw)
    return r


def fixture():
    return [
        opp("o1", 500, 1000, 2000, 0.10, 0.05, 0.20, 5, "2026-11-01", kind="scholarship"),
        opp("o2", 2000, 5000, 10000, 0.04, 0.02, 0.08, 20, "2026-12-01", kind="grant"),
        opp("o3", 100, 300, 600, 0.25, 0.2, 0.3, 2, "2026-10-20", kind="prize"),
        opp("o4", 200, 400, 600, 0.9, 0.8, 0.95, 8, "2026-10-25"),
        opp("o5", 50, 150, 300, 0.5, 0.3, 0.7, 4, "2026-11-15", kind="hustle"),
        opp("o6", 300, 800, 1200, 0.6, 0.5, 0.7, 10, "2026-11-10", cash=100),
        opp("o7", 100, 200, 300, 0.5, 0.4, 0.6, 1, "2026-10-10"),
        opp("o8", 20, 60, 100, 1, 1, 1, 1, "2026-10-11"),
        opp("o9", 100, 400, 800, 0.3, 0.2, 0.4, 3, "2026-11-30", requires_outreach=True,
            kind="scholarship"),
        opp("o10", 100, 200, 300, 0.4, 0.3, 0.5, 3, "2026-11-05"),
    ]


def refusal(test, r, text):
    with test.assertRaises(ValueError) as cm:
        m.run(r)
    test.assertEqual(str(cm.exception), text)


class HandComputed(unittest.TestCase):
    def setUp(self):
        self.out = m.run(req(fixture()))
        self.by = {x["id"]: x for x in self.out["ranked"]}

    def test_exact_evs(self):
        want = {"o1": (50, -25, 350), "o2": (0, -160, 600), "o3": (55, 0, 160),
                "o4": (280, 80, 490), "o5": (35, -25, 170), "o8": (50, 10, 90),
                "o9": (90, -10, 290), "o10": (50, 0, 120)}
        for k, (ev, lo, hi) in want.items():
            self.assertEqual((self.by[k]["ev"], self.by[k]["ev_low"], self.by[k]["ev_high"]),
                             (ev, lo, hi), k)

    def test_ranking_order_and_ties(self):
        self.assertEqual([x["id"] for x in self.out["ranked"]],
                         ["o4", "o9", "o3", "o8", "o10", "o1", "o5", "o2"])
        self.assertEqual([x["rank"] for x in self.out["ranked"]], list(range(1, 9)))

    def test_ev_per_hour(self):
        self.assertEqual(self.by["o8"]["ev_per_hour"], 50)
        self.assertEqual(self.by["o4"]["ev_per_hour"], 35)
        self.assertEqual(self.by["o10"]["ev_per_hour"], 16.666667)
        self.assertEqual(self.by["o5"]["ev_per_hour"], 8.75)

    def test_cash_item_segregated_with_info_ev(self):
        na = self.out["not_actionable_without_separate_approval"]
        self.assertEqual([x["id"] for x in na], ["o6"])
        self.assertEqual((na[0]["ev"], na[0]["ev_low"], na[0]["ev_high"]), (280, -50, 640))
        self.assertIn("spending needs the owner's separate per-action approval outside this unit",
                      na[0]["note"])
        self.assertNotIn("o6", self.by)

    def test_expired_and_equal_deadline(self):
        self.assertEqual([x["id"] for x in self.out["expired"]], ["o7"])
        self.assertNotIn("o7", self.by)
        self.assertEqual(self.by["o8"]["weeks_available"], 1)
        self.assertEqual(self.by["o8"]["days_to_deadline"], 0)
        self.assertEqual(self.by["o3"]["weeks_available"], 2)  # 9 days
        self.assertEqual(self.by["o4"]["weeks_available"], 2)  # 14 days
        self.assertEqual(self.by["o1"]["weeks_available"], 3)  # 21 days

    def test_outreach_flag(self):
        self.assertEqual(self.by["o9"]["flags"], ["draft_only_needs_approval"])
        self.assertEqual(self.by["o4"]["flags"], [])

    def test_plan_greedy_and_brute_force(self):
        plan = self.out["plan"]
        self.assertEqual(plan["greedy"]["selected"], ["o8", "o4", "o9", "o3", "o10", "o1", "o5"])
        self.assertEqual(plan["greedy"]["total_ev"], 610)
        self.assertEqual(plan["greedy"]["total_hours"], 26)
        self.assertEqual(plan["brute_force"]["total_ev"], 610)
        self.assertEqual(plan["gap_ev"], 0)
        self.assertEqual(plan["brute_force"]["considered"], 8)

    def test_banner_scope_and_language(self):
        self.assertEqual(self.out["banner"],
                         "Expected values from supplied estimates; not a promise of income.")
        self.assertIn("market data", " ".join(self.out["scope"]["not_implemented"]))
        text = json.dumps(self.out).lower()
        for bad in ("will earn", "guaranteed", "guarantee"):
            self.assertNotIn(bad, text)

    def test_determinism_bytes(self):
        a = json.dumps(m.run(req(fixture())), sort_keys=True)
        b = json.dumps(m.run(req(list(reversed(fixture())))), sort_keys=True)
        self.assertEqual(a, b)

    def test_input_not_mutated(self):
        r = req(fixture())
        before = copy.deepcopy(r)
        m.run(r)
        self.assertEqual(r, before)


class Ties(unittest.TestCase):
    def test_tie_hours_then_deadline_then_id(self):
        # all EV 50 at hourly_value 0: p*base
        a = opp("a", 0, 100, 100, 0.5, 0.5, 0.5, 4, "2026-11-01")
        b = opp("b", 0, 100, 100, 0.5, 0.5, 0.5, 2, "2026-11-20")
        c = opp("c", 0, 100, 100, 0.5, 0.5, 0.5, 2, "2026-11-10")
        d = opp("d", 0, 100, 100, 0.5, 0.5, 0.5, 2, "2026-11-10")
        out = m.run(req([d, a, b, c], hourly_value=0))
        self.assertEqual([x["id"] for x in out["ranked"]], ["c", "d", "b", "a"])


class Plan(unittest.TestCase):
    def test_greedy_gap_vs_brute_force(self):
        A = opp("A", 0, 100, 100, 0.6, 0.6, 0.6, 6, "2026-10-18")
        B = opp("B", 0, 100, 100, 0.45, 0.45, 0.45, 5, "2026-10-18")
        C = opp("C", 0, 100, 100, 0.45, 0.45, 0.45, 5, "2026-10-18")
        out = m.run(req([A, B, C], hourly_value=0))
        p = out["plan"]
        self.assertEqual(p["greedy"]["selected"], ["A"])
        self.assertEqual(p["greedy"]["total_ev"], 60)
        self.assertEqual(p["brute_force"]["selected"], ["B", "C"])
        self.assertEqual(p["brute_force"]["total_ev"], 90)
        self.assertEqual(p["gap_ev"], 30)

    def test_deadline_aware_feasibility(self):
        # 10h/week; X due in 7 days (1 week -> cap 10h), Y due in 14 days (2 weeks -> 20h cumulative)
        X = opp("X", 0, 100, 100, 1, 1, 1, 10, "2026-10-18")
        Y = opp("Y", 0, 100, 100, 1, 1, 1, 10, "2026-10-25")
        Z = opp("Z", 0, 100, 100, 0.5, 0.5, 0.5, 1, "2026-10-18")
        out = m.run(req([X, Y, Z], hourly_value=0))
        sel = out["plan"]["brute_force"]["selected"]
        self.assertEqual(sorted(sel), ["X", "Y"])  # Z cannot also fit before 10-18 with X
        self.assertEqual(out["plan"]["greedy"]["total_hours"] <= 20, True)

    def test_brute_force_skipped_over_15(self):
        opps = [opp("p%02d" % i, 0, 100, 100, 0.5, 0.5, 0.5, 1, "2026-11-30") for i in range(16)]
        out = m.run(req(opps, hours_budget_per_week=100))
        self.assertIsNone(out["plan"]["brute_force"])
        self.assertIsNone(out["plan"]["gap_ev"])
        opps15 = opps[:15]
        self.assertIsNotNone(m.run(req(opps15, hours_budget_per_week=100))["plan"]["brute_force"])

    def test_zero_budget_empty_plan(self):
        out = m.run(req([opp("a", 0, 100, 100, 0.5, 0.5, 0.5, 2, "2026-11-01")],
                        hours_budget_per_week=0))
        self.assertEqual(out["plan"]["greedy"]["selected"], [])

    def test_negative_ev_never_in_plan(self):
        out = m.run(req([opp("n", 0, 100, 100, 0.1, 0.1, 0.1, 5, "2026-11-01")]))
        self.assertEqual(out["plan"]["greedy"]["selected"], [])


class Spend(unittest.TestCase):
    def test_requires_spend_flag_segregated_even_with_zero_cash(self):
        o = opp("s", 0, 100, 100, 0.5, 0.5, 0.5, 1, "2026-11-01", requires_spend=True)
        out = m.run(req([o]))
        self.assertEqual(out["ranked"], [])
        self.assertEqual(out["not_actionable_without_separate_approval"][0]["id"], "s")

    def test_no_input_moves_cash_item_to_actionable(self):
        o = opp("c", 0, 100, 100, 0.9, 0.9, 0.9, 1, "2026-11-01", cash=5)
        for extra in ({"spend_approved_ids": ["c"]}, {"approved": True}, {"approval_ids": ["c"]}):
            r = req([o])
            r.update(extra)
            out = m.run(r)
            self.assertEqual(out["ranked"], [], extra)
            self.assertEqual(len(out["not_actionable_without_separate_approval"]), 1)
        o2 = copy.deepcopy(o)
        o2.update({"approved": True, "spend_approved": True, "approval_id": "x"})
        self.assertEqual(m.run(req([o2]))["ranked"], [])

    def test_cash_in_other_currency_still_segregated(self):
        o = opp("c", 0, 100, 100, 0.9, 0.9, 0.9, 1, "2026-11-01")
        o["cost"]["cash"] = 1
        o["cost"]["currency"] = "EUR"
        out = m.run(req([o], fx={"as_of": "2026-10-10", "rates_to_base": {"EUR": 1.08}}))
        self.assertEqual(out["ranked"], [])

    def test_tiny_cash_still_segregated(self):
        o = opp("c", 0, 100, 100, 0.9, 0.9, 0.9, 1, "2026-11-01", cash=0.000001)
        self.assertEqual(m.run(req([o]))["ranked"], [])


class Currency(unittest.TestCase):
    FX = {"as_of": "2026-10-10", "rates_to_base": {"EUR": 1.08}}

    def eur(self, **kw):
        o = opp("e", 0, 1000, 2000, 0.1, 0.05, 0.2, 0, "2026-11-01")
        o["payoff"]["currency"] = "EUR"
        o.update(kw)
        return o

    def test_mixed_without_fx_refused(self):
        refusal(self, req([self.eur(), opp("u", 0, 100, 100, 0.5, 0.5, 0.5, 1, "2026-11-01")]),
                "MONEY_REFUSED_CURRENCY:EUR")

    def test_foreign_currency_alone_without_fx_refused(self):
        refusal(self, req([self.eur()]), "MONEY_REFUSED_CURRENCY:EUR")

    def test_fx_converts_and_prints_originals(self):
        out = m.run(req([self.eur()], fx=self.FX, hourly_value=0))
        x = out["ranked"][0]
        self.assertEqual(x["ev"], 108)          # 0.1 * 1000 EUR * 1.08
        self.assertEqual(x["ev_high"], 432)     # 0.2 * 2000 * 1.08
        self.assertEqual(x["original"]["payoff"]["currency"], "EUR")
        self.assertEqual(x["original"]["payoff"]["base"], 1000)
        self.assertEqual(x["fx"]["EUR"], {"rate_to_base": 1.08, "as_of": "2026-10-10"})
        self.assertEqual(out["fx_used"], [{"currency": "EUR", "rate_to_base": 1.08,
                                           "as_of": "2026-10-10"}])

    def test_fx_missing_currency_refused(self):
        o = self.eur()
        o["payoff"]["currency"] = "GBP"
        refusal(self, req([o], fx=self.FX), "MONEY_REFUSED_CURRENCY:GBP")

    def test_fx_missing_as_of_refused(self):
        refusal(self, req([self.eur()], fx={"rates_to_base": {"EUR": 1.08}}),
                "MONEY_REFUSED_CURRENCY:fx.as_of")

    def test_fx_bad_rate_refused(self):
        for bad in (0, -1, True, "1.08", float("inf")):
            refusal(self, req([self.eur()], fx={"as_of": "2026-10-10", "rates_to_base": {"EUR": bad}}),
                    "MONEY_REFUSED_CURRENCY:fx.rates_to_base")

    def test_cost_currency_override(self):
        o = opp("c", 0, 100, 100, 0.9, 0.9, 0.9, 0, "2026-11-01", cash=10)
        o["cost"]["currency"] = "EUR"
        out = m.run(req([o], fx=self.FX, hourly_value=0))
        na = out["not_actionable_without_separate_approval"][0]
        self.assertEqual(na["ev"], 79.2)  # 90 - 10*1.08
        self.assertEqual(na["original"]["cash"], {"amount": 10, "currency": "EUR"})

    def test_cash_defaults_to_payoff_currency(self):
        o = self.eur(cost={"cash": 10, "hours": 0})
        out = m.run(req([o], fx=self.FX, hourly_value=0))
        na = out["not_actionable_without_separate_approval"][0]
        self.assertEqual(na["original"]["cash"]["currency"], "EUR")
        self.assertEqual(na["ev"], 97.2)  # 108 - 10.8

    def test_fx_not_a_dict_or_bad_date_refused(self):
        refusal(self, req([self.eur()], fx=[1]), "MONEY_REFUSED_CURRENCY:fx")
        refusal(self, req([self.eur()], fx={"as_of": "10/10", "rates_to_base": {"EUR": 1.08}}),
                "MONEY_REFUSED_CURRENCY:fx.as_of")
        refusal(self, req([self.eur()], fx={"as_of": "2026-10-10", "rates_to_base": [1]}),
                "MONEY_REFUSED_CURRENCY:fx.rates_to_base")

    def test_bad_currency_codes(self):
        for bad in ("usd", "US", "USDX", 5, "U\u00dfD"):
            refusal(self, req([opp("a", 0, 1, 1, 0.5, 0.5, 0.5, 1, "2026-11-01")], currency=bad),
                    "MONEY_REFUSED_BAD_TYPE:currency")

    def test_hourly_value_is_base(self):
        o = self.eur(cost={"cash": 0, "hours": 10})
        out = m.run(req([o], fx=self.FX, hourly_value=2))
        self.assertEqual(out["ranked"][0]["ev"], 88)  # 108 - 20


class Refusals(unittest.TestCase):
    def base(self):
        return req([opp("a", 0, 100, 100, 0.5, 0.5, 0.5, 1, "2026-11-01")])

    def test_probability(self):
        for key, v in (("point", 1.1), ("point", -0.1), ("low", 2), ("high", -1)):
            r = self.base()
            r["opportunities"][0]["p_success"][key] = v
            refusal(self, r, "MONEY_REFUSED_BADPROB:p_success.%s" % key)

    def test_probability_order(self):
        r = self.base()
        r["opportunities"][0]["p_success"] = {"point": 0.5, "low": 0.6, "high": 0.7}
        refusal(self, r, "MONEY_REFUSED_BADPROB:p_success")

    def test_probability_boundaries_allowed(self):
        r = self.base()
        r["opportunities"][0]["p_success"] = {"point": 0, "low": 0, "high": 1}
        m.run(r)
        r["opportunities"][0]["p_success"] = {"point": 1, "low": 1, "high": 1}
        m.run(r)

    def test_payoff_order(self):
        r = self.base()
        r["opportunities"][0]["payoff"].update({"low": 200})
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:payoff")
        r = self.base()
        r["opportunities"][0]["payoff"].update({"high": 50})
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:payoff")

    def test_missing_source_url(self):
        r = self.base()
        del r["opportunities"][0]["source_url"]
        refusal(self, r, "MONEY_REFUSED_NOINPUT:source_url")
        r = self.base()
        r["opportunities"][0]["source_url"] = "   "
        refusal(self, r, "MONEY_REFUSED_EMPTY:source_url")

    def test_missing_required_fields(self):
        for k in ("payoff", "p_success", "cost", "deadline", "name", "id"):
            r = self.base()
            del r["opportunities"][0][k]
            refusal(self, r, "MONEY_REFUSED_NOINPUT:%s" % k)
        for k in ("as_of", "hours_budget_per_week", "hourly_value", "currency", "opportunities"):
            r = self.base()
            del r[k]
            refusal(self, r, "MONEY_REFUSED_NOINPUT:%s" % k)

    def test_empty_opportunities(self):
        r = self.base()
        r["opportunities"] = []
        refusal(self, r, "MONEY_REFUSED_EMPTY:opportunities")

    def test_bad_types(self):
        refusal(self, [], "MONEY_REFUSED_BAD_TYPE:request")
        r = self.base()
        r["opportunities"] = "x"
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:opportunities")
        r = self.base()
        r["opportunities"] = [5]
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:opportunity")
        r = self.base()
        r["opportunities"][0]["cost"]["hours"] = True
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:cost.hours")
        r = self.base()
        r["opportunities"][0]["cost"]["cash"] = -1
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:cost.cash")
        r = self.base()
        r["opportunities"][0]["payoff"]["base"] = float("nan")
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:payoff.base")
        r = self.base()
        r["opportunities"][0]["requires_spend"] = "no"
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:requires_spend")
        r = self.base()
        r["opportunities"][0]["kind"] = "lottery"
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:kind")
        r = self.base()
        r["hourly_value"] = -1
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:hourly_value")
        r = self.base()
        r["hours_budget_per_week"] = -1
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:hours_budget_per_week")

    def test_bad_dates(self):
        for bad in ("2026-13-01", "20261101", "2026-1-1", 5):
            r = self.base()
            r["opportunities"][0]["deadline"] = bad
            refusal(self, r, "MONEY_REFUSED_BAD_TYPE:deadline")
        r = self.base()
        r["as_of"] = "tomorrow"
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:as_of")

    def test_duplicate_ids(self):
        r = self.base()
        r["opportunities"].append(copy.deepcopy(r["opportunities"][0]))
        refusal(self, r, "MONEY_REFUSED_BAD_TYPE:id")

    def test_guarantee_language_refused(self):
        for phrase in ("Guaranteed income", "you will earn $5k", "risk-free money", "GUARANTEE"):
            r = self.base()
            r["opportunities"][0]["name"] = phrase
            refusal(self, r, "MONEY_REFUSED_GUARANTEE:name")

    def test_guarantee_phrases_all_fields_case_insensitive(self):
        for phrase in ("guaranteed", "Risk-Free", "WILL EARN", "sure thing", "Certain Profit"):
            for field in ("name", "notes", "label"):
                r = self.base()
                r["opportunities"][0][field] = "x " + phrase + " y"
                refusal(self, r, "MONEY_REFUSED_GUARANTEE:%s" % field)

    def test_all_every_best_not_scanned_in_caller_text(self):
        r = self.base()
        r["opportunities"][0]["name"] = "Best of every contest, all of them"
        r["opportunities"][0]["notes"] = "best"
        out = m.run(r)
        self.assertEqual(out["ranked"][0]["name"], "Best of every contest, all of them")
        self.assertEqual(out["ranked"][0]["notes"], "best")

    def test_generated_text_all_every_best_only_with_number(self):
        out = m.run(req(fixture()))
        s = out["summary"]
        self.assertEqual(s, "highest EV: 280.0 (o4) of 8 ranked supplied; "
                            "1 supplied excluded as expired; 1 held for separate approval")
        import re
        for key in ("summary", "banner"):
            for w in re.findall(r"\b(all|every|best)\b", out[key].lower()):
                self.fail("unqualified %s in %s" % (w, key))

    def test_control_chars_refused_by_policy(self):
        r = self.base()
        r["opportunities"][0]["name"] = "bad\x00name"
        refusal(self, r, "MONEY_REFUSED_CONTROL_CHARS:name")

    def test_fx_not_required_when_all_base(self):
        m.run(self.base())


class Survivors(unittest.TestCase):
    """Added after the first mutation run left M34, M45, M47, M55 alive."""

    def test_fx_as_of_non_string_refused(self):
        o = opp("e", 0, 1000, 2000, 0.1, 0.05, 0.2, 0, "2026-11-01")
        o["payoff"]["currency"] = "EUR"
        for bad in (5, None, True):
            refusal(self, req([o], fx={"as_of": bad, "rates_to_base": {"EUR": 1.08}}),
                    "MONEY_REFUSED_CURRENCY:fx.as_of")

    def test_zero_hour_items_come_first_in_greedy_selection(self):
        z = opp("z", 0, 100, 100, 0.5, 0.5, 0.5, 0, "2026-11-01")
        a = opp("a", 0, 1000, 1000, 0.5, 0.5, 0.5, 1, "2026-11-01")
        out = m.run(req([a, z], hourly_value=0))
        self.assertEqual(out["plan"]["greedy"]["selected"], ["z", "a"])
        self.assertIsNone(out["ranked"][1]["ev_per_hour"])

    def test_brute_force_tie_prefers_fewer_hours(self):
        # both EV 50, 5h budget in one week: either alone fits, together do not
        a = opp("a", 0, 100, 100, 0.5, 0.5, 0.5, 5, "2026-10-18")
        b = opp("b", 0, 100, 100, 0.5, 0.5, 0.5, 3, "2026-10-18")
        c = opp("c", 0, 100, 100, 0.5, 0.5, 0.5, 3, "2026-10-18")
        out = m.run(req([a, b, c], hourly_value=0, hours_budget_per_week=5))
        self.assertEqual(out["plan"]["brute_force"]["selected"], ["b"])
        self.assertEqual(out["plan"]["brute_force"]["total_hours"], 3)

    def test_decimal_exact_arithmetic_tie(self):
        # 0.1*3 and 0.3*1 are both exactly 0.3 in decimal; binary floats differ
        a = opp("a", 0, 3, 3, 0.1, 0.1, 0.1, 2, "2026-11-01")
        b = opp("b", 0, 1, 1, 0.3, 0.3, 0.3, 1, "2026-11-01")
        out = m.run(req([a, b], hourly_value=0))
        self.assertEqual([x["id"] for x in out["ranked"]], ["b", "a"])


class DecimalExactNum(unittest.TestCase):
    def test_hourly_value_and_payoff_decimal_exact(self):
        # 0.4 - 1*0.1 and 0.3 are both exactly 0.3 in decimal; binary floats differ
        a = opp("a", 0, 0.4, 0.4, 1, 1, 1, 1, "2026-11-01")
        b = opp("b", 0, 0.3, 0.3, 1, 1, 1, 0, "2026-11-01")
        out = m.run(req([a, b], hourly_value=0.1))
        self.assertEqual([x["id"] for x in out["ranked"]], ["b", "a"])


class BudgetRuling(unittest.TestCase):
    """Hours budget: for every member deadline d, hours of members with
    deadline <= d must fit weekly x weeks_available(d). Over-budget
    candidates are skipped and flagged; usage vs capacity is printed."""

    def test_over_budget_flag_and_usage_greedy(self):
        A = opp("A", 0, 100, 100, 0.6, 0.6, 0.6, 6, "2026-10-18")
        B = opp("B", 0, 100, 100, 0.45, 0.45, 0.45, 5, "2026-10-18")
        C = opp("C", 0, 100, 100, 0.45, 0.45, 0.45, 5, "2026-10-18")
        out = m.run(req([A, B, C], hourly_value=0))
        g = out["plan"]["greedy"]
        self.assertEqual(g["selected"], ["A"])
        self.assertEqual(g["over_budget"], ["B", "C"])
        self.assertEqual(g["usage"], [{"deadline": "2026-10-18", "weeks_available": 1,
                                       "used_hours": 6, "capacity_hours": 10}])
        flags = {x["id"]: x["flags"] for x in out["ranked"]}
        self.assertEqual(flags["A"], [])
        self.assertEqual(flags["B"], ["over_budget"])
        self.assertEqual(flags["C"], ["over_budget"])
        self.assertEqual(out["plan"]["brute_force"]["usage"],
                         [{"deadline": "2026-10-18", "weeks_available": 1,
                           "used_hours": 10, "capacity_hours": 10}])

    def test_prefix_cumulative_across_deadlines(self):
        X = opp("X", 0, 100, 100, 1, 1, 1, 8, "2026-10-18")   # prefix cap 10
        Y = opp("Y", 0, 100, 100, 1, 1, 1, 10, "2026-10-25")  # cumulative cap 20
        Z = opp("Z", 0, 100, 100, 0.5, 0.5, 0.5, 3, "2026-10-18")  # with X: 8+3 > 10 at 10-18
        out = m.run(req([X, Y, Z], hourly_value=0))
        g = out["plan"]["greedy"]
        # greedy takes Z first (16.67 EV/h), X would make 11 > 10 at 10-18 so it is skipped
        self.assertEqual(g["selected"], ["Z", "Y"])
        self.assertEqual(g["over_budget"], ["X"])
        self.assertEqual(g["usage"], [
            {"deadline": "2026-10-18", "weeks_available": 1, "used_hours": 3, "capacity_hours": 10},
            {"deadline": "2026-10-25", "weeks_available": 2, "used_hours": 13, "capacity_hours": 20}])
        bf = out["plan"]["brute_force"]
        self.assertEqual(bf["selected"], ["X", "Y"])
        self.assertEqual(bf["usage"], [
            {"deadline": "2026-10-18", "weeks_available": 1, "used_hours": 8, "capacity_hours": 10},
            {"deadline": "2026-10-25", "weeks_available": 2, "used_hours": 18, "capacity_hours": 20}])
        self.assertEqual(out["plan"]["gap_ev"], 50)

    def test_usage_counts_all_members_with_deadline_up_to_d(self):
        a = opp("a", 0, 100, 100, 1, 1, 1, 4, "2026-10-18")
        b = opp("b", 0, 100, 100, 1, 1, 1, 4, "2026-10-18")
        out = m.run(req([a, b], hourly_value=0))
        self.assertEqual(out["plan"]["greedy"]["usage"],
                         [{"deadline": "2026-10-18", "weeks_available": 1,
                           "used_hours": 8, "capacity_hours": 10}])
        self.assertEqual(out["plan"]["greedy"]["over_budget"], [])

    def test_no_over_budget_for_non_positive_ev_or_cash_items(self):
        n = opp("n", 0, 100, 100, 0.1, 0.1, 0.1, 5, "2026-10-18")
        out = m.run(req([n]))
        self.assertEqual(out["plan"]["greedy"]["over_budget"], [])
        self.assertEqual(out["ranked"][0]["flags"], [])

    def test_fixture_usage_exact(self):
        out = m.run(req(fixture()))
        self.assertEqual(out["plan"]["greedy"]["over_budget"], [])
        u = {x["deadline"]: x for x in out["plan"]["greedy"]["usage"]}
        self.assertEqual(u["2026-10-11"]["used_hours"], 1)
        self.assertEqual(u["2026-10-25"]["used_hours"], 11)
        self.assertEqual(u["2026-11-30"]["used_hours"], 26)
        self.assertEqual(u["2026-11-30"]["capacity_hours"], 80)


class Warnings(unittest.TestCase):
    def test_single_high_variance_item_warning(self):
        big = opp("big", 0, 1000, 5000, 0.5, 0.1, 0.9, 1, "2026-11-01")
        small = opp("small", 0, 10, 10, 0.5, 0.5, 0.5, 1, "2026-11-01")
        out = m.run(req([big, small], hourly_value=0))
        self.assertIn("single_item_dominates:big", out["warnings"])

    def test_no_warning_when_balanced(self):
        a = opp("a", 0, 100, 100, 0.5, 0.5, 0.5, 1, "2026-11-01")
        b = opp("b", 0, 100, 100, 0.5, 0.5, 0.5, 1, "2026-11-01")
        self.assertEqual(m.run(req([a, b], hourly_value=0))["warnings"], [])

    def test_negative_ev_warning(self):
        n = opp("n", 0, 100, 100, 0.1, 0.1, 0.1, 5, "2026-11-01")
        self.assertIn("negative_ev:n", m.run(req([n]))["warnings"])


class NoEffectSurface(unittest.TestCase):
    def test_only_run_is_public(self):
        pub = [k for k, v in vars(m).items() if callable(v) and not k.startswith("_")
               and getattr(v, "__module__", None) == "c36_ev"]
        self.assertEqual(pub, ["run"])

    def test_imports_are_offline_only(self):
        tree = ast.parse(_P.read_text())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module)
        self.assertTrue(mods <= {"__future__", "datetime", "fractions", "itertools", "math",
                                 "app.modules.c30"}, mods)

    def test_no_authority_words_in_code_names(self):
        names = {n.name.lower() for n in ast.walk(ast.parse(_P.read_text()))
                 if isinstance(n, ast.FunctionDef)}
        for bad in ("send", "post", "pay", "spend", "trade", "purchase", "register", "signup",
                    "submit", "fetch", "scrape", "email"):
            self.assertFalse(any(bad in n for n in names), bad)

    def test_uses_real_policy(self):
        self.assertEqual(m.policy.__name__, "app.modules.c30.policy")
        self.assertEqual(m.policy.__file__.replace("\\", "/").split("backend/")[-1],
                         "app/modules/c30/policy.py")
        self.assertEqual(m.run(req(fixture()))["scope"]["implemented"][0].split()[0], "EV")


if __name__ == "__main__":
    unittest.main()
