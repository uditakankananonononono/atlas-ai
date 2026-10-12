"""S4.3 / c35.waiver_drafts tests. Hermetic, stdlib unittest, no network.

Prep only: the module drafts text and exposes no function that sends,
registers, submits, pays or logs in. Cross-category check ORDER (forbidden
keys vs types vs fee) was left open in the original test block: every
refusal test in that block triggers exactly one category. Later classes pin order.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c35/waiver_drafts.py"
_spec = importlib.util.spec_from_file_location("c35_waiver_drafts", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c35_waiver_drafts"] = m
_spec.loader.exec_module(m)

TEMPLATE = "Dear {contact}, I am {name} from {school}. I request a fee waiver for {opportunity} (fee {fee}, deadline {deadline})."


def op(i, fee, email="x@y.org", **kw):
    d = {"id": i, "title": "Contest " + str(i), "fee": fee, "contact_email": email,
         "deadline": "2026-12-01"}
    d.update(kw)
    return d


def req(**kw):
    r = {"as_of": "2026-10-11", "profile": {"name": "UserA", "school": "Test School"},
         "opportunities": [op("o1", "USD 25")], "template": TEMPLATE}
    r.update(kw)
    return r


def refused(tc, request, code):
    with tc.assertRaises(ValueError) as cm:
        m.run(request)
    tc.assertEqual(str(cm.exception), code)


def fixture8():
    return req(opportunities=[
        op("a1", "USD 25"),
        op("a2", "free"),
        op("a3", "0"),
        op("a4", "$0.00"),
        op("a5", "EUR 25.50", email=None),
        op("a6", "TBD"),
        op("a7", "Rs 500", contact_name="Dr Rao"),
        op("a8", "1,000", email="not-an-email"),
    ])


class Success(unittest.TestCase):
    def test_fixture8_partition(self):
        out = m.run(fixture8())
        self.assertEqual([d["opportunity_id"] for d in out["drafts"]], ["a1", "a5", "a7", "a8"])
        self.assertEqual(out["skipped_no_fee"], ["a2", "a3", "a4"])
        self.assertEqual(out["fee_unknown"], ["a6"])
        self.assertEqual(set(out), {"drafts", "skipped_no_fee", "fee_unknown", "scope"})

    def test_draft_fields_exact(self):
        out = m.run(req())
        d = out["drafts"][0]
        self.assertEqual(set(d), {"draft_id", "opportunity_id", "recipient", "subject", "body",
                                  "status", "needs_recipient", "recipient_invalid"})
        self.assertEqual(d["recipient"], "x@y.org")
        self.assertEqual(d["subject"], "Fee waiver request: Contest o1")
        self.assertEqual(d["status"], "awaiting_exact_draft_approval")
        self.assertIs(d["needs_recipient"], False)
        self.assertIs(d["recipient_invalid"], False)
        self.assertEqual(d["body"], "Dear Admissions Team, I am UserA from Test School. "
                         "I request a fee waiver for Contest o1 (fee USD 25, deadline 2026-12-01).")

    def test_contact_name_used(self):
        out = m.run(req(opportunities=[op("o1", "10", contact_name="Dr Rao")]))
        self.assertTrue(out["drafts"][0]["body"].startswith("Dear Dr Rao, "))

    def test_contact_name_blank_defaults(self):
        out = m.run(req(opportunities=[op("o1", "10", contact_name="  ")]))
        self.assertTrue(out["drafts"][0]["body"].startswith("Dear Admissions Team, "))

    def test_fee_placeholder_is_raw_stripped(self):
        out = m.run(req(opportunities=[op("o1", "  $25  ")]))
        self.assertIn("(fee $25,", out["drafts"][0]["body"])

    def test_missing_recipient_flag(self):
        d = m.run(req(opportunities=[op("o1", "5", email=None)]))["drafts"][0]
        self.assertIsNone(d["recipient"])
        self.assertIs(d["needs_recipient"], True)
        self.assertIs(d["recipient_invalid"], False)

    def test_blank_recipient_is_missing_not_invalid(self):
        d = m.run(req(opportunities=[op("o1", "5", email="   ")]))["drafts"][0]
        self.assertIsNone(d["recipient"])
        self.assertIs(d["needs_recipient"], True)
        self.assertIs(d["recipient_invalid"], False)

    def test_invalid_recipient_flags(self):
        for bad in ["not-an-email", "a@b", "a b@c.org", "a@@c.org", "@c.org", "a@.org"[:0] + "a@c .org"]:
            d = m.run(req(opportunities=[op("o1", "5", email=bad)]))["drafts"][0]
            self.assertIsNone(d["recipient"], bad)
            self.assertIs(d["needs_recipient"], True, bad)
            self.assertIs(d["recipient_invalid"], True, bad)

    def test_control_char_recipient_invalid(self):
        for bad in ["a\x00@b.org", "a\x7f@b.org", "a@b\x01.org"]:
            d = m.run(req(opportunities=[op("o1", "5", email=bad)]))["drafts"][0]
            self.assertIs(d["recipient_invalid"], True, repr(bad))
            self.assertIsNone(d["recipient"])

    def test_valid_recipient_stripped(self):
        d = m.run(req(opportunities=[op("o1", "5", email="  a.b@c.org ")]))["drafts"][0]
        self.assertEqual(d["recipient"], "a.b@c.org")
        self.assertIs(d["needs_recipient"], False)

    def test_draft_id_formula(self):
        d = m.run(req())["drafts"][0]
        raw = json.dumps([d["recipient"] or "", d["subject"], d["body"]], ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
        self.assertEqual(d["draft_id"], hashlib.sha256(raw).hexdigest()[:16])
        self.assertEqual(len(d["draft_id"]), 16)

    def test_draft_id_null_recipient_uses_empty(self):
        d = m.run(req(opportunities=[op("o1", "5", email=None)]))["drafts"][0]
        raw = json.dumps(["", d["subject"], d["body"]], ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
        self.assertEqual(d["draft_id"], hashlib.sha256(raw).hexdigest()[:16])

    def test_draft_id_framed_not_concatenated(self):
        a = m.run(req(opportunities=[op("o1", "5", email="a@b.org")]))["drafts"][0]
        b = m.run(req(opportunities=[op("o1", "5", email="a@b.org", title="X")]))["drafts"][0]
        self.assertNotEqual(a["draft_id"], b["draft_id"])
        self.assertNotEqual(m.run(req(opportunities=[op("o1", "5", email="a@b.org")]))["drafts"][0]["draft_id"],
                            m.run(req(opportunities=[op("o1", "5", email="c@d.org")]))["drafts"][0]["draft_id"])

    def test_deterministic_byte_identical(self):
        a = json.dumps(m.run(fixture8()), sort_keys=True, ensure_ascii=False)
        b = json.dumps(m.run(fixture8()), sort_keys=True, ensure_ascii=False)
        self.assertEqual(a, b)

    def test_request_not_mutated(self):
        r = fixture8()
        before = copy.deepcopy(r)
        m.run(r)
        self.assertEqual(r, before)

    def test_sorted_id_lists(self):
        out = m.run(req(opportunities=[op("z", "free"), op("b", "free"), op("m", "tbd"), op("c", "tbd")]))
        self.assertEqual(out["skipped_no_fee"], ["b", "z"])
        self.assertEqual(out["fee_unknown"], ["c", "m"])
        self.assertEqual(out["drafts"], [])

    def test_scope_block(self):
        s = m.run(req())["scope"]
        self.assertEqual(set(s), {"implemented", "not_implemented", "data_source", "as_of"})
        self.assertEqual(s["as_of"], "2026-10-11")
        joined = " ".join(s["not_implemented"]).lower()
        for word in ["send", "register", "submit", "fee action", "login", "waiver will be granted"]:
            self.assertIn(word, joined)

    def test_as_of_not_used_in_logic(self):
        a = m.run(req(as_of="2026-10-11"))
        b = m.run(req(as_of="2030-01-01"))
        a["scope"].pop("as_of"); b["scope"].pop("as_of")
        self.assertEqual(a, b)

    def test_placeholder_only_checked_if_used(self):
        r = req(template="Hello {name} re {opportunity}", opportunities=[
            {"id": "o1", "title": "T", "fee": "5"}])  # no deadline, no email: fine
        d = m.run(r)["drafts"][0]
        self.assertEqual(d["body"], "Hello UserA re T")

    def test_value_with_braces_not_reexpanded(self):
        r = req(template="Hi {name}", profile={"name": "A{school}B", "school": "S"})
        self.assertEqual(m.run(r)["drafts"][0]["body"], "Hi A{school}B")

    def test_template_whitespace_preserved(self):
        r = req(template="Dear {contact},\n\n\tI am {name}.\n")
        self.assertEqual(m.run(r)["drafts"][0]["body"], "Dear Admissions Team,\n\n\tI am UserA.\n")


class Fee(unittest.TestCase):
    def kinds(self, fee):
        out = m.run(req(opportunities=[op("o1", fee)]))
        return ("draft" if out["drafts"] else "free" if out["skipped_no_fee"] else "unknown")

    def test_free_set(self):
        for f in ["free", "FREE", " Free ", "0", "0.0", "0.00", "usd 0", "USD 0", "$0", "no fee", "None", 0, 0.0]:
            self.assertEqual(self.kinds(f), "free", repr(f))

    def test_unknown_set(self):
        for f in ["", "  ", "n/a", "N/A", "tbd", "TBD", "unknown", "varies", "Varies", None]:
            self.assertEqual(self.kinds(f), "unknown", repr(f))

    def test_missing_fee_key_is_unknown(self):
        out = m.run(req(opportunities=[{"id": "o1", "title": "T"}]))
        self.assertEqual(out["fee_unknown"], ["o1"])

    def test_positive_forms_draft(self):
        for f in ["25", "$25", "USD 25", "25 USD", "EUR 25.50", "Rs 500", "1,000", "\u20b9500",
                  "\u20ac10", "\u00a35", "gbp 5", "5 inr", "1,000.50", "0.50", "0.01"]:
            self.assertEqual(self.kinds(f), "draft", repr(f))

    def test_zero_any_currency_form_free(self):
        for f in ["0.00 usd", "$0.00", "EUR 0", "rs 0", "0 inr", "00", "0,000"[:1], "\u20b90"]:
            self.assertEqual(self.kinds(f), "free", repr(f))

    def test_bad_fee_strings(self):
        for f in ["25-30", "twenty", "usd", "$", "25 usd extra", "1,00", "1,0000", "25.", ".5",
                  "25.123", "-5", "$-5", "usd 25 usd", "$25 usd", "usd25usd", "25 rs", "rs 25 inr",
                  "\u0663\u0665", "5 5", "free!", "nofee"]:
            refused(self, req(opportunities=[op("o1", f)]), "APPLY_REFUSED_BAD_TYPE:fee")

    def test_prefix_and_suffix_both_is_bad_type(self):
        refused(self, req(opportunities=[op("o1", "usd 25 eur")]), "APPLY_REFUSED_BAD_TYPE:fee")
        refused(self, req(opportunities=[op("o1", "$25 usd")]), "APPLY_REFUSED_BAD_TYPE:fee")

    def test_non_string_fee_types(self):
        for f in [True, False, -1, -0.5, float("nan"), float("inf"), [], {}, ("1",)]:
            refused(self, req(opportunities=[op("o1", f)]), "APPLY_REFUSED_BAD_TYPE:fee")

    def test_positive_numeric_drafted_as_str(self):
        d = m.run(req(opportunities=[op("o1", 25)]))["drafts"][0]
        self.assertIn("(fee 25,", d["body"])
        d = m.run(req(opportunities=[op("o1", 12.5)]))["drafts"][0]
        self.assertIn("(fee 12.5,", d["body"])

    def test_one_bad_fee_refuses_whole_request(self):
        refused(self, req(opportunities=[op("o1", "5"), op("o2", "twenty")]), "APPLY_REFUSED_BAD_TYPE:fee")


class Recipient(unittest.TestCase):
    def test_strict_missing(self):
        refused(self, req(strict=True, opportunities=[op("o1", "5"), op("o2", "5", email=None)]),
                "APPLY_REFUSED_NORECIPIENT:contact_email")

    def test_strict_invalid(self):
        refused(self, req(strict=True, opportunities=[op("o1", "5", email="bad")]),
                "APPLY_REFUSED_NORECIPIENT:contact_email")

    def test_strict_reason_is_literal_not_id(self):
        refused(self, req(strict=True, opportunities=[op("o1", "5", email=None), op("o2", "5", email="bad")]),
                "APPLY_REFUSED_NORECIPIENT:contact_email")

    def test_strict_ignores_non_drafted(self):
        out = m.run(req(strict=True, opportunities=[op("o1", "free", email=None), op("o2", "tbd", email="bad"),
                                                    op("o3", "5")]))
        self.assertEqual(len(out["drafts"]), 1)

    def test_strict_false_and_absent(self):
        self.assertEqual(len(m.run(req(strict=False, opportunities=[op("o1", "5", email=None)]))["drafts"]), 1)
        self.assertEqual(len(m.run(req(opportunities=[op("o1", "5", email=None)]))["drafts"]), 1)

    def test_strict_true_all_valid(self):
        self.assertEqual(len(m.run(req(strict=True))["drafts"]), 1)

    def test_strict_non_bool(self):
        for s in ["true", 1, 0, None, []]:
            refused(self, req(strict=s), "APPLY_REFUSED_BAD_TYPE:strict")

    def test_contact_email_non_string(self):
        refused(self, req(opportunities=[op("o1", "5", email=5)]), "APPLY_REFUSED_BAD_TYPE:contact_email")


class Placeholders(unittest.TestCase):
    def test_unknown_placeholder(self):
        refused(self, req(template="Hi {name} {phone}"), "APPLY_REFUSED_UNFILLED:template")
        refused(self, req(template="Hi {Name}"), "APPLY_REFUSED_UNFILLED:template")
        refused(self, req(template="Hi {}"), "APPLY_REFUSED_UNFILLED:template")

    def test_missing_profile_value_if_used(self):
        refused(self, req(profile={"name": "U"}), "APPLY_REFUSED_UNFILLED:school")
        refused(self, req(profile={"school": "S"}), "APPLY_REFUSED_UNFILLED:name")
        refused(self, req(profile={"name": " ", "school": "S"}), "APPLY_REFUSED_UNFILLED:name")

    def test_missing_profile_value_unused_ok(self):
        out = m.run(req(template="Hi {opportunity}", profile={}))
        self.assertEqual(out["drafts"][0]["body"], "Hi Contest o1")

    def test_missing_deadline_if_used(self):
        refused(self, req(opportunities=[{"id": "o1", "title": "T", "fee": "5"}]), "APPLY_REFUSED_UNFILLED:deadline")
        refused(self, req(opportunities=[op("o1", "5", deadline="  ")]), "APPLY_REFUSED_UNFILLED:deadline")

    def test_template_unknown_placeholder_even_without_drafts(self):
        refused(self, req(template="{zzz}", opportunities=[op("o1", "free")]), "APPLY_REFUSED_UNFILLED:template")

    def test_missing_value_for_non_drafted_opportunity_ok(self):
        out = m.run(req(opportunities=[{"id": "o1", "title": "T", "fee": "free"}, op("o2", "5")]))
        self.assertEqual(len(out["drafts"]), 1)


class ForbiddenKeys(unittest.TestCase):
    SEND = ["send", "approve", "approved", "approval", "approval_token", "smtp", "token", "email_send",
            "sender", "smtp_host", "smtp_port", "smtp_user"]
    SPEND = ["pay", "waive_fee", "fee_action"]
    SUBMIT = ["register", "submit", "attempt"]
    NOCREDS = ["login", "password", "username", "credentials", "otp", "api_key", "access_token",
               "refresh_token", "bearer", "pass", "passwd"]

    def test_each_key_top_level(self):
        for rule, keys in [("SEND", self.SEND), ("SPEND", self.SPEND), ("SUBMIT", self.SUBMIT),
                           ("NOCREDS", self.NOCREDS)]:
            for k in keys:
                refused(self, req(**{k: True}), "APPLY_REFUSED_%s:%s" % (rule, k))

    def test_nested_depths(self):
        refused(self, req(profile={"name": "U", "school": "S", "token": "x"}), "APPLY_REFUSED_SEND:token")
        o = op("o1", "5")
        o["approval_token"] = "abc"
        refused(self, req(opportunities=[o]), "APPLY_REFUSED_SEND:approval_token")
        o = op("o1", "5")
        o["extra"] = {"deep": [{"x": {"login": 1}}]}
        refused(self, req(opportunities=[o]), "APPLY_REFUSED_NOCREDS:login")
        refused(self, req(opportunities=[[{"submit": 1}]]), "APPLY_REFUSED_SUBMIT:submit")
        refused(self, req(opportunities=[{"a": ({"pay": 1},)}]), "APPLY_REFUSED_SPEND:pay")

    def test_casefold_and_hyphen(self):
        refused(self, req(**{"Approval_Token": 1}), "APPLY_REFUSED_SEND:approval_token")
        refused(self, req(**{"APPROVAL-TOKEN": 1}), "APPLY_REFUSED_SEND:approval_token")
        refused(self, req(**{"Api-Key": 1}), "APPLY_REFUSED_NOCREDS:api_key")
        refused(self, req(**{"SMTP-HOST": 1}), "APPLY_REFUSED_SEND:smtp_host")
        refused(self, req(**{"Waive-Fee": 1}), "APPLY_REFUSED_SPEND:waive_fee")

    def test_exact_match_only(self):
        for k in ["sending", "tokens", "token_count", "paypal", "registered", "submitted", "passport",
                  "login_url", "usernames", "approver", "attempts", "sender_name", "otp_code", "pay_by"]:
            refused(self, req(**{k: 1}), "APPLY_REFUSED_UNKNOWN:request")  # exact match: not forbidden, but unknown

    def test_values_not_scanned(self):
        r = req(profile={"name": "send", "school": "token password login"})
        out = m.run(r)
        self.assertEqual(len(out["drafts"]), 1)
        r = req(opportunities=[op("o1", "5", title="submit token")])
        self.assertEqual(len(m.run(r)["drafts"]), 1)

    def test_precedence(self):
        for hit, expect in [
            ({"login": 1, "submit": 1, "pay": 1, "send": 1}, "SEND:send"),
            ({"login": 1, "submit": 1, "pay": 1}, "SPEND:pay"),
            ({"login": 1, "submit": 1}, "SUBMIT:submit"),
            ({"login": 1}, "NOCREDS:login")]:
            refused(self, req(**hit), "APPLY_REFUSED_" + expect)

    def test_matched_key_is_alphabetically_first_of_winning_rule(self):
        refused(self, req(token=1, approve=1, smtp=1), "APPLY_REFUSED_SEND:approve")
        o = op("o1", "5")
        o["zzz"] = {"token": 1}
        refused(self, req(opportunities=[o], approval=1, sender=1), "APPLY_REFUSED_SEND:approval")
        refused(self, req(passwd=1, bearer=1, otp=1, **{"Api-Key": 1}), "APPLY_REFUSED_NOCREDS:api_key")
        refused(self, req(register=1, attempt=1), "APPLY_REFUSED_SUBMIT:attempt")
        refused(self, req(pay=1, fee_action=1, waive_fee=1), "APPLY_REFUSED_SPEND:fee_action")

    def test_reason_never_echoes_request_text(self):
        with self.assertRaises(ValueError) as cm:
            m.run(req(**{"Approval-TOKEN": 1, "zzUnknown": 1}))
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_SEND:approval_token")

    def test_precedence_across_depths(self):
        o = op("o1", "5")
        o["login"] = 1
        refused(self, req(opportunities=[o], send=1), "APPLY_REFUSED_SEND:send")
        refused(self, req(opportunities=[o], pay=1), "APPLY_REFUSED_SPEND:pay")

    def test_no_partial_output(self):
        # token in the SECOND opportunity: whole request refused, nothing returned
        o2 = op("o2", "5")
        o2["token"] = "t"
        refused(self, req(opportunities=[op("o1", "5"), o2]), "APPLY_REFUSED_SEND:token")

    def test_token_fixture_separate_from_prep_fixture(self):
        r = fixture8()
        self.assertTrue(all("token" not in json.dumps(o) for o in r["opportunities"]))
        self.assertEqual(len(m.run(r)["drafts"]), 4)
        bad = fixture8()
        bad["opportunities"][1]["approval_token"] = "x"
        refused(self, bad, "APPLY_REFUSED_SEND:approval_token")


class Validation(unittest.TestCase):
    def test_request_type(self):
        for r in [None, [], "x", 1]:
            refused(self, r, "APPLY_REFUSED_BAD_TYPE:request")

    def test_as_of(self):
        r = req(); del r["as_of"]
        refused(self, r, "APPLY_REFUSED_BAD_TYPE:as_of")
        for bad in [5, None, True]:
            refused(self, req(as_of=bad), "APPLY_REFUSED_BAD_TYPE:as_of")
        for bad in ["", "  ", "\x00", "bad\x01"]:
            refused(self, req(as_of=bad), "APPLY_REFUSED_BAD_TYPE:as_of")
        for bad in ["2026-10-1", "10/11/2026", "2026-13-01", "2026-02-30", "2026-10-11T00:00", " 2026-10-11"]:
            refused(self, req(as_of=bad), "APPLY_REFUSED_BAD_TYPE:as_of")
        refused(self, req(as_of="\u0662026-10-11"), "APPLY_REFUSED_BAD_TYPE:as_of")
        refused(self, req(as_of="2026-10-11\n"), "APPLY_REFUSED_BAD_TYPE:as_of")
        refused(self, req(as_of="2026-10-11" + "x" * 50), "APPLY_REFUSED_BAD_TYPE:as_of")
        refused(self, req(as_of="2" * 65), "APPLY_REFUSED_OVERSIZE:as_of")
        self.assertEqual(m.run(req(as_of="2028-02-29"))["scope"]["as_of"], "2028-02-29")
        refused(self, req(as_of="2027-02-29"), "APPLY_REFUSED_BAD_TYPE:as_of")
        refused(self, req(as_of="1900-02-29"), "APPLY_REFUSED_BAD_TYPE:as_of")
        self.assertEqual(m.run(req(as_of="2000-02-29"))["scope"]["as_of"], "2000-02-29")
        refused(self, req(as_of="2026-04-31"), "APPLY_REFUSED_BAD_TYPE:as_of")
        refused(self, req(as_of="2026-00-10"), "APPLY_REFUSED_BAD_TYPE:as_of")
        refused(self, req(as_of="2026-10-00"), "APPLY_REFUSED_BAD_TYPE:as_of")

    def test_profile_type(self):
        for p in [None, [], "x"]:
            refused(self, req(profile=p), "APPLY_REFUSED_BAD_TYPE:profile")
        r = req(); del r["profile"]
        refused(self, r, "APPLY_REFUSED_BAD_TYPE:profile")

    def test_opportunities_type(self):
        for o in [None, {}, "x", 5]:
            refused(self, req(opportunities=o), "APPLY_REFUSED_BAD_TYPE:opportunities")
        refused(self, req(opportunities=[]), "APPLY_REFUSED_EMPTY")
        refused(self, req(opportunities=["x"]), "APPLY_REFUSED_BAD_TYPE:opportunities")
        refused(self, req(opportunities=[None]), "APPLY_REFUSED_BAD_TYPE:opportunities")

    def test_opportunity_cap(self):
        ok = req(opportunities=[op("i%d" % i, "free") for i in range(m.MAX_OPPORTUNITIES)])
        self.assertEqual(len(m.run(ok)["skipped_no_fee"]), m.MAX_OPPORTUNITIES)
        refused(self, req(opportunities=[op("i%d" % i, "free") for i in range(m.MAX_OPPORTUNITIES + 1)]),
                "APPLY_REFUSED_OVERSIZE:opportunities")

    def test_duplicate_ids(self):
        refused(self, req(opportunities=[op("o1", "5"), op("o1", "free")]), "APPLY_REFUSED_BAD_TYPE:opportunities")

    def test_id_and_title(self):
        refused(self, req(opportunities=[{"title": "T", "fee": "5"}]), "APPLY_REFUSED_BAD_TYPE:id")
        refused(self, req(opportunities=[op(5, "5")]), "APPLY_REFUSED_BAD_TYPE:id")
        refused(self, req(opportunities=[op(" ", "5")]), "APPLY_REFUSED_EMPTY:id")
        refused(self, req(opportunities=[op("o1", "5", title=None)]), "APPLY_REFUSED_BAD_TYPE:title")
        refused(self, req(opportunities=[op("o1", "5", title="")]), "APPLY_REFUSED_EMPTY:title")
        refused(self, req(opportunities=[op("o1", "5", title="a\x00b")]), "APPLY_REFUSED_CONTROL_CHARS:title")
        refused(self, req(opportunities=[op("o1", "5", title="a\nb")]), "APPLY_REFUSED_CONTROL_CHARS:title")
        refused(self, req(opportunities=[op("o1", "5", title="x" * 201)]), "APPLY_REFUSED_OVERSIZE:title")
        self.assertEqual(len(m.run(req(opportunities=[op("o1", "5", title="x" * 200)]))["drafts"]), 1)
        refused(self, req(opportunities=[op("i" * 129, "5")]), "APPLY_REFUSED_OVERSIZE:id")

    def test_template(self):
        for t in [None, 5, []]:
            refused(self, req(template=t), "APPLY_REFUSED_BAD_TYPE:template")
        refused(self, req(template="  "), "APPLY_REFUSED_EMPTY:template")
        refused(self, req(template="a\x00{name}"), "APPLY_REFUSED_CONTROL_CHARS:template")
        refused(self, req(template="a" * 20001), "APPLY_REFUSED_OVERSIZE:template")
        self.assertEqual(len(m.run(req(template="{name}" + "a" * 19994))["drafts"]), 1)

    def test_profile_values(self):
        refused(self, req(profile={"name": 5, "school": "S"}), "APPLY_REFUSED_BAD_TYPE:name")
        refused(self, req(profile={"name": "a\nb", "school": "S"}), "APPLY_REFUSED_CONTROL_CHARS:name")
        refused(self, req(profile={"name": "x" * 201, "school": "S"}), "APPLY_REFUSED_OVERSIZE:profile")
        refused(self, req(profile={"name": "U", "school": 5}), "APPLY_REFUSED_BAD_TYPE:school")

    def test_body_length_cap(self):
        refused(self, req(template="{name}" * 3000, profile={"name": "a" * 20, "school": "S"}),
                "APPLY_REFUSED_OVERSIZE:template")

    def test_non_str_deadline_and_contact(self):
        refused(self, req(opportunities=[op("o1", "5", deadline=5)]), "APPLY_REFUSED_BAD_TYPE:deadline")
        refused(self, req(opportunities=[op("o1", "5", contact_name=5)]), "APPLY_REFUSED_BAD_TYPE:contact_name")


class CheckOrder(unittest.TestCase):
    """Earlier order pins: 1 request dict, 2 forbidden keys, 3 top-level,
    4 per-opportunity types + duplicate ids, 5 fee, 6 template, 7 recipient."""

    def test_1_before_2(self):
        refused(self, [{"token": 1}], "APPLY_REFUSED_BAD_TYPE:request")

    def test_2_before_3(self):
        refused(self, {"as_of": 5, "token": 1}, "APPLY_REFUSED_SEND:token")
        refused(self, {"profile": 5, "opportunities": "x", "strict": "no", "login": 1},
                "APPLY_REFUSED_NOCREDS:login")

    def test_2_scans_malformed_records(self):
        refused(self, req(opportunities=[5, {"x": [{"pay": 1}]}]), "APPLY_REFUSED_SPEND:pay")
        refused(self, req(opportunities=[{"id": 5, "fee": [], "token": 1}]), "APPLY_REFUSED_SEND:token")

    def test_3_before_4(self):
        refused(self, req(strict="x", opportunities=[{"id": 5}]), "APPLY_REFUSED_BAD_TYPE:strict")
        refused(self, req(template=None, opportunities=[{"id": 5}]), "APPLY_REFUSED_BAD_TYPE:template")

    def test_4_before_5(self):
        refused(self, req(opportunities=[op("o1", "twenty"), {"title": "T"}]), "APPLY_REFUSED_BAD_TYPE:id")
        refused(self, req(opportunities=[op("o1", "twenty"), op("o1", "5")]), "APPLY_REFUSED_BAD_TYPE:opportunities")

    def test_4_first_opportunity_in_list_order(self):
        refused(self, req(opportunities=[op("o1", "5"), op("o2", "5", title=None), {"id": 7}]),
                "APPLY_REFUSED_BAD_TYPE:title")
        refused(self, req(opportunities=[op("o1", "5"), {"id": 7}, op("o2", "5", title=None)]),
                "APPLY_REFUSED_BAD_TYPE:id")

    def test_5_before_6(self):
        refused(self, req(template="{zzz}", opportunities=[op("o1", "twenty")]), "APPLY_REFUSED_BAD_TYPE:fee")
        refused(self, req(profile={}, opportunities=[op("o1", "twenty")]), "APPLY_REFUSED_BAD_TYPE:fee")

    def test_5_first_bad_fee_in_list_order_not_validation_of_later(self):
        # the later bad fee is never reached; earlier invalid recipient type is step 4 so first
        refused(self, req(opportunities=[op("o1", "5"), op("o2", "bad!"), op("o3", True)]),
                "APPLY_REFUSED_BAD_TYPE:fee")
        refused(self, req(opportunities=[op("o1", "5", email=5), op("o2", "bad!")]),
                "APPLY_REFUSED_BAD_TYPE:contact_email")

    def test_6_before_7(self):
        refused(self, req(strict=True, template="{zzz}", opportunities=[op("o1", "5", email=None)]),
                "APPLY_REFUSED_UNFILLED:template")
        refused(self, req(strict=True, opportunities=[
            {"id": "o1", "title": "T", "fee": "5"}]), "APPLY_REFUSED_UNFILLED:deadline")

    def test_6_deadline_first_opportunity_in_list_order(self):
        refused(self, req(opportunities=[op("o1", "5"), {"id": "o2", "title": "T", "fee": "5"}]),
                "APPLY_REFUSED_UNFILLED:deadline")

    def test_7_only_when_strict(self):
        refused(self, req(strict=True, opportunities=[op("o1", "5", email="bad")]),
                "APPLY_REFUSED_NORECIPIENT:contact_email")

    def test_5_refuses_before_any_drafts_even_with_earlier_good_items(self):
        with self.assertRaises(ValueError):
            m.run(req(opportunities=[op("o1", "5"), op("o2", "nonsense!")]))


class Boundaries(unittest.TestCase):
    """Added after mutation run 1 (41 survivors, mostly constants and boundaries)."""

    def test_month_lengths_every_month(self):
        last = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
        for mo, d in last.items():
            ok = "2026-%02d-%02d" % (mo, d)
            self.assertEqual(m.run(req(as_of=ok))["scope"]["as_of"], ok)
            refused(self, req(as_of="2026-%02d-%02d" % (mo, d + 1)), "APPLY_REFUSED_BAD_TYPE:as_of")
        for ok in ["2026-01-01", "2026-12-01"]:
            self.assertEqual(m.run(req(as_of=ok))["scope"]["as_of"], ok)
        refused(self, req(as_of="2026-13-01"), "APPLY_REFUSED_BAD_TYPE:as_of")
        refused(self, req(as_of="2026-00-01"), "APPLY_REFUSED_BAD_TYPE:as_of")
        self.assertEqual(m.run(req(as_of="2024-02-29"))["scope"]["as_of"], "2024-02-29")
        refused(self, req(as_of="2024-02-30"), "APPLY_REFUSED_BAD_TYPE:as_of")

    def test_as_of_length_limit_64(self):
        refused(self, req(as_of="2026-10-11" + "x" * 54), "APPLY_REFUSED_BAD_TYPE:as_of")  # 64 chars
        refused(self, req(as_of="2026-10-11" + "x" * 55), "APPLY_REFUSED_OVERSIZE:as_of")  # 65

    def test_opportunity_cap_exact_1000(self):
        ok = req(opportunities=[op("i%d" % i, "free") for i in range(1000)])
        self.assertEqual(len(m.run(ok)["skipped_no_fee"]), 1000)
        bad = req(opportunities=[op("i%d" % i, "free") for i in range(1001)])
        refused(self, bad, "APPLY_REFUSED_OVERSIZE:opportunities")

    def test_body_cap_exact_20000(self):
        r = req(template="{name}" * 100 + "a" * 100, profile={"name": "n" * 199, "school": "S"})
        # 100*199 + 100 = 20000 exactly: allowed; template length 600+100 is under its own cap
        out = m.run(r)
        self.assertEqual(len(out["drafts"][0]["body"]), 20000)
        r = req(template="{name}" * 100 + "a" * 101, profile={"name": "n" * 199, "school": "S"})
        refused(self, r, "APPLY_REFUSED_OVERSIZE:template")

    def test_field_limits_exact(self):
        ok = m.run(req(profile={"name": "n" * 200, "school": "s" * 200}))
        self.assertEqual(len(ok["drafts"]), 1)
        refused(self, req(profile={"name": "n" * 201, "school": "S"}), "APPLY_REFUSED_OVERSIZE:profile")
        refused(self, req(profile={"name": "n", "school": "s" * 201}), "APPLY_REFUSED_OVERSIZE:profile")
        self.assertEqual(len(m.run(req(opportunities=[op("i" * 128, "5")]))["drafts"]), 1)
        self.assertEqual(len(m.run(req(opportunities=[op("o1", "5", contact_name="c" * 200)]))["drafts"]), 1)
        refused(self, req(opportunities=[op("o1", "5", contact_name="c" * 201)]),
                "APPLY_REFUSED_OVERSIZE:contact_name")
        self.assertEqual(len(m.run(req(opportunities=[op("o1", "5", deadline="d" * 100)]))["drafts"]), 1)
        refused(self, req(opportunities=[op("o1", "5", deadline="d" * 101)]),
                "APPLY_REFUSED_OVERSIZE:deadline")

    def test_oversize_field_tokens_and_cap_checked_before_clean_text(self):
        long_ctl = "\x00" * 1  # control char AND over the cap: the cap is checked first
        cases = [
            (req(as_of="2" * 65), "as_of"),
            (req(profile={"name": "n" * 201, "school": "S"}), "profile"),
            (req(profile={"name": "n", "school": "s" * 201}), "profile"),
            (req(opportunities=[op("i" * 129, "5")]), "id"),
            (req(opportunities=[op("o1", "5", title="t" * 201)]), "title"),
            (req(opportunities=[op("o1", "5", contact_name="c" * 201)]), "contact_name"),
            (req(opportunities=[op("o1", "5", deadline="d" * 101)]), "deadline"),
            (req(template="a" * 20001), "template"),
            (req(opportunities=[op("i%d" % i, "free") for i in range(1001)]), "opportunities"),
            (req(as_of="2" * 64 + long_ctl), "as_of"),
            (req(profile={"name": "n" * 200 + long_ctl, "school": "S"}), "profile"),
            (req(opportunities=[op("i" * 128 + long_ctl, "5")]), "id"),
            (req(opportunities=[op("o1", "5", title="t" * 200 + long_ctl)]), "title"),
            (req(template="a" * 20000 + long_ctl), "template"),
        ]
        for r, field in cases:
            refused(self, r, "APPLY_REFUSED_OVERSIZE:" + field)

    def test_text_too_long_never_surfaces(self):
        src = _P.read_text(encoding="utf-8")
        self.assertNotIn("TEXT_TOO_LONG", src)
        for r in [req(as_of="2" * 500), req(profile={"name": "n" * 5000, "school": "S"}),
                  req(template="a" * 50000), req(opportunities=[op("i" * 9999, "5")])]:
            with self.assertRaises(ValueError) as cm:
                m.run(r)
            self.assertNotIn("TEXT_TOO_LONG", str(cm.exception))
            self.assertIn("OVERSIZE", str(cm.exception))

    def test_non_length_clean_text_codes_unchanged(self):
        refused(self, req(opportunities=[op("o1", "5", title="a\x00")]), "APPLY_REFUSED_CONTROL_CHARS:title")
        refused(self, req(opportunities=[op("o1", "5", title="")]), "APPLY_REFUSED_EMPTY:title")
        refused(self, req(opportunities=[op("o1", "5", title=5)]), "APPLY_REFUSED_BAD_TYPE:title")

    def test_drafts_keep_input_order(self):
        out = m.run(req(opportunities=[op("z", "5"), op("b", "5"), op("m", "5")]))
        self.assertEqual([d["opportunity_id"] for d in out["drafts"]], ["z", "b", "m"])

    def test_ids_kept_byte_exact(self):
        out = m.run(req(opportunities=[op(" o1 ", "5"), op("o1", "5")]))
        self.assertEqual([d["opportunity_id"] for d in out["drafts"]], [" o1 ", "o1"])
        out = m.run(req(opportunities=[op(" a", "free")]))
        self.assertEqual(out["skipped_no_fee"], [" a"])

    def test_control_char_boundary_recipient(self):
        for code in (0, 1, 9, 31, 127):
            d = m.run(req(opportunities=[op("o1", "5", email="a%sb@c.org" % chr(code))]))["drafts"][0]
            self.assertIs(d["recipient_invalid"], True, code)
        d = m.run(req(opportunities=[op("o1", "5", email="a-b@c.org")]))["drafts"][0]
        self.assertIs(d["recipient_invalid"], False)
        d = m.run(req(opportunities=[op("o1", "5", email="a~b@c.org")]))["drafts"][0]  # 126 stays valid
        self.assertIs(d["recipient_invalid"], False)

    def test_draft_id_keeps_non_ascii_unescaped(self):
        d = m.run(req(opportunities=[op("o1", "5", title="Caf\u00e9 \u4e2d")]))["drafts"][0]
        raw = json.dumps([d["recipient"], d["subject"], d["body"]], ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
        self.assertEqual(d["draft_id"], hashlib.sha256(raw).hexdigest()[:16])
        raw_ascii = json.dumps([d["recipient"], d["subject"], d["body"]], ensure_ascii=True,
                               separators=(",", ":")).encode("utf-8")
        self.assertNotEqual(hashlib.sha256(raw_ascii).hexdigest()[:16], d["draft_id"])


class SchemaKeys(unittest.TestCase):
    """Schema repair choices: UNKNOWN:<parent>, BAD_TYPE:key."""

    def test_unknown_top_level_key(self):
        refused(self, req(zzz=1), "APPLY_REFUSED_UNKNOWN:request")
        refused(self, req(**{"Strict": True}), "APPLY_REFUSED_UNKNOWN:request")  # case-sensitive schema

    def test_unknown_profile_key(self):
        refused(self, req(profile={"name": "U", "school": "S", "email": "a"}), "APPLY_REFUSED_UNKNOWN:profile")

    def test_unknown_opportunity_key(self):
        o = op("o1", "5")
        o["notes"] = "x"
        refused(self, req(opportunities=[o]), "APPLY_REFUSED_UNKNOWN:opportunities")

    def test_reason_is_schema_parent_never_key_text(self):
        with self.assertRaises(ValueError) as cm:
            m.run(req(**{"my secret key": 1}))
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_UNKNOWN:request")

    def test_allowed_keys_accepted(self):
        r = req(strict=False)
        self.assertEqual(len(m.run(r)["drafts"]), 1)
        o = op("o1", "5", contact_name="Dr R")
        self.assertEqual(len(m.run(req(opportunities=[o]))["drafts"]), 1)
        self.assertEqual(len(m.run(req(profile={"name": "U"}, template="Hi {opportunity}"))["drafts"]), 1)

    def test_unknown_key_checked_after_forbidden_scan(self):
        refused(self, req(zzz=1, token=1), "APPLY_REFUSED_SEND:token")
        o = op("o1", "5")
        o["notes"] = 1
        o["extra"] = {"login": 1}
        refused(self, req(opportunities=[o]), "APPLY_REFUSED_NOCREDS:login")

    def test_unknown_top_level_before_field_types(self):
        refused(self, req(zzz=1, as_of=5), "APPLY_REFUSED_UNKNOWN:request")

    def test_unknown_opportunity_key_in_step_4_before_fee(self):
        o = op("o1", "twenty")
        o["notes"] = 1
        refused(self, req(opportunities=[o]), "APPLY_REFUSED_UNKNOWN:opportunities")

    def test_non_str_key_anywhere(self):
        r = req()
        r[5] = 1
        refused(self, r, "APPLY_REFUSED_BAD_TYPE:key")
        o = op("o1", "5")
        o[None] = 1
        refused(self, req(opportunities=[o]), "APPLY_REFUSED_BAD_TYPE:key")
        refused(self, req(profile={"name": "U", "school": "S", 1: "x"}), "APPLY_REFUSED_BAD_TYPE:key")
        refused(self, req(opportunities=[{"a": [{(1, 2): 1}]}]), "APPLY_REFUSED_BAD_TYPE:key")

    def test_forbidden_wins_over_non_str_key(self):
        r = req(token=1)
        r[5] = 1
        refused(self, r, "APPLY_REFUSED_SEND:token")

    def test_non_str_key_before_unknown_and_types(self):
        r = req(zzz=1, as_of=5)
        r[5] = 1
        refused(self, r, "APPLY_REFUSED_BAD_TYPE:key")

    def test_placeholder_text_never_echoed(self):
        with self.assertRaises(ValueError) as cm:
            m.run(req(template="Hi {secret_thing}"))
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_UNFILLED:template")

    def test_unfilled_value_token_is_allowlisted_name(self):
        refused(self, req(profile={"name": "U"}), "APPLY_REFUSED_UNFILLED:school")
        refused(self, req(opportunities=[{"id": "o1", "title": "T", "fee": "5"}]),
                "APPLY_REFUSED_UNFILLED:deadline")

    def test_reasons_never_contain_ids_or_values(self):
        for r in [req(opportunities=[op("SECRET-ID", "5"), op("SECRET-ID", "5")]),
                  req(opportunities=[op("SECRET-ID", "bad value!")]),
                  req(strict=True, opportunities=[op("SECRET-ID", "5", email=None)]),
                  req(opportunities=[op("SECRET-ID", "5", title=None)])]:
            with self.assertRaises(ValueError) as cm:
                m.run(r)
            self.assertNotIn("SECRET-ID", str(cm.exception))
            self.assertNotIn("bad value", str(cm.exception))


class FullOrder(unittest.TestCase):
    """Full order: 1 dict; 2 forbidden; 3 non-str key; 4 unknown allowlists (top, profile,
    opportunities in order); 5 top types; 6 top caps; 7 clean_text; 8 per-opp types, caps, clean, then
    duplicate ids; 9 fee; 10 placeholders; 11 strict recipient. Earlier step wins; first item wins."""

    def test_1_over_2(self):
        refused(self, [{"token": 1}], "APPLY_REFUSED_BAD_TYPE:request")

    def test_2_over_3(self):
        r = req(token=1)
        r[5] = 1
        refused(self, r, "APPLY_REFUSED_SEND:token")

    def test_3_over_4(self):
        r = req(zzz=1)
        r[5] = 1
        refused(self, r, "APPLY_REFUSED_BAD_TYPE:key")

    def test_4_top_then_profile_then_opportunities(self):
        o = op("o1", "5"); o["notes"] = 1
        refused(self, req(zzz=1, profile={"name": "U", "x": 1}, opportunities=[o]), "APPLY_REFUSED_UNKNOWN:request")
        refused(self, req(profile={"name": "U", "x": 1}, opportunities=[o]), "APPLY_REFUSED_UNKNOWN:profile")
        refused(self, req(opportunities=[o]), "APPLY_REFUSED_UNKNOWN:opportunities")

    def test_4_over_5(self):
        refused(self, req(zzz=1, as_of=5, profile=3), "APPLY_REFUSED_UNKNOWN:request")
        o = op("o1", "5"); o["notes"] = 1
        refused(self, req(as_of=5, opportunities=[o]), "APPLY_REFUSED_UNKNOWN:opportunities")
        refused(self, req(template=None, profile={"x": 1}), "APPLY_REFUSED_UNKNOWN:profile")

    def test_4_skips_non_dict_profile_and_elements(self):
        refused(self, req(profile=5), "APPLY_REFUSED_BAD_TYPE:profile")
        refused(self, req(opportunities=["x"]), "APPLY_REFUSED_BAD_TYPE:opportunities")
        o = op("o1", "5"); o["notes"] = 1
        refused(self, req(opportunities=["x", o]), "APPLY_REFUSED_UNKNOWN:opportunities")

    def test_5_type_order(self):
        refused(self, req(as_of=5, profile=1, template=1, opportunities=1, strict=1), "APPLY_REFUSED_BAD_TYPE:as_of")
        refused(self, req(profile=1, template=1, opportunities=1, strict=1), "APPLY_REFUSED_BAD_TYPE:profile")
        refused(self, req(template=1, opportunities=1, strict=1), "APPLY_REFUSED_BAD_TYPE:template")
        refused(self, req(opportunities=1, strict=1), "APPLY_REFUSED_BAD_TYPE:opportunities")
        refused(self, req(opportunities=[], strict=1), "APPLY_REFUSED_EMPTY")
        refused(self, req(strict=1), "APPLY_REFUSED_BAD_TYPE:strict")
        refused(self, req(opportunities=()), "APPLY_REFUSED_BAD_TYPE:opportunities")  # list only

    def test_5_over_6(self):
        refused(self, req(as_of=5, template="a" * 20001), "APPLY_REFUSED_BAD_TYPE:as_of")
        refused(self, req(strict="x", template="a" * 20001), "APPLY_REFUSED_BAD_TYPE:strict")

    def test_6_cap_order(self):
        big_ops = [op("i%d" % i, "free") for i in range(1001)]
        refused(self, req(opportunities=big_ops, template="a" * 20001, as_of="2" * 65,
                          profile={"name": "n" * 201, "school": "s" * 201}), "APPLY_REFUSED_OVERSIZE:opportunities")
        refused(self, req(template="a" * 20001, as_of="2" * 65, profile={"name": "n" * 201}),
                "APPLY_REFUSED_OVERSIZE:template")
        refused(self, req(as_of="2" * 65, profile={"name": "n" * 201}), "APPLY_REFUSED_OVERSIZE:as_of")
        refused(self, req(profile={"name": "n" * 201}), "APPLY_REFUSED_OVERSIZE:profile")

    def test_6_over_7(self):
        refused(self, req(as_of="\x00" * 65), "APPLY_REFUSED_OVERSIZE:as_of")
        refused(self, req(template="\x00" * 20001), "APPLY_REFUSED_OVERSIZE:template")
        refused(self, req(profile={"name": "\x00" * 201, "school": 5}), "APPLY_REFUSED_OVERSIZE:profile")

    def test_7_clean_text_before_per_opportunity(self):
        refused(self, req(as_of="", opportunities=[op("o1", "5", title=None)]), "APPLY_REFUSED_BAD_TYPE:as_of")
        # Validation order: ISO shape is checked after the caps and BEFORE clean_text
        refused(self, req(as_of="\x00" * 65), "APPLY_REFUSED_OVERSIZE:as_of")
        refused(self, req(as_of="x\x01", profile={"name": "a\x01", "school": "S"}), "APPLY_REFUSED_BAD_TYPE:as_of")
        refused(self, req(as_of="bad", profile={"name": "a" * 201, "school": "S"}), "APPLY_REFUSED_OVERSIZE:profile")
        refused(self, req(profile={"name": "a\x00", "school": "S"}, opportunities=[{"id": 5}]),
                "APPLY_REFUSED_CONTROL_CHARS:name")
        refused(self, req(template="a\x00", opportunities=[{"id": 5}]), "APPLY_REFUSED_CONTROL_CHARS:template")
        refused(self, req(profile={"name": 5, "school": 5}), "APPLY_REFUSED_BAD_TYPE:name")
        refused(self, req(profile={"name": "U", "school": 5}), "APPLY_REFUSED_BAD_TYPE:school")

    def test_8_types_then_caps_then_clean_within_one_opportunity(self):
        refused(self, req(opportunities=[{"id": "i" * 129, "title": 5}]), "APPLY_REFUSED_BAD_TYPE:title")
        refused(self, req(opportunities=[{"id": "i" * 129 + "\x00", "title": "\x00"}]), "APPLY_REFUSED_OVERSIZE:id")
        refused(self, req(opportunities=[{"id": "\x00", "title": "t" * 201}]), "APPLY_REFUSED_OVERSIZE:title")
        refused(self, req(opportunities=[{"id": "\x00", "title": ""}]), "APPLY_REFUSED_CONTROL_CHARS:id")

    def test_8_all_types_before_caps_for_every_typed_field(self):
        big = "i" * 129
        refused(self, req(opportunities=[{"id": big, "title": "T", "deadline": 5}]), "APPLY_REFUSED_BAD_TYPE:deadline")
        refused(self, req(opportunities=[{"id": big, "title": "T", "contact_name": 5}]),
                "APPLY_REFUSED_BAD_TYPE:contact_name")
        refused(self, req(opportunities=[{"id": big, "title": "T", "contact_email": 5}]),
                "APPLY_REFUSED_BAD_TYPE:contact_email")
        refused(self, req(opportunities=[{"id": big, "title": 5}]), "APPLY_REFUSED_BAD_TYPE:title")
        refused(self, req(opportunities=[{"id": 5, "title": "t" * 201}]), "APPLY_REFUSED_BAD_TYPE:id")

    def test_8_first_offending_opportunity_wins_across_kinds(self):
        refused(self, req(opportunities=[op("o1", "5", title="t" * 201), {"id": 5}]), "APPLY_REFUSED_OVERSIZE:title")
        refused(self, req(opportunities=[{"id": 5}, op("o1", "5", title="t" * 201)]), "APPLY_REFUSED_BAD_TYPE:id")

    def test_8_duplicate_ids_after_whole_pass(self):
        refused(self, req(opportunities=[op("o1", "5"), op("o1", "5"), op("o3", "5", title=None)]),
                "APPLY_REFUSED_BAD_TYPE:title")
        refused(self, req(opportunities=[op("o1", "5"), op("o1", "5"), op("o3", "5", title="t" * 201)]),
                "APPLY_REFUSED_OVERSIZE:title")

    def test_8_over_9(self):
        refused(self, req(opportunities=[op("o1", "twenty"), op("o1", "5")]), "APPLY_REFUSED_BAD_TYPE:opportunities")
        refused(self, req(opportunities=[op("o1", "twenty"), op("o2", "5", email=5)]),
                "APPLY_REFUSED_BAD_TYPE:contact_email")

    def test_9_over_10(self):
        refused(self, req(template="{zzz}", opportunities=[op("o1", "twenty")]), "APPLY_REFUSED_BAD_TYPE:fee")

    def test_9_first_bad_fee_wins(self):
        refused(self, req(opportunities=[op("o1", "5"), op("o2", "bad!"), op("o3", True)]),
                "APPLY_REFUSED_BAD_TYPE:fee")

    def test_10_unknown_placeholder_before_missing_values(self):
        refused(self, req(template="{zzz} {name}", profile={"school": "S"}), "APPLY_REFUSED_UNFILLED:template")
        refused(self, req(template="{name} {school} {deadline}", profile={"school": "S"}), "APPLY_REFUSED_UNFILLED:name")
        refused(self, req(template="{school} {deadline}", profile={"name": "U"}), "APPLY_REFUSED_UNFILLED:school")

    def test_10_over_11(self):
        refused(self, req(strict=True, template="{zzz}", opportunities=[op("o1", "5", email=None)]),
                "APPLY_REFUSED_UNFILLED:template")
        refused(self, req(strict=True, opportunities=[{"id": "o1", "title": "T", "fee": "5"}]),
                "APPLY_REFUSED_UNFILLED:deadline")
        refused(self, req(strict=True, opportunities=[op("o1", "5", email=None)]), "APPLY_REFUSED_NORECIPIENT:contact_email")

    def test_clean_text_suffixes_keep_safe_constants(self):
        # blank profile value counts as MISSING (allow_blank), so it is UNFILLED only if the template uses it
        refused(self, req(profile={"name": "", "school": "S"}), "APPLY_REFUSED_UNFILLED:name")
        self.assertEqual(len(m.run(req(profile={"name": "", "school": "S"}, template="Hi {school}"))["drafts"]), 1)
        refused(self, req(profile={"name": "U", "school": "a\x01"}), "APPLY_REFUSED_CONTROL_CHARS:school")


class NoEffects(unittest.TestCase):
    BAD_WORDS = ("send", "smtp", "submit", "register", "login", "pay", "attempt", "post", "email_send")

    def test_public_callables_are_not_effects(self):
        for n in dir(m):
            if n.startswith("_"):
                continue
            if callable(getattr(m, n)) and getattr(getattr(m, n), "__module__", "") == m.__name__:
                low = n.lower()
                for w in self.BAD_WORDS:
                    self.assertNotIn(w, low, n)

    def test_public_surface(self):
        fns = sorted(n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))
                     and getattr(m, n).__module__ == m.__name__)
        self.assertEqual(fns, ["run"])

    def test_no_io_imports(self):
        tree = ast.parse(_P.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        banned = {"smtplib", "socket", "urllib", "http", "requests", "httpx", "subprocess", "os",
                  "ssl", "email", "ftplib", "imaplib", "poplib", "webbrowser", "asyncio", "time",
                  "datetime", "random", "sqlite3", "shutil", "pathlib", "builtins"}
        self.assertEqual(names & banned, set())
        self.assertTrue(names <= {"__future__", "hashlib", "json", "re", "decimal", "unicodedata", "app"}, names)

    def test_no_open_or_eval_calls(self):
        tree = ast.parse(_P.read_text(encoding="utf-8"))
        calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertEqual(calls & {"open", "eval", "exec", "compile", "__import__", "input"}, set())

    def test_uses_shared_policy_helper(self):
        src = _P.read_text(encoding="utf-8")
        self.assertIn("from app.modules.c30 import policy", src)
        self.assertIn("policy.clean_text", src)
        self.assertIn("policy.scope", src)

    def test_c35_init_untouched_empty(self):
        init = _P.parent / "__init__.py"
        self.assertEqual(init.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
