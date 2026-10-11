"""c30.policy shared guard tests. Hermetic, stdlib unittest."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c30/policy.py"
_spec = importlib.util.spec_from_file_location("c30_policy", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c30_policy"] = m
_spec.loader.exec_module(m)


class Guard(unittest.TestCase):
    def test_six_standing_refusals(self):
        for action, reason in (("spend", "SPEND"), ("outreach", "OUTREACH"),
                               ("fakeacct", "FAKEACCT"), ("autopost", "AUTOPOST"),
                               ("scrape", "SCRAPE"), ("trade", "TRADE")):
            with self.assertRaises(ValueError) as cm:
                m.check(action, "TREND")
            self.assertEqual(str(cm.exception), "TREND_REFUSED_" + reason)

    def test_unit_prefix_carried(self):
        with self.assertRaises(ValueError) as cm:
            m.check("scrape", "SOCIAL")
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_SCRAPE")

    def test_unknown_action_refused_fail_closed(self):
        # canonical ruling: unknown actions refuse, never pass-with-docs
        with self.assertRaises(ValueError) as cm:
            m.check("read-supplied-data", "TREND")
        self.assertEqual(str(cm.exception), "TREND_REFUSED_UNKNOWN:read-supplied-data")
        with self.assertRaises(ValueError) as cm:
            m.check("", "SOCIAL")
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_UNKNOWN:")

    def test_prefix_is_per_unit(self):
        # canonical ruling: each family's refusal carries its own prefix
        with self.assertRaises(ValueError) as cm:
            m.check("fakeacct", "SOCIAL")
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_FAKEACCT")

    def test_clean_text(self):
        self.assertEqual(m.clean_text("ok", "TREND", "f", 8), "ok")
        for bad in (True, 1, None, []):
            with self.assertRaises(ValueError) as cm:
                m.clean_text(bad, "TREND", "f", 8)
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:f")
        with self.assertRaises(ValueError) as cm:
            m.clean_text("  ", "TREND", "f", 8)
        self.assertEqual(str(cm.exception), "TREND_REFUSED_EMPTY:f")
        for ch in ("\n", "\t", "\x00", "\u2028", "\u2029"):
            with self.assertRaises(ValueError) as cm:
                m.clean_text("a" + ch, "TREND", "f", 8)
            self.assertEqual(str(cm.exception), "TREND_REFUSED_CONTROL_CHARS:f")
        self.assertEqual(m.clean_text("a" * 8, "TREND", "f", 8), "a" * 8)
        with self.assertRaises(ValueError) as cm:
            m.clean_text("a" * 9, "TREND", "f", 8)
        self.assertEqual(str(cm.exception), "TREND_REFUSED_TEXT_TOO_LONG:f")

    def test_one_account_per_platform_enforced(self):
        # canonical ruling: enforced check, not prose, in account-creation paths
        first = m.check_account("instagram", [], "SOCIAL")
        self.assertEqual(first, {"platform": "instagram", "official": True})
        with self.assertRaises(ValueError) as cm:
            m.check_account("instagram", [{"platform": "instagram", "official": True}], "SOCIAL")
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_FAKEACCT")
        # a different platform is fine
        m.check_account("linkedin", [{"platform": "instagram", "official": True}], "SOCIAL")
        with self.assertRaises(ValueError) as cm:
            m.check_account("instagram", [{"platform": "instagram", "official": False}], "SOCIAL")
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_FAKEACCT")  # fake alt counts
        with self.assertRaises(ValueError) as cm:
            m.check_account("insta\ngram", [], "SOCIAL")
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_CONTROL_CHARS:platform")

    def test_check_account_registry_type_pins(self):
        # auditor survivors policy-2/8/9: registry type + row-dict refusals
        for bad in (True, {"a": 1}, "x", 5, 3.2):
            with self.assertRaises(ValueError) as cm:
                m.check_account("p", bad, "SOCIAL")
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:existing")
        for rows in (["x"], [5], [{"platform": "p"}, "x"]):
            with self.assertRaises(ValueError) as cm:
                m.check_account("q", rows, "SOCIAL")
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:account")
        # valid list passes; boundary: empty
        self.assertEqual(m.check_account("p", [], "SOCIAL"),
                         {"platform": "p", "official": True})

    def test_descriptor_validation(self):
        good = {"class": "offline", "module_id": 24, "tenant_id": "u1",
                "action_type": "analyze", "payload": {"k": 1}}
        m.validate_descriptor(good)  # passes
        for bad in (None, True, "x", [], 5):
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor(bad)
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:keys")
        for keys in ({"class", "module_id", "tenant_id", "action_type"},
                     {"class", "module_id", "tenant_id", "action_type", "payload", "extra"}):
            d = dict(good); d["extra"] = 1
            d = {k: good.get(k, 1) for k in keys}
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor(d)
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:keys")
        for bad in (True, "x", 0, -1, 2.5):
            d = dict(good, module_id=bad)
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor(d)
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:module_id")
        for bad in ("", "  ", "a\nb", 5, None):
            d = dict(good, tenant_id=bad)
            with self.assertRaises(ValueError):
                m.validate_descriptor(d)
        for bad in ("", "  ", "a" * 101, 5, None, True):
            d = dict(good, action_type=bad)
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor(d)
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:action_type")
        for bad in ("x", 5, None, [1], float("nan")):
            d = dict(good, payload=bad)
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor(d)
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:payload")
        d = dict(good, payload={"n": float("nan")})
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(d)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:payload")
        d = dict(good, **{"class": "teleport"})
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(d)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_UNKNOWN:teleport")

    def test_descriptor_hash_non_ascii_m00_parity(self):
        # non-ASCII descriptor: exact m00 _request_hash parity (ensure_ascii=False)
        import hashlib, json
        from app.modules.m00_approval_center.service import _request_hash
        d = m.bind_spend(tenant_id="u1", module_id=24, merchant="Café Münchën ☕",
                         item="donnée €", amount=5, currency="EUR", quantity=1,
                         fees=0, undo_terms="rückgängig", effect_id="e-ü")
        expected = _request_hash(module_id=24, action_type="spend",
                                 payload=d["payload"], user_id="u1")
        self.assertEqual(m.descriptor_hash(d), expected)
        # and the parity is byte-exact UTF-8 of the canonical non-ASCII JSON
        body = {"module_id": 24, "action_type": "spend", "payload": d["payload"],
                "user_id": "u1"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
        self.assertIn("café" if False else "Café", canonical)  # not \u escaped
        self.assertEqual(hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                         expected)

    def test_bind_outreach_dict_recipients_refused(self):
        # M5: dict recipients must refuse, never be coerced into a list
        for bad in ({"a@x.test": 1}, {"k": "v"}):
            with self.assertRaises(ValueError) as cm:
                m.bind_outreach(tenant_id="u1", module_id=24, sender="s@x.test",
                                channel="email", send_at="2026-10-12T09:00:00Z",
                                to=bad, cc=[], bcc=[], subject="hi", body="body")
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:to")

    def test_bind_outreach_bcc_invalid_types_refused(self):
        # BCC mirrors the pinned TO path: dict/bool/string refuse, never coerce
        base = dict(tenant_id="u1", module_id=24, sender="s@x.test",
                    channel="email", send_at="2026-10-12T09:00:00Z",
                    to=["a@x.test"], cc=[], subject="hi", body="body")
        for bad in ({"b@x.test": 1}, {"k": "v"}, True, "b@x.test"):
            with self.assertRaises(ValueError) as cm:
                m.bind_outreach(**dict(base, bcc=bad))
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:bcc")

    def test_class_action_compatibility(self):
        # auditor repro: hard class relabeled as gated must be impossible
        d = {"class": "spend", "module_id": 24, "tenant_id": "u1",
             "action_type": "trade", "payload": {"effect_id": "e"}}
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(d)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:action_type")
        # execute never reaches consume with a mismatched descriptor
        calls = []
        with self.assertRaises(ValueError) as cm:
            m.execute(d, "appr-1", actor="her", consume=lambda **kw: calls.append(kw))
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:action_type")
        self.assertEqual(calls, [])
        for cls, at in (("spend", "analyze"), ("outreach", "spend"), ("spend", "outreach")):
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor({"class": cls, "module_id": 24, "tenant_id": "u1",
                                       "action_type": at, "payload": {}})
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:action_type")
        # hard classes validate with any action string and still refuse at classify
        out = m.classify({"class": "trade", "module_id": 24, "tenant_id": "u1",
                          "action_type": "spend", "payload": {}})
        self.assertEqual(out["code"], "POLICY_REFUSED_TRADE")

    def test_spend_payload_schema_at_validate(self):
        # directly-constructed descriptors face the same schema as bind_spend
        base = m.bind_spend(tenant_id="u1", module_id=24, merchant="Acme", item="d",
                            amount=5, currency="USD", quantity=1, fees=0,
                            undo_terms="r", effect_id="e1")
        m.validate_descriptor(base)  # passes
        for mutate in (lambda p: p.pop("merchant"), lambda p: p.pop("effect_id"),
                       lambda p: p.update(extra=1)):
            d = dict(base, payload=dict(base["payload"]))
            mutate(d["payload"])
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor(d)
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:payload")
        d = dict(base, payload=dict(base["payload"], amount=0))
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(d)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:amount")
        d = dict(base, payload=dict(base["payload"], quantity=1.5))
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(d)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:quantity")
        d = dict(base, payload=dict(base["payload"], currency="US"))
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(d)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:currency")

    def test_outreach_payload_schema_at_validate(self):
        base = m.bind_outreach(tenant_id="u1", module_id=24, sender="h@x", channel="email",
                               send_at="t", to=["a@x"], cc=[], bcc=[], subject="s", body="b")
        m.validate_descriptor(base)
        d = dict(base, payload=dict(base["payload"]))
        del d["payload"]["body_sha256"]
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(d)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:payload")
        d = dict(base, payload=dict(base["payload"], body_sha256="0" * 64))
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(d)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:body_sha256")
        d = dict(base, payload=dict(base["payload"], extra=1))
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(d)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:payload")

    def test_payload_key_integrity(self):
        # m00 parity: no JSON key coercion anywhere in the payload tree
        for bad in ({1: "x"}, {"a": {2: "x"}}, {"a": [{3: "x"}]}, {"a": [["ok"], {4: 1}]}):
            d = {"class": "offline", "module_id": 24, "tenant_id": "u1",
                 "action_type": "analyze", "payload": bad}
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor(d)
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:payload")
        # string keys pass, and payload_hash cannot collide across coerced shapes
        m.validate_descriptor({"class": "offline", "module_id": 24, "tenant_id": "u1",
                               "action_type": "analyze", "payload": {"1": "x"}})

    def test_message_text_policy(self):
        # ordinary message bytes are valid: LF, CRLF, tab; empty subject valid
        d = m.bind_outreach(tenant_id="u1", module_id=24, sender="h@x", channel="sms",
                            send_at="t", to=["a@x"], cc=[], bcc=[], subject="",
                            body="line1\nline2\r\nline3\ttabbed")
        import hashlib
        self.assertEqual(d["payload"]["body_sha256"],
                         hashlib.sha256("line1\nline2\r\nline3\ttabbed".encode("utf-8")).hexdigest())
        m.validate_descriptor(d)  # schema validation accepts the same bytes
        for bad in ("a\x00b", "a\u2028b", "a\x07b", "a\u2029b"):
            with self.assertRaises(ValueError) as cm:
                m.bind_outreach(tenant_id="u1", module_id=24, sender="h@x", channel="sms",
                                send_at="t", to=["a@x"], cc=[], bcc=[], subject="s", body=bad)
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_CONTROL_CHARS:body")
        with self.assertRaises(ValueError) as cm:
            m.bind_outreach(tenant_id="u1", module_id=24, sender="h@x", channel="sms",
                            send_at="t", to=["a@x"], cc=[], bcc=[], subject="s", body="  ")
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_EMPTY:body")

    def test_payload_hash_nonascii_canonical(self):
        # ensure_ascii=False parity with m00 canonical bytes
        import hashlib, json
        expected = hashlib.sha256(json.dumps({"k": "caf\u00e9"}, sort_keys=True,
                                             separators=(",", ":"), ensure_ascii=False,
                                             allow_nan=False).encode()).hexdigest()
        self.assertEqual(m.payload_hash({"k": "caf\u00e9"}), expected)

    def test_outreach_schema_to_nonempty(self):
        # schema path (not only bind_*) refuses an empty to list
        d = m.bind_outreach(tenant_id="u1", module_id=24, sender="h@x", channel="sms",
                            send_at="t", to=["a@x"], cc=[], bcc=[], subject="s", body="b")
        d["payload"]["to"] = []
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(d)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_EMPTY:to")

    def test_descriptor_hash_matches_m00_formula(self):
        import hashlib, json
        d = m.bind_spend(tenant_id="u1", module_id=24, merchant="Acme", item="d",
                         amount=5, currency="USD", quantity=1, fees=0,
                         undo_terms="r", effect_id="e1")
        body = {"module_id": 24, "action_type": "spend", "payload": d["payload"],
                "user_id": "u1"}
        expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"),
                                             ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        self.assertEqual(m.descriptor_hash(d), expected)

    def test_module_id_registered_source(self):
        d = m.bind_spend(tenant_id="u1", module_id=24, merchant="Acme", item="d",
                         amount=5, currency="USD", quantity=1, fees=0,
                         undo_terms="r", effect_id="e1")
        m.validate_descriptor(d)  # registered module passes
        for bad in (999, 26, 1000000):
            dd = dict(d, module_id=bad)
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor(dd)
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:module_id")

    def test_classify_decisions(self):
        base = {"module_id": 24, "tenant_id": "u1", "payload": {}}
        for at in ("analyze", "draft", "plan", "record", "read"):
            out = m.classify(dict(base, **{"class": "offline"}, action_type=at))
            self.assertEqual(out, {"decision": "allow", "code": None, "approval_id": None})
        out = m.classify(dict(base, **{"class": "offline"}, action_type="delete_prod"))
        self.assertEqual(out["decision"], "refuse")
        self.assertEqual(out["code"], "POLICY_REFUSED_UNKNOWN:delete_prod")
        for cls in ("fakeacct", "autopost", "trade", "scrape"):
            out = m.classify(dict(base, **{"class": cls}, action_type="x"))
            self.assertEqual(out["decision"], "refuse")
            self.assertEqual(out["code"], "POLICY_REFUSED_" + cls.upper())
            self.assertIsNone(out["approval_id"])
        spend = m.bind_spend(tenant_id="u1", module_id=24, merchant="Acme", item="d",
                             amount=5, currency="USD", quantity=1, fees=0,
                             undo_terms="r", effect_id="e1")
        out = m.classify(spend)
        self.assertEqual(out, {"decision": "needs_approval", "code": None,
                               "approval_id": None})
        outreach = m.bind_outreach(tenant_id="u1", module_id=24, sender="h@x",
                                   channel="email", send_at="t", to=["a@x"], cc=[],
                                   bcc=[], subject="s", body="b")
        out = m.classify(outreach)
        self.assertEqual(out, {"decision": "needs_approval", "code": None,
                               "approval_id": None})
        # side-effect-free + deterministic: no service argument exists, same in = same out
        self.assertEqual(m.classify(spend), m.classify(dict(spend, payload=dict(spend["payload"]))))

    def test_payload_hash_key_integrity(self):
        # auditor: payload_hash({1:'x'}) must refuse, not collide with {'1':'x'}
        for bad in ({1: "x"}, {"a": {2: "x"}}, {"n": float("nan")}):
            with self.assertRaises(ValueError):
                m.payload_hash(bad)

    def test_outreach_attachment_dict_refused(self):
        # auditor: dict after list coercion must not pass as hashes
        for bad in ({"a" * 64: 1}, "a" * 64, 5, True):
            with self.assertRaises(ValueError) as cm:
                m.bind_outreach(tenant_id="u1", module_id=24, sender="h@x", channel="sms",
                                send_at="t", to=["a@x"], cc=[], bcc=[], subject="s",
                                body="b", attachment_hashes=bad)
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:attachment_hashes")
        d = m.bind_outreach(tenant_id="u1", module_id=24, sender="h@x", channel="sms",
                            send_at="t", to=["a@x"], cc=[], bcc=[], subject="s", body="b")
        d["payload"]["attachment_hashes"] = {"a" * 64: 1}
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(d)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:attachment_hashes")

    def test_subject_single_line_policy(self):
        # decided policy: subjects are single-line (no LF/CR/TAB); blank is valid
        for bad in ("a\nb", "a\rb", "a\tb", "a\x00b", "a\u2028b"):
            with self.assertRaises(ValueError) as cm:
                m.bind_outreach(tenant_id="u1", module_id=24, sender="h@x", channel="sms",
                                send_at="t", to=["a@x"], cc=[], bcc=[], subject=bad, body="b")
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_CONTROL_CHARS:subject")

    def test_outreach_direct_schema_field_hygiene(self):
        # direct descriptors face binder-identical hygiene on every field
        d = m.bind_outreach(tenant_id="u1", module_id=24, sender="h@x", channel="sms",
                            send_at="t", to=["a@x"], cc=[], bcc=[], subject="s", body="b")
        for field, bad, code in (
                ("sender", "s\x00x", "POLICY_REFUSED_CONTROL_CHARS:sender"),
                ("channel", "c\t", "POLICY_REFUSED_CONTROL_CHARS:channel"),
                ("send_at", "", "POLICY_REFUSED_EMPTY:send_at"),
                ("subject", "s\n", "POLICY_REFUSED_CONTROL_CHARS:subject"),
                ("body", "b\x00", "POLICY_REFUSED_CONTROL_CHARS:body"),
                ("body", "", "POLICY_REFUSED_EMPTY:body")):
            dd = dict(d, payload=dict(d["payload"], **{field: bad}))
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor(dd)
            self.assertEqual(str(cm.exception), code)
        dd = dict(d, payload=dict(d["payload"], to=["a\x00@x"]))
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(dd)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_CONTROL_CHARS:to")
        dd = dict(d, payload=dict(d["payload"], sender="s" * 321))
        with self.assertRaises(ValueError) as cm:
            m.validate_descriptor(dd)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_TEXT_TOO_LONG:sender")

    def test_spend_direct_schema_field_hygiene(self):
        d = m.bind_spend(tenant_id="u1", module_id=24, merchant="Acme", item="d",
                         amount=5, currency="USD", quantity=1, fees=0,
                         undo_terms="r", effect_id="e1")
        for field, bad, code in (
                ("fees", -0.01, "POLICY_REFUSED_BAD_DESCRIPTOR:fees"),
                ("fees", float("nan"), "POLICY_REFUSED_BAD_DESCRIPTOR:fees"),
                ("effect_id", "", "POLICY_REFUSED_EMPTY:effect_id"),
                ("options", "x", "POLICY_REFUSED_BAD_DESCRIPTOR:options"),
                ("merchant", "", "POLICY_REFUSED_EMPTY:merchant"),
                ("item", "i" * 257, "POLICY_REFUSED_TEXT_TOO_LONG:item"),
                ("undo_terms", True, "POLICY_REFUSED_BAD_TYPE:undo_terms")):
            dd = dict(d, payload=dict(d["payload"], **{field: bad}))
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor(dd)
            self.assertEqual(str(cm.exception), code)

    def test_payload_hash_canonical(self):
        h1 = m.payload_hash({"b": 1, "a": [2, 3]})
        h2 = m.payload_hash({"a": [2, 3], "b": 1})  # key order irrelevant
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)
        self.assertNotEqual(h1, m.payload_hash({"a": [2, 3], "b": 2}))  # changed cost = new review

    def test_bind_spend(self):
        d = m.bind_spend(tenant_id="u1", module_id=24, merchant="Acme", item="domain",
                         amount=12.5, currency="USD", quantity=1, fees=0.0,
                         undo_terms="refundable 30d", effect_id="eff-1")
        self.assertEqual(d["class"], "spend")
        self.assertEqual(d["action_type"], "spend")
        self.assertEqual(d["tenant_id"], "u1")
        p = d["payload"]
        for k in ("merchant", "item", "amount", "currency", "quantity", "fees",
                  "undo_terms", "effect_id", "resource", "options"):
            self.assertIn(k, p)
        self.assertEqual(p["amount"], 12.5)
        m.validate_descriptor(d)
        good = dict(tenant_id="u1", module_id=24, merchant="Acme", item="domain",
                    amount=12.5, currency="USD", quantity=1, fees=0.0,
                    undo_terms="r", effect_id="eff-1")
        for field, bads in (("amount", (0, -1, True, "x", float("nan"), float("inf"))),
                            ("currency", ("us", "usd1", 5, "USDD", True)),
                            ("quantity", (0, -1, 1.5, True, "x")),
                            ("fees", (-0.01, True, "x", float("nan"))),
                            ("options", ("x", 5, [1]))):
            for bad in bads:
                kw = dict(good); kw[field] = bad
                with self.assertRaises(ValueError) as cm:
                    m.bind_spend(**kw)
                self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:" + field)
        # resource shares the single clean_text hygiene path (same codes as bind/direct)
        for bad in (5, True, "bad\x00resource"):
            with self.assertRaises(ValueError) as cm:
                m.bind_spend(**dict(good, resource=bad))
            self.assertTrue(str(cm.exception).startswith("POLICY_REFUSED_BAD_TYPE:resource")
                            or str(cm.exception).startswith("POLICY_REFUSED_CONTROL_CHARS:resource"))
        # auditor repro: control chars in direct-descriptor string fields refuse
        d = m.bind_spend(**good)
        for field, bad in (("merchant", "bad\x00merchant"), ("resource", "r\n"),
                           ("effect_id", "e\x00")):
            dd = dict(d, payload=dict(d["payload"], **{field: bad}))
            with self.assertRaises(ValueError) as cm:
                m.validate_descriptor(dd)
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_CONTROL_CHARS:" + field)
        # currency normalized to upper
        d = m.bind_spend(**dict(good, currency="usd"))
        self.assertEqual(d["payload"]["currency"], "USD")

    def test_bind_outreach(self):
        import hashlib
        d = m.bind_outreach(tenant_id="u1", module_id=24, sender="her@x.com",
                            channel="email", send_at="2026-10-12T09:00:00+05:30",
                            to=["a@x.com"], cc=[], bcc=[], subject="Hi",
                            body="exact body text", attachment_hashes=["a" * 64])
        self.assertEqual(d["class"], "outreach")
        p = d["payload"]
        self.assertEqual(p["body_sha256"],
                         hashlib.sha256(b"exact body text").hexdigest())
        self.assertEqual(p["to"], ["a@x.com"])
        m.validate_descriptor(d)
        good = dict(tenant_id="u1", module_id=24, sender="her@x.com", channel="email",
                    send_at="t", to=["a@x.com"], cc=[], bcc=[], subject="s", body="b")
        with self.assertRaises(ValueError) as cm:
            m.bind_outreach(**dict(good, to=[]))
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_EMPTY:to")
        with self.assertRaises(ValueError) as cm:
            m.bind_outreach(**dict(good, to="a@x.com"))
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:to")
        with self.assertRaises(ValueError) as cm:
            m.bind_outreach(**dict(good, cc="x@y.com"))
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:cc")
        with self.assertRaises(ValueError) as cm:
            m.bind_outreach(**dict(good, attachment_hashes=["nothex"]))
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:attachment_hashes")
        with self.assertRaises(ValueError) as cm:
            m.bind_outreach(**dict(good, attachment_hashes="a" * 64))
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:attachment_hashes")

    def test_execute_through_injected_consume(self):
        d = m.bind_spend(tenant_id="u1", module_id=24, merchant="Acme", item="domain",
                         amount=5, currency="USD", quantity=1, fees=0,
                         undo_terms="r", effect_id="eff-1")
        calls = []
        def fake_consume(**kw):
            calls.append(kw)
            return {"allowed": True, "effect_id": kw["effect_id"]}
        out = m.execute(d, "appr-1", actor="her", consume=fake_consume)
        self.assertEqual(out, {"allowed": True, "effect_id": "eff-1"})
        self.assertEqual(calls[0]["approval_id"], "appr-1")
        self.assertEqual(calls[0]["module_id"], 24)
        self.assertEqual(calls[0]["action_type"], "spend")
        self.assertEqual(calls[0]["payload"], d["payload"])  # unchanged descriptor payload
        self.assertEqual(calls[0]["user_id"], "u1")
        self.assertEqual(calls[0]["effect_id"], "eff-1")
        self.assertEqual(calls[0]["actor"], "her")

    def test_execute_hard_refuse_cannot_be_overridden(self):
        for cls in ("fakeacct", "autopost", "trade", "scrape"):
            d = {"class": cls, "module_id": 24, "tenant_id": "u1",
                 "action_type": "x", "payload": {}}
            with self.assertRaises(ValueError) as cm:
                m.execute(d, "appr-1", actor="her",
                          consume=lambda **kw: {"allowed": True})  # even if m00 said allow
            self.assertEqual(str(cm.exception), "POLICY_REFUSED_" + cls.upper())

    def test_execute_offline_not_executable(self):
        d = {"class": "offline", "module_id": 24, "tenant_id": "u1",
             "action_type": "analyze", "payload": {}}
        with self.assertRaises(ValueError) as cm:
            m.execute(d, "appr-1", actor="her", consume=lambda **kw: {})
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_NOT_EXECUTABLE:offline")

    def test_execute_validation_order(self):
        d = m.bind_spend(tenant_id="u1", module_id=24, merchant="Acme", item="d",
                         amount=5, currency="USD", quantity=1, fees=0,
                         undo_terms="r", effect_id="e1")
        with self.assertRaises(ValueError) as cm:
            m.execute(d, "", actor="her", consume=lambda **kw: {})
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_EMPTY:approval_id")
        # effect_id falls back to the payload's bound effect id
        no_eff = m.bind_outreach(tenant_id="u1", module_id=24, sender="h@x",
                                 channel="email", send_at="t", to=["a@x"], cc=[],
                                 bcc=[], subject="s", body="b")
        with self.assertRaises(ValueError) as cm:
            m.execute(no_eff, "appr-1", actor="her", consume=lambda **kw: {})
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_BAD_DESCRIPTOR:effect_id")
        out = m.execute(no_eff, "appr-1", actor="her", effect_id="eff-9",
                        consume=lambda **kw: {"ok": kw["effect_id"]})
        self.assertEqual(out, {"ok": "eff-9"})

    def test_scope_block(self):
        s = m.scope(["a"], ["b"], "supplied")
        self.assertEqual(s, {"implemented": ["a"], "not_implemented": ["b"],
                             "data_source": "supplied", "as_of": "supplied-input"})


if __name__ == "__main__":
    unittest.main()
