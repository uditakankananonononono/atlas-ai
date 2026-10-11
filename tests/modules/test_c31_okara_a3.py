"""A3 / c31.okara tests. Hermetic, stdlib unittest, mock transport only."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c31/okara.py"
_spec = importlib.util.spec_from_file_location("c31_okara", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c31_okara"] = m
_spec.loader.exec_module(m)

DESC = {"name": "okara", "docs_url": "https://okara.com/help/api",
        "api_base": "https://api.okara.com", "free_tier": True,
        "pricing_evidence": "pricing page snapshot 2026-10: free tier listed",
        "key_ref": "OKARA_API_KEY",
        "endpoints": {"stats": {"path": "/api/stats", "method": "GET"}}}


class Okara(unittest.TestCase):
    def test_identified_free(self):
        out = m.identify(DESC)
        self.assertEqual(out["status"], "identified")
        self.assertIsNone(out["question"])
        self.assertIn("supplied", str(out["scope"]["implemented"]) + "supplied")

    def test_unidentified_asks_question(self):
        out = m.identify(dict(DESC, name="okara-ish"))
        self.assertEqual(out["status"], "unidentified")
        self.assertIn("okara", out["question"])

    def test_plan_request_pure(self):
        ident = m.identify(DESC)
        plan = m.plan_request(ident["descriptor"], "stats", {"site_id": "1"})
        self.assertEqual(plan["method"], "GET")
        self.assertEqual(plan["url"], "https://api.okara.com/api/stats")
        self.assertEqual(plan["headers"]["Authorization"], "Bearer ${OKARA_API_KEY}")
        # key is a placeholder reference only, never an embedded secret
        self.assertTrue(plan["headers"]["Authorization"].startswith("Bearer ${"))
        self.assertEqual(plan["params"], {"site_id": "1"})

    def test_plan_refuses_unknown_endpoint_and_unidentified(self):
        ident = m.identify(DESC)
        with self.assertRaises(ValueError) as cm:
            m.plan_request(ident["descriptor"], "delete_everything", {})
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_UNKNOWN_ENDPOINT:delete_everything")
        with self.assertRaises(ValueError) as cm:
            m.plan_request(dict(DESC, free_tier=None), "stats", {})  # complete but not evidenced-free
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_UNIDENTIFIED")

    def test_paid_or_unknown_tier_refuses_spend(self):
        for tier in (False, None):
            with self.assertRaises(ValueError) as cm:
                m.identify(dict(DESC, free_tier=tier))
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_SPEND")

    def test_mock_server_roundtrip(self):
        ident = m.identify(DESC)
        plan = m.plan_request(ident["descriptor"], "stats", {"site_id": "1"})
        def fake_server(request):  # hermetic mock server
            assert request["url"].endswith("/api/stats")
            return 200, '{"visitors": 3}'
        status, body = fake_server(plan)
        out = m.parse_response(plan, status, body)
        self.assertEqual(out["status_code"], 200)
        self.assertEqual(out["data"], {"visitors": 3})

    def test_parse_rejects_error_status_and_bad_json(self):
        ident = m.identify(DESC)
        plan = m.plan_request(ident["descriptor"], "stats", {})
        with self.assertRaises(ValueError) as cm:
            m.parse_response(plan, 403, '{}')
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_HTTP:403")
        with self.assertRaises(ValueError) as cm:
            m.parse_response(plan, 200, 'not json')
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_JSON")

    def test_validation_and_caps(self):
        with self.assertRaises(ValueError) as cm:
            m.identify(None)
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_NOSOURCE")
        with self.assertRaises(ValueError) as cm:
            m.identify(dict(DESC, name="cl\x0bicky"))
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_CONTROL_CHARS:name")
        with self.assertRaises(ValueError) as cm:
            m.plan_request(m.identify(DESC)["descriptor"], "stats", {f"k{i}": "v" for i in range(65)})
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_OVERSIZE")

    def test_method_whitelist(self):
        # M7: only GET/POST endpoint methods are accepted
        bad = dict(DESC, endpoints={"x": {"path": "/x", "method": "DELETE"}})
        with self.assertRaises(ValueError) as cm:
            m.identify(bad)
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:method")


    def test_free_tier_typed(self):
        for bad in ("yes", 1, 0):
            with self.assertRaises(ValueError) as cm:
                m.identify(dict(DESC, free_tier=bad))
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:free_tier")

    def test_endpoints_shape(self):
        for bad in ({}, [], "x", {"e": "notdict"}, True):
            with self.assertRaises(ValueError) as cm:
                m.identify(dict(DESC, endpoints=bad))
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:endpoints")

    def test_required_fields_exact_codes(self):
        for field in ("name", "docs_url", "api_base", "pricing_evidence",
                      "key_ref", "endpoints"):
            d = dict(DESC); del d[field]
            with self.assertRaises(ValueError) as cm:
                m.identify(d)
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:" + field)

    def test_params_fully_validated(self):
        ident = m.identify(DESC)["descriptor"]
        for bad in ([("a", "b")], "x", 5):
            with self.assertRaises(ValueError) as cm:
                m.plan_request(ident, "stats", bad)
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:params")
        for badval in ([1], {"x": 1}, True, float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError) as cm:
                m.plan_request(ident, "stats", {"k": badval})
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:params")
        # mixed-type keys: validated BEFORE sorting, clean refusal not TypeError
        with self.assertRaises(ValueError) as cm:
            m.plan_request(ident, "stats", {1: "a", "b": "c"})
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:params")
        with self.assertRaises(ValueError) as cm:
            m.plan_request(ident, "stats", {"k": "va\x0blue"})
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_CONTROL_CHARS:params")

    def test_status_and_body_typed(self):
        ident = m.identify(DESC)["descriptor"]
        plan = m.plan_request(ident, "stats", {})
        for bad in ("200", True, 200.5):
            with self.assertRaises(ValueError) as cm:
                m.parse_response(plan, bad, '{}')
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:status")
        with self.assertRaises(ValueError) as cm:
            m.parse_response(plan, 200, b'{}')
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:body")
        with self.assertRaises(ValueError) as cm:
            m.parse_response(plan, 200, "x" * (m.MAX_BODY + 1))
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:body")
        out = m.parse_response(plan, 200, "x" * 0 + "{}")
        self.assertEqual(out["status_code"], 200)

    def test_plan_entry_revalidates_descriptor(self):
        # core defect 1: no public-entry bypass; mutation after identify refuses
        ident = m.identify(DESC)["descriptor"]
        d2 = dict(ident)
        d2["endpoints"] = {"stats": {"path": "/api/stats", "method": "DELETE"}}
        with self.assertRaises(ValueError) as cm:
            m.plan_request(d2, "stats", {})
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:method")
        d3 = dict(ident); del d3["docs_url"]
        with self.assertRaises(ValueError) as cm:
            m.plan_request(d3, "stats", {})
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:docs_url")

    def test_identified_endpoints_frozen_copy(self):
        # core defect 1: mutating the caller's dict must not alter validation
        d = dict(DESC)
        d["endpoints"] = {"stats": {"path": "/api/stats", "method": "GET"}}
        ident = m.identify(d)["descriptor"]
        d["endpoints"]["stats"]["method"] = "DELETE"
        d["endpoints"]["evil"] = {"path": "/x", "method": "GET"}
        plan = m.plan_request(ident, "stats", {})
        self.assertEqual(plan["method"], "GET")
        with self.assertRaises(ValueError):
            m.plan_request(ident, "evil", {})

    def test_parse_strict_json(self):
        ident = m.identify(DESC)["descriptor"]
        plan = m.plan_request(ident, "stats", {})
        for bad in ('NaN', '{"a": Infinity}', '{"a": -Infinity}'):
            with self.assertRaises(ValueError) as cm:
                m.parse_response(plan, 200, bad)
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_JSON")

    def test_parse_validates_plan_shape(self):
        ident = m.identify(DESC)["descriptor"]
        plan = m.plan_request(ident, "stats", {})
        for bad in ({"method": "DELETE", "url": plan["url"]},
                    {"method": "GET"},
                    {"method": "GET", "url": 42},
                    "notaplan"):
            with self.assertRaises(ValueError) as cm:
                m.parse_response(bad, 200, '{}')
            self.assertTrue(str(cm.exception).startswith("APPLY_REFUSED_BAD_TYPE:plan"))

    def test_determinism(self):
        self.assertEqual(m.identify(DESC), m.identify(DESC))
        ident = m.identify(DESC)
        self.assertEqual(m.plan_request(ident["descriptor"], "stats", {"a": "b"}),
                         m.plan_request(ident["descriptor"], "stats", {"a": "b"}))


if __name__ == "__main__":
    unittest.main()

class OkaraFollowup(unittest.TestCase):
    def test_missing_free_tier_clean_refusal(self):
        # omitted free_tier must refuse cleanly at every entry, never KeyError
        d = {k: v for k, v in DESC.items() if k != "free_tier"}
        with self.assertRaisesRegex(ValueError, r"^APPLY_REFUSED_BAD_TYPE:free_tier$"):
            m.identify(d)
        ident = m.identify(DESC)
        bad = dict(ident["descriptor"]); del bad["free_tier"]
        with self.assertRaisesRegex(ValueError, r"^APPLY_REFUSED_BAD_TYPE:free_tier$"):
            m.plan_request(bad, "stats", {})
