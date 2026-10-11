"""S5.1 / c36.blueprint tests. Hermetic, stdlib unittest, no network."""
import importlib.util, json, pathlib, re, sys, unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
_P = _ROOT / "backend/app/modules/c36/blueprint.py"
_spec = importlib.util.spec_from_file_location("c36_blueprint", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c36_blueprint"] = m
_spec.loader.exec_module(m)

ALL_ROLES = ["researcher", "analyst", "writer", "critic", "auditor", "builder"]


def niche(i, **kw):
    d = {"id": "n%03d" % i, "name": "Niche %d" % i, "audience": "folks %d" % i,
         "problem": "problem %d" % i, "price_points": [19, 49.5], "currency": "USD",
         "regulated_flags": [], "channels": ["email"], "worker_roles": ["researcher", "writer", "critic"]}
    d.update(kw)
    return d


def req(niches, as_of="2026-10-11"):
    return {"as_of": as_of, "niches": niches}


def fixture30():
    ns = [niche(i) for i in range(30)]
    for i in (3, 7, 11, 19, 23):
        ns[i]["regulated_flags"] = ["health"]
    ns[5]["price_points"] = []
    ns[5]["currency"] = None
    return ns


def refusal(test, request):
    with test.assertRaises(ValueError) as cm:
        m.run(request)
    return str(cm.exception)


class Fixture(unittest.TestCase):
    def test_counts_and_sort(self):
        ns = fixture30()
        ns.reverse()
        out = m.run(req(ns))
        self.assertEqual(out["coverage"], {"niches_supplied": 30, "blueprints_built": 25, "regulated_review_count": 5})
        ids = [b["id"] for b in out["blueprints"]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), 25)
        self.assertEqual([r["id"] for r in out["regulated_review"]], ["n003", "n007", "n011", "n019", "n023"])
        for r in out["regulated_review"]:
            self.assertEqual(r["status"], "regulated_review_needed")
            self.assertEqual(set(r), {"id", "status"})
        self.assertEqual(set(out), {"blueprints", "regulated_review", "coverage", "scope"})
        self.assertEqual(out["scope"]["as_of"], "2026-10-11")
        self.assertTrue(out["scope"]["implemented"] and out["scope"]["not_implemented"])

    def test_determinism(self):
        a = json.dumps(m.run(req(fixture30())), sort_keys=True)
        b = json.dumps(m.run(req(fixture30())), sort_keys=True)
        self.assertEqual(a, b)

    def test_offer_template(self):
        out = m.run(req([niche(1, name="Pet Bakery", problem="no safe treats", audience="dog owners")]))
        self.assertEqual(out["blueprints"][0]["offer"], "Pet Bakery: no safe treats for dog owners")

    def test_pricing_passthrough_and_missing(self):
        out = m.run(req(fixture30()))
        by = {b["id"]: b for b in out["blueprints"]}
        self.assertEqual(by["n000"]["pricing"], {"status": "priced", "price_points": [19, 49.5], "currency": "USD"})
        self.assertEqual(by["n005"]["pricing"], {"status": "pricing_missing"})
        r = m.run(req([niche(1, price_points=[1.23456789], currency=None)]))
        self.assertEqual(r["blueprints"][0]["pricing"]["price_points"], [1.234568])
        self.assertIsNone(r["blueprints"][0]["pricing"]["currency"])

    def test_edges_only_when_both_supplied(self):
        def g(roles):
            return m.run(req([niche(1, worker_roles=roles)]))["blueprints"][0]["worker_graph"]
        full = g(ALL_ROLES)
        self.assertEqual(full["edges"], sorted([
            {"from": "analyst", "to": "writer"}, {"from": "builder", "to": "critic"},
            {"from": "critic", "to": "auditor"}, {"from": "researcher", "to": "analyst"},
            {"from": "writer", "to": "critic"}], key=lambda e: (e["from"], e["to"])))
        part = g(["researcher", "writer", "critic"])
        self.assertEqual(part["edges"], [{"from": "writer", "to": "critic"}])
        self.assertEqual(part["isolated"], ["researcher"])
        self.assertEqual(g(["researcher", "analyst"])["edges"], [{"from": "researcher", "to": "analyst"}])
        self.assertEqual(g(["analyst", "researcher"])["edges"], [{"from": "researcher", "to": "analyst"}])
        self.assertEqual(g(["critic", "writer"])["edges"], [{"from": "writer", "to": "critic"}])
        self.assertEqual(g(["critic", "builder"])["edges"], [{"from": "builder", "to": "critic"}])
        self.assertEqual(g(["auditor", "critic"])["edges"], [{"from": "critic", "to": "auditor"}])
        # no transitive edge when the middle role is missing
        self.assertEqual(g(["researcher", "writer"])["edges"], [])
        unk = g(["wizard", "writer", "writer"])
        self.assertEqual(unk["nodes"], ["wizard", "writer"])
        self.assertEqual(unk["isolated"], ["wizard", "writer"])
        self.assertEqual(g([])["nodes"], [])

    def test_kpis_null_targets(self):
        k = m.run(req([niche(1)]))["blueprints"][0]["kpis"]
        self.assertEqual([x["name"] for x in k], ["visitors", "trial_starts", "purchases", "retention_rate"])
        for x in k:
            self.assertEqual(set(x), {"name", "target"})
            self.assertIsNone(x["target"])

    def test_scaffold(self):
        sc = m.run(req([niche(1)]))["blueprints"][0]["scaffold"]
        self.assertEqual(sorted(sc), ["README.md", "kpis.csv", "plan.md"])
        self.assertEqual(sc["kpis.csv"], "kpi,target\n")
        self.assertTrue(all(isinstance(v, str) and v for v in sc.values()))
        blob = json.dumps(sc).lower()
        for bad in ("http", "import ", "requests", "urllib", "socket", "fetch(", "curl"):
            self.assertNotIn(bad, blob)

    def test_no_forbidden_output_fields(self):
        b = m.run(req([niche(1)]))["blueprints"][0]
        self.assertEqual(set(b), {"id", "offer", "pricing", "worker_graph", "kpis", "scaffold"})
        self.assertNotIn("funnel", json.dumps(b).lower())

    def test_input_not_mutated(self):
        r = req(fixture30())
        before = json.dumps(r, sort_keys=True)
        m.run(r)
        self.assertEqual(json.dumps(r, sort_keys=True), before)


class Refusals(unittest.TestCase):
    def test_all_regulated(self):
        self.assertEqual(refusal(self, req([niche(1, regulated_flags=["x"]), niche(2, regulated_flags=["y"])])),
                         "VENT_REFUSED_REGULATED:niches")

    def test_duplicate_ids(self):
        self.assertEqual(refusal(self, req([niche(1), niche(1)])), "VENT_REFUSED_BAD_TYPE:niches")

    def test_effect_key(self):
        for k in ("register", "register_company", "incorporate", "launch", "deploy"):
            n = niche(1)
            n[k] = True
            self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_EFFECT:" + k)
        self.assertEqual(refusal(self, {"as_of": "2026-10-11", "niches": [niche(1)], "Launch": 1}),
                         "VENT_REFUSED_EFFECT:launch")

    def test_send_key(self):
        n = niche(1)
        n["token"] = "x"
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_SEND:token")
        self.assertEqual(refusal(self, {"as_of": "2026-10-11", "niches": [niche(1)], "approval-token": "x"}),
                         "VENT_REFUSED_SEND:approval_token")

    def test_spend_and_nocreds(self):
        n = niche(1); n["checkout"] = 1
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_SPEND:checkout")
        n = niche(1); n["password"] = "p"
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_NOCREDS:password")

    def test_precedence(self):
        n = niche(1)
        n.update({"password": 1, "launch": 1, "buy": 1, "send": 1})
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_SEND:send")
        n = niche(1); n.update({"password": 1, "launch": 1, "buy": 1})
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_SPEND:buy")
        n = niche(1); n.update({"password": 1, "launch": 1})
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_EFFECT:launch")
        n = niche(1); n.update({"zeta": 1, "approve": 1, "approval": 1})
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_SEND:approval")  # alphabetically first

    def test_key_scan_is_recursive_and_before_unknown(self):
        n = niche(1)
        n["channels"] = [{"deep": {"send": 1}}]
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_SEND:send")
        n = niche(1); n["bogus"] = 1; n["pay"] = 1
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_SPEND:pay")
        # exact match, no substrings
        n = niche(1); n["payload_note"] = 1
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_UNKNOWN:niches")

    def test_bad_type_request_and_key(self):
        for bad in (None, [], "x", 3):
            self.assertEqual(refusal(self, bad), "VENT_REFUSED_BAD_TYPE:request")
        self.assertEqual(refusal(self, {1: 2}), "VENT_REFUSED_BAD_TYPE:key")
        n = niche(1); n[5] = 1
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_BAD_TYPE:key")

    def test_unknown_keys(self):
        self.assertEqual(refusal(self, {"as_of": "2026-10-11", "niches": [niche(1)], "extra": 1}),
                         "VENT_REFUSED_UNKNOWN:request")
        n = niche(1); n["extra"] = 1
        self.assertEqual(refusal(self, req([n])), "VENT_REFUSED_UNKNOWN:niches")

    def test_top_level_types(self):
        for as_of in ("2026-13-40", "10/11/2026", 5, None, "2026-10-1"):
            self.assertEqual(refusal(self, req([niche(1)], as_of=as_of)), "VENT_REFUSED_BAD_TYPE:as_of")
        self.assertEqual(refusal(self, {"as_of": "2026-10-11", "niches": "x"}), "VENT_REFUSED_BAD_TYPE:niches")
        self.assertEqual(refusal(self, req([])), "VENT_REFUSED_EMPTY:niches")
        self.assertEqual(refusal(self, {"niches": [niche(1)]}), "VENT_REFUSED_BAD_TYPE:as_of")
        self.assertEqual(refusal(self, {"as_of": "2026-10-11"}), "VENT_REFUSED_BAD_TYPE:niches")

    def test_caps_before_clean_text(self):
        self.assertEqual(refusal(self, req([niche(i) for i in range(2001)])), "VENT_REFUSED_OVERSIZE:niches")
        for f in ("id", "name", "audience", "problem"):
            self.assertEqual(refusal(self, req([niche(1, **{f: "a" * 201})])), "VENT_REFUSED_OVERSIZE:" + f)
            m.run(req([niche(1, **{f: "a" * 200})]))
        self.assertEqual(refusal(self, req([niche(1, price_points=[1] * 21)])), "VENT_REFUSED_OVERSIZE:price_points")
        self.assertEqual(refusal(self, req([niche(1, channels=["c"] * 21)])), "VENT_REFUSED_OVERSIZE:channels")
        self.assertEqual(refusal(self, req([niche(1, worker_roles=["r"] * 13)])), "VENT_REFUSED_OVERSIZE:worker_roles")
        self.assertEqual(refusal(self, req([niche(1, regulated_flags=["f"] * 11)])), "VENT_REFUSED_OVERSIZE:regulated_flags")
        self.assertEqual(refusal(self, req([niche(1, regulated_flags=["f" * 51])])), "VENT_REFUSED_OVERSIZE:regulated_flags")
        # oversize wins over a bad control char in the same field
        self.assertEqual(refusal(self, req([niche(1, name="\x00" + "a" * 201)])), "VENT_REFUSED_OVERSIZE:name")
        # cap exactly at limits passes
        m.run(req([{k:v for k,v in niche(i).items() if k not in ("channels","worker_roles","regulated_flags")} for i in range(2000)]))
        m.run(req([niche(1, price_points=[1] * 20, channels=["c"] * 20, worker_roles=["r"] * 12),
                   niche(2, regulated_flags=["f" * 50] * 10)]))

    def test_text_too_long_never_surfaces(self):
        for payload in ("a" * 201, "a" * 5000):
            for f in ("id", "name", "audience", "problem"):
                self.assertNotIn("TEXT_TOO_LONG", refusal(self, req([niche(1, **{f: payload})])))

    def test_field_validation(self):
        cases = [
            (dict(id=""), "VENT_REFUSED_EMPTY:id"), (dict(name="  "), "VENT_REFUSED_EMPTY:name"),
            (dict(id=5), "VENT_REFUSED_BAD_TYPE:id"), (dict(audience=None), "VENT_REFUSED_BAD_TYPE:audience"),
            (dict(problem="a\x00b"), "VENT_REFUSED_CONTROL_CHARS:problem"),
            (dict(price_points="19"), "VENT_REFUSED_BAD_TYPE:price_points"),
            (dict(price_points=[0]), "VENT_REFUSED_BAD_TYPE:price_points"),
            (dict(price_points=[-1]), "VENT_REFUSED_BAD_TYPE:price_points"),
            (dict(price_points=[True]), "VENT_REFUSED_BAD_TYPE:price_points"),
            (dict(price_points=[float("nan")]), "VENT_REFUSED_BAD_TYPE:price_points"),
            (dict(price_points=[float("inf")]), "VENT_REFUSED_BAD_TYPE:price_points"),
            (dict(price_points=["5"]), "VENT_REFUSED_BAD_TYPE:price_points"),
            (dict(currency="usd"), "VENT_REFUSED_BAD_TYPE:currency"),
            (dict(currency="US"), "VENT_REFUSED_BAD_TYPE:currency"),
            (dict(currency=5), "VENT_REFUSED_BAD_TYPE:currency"),
            (dict(currency=5, price_points=[]), "VENT_REFUSED_BAD_TYPE:currency"),
            (dict(currency=["USD"], price_points=[]), "VENT_REFUSED_BAD_TYPE:currency"),
            (dict(regulated_flags=[""]), "VENT_REFUSED_EMPTY:regulated_flags"),
            (dict(regulated_flags=["  "]), "VENT_REFUSED_EMPTY:regulated_flags"),
            (dict(channels="email"), "VENT_REFUSED_BAD_TYPE:channels"),
            (dict(channels=[""]), "VENT_REFUSED_EMPTY:channels"),
            (dict(channels=[3]), "VENT_REFUSED_BAD_TYPE:channels"),
            (dict(worker_roles=" "), "VENT_REFUSED_BAD_TYPE:worker_roles"),
            (dict(worker_roles=["  "]), "VENT_REFUSED_EMPTY:worker_roles"),
            (dict(regulated_flags="x"), "VENT_REFUSED_BAD_TYPE:regulated_flags"),
            (dict(regulated_flags=[3]), "VENT_REFUSED_BAD_TYPE:regulated_flags"),
        ]
        for kw, want in cases:
            self.assertEqual(refusal(self, req([niche(1, **kw)])), want, kw)
        self.assertEqual(refusal(self, req(["x"])), "VENT_REFUSED_BAD_TYPE:niches")

    def test_as_of_ascii_fullmatch_and_calendar(self):
        for bad in ("2026-10-11\n", " 2026-10-11", "2026-10-11 ", "\u0662\u0660\u0662\u0666-\u0661\u0660-\u0661\u0661",
                    "2026-1-1", "2026-02-30", "20261011", "2026-13-01", "2026-00-10", "2026-10-11\r\n", ""):
            self.assertEqual(refusal(self, req([niche(1)], as_of=bad)), ("VENT_REFUSED_OVERSIZE:as_of" if len(bad)>10 else "VENT_REFUSED_BAD_TYPE:as_of"), repr(bad))
        out = m.run(req([niche(1)], as_of="2026-10-11"))
        self.assertEqual(out["scope"]["as_of"], "2026-10-11")
        self.assertEqual(m.run(req([niche(1)], as_of="2028-02-29"))["scope"]["as_of"], "2028-02-29")
        self.assertEqual(refusal(self, req([niche(1)], as_of="2027-02-29")), "VENT_REFUSED_BAD_TYPE:as_of")

    def test_currency_format_ascii_fullmatch(self):
        for bad in ("USD\n", " USD", "USD ", "U SD", "usd", "US", "USDD", "\u00dcSD", "\uff35\uff33\uff24", "USD\r\n", "USD\x00", ""):
            self.assertEqual(refusal(self, req([niche(1, currency=bad)])), ("VENT_REFUSED_OVERSIZE:currency" if len(bad)>3 else "VENT_REFUSED_BAD_TYPE:currency"), repr(bad))
        self.assertEqual(m.run(req([niche(1, currency="USD")]))["blueprints"][0]["pricing"]["currency"], "USD")
        for bad in ("\u00dcSD", "usd"):
            out = m.run(req([niche(1, price_points=[], currency=bad)]))
            self.assertEqual(out["blueprints"][0]["pricing"], {"status": "pricing_missing"})
            self.assertNotIn(bad.strip(), json.dumps(out))

    def test_plan_md_exact(self):
        def plan(roles):
            return m.run(req([niche(1, worker_roles=roles)]))["blueprints"][0]["scaffold"]["plan.md"]
        self.assertEqual(plan(["researcher", "writer", "critic"]),
                         "# Plan\n\nWorker roles: critic, researcher, writer\n\nEdges:\n- writer -> critic\n")
        self.assertEqual(plan(ALL_ROLES),
                         "# Plan\n\nWorker roles: analyst, auditor, builder, critic, researcher, writer\n\nEdges:\n"
                         "- analyst -> writer\n- builder -> critic\n- critic -> auditor\n- researcher -> analyst\n- writer -> critic\n")
        self.assertEqual(plan(["researcher", "writer"]),
                         "# Plan\n\nWorker roles: researcher, writer\n\nEdges:\n- none\n")
        self.assertEqual(plan([]), "# Plan\n\nWorker roles: none supplied\n\nEdges:\n- none\n")
        self.assertEqual(plan(["wizard"]), "# Plan\n\nWorker roles: wizard\n\nEdges:\n- none\n")

    def test_readme_exact(self):
        sc = m.run(req([niche(1, name="Pet Bakery", problem="no safe treats", audience="dog owners")]))["blueprints"][0]["scaffold"]
        self.assertEqual(sc["README.md"], "# Pet Bakery\n\nPet Bakery: no safe treats for dog owners\n")

    def test_bad_format_currency_ignored_when_no_prices(self):
        b = m.run(req([niche(1, price_points=[], currency="usd")]))
        self.assertEqual(b["blueprints"][0]["pricing"], {"status": "pricing_missing"})
        self.assertNotIn("usd", json.dumps(b))
        b = m.run(req([niche(1, price_points=[5], currency=None)]))
        self.assertEqual(b["blueprints"][0]["pricing"], {"status": "priced", "price_points": [5], "currency": None})

    def test_position_independent_scan(self):
        a = niche(1); a["send"] = 1
        b = niche(2); b["pay"] = 1
        for order in ([a, b], [b, a]):
            self.assertEqual(refusal(self, req(order)), "VENT_REFUSED_SEND:send")
        top = {"launch": 1, "as_of": "2026-10-11", "niches": [niche(1, **{"approve": 1})]}
        self.assertEqual(refusal(self, top), "VENT_REFUSED_SEND:approve")

    def test_roles_case_sensitive_no_trim(self):
        g = m.run(req([niche(1, worker_roles=["Writer", "critic", " writer"])]))["blueprints"][0]["worker_graph"]
        self.assertEqual(g["edges"], [])
        self.assertEqual(g["isolated"], g["nodes"])

    def test_optional_fields_default(self):
        n = {"id": "a", "name": "n", "audience": "u", "problem": "p"}
        b = m.run(req([n]))["blueprints"][0]
        self.assertEqual(b["pricing"], {"status": "pricing_missing"})
        self.assertEqual(b["worker_graph"], {"nodes": [], "edges": [], "isolated": []})

    def test_reasons_never_echo_input(self):
        n = niche(1); n["SECRET_KEY_TEXT"] = "v"
        msg = refusal(self, req([n]))
        self.assertNotIn("SECRET", msg.upper())
        self.assertEqual(msg, "VENT_REFUSED_UNKNOWN:niches")
        n = niche(1, id="abc\x00def")
        self.assertNotIn("abc", refusal(self, req([n])))


class Surface(unittest.TestCase):
    def test_no_effect_functions(self):
        names = [n for n in dir(m) if callable(getattr(m, n)) and not n.startswith("_")
                 and getattr(getattr(m, n), "__module__", None) == "c36_blueprint"]
        self.assertEqual(names, ["run"])
        for n in names + [x for x in dir(m) if callable(getattr(m, x))]:
            for w in ("send", "spend", "pay", "post", "publish", "file", "register", "launch", "deploy"):
                self.assertFalse(n.lower().startswith(w), n)

    def test_source_is_offline_and_no_policy_check(self):
        src = _P.read_text()
        self.assertNotRegex(src, r"(?m)^\s*(import|from)\s+(httpx|urllib|requests|socket|aiohttp|subprocess)")
        self.assertNotIn("policy.check", src)
        self.assertNotIn("m05", src)
        self.assertNotIn("m08", src)
        self.assertNotIn("m18", src)
        self.assertIn("policy.clean_text", src)
        self.assertIn("policy.scope", src)
        self.assertEqual((_P.parent / "__init__.py").read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
